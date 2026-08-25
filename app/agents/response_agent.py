import json
import logging
from collections.abc import Iterable
from time import perf_counter
from typing import Any

from app.agents.prompt_builder import (
    NO_ANSWER,
    build_conversation_prompt,
    build_document_prompt,
    build_document_retry_prompt,
    build_sql_prompt,
    build_web_prompt,
)
from app.observability.langsmith import add_trace_metadata
from app.rag.generator import llm
from app.rag.numeric_fidelity import correct_unsupported_negative_quantities

MAX_SOURCES = 3
logger = logging.getLogger(__name__)


def _effective_query(state: dict[str, Any]) -> str:
    return state.get("resolved_query") or state.get("query", "")


def _parse_generation(content: Any) -> tuple[str, list[int]] | None:
    """Validate the model response before using it for an answer or citation."""
    if not isinstance(content, str):
        return None

    text = content.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    answer = payload.get("answer")
    used_doc_ids = payload.get("used_doc_ids")
    if not isinstance(answer, str) or not isinstance(used_doc_ids, list):
        return None

    return answer.strip(), [
        doc_id
        for doc_id in used_doc_ids
        if isinstance(doc_id, int) and not isinstance(doc_id, bool)
    ]


def _build_sources(
    documents: Iterable[dict[str, Any]], used_doc_ids: Iterable[int]
) -> list[dict[str, Any]]:
    """Return max three cited page sources, choosing each page's best rerank."""
    documents_by_id = {
        document["document_id"]: document
        for document in documents
        if isinstance(document.get("document_id"), int)
        and not isinstance(document.get("document_id"), bool)
    }

    cited_documents = []
    seen_ids = set()
    for document_id in used_doc_ids:
        if document_id in seen_ids:
            continue
        document = documents_by_id.get(document_id)
        if document is not None:
            cited_documents.append(document)
            seen_ids.add(document_id)

    best_by_page: dict[tuple[str, int], dict[str, Any]] = {}
    for document in cited_documents:
        key = (document["filename"], document["page_number"])
        current = best_by_page.get(key)
        if current is None or document.get("rerank_score", float("-inf")) > current.get(
            "rerank_score", float("-inf")
        ):
            best_by_page[key] = document

    best_documents = sorted(
        best_by_page.values(),
        key=lambda document: document.get("rerank_score", float("-inf")),
        reverse=True,
    )[:MAX_SOURCES]
    return [
        {
            "file": document["filename"],
            "page": document["page_number"],
            "snippet": document["content"].strip()[:250],
        }
        for document in best_documents
    ]


def _is_incomplete_answer(answer: str) -> bool:
    """Catch obvious fragments without rejecting concise valid answers."""
    return len(answer.split()) <= 2


def _get_web_results(state: dict[str, Any]) -> list[dict[str, Any]]:
    web_output = state.get("web_output", [])
    if isinstance(web_output, dict):
        web_output = web_output.get("results", [])
    if not isinstance(web_output, list):
        return []
    return [result for result in web_output if isinstance(result, dict)]


def _result(
    answer: str, sources: list[dict[str, Any]], answer_llm_ms: float
) -> dict[str, Any]:
    return {
        "answer": answer or NO_ANSWER,
        "sources": sources,
        "performance_metrics": {"answer_llm_ms": answer_llm_ms},
    }


def handle_document_response(
    state: dict[str, Any], documents: list[dict[str, Any]]
) -> dict[str, Any]:
    query = _effective_query(state)
    answer_started_at = perf_counter()
    prompt = build_document_prompt(documents, query)
    response = llm.invoke(prompt)
    parsed = _parse_generation(response.content)
    if parsed is None:
        answer_llm_ms = (perf_counter() - answer_started_at) * 1000
        return _result(NO_ANSWER, [], answer_llm_ms)

    answer, used_doc_ids = parsed
    if _is_incomplete_answer(answer):
        add_trace_metadata(response_retry_attempted=True)
        logger.warning("rag_generation incomplete_answer_retry=true")
        retry_prompt = build_document_retry_prompt(documents, query)
        retry_response = llm.invoke(retry_prompt)
        retry_parsed = _parse_generation(retry_response.content)
        if retry_parsed is None:
            answer_llm_ms = (perf_counter() - answer_started_at) * 1000
            return _result(NO_ANSWER, [], answer_llm_ms)
        answer, used_doc_ids = retry_parsed
        if _is_incomplete_answer(answer):
            answer_llm_ms = (perf_counter() - answer_started_at) * 1000
            return _result(NO_ANSWER, [], answer_llm_ms)

    answer = correct_unsupported_negative_quantities(answer, documents)
    answer_llm_ms = (perf_counter() - answer_started_at) * 1000
    logger.info(
        "rag_timing answer_llm_ms=%.2f document_count=%d",
        answer_llm_ms,
        len(documents),
    )
    sources = _build_sources(documents, used_doc_ids)
    add_trace_metadata(
        response_route="document",
        prompt_chars=len(prompt),
        context_chars=sum(len(str(doc.get("content", ""))) for doc in documents),
        document_count=len(documents),
        selected_document_ids=used_doc_ids,
        source_count=len(sources),
        answer_chars=len(answer),
        answer_llm_ms=answer_llm_ms,
    )
    return _result(answer, sources, answer_llm_ms)


