import logging
from time import perf_counter
from typing import Any

from langgraph.types import StreamWriter

from app.agents.prompt_builder import (
    NO_ANSWER,
    build_conversation_stream_prompt,
    build_document_stream_prompt,
    build_sql_stream_prompt,
    build_web_stream_prompt,
)
from app.agents.response_agent import (
    MAX_SOURCES,
    _build_sources,
    _effective_query,
    _fallback_sql_answer,
    _get_web_results,
    _result,
)
from app.observability.langsmith import add_trace_metadata
from app.rag.generator import llm
from app.rag.numeric_fidelity import stream_corrected_numeric_chunks
from app.rag.providers import extract_text_content

logger = logging.getLogger(__name__)


def _stream_prompt(
    prompt: str,
    writer: StreamWriter,
    documents: list[dict[str, Any]] | None = None,
) -> str:
    parts = []
    started_at = perf_counter()
    first_token_ms = None
    chunk_count = 0
    raw_chunks = (
        content
        for chunk in llm.stream(prompt)
        if (content := extract_text_content(getattr(chunk, "content", "")))
    )
    output_chunks = (
        stream_corrected_numeric_chunks(raw_chunks, documents)
        if documents is not None
        else raw_chunks
    )
    for content in output_chunks:
        if first_token_ms is None:
            first_token_ms = (perf_counter() - started_at) * 1000
        chunk_count += 1
        parts.append(content)
        writer(content)
    add_trace_metadata(
        stream_chunk_count=chunk_count,
        time_to_first_token_ms=first_token_ms or 0.0,
        stream_total_ms=(perf_counter() - started_at) * 1000,
    )
    return "".join(parts)


def _handle_document_response(
    state: dict[str, Any],
    documents: list[dict[str, Any]],
    writer: StreamWriter,
) -> dict[str, Any]:
    query = _effective_query(state)
    answer_started_at = perf_counter()
    prompt = build_document_stream_prompt(documents, query)
    answer = _stream_prompt(prompt, writer, documents).strip()

    answer_llm_ms = (perf_counter() - answer_started_at) * 1000
    logger.info(
        "rag_timing answer_llm_ms=%.2f document_count=%d",
        answer_llm_ms,
        len(documents),
    )
    document_ids = (
        document.get("document_id")
        for document in documents
        if isinstance(document.get("document_id"), int)
        and not isinstance(document.get("document_id"), bool)
    )
    selected_ids = list(document_ids)
    sources = _build_sources(documents, selected_ids)
    add_trace_metadata(
        response_route="document",
        streaming=True,
        prompt_chars=len(prompt),
        context_chars=sum(len(str(doc.get("content", ""))) for doc in documents),
        document_count=len(documents),
        selected_document_ids=selected_ids,
        source_count=len(sources),
        answer_chars=len(answer),
        answer_llm_ms=answer_llm_ms,
    )
    return _result(answer, sources, answer_llm_ms)


def _handle_web_response(
    state: dict[str, Any],
    web_results: list[dict[str, Any]],
    writer: StreamWriter,
) -> dict[str, Any]:
    answer_started_at = perf_counter()
    prompt = build_web_stream_prompt(web_results, _effective_query(state))
    answer = _stream_prompt(prompt, writer).strip()

    answer_llm_ms = (perf_counter() - answer_started_at) * 1000
    logger.info("rag_timing answer_llm_ms=%.2f document_count=0", answer_llm_ms)
    sources = web_results[:MAX_SOURCES]
    add_trace_metadata(
        response_route="web",
        streaming=True,
        prompt_chars=len(prompt),
        web_result_count=len(web_results),
        source_count=len(sources),
        answer_chars=len(answer),
        answer_llm_ms=answer_llm_ms,
    )
    return _result(answer, sources, answer_llm_ms)