def handle_web_response(
    state: dict[str, Any], web_results: list[dict[str, Any]]
) -> dict[str, Any]:
    answer_started_at = perf_counter()
    prompt = build_web_prompt(web_results, _effective_query(state))
    response = llm.invoke(prompt)
    answer = response.content.strip()
    try:
        payload = json.loads(answer)
        if isinstance(payload, dict) and isinstance(payload.get("answer"), str):
            answer = payload["answer"].strip()
    except json.JSONDecodeError:
        pass

    answer_llm_ms = (perf_counter() - answer_started_at) * 1000
    logger.info(
        "rag_timing answer_llm_ms=%.2f document_count=0",
        answer_llm_ms,
    )
    sources = web_results[:MAX_SOURCES]
    add_trace_metadata(
        response_route="web",
        prompt_chars=len(prompt),
        web_result_count=len(web_results),
        source_count=len(sources),
        answer_chars=len(answer),
        answer_llm_ms=answer_llm_ms,
    )
    return _result(answer, sources, answer_llm_ms)


def handle_calculator_response(state: dict[str, Any]) -> dict[str, Any]:
    calculator_output = state.get("calculator_output", "")
    return _result(str(calculator_output), [], 0.0)


def handle_memory_response(state: dict[str, Any]) -> dict[str, Any]:
    return _result(str(state.get("memory_output", "")), [], 0.0)


def handle_sql_response(state: dict[str, Any]) -> dict[str, Any]:
    sql_error = state.get("sql_error")
    if sql_error:
        return _result(str(sql_error), [], 0.0)

    sql_output = state.get("sql_output", [])
    if not sql_output:
        return _result("No matching data was found.", [], 0.0)

    answer_started_at = perf_counter()
    prompt = build_sql_prompt(sql_output, _effective_query(state))
    response = llm.invoke(prompt)
    answer_llm_ms = (perf_counter() - answer_started_at) * 1000
    logger.info(
        "rag_timing answer_llm_ms=%.2f document_count=0",
        answer_llm_ms,
    )
    answer = response.content.strip()
    if (
        "no matching data" in answer.casefold()
        or "no data was found" in answer.casefold()
    ):
        answer = _fallback_sql_answer(sql_output)
    add_trace_metadata(
        response_route="sql",
        prompt_chars=len(prompt),
        sql_row_count=len(sql_output),
        answer_chars=len(answer),
        answer_llm_ms=answer_llm_ms,
    )
    return _result(answer, [], answer_llm_ms)


def handle_conversation_response(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("conversation_answer"):
        return _result(str(state["conversation_answer"]), [], 0.0)
    answer_started_at = perf_counter()
    response = llm.invoke(
        build_conversation_prompt(
            state.get("conversation_context", ""),
            state.get("query", ""),
        )
    )
    answer_llm_ms = (perf_counter() - answer_started_at) * 1000
    answer = response.content.strip()
    logger.info("rag_timing answer_llm_ms=%.2f document_count=0", answer_llm_ms)
    return _result(answer, [], answer_llm_ms)


def _fallback_sql_answer(sql_output: list[dict[str, Any]]) -> str:
    if sql_output and all("title" in row for row in sql_output):
        conversations = []
        for row in sql_output:
            description = f'"{row["title"]}"'
            if row.get("created_at"):
                description += f" ({row['created_at']})"
            conversations.append(description)
        noun = "conversation is" if len(conversations) == 1 else "conversations are"
        return f"Your most recent {noun}: {', '.join(conversations)}."

    rows = []
    for row in sql_output:
        values = ", ".join(
            f"{key.replace('_', ' ')}: {value}"
            for key, value in row.items()
            if key != "id" and not key.endswith("_id")
        )
        if values:
            rows.append(values)
    return "; ".join(rows) + "."


def response_agent(state: dict[str, Any]) -> dict[str, Any]:
    documents = state.get("documents", [])
    web_results = _get_web_results(state)
    calculator_output = state.get("calculator_output", "")
    has_sql_output = "sql_output" in state or bool(state.get("sql_error"))
    has_conversation_context = "conversation_context" in state
    has_memory_output = "memory_output" in state

    add_trace_metadata(
        streaming=False,
        route=state.get("route"),
        document_count=len(documents),
        web_result_count=len(web_results),
        sql_row_count=len(state.get("sql_output", [])),
    )

    if has_memory_output:
        return handle_memory_response(state)
    if has_conversation_context:
        return handle_conversation_response(state)
    if documents:
        return handle_document_response(state, documents)
    elif web_results:
        return handle_web_response(state, web_results)
    elif calculator_output:
        return handle_calculator_response(state)
    elif has_sql_output:
        return handle_sql_response(state)
    else:
        logger.info("rag_timing answer_llm_ms=0.00 document_count=0")
        return _result(NO_ANSWER, [], 0.0)