def _handle_sql_response(state: dict[str, Any], writer: StreamWriter) -> dict[str, Any]:
    sql_error = state.get("sql_error")
    if sql_error:
        content = str(sql_error)
        writer(content)
        return _result(content, [], 0.0)

    sql_output = state.get("sql_output", [])
    if not sql_output:
        content = "No matching data was found."
        writer(content)
        return _result(content, [], 0.0)

    answer_started_at = perf_counter()
    prompt = build_sql_stream_prompt(sql_output, _effective_query(state))
    parts = []
    withheld = ""
    contradictory = False
    no_data_phrases = ("no matching data", "no data was found")
    first_token_ms = None
    chunk_count = 0
    for chunk in llm.stream(prompt):
        content = extract_text_content(getattr(chunk, "content", ""))
        if not content:
            continue
        if first_token_ms is None:
            first_token_ms = (perf_counter() - answer_started_at) * 1000
        chunk_count += 1
        if parts:
            parts.append(content)
            writer(content)
            continue
        withheld += content
        normalized = withheld.lstrip().casefold()
        if any(phrase.startswith(normalized) for phrase in no_data_phrases):
            continue
        if any(normalized.startswith(phrase) for phrase in no_data_phrases):
            contradictory = True
            continue
        parts.append(withheld)
        writer(withheld)
        withheld = ""

    if contradictory:
        answer = _fallback_sql_answer(sql_output)
        writer(answer)
    else:
        if withheld:
            parts.append(withheld)
            writer(withheld)
        answer = "".join(parts).strip()
    answer_llm_ms = (perf_counter() - answer_started_at) * 1000
    add_trace_metadata(
        response_route="sql",
        streaming=True,
        prompt_chars=len(prompt),
        sql_row_count=len(sql_output),
        stream_chunk_count=chunk_count,
        time_to_first_token_ms=first_token_ms or 0.0,
        stream_total_ms=answer_llm_ms,
        answer_chars=len(answer),
        answer_llm_ms=answer_llm_ms,
    )
    logger.info("rag_timing answer_llm_ms=%.2f document_count=0", answer_llm_ms)
    return _result(answer, [], answer_llm_ms)


def _handle_conversation_response(
    state: dict[str, Any], writer: StreamWriter
) -> dict[str, Any]:
    if state.get("conversation_answer"):
        content = str(state["conversation_answer"])
        writer(content)
        return _result(content, [], 0.0)
    answer_started_at = perf_counter()
    answer = _stream_prompt(
        build_conversation_stream_prompt(
            state.get("conversation_context", ""),
            state.get("query", ""),
        ),
        writer,
    ).strip()
    answer_llm_ms = (perf_counter() - answer_started_at) * 1000
    logger.info("rag_timing answer_llm_ms=%.2f document_count=0", answer_llm_ms)
    return _result(answer, [], answer_llm_ms)


def response_stream_agent(
    state: dict[str, Any], *, writer: StreamWriter
) -> dict[str, Any]:
    documents = state.get("documents", [])
    web_results = _get_web_results(state)
    calculator_output = state.get("calculator_output", "")
    has_sql_output = "sql_output" in state or bool(state.get("sql_error"))
    has_conversation_context = "conversation_context" in state
    has_memory_output = "memory_output" in state

    add_trace_metadata(
        streaming=True,
        route=state.get("route"),
        document_count=len(documents),
        web_result_count=len(web_results),
        sql_row_count=len(state.get("sql_output", [])),
    )

    if has_memory_output:
        content = str(state.get("memory_output", ""))
        writer(content)
        return _result(content, [], 0.0)
    if has_conversation_context:
        return _handle_conversation_response(state, writer)
    if documents:
        return _handle_document_response(state, documents, writer)
    if web_results:
        return _handle_web_response(state, web_results, writer)
    if calculator_output:
        content = str(calculator_output)
        writer(content)
        return _result(content, [], 0.0)
    if has_sql_output:
        return _handle_sql_response(state, writer)

    logger.info("rag_timing answer_llm_ms=0.00 document_count=0")
    writer(NO_ANSWER)
    return _result(NO_ANSWER, [], 0.0)
