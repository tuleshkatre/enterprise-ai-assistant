import json
import logging
import re
from time import perf_counter
from typing import Any

from app.agents.memory_policy import normalize_recall_key, parse_memory_command
from app.rag.generator import llm
from app.rag.providers import extract_text_content

logger = logging.getLogger(__name__)

MAX_CONTEXT_HISTORY_CHARS = 4000
CONTEXT_DEPENDENT_PATTERNS = (
    r"\b(it|its|this|that|they|them|their|those|these|one|ones)\b",
    r"\b(what about|how about|and what|why not)\b",
    r"^\s*and\b",
    r"\b(how many|how much)\s+(are|were|can|could|do|does|did)\b",
    r"\b(?:what\s+(?:is|was)|what['’]?s)\s+my\b",
    r"\bwho\s+(am|was)\s+i\b",
)
EXPLICIT_FACT_QUERY_PATTERN = re.compile(
    r"^\s*(?:what\s+(?:is|was)|what['’]?s)\s+my\s+(.+?)\??\s*$",
    re.IGNORECASE,
)
EXPLICIT_FACT_DECLARATION_PATTERN = re.compile(
    r"^\s*my\s+(?:name|preferred\s+name|role|department|location|timezone|"
    r"language|preference)\s+(?:is|was)\s+\S.+?\.?\s*$",
    re.IGNORECASE,
)


def is_explicit_user_fact_declaration(query: str) -> bool:
    return EXPLICIT_FACT_DECLARATION_PATTERN.match(query) is not None


def build_bounded_memory_context(
    summary: str,
    history: str,
    max_chars: int = MAX_CONTEXT_HISTORY_CHARS,
    long_term_memories: list[dict[str, str]] | None = None,
) -> str:
    long_term_text = ""
    if long_term_memories:
        facts = "\n".join(
            f"- {memory['memory_key']}: {memory['memory_value']}"
            for memory in long_term_memories
            if memory.get("memory_key") and memory.get("memory_value")
        )
        if facts:
            long_term_text = f"Saved User Memories:\n{facts}\n\n"

    if not summary.strip():
        history_budget = max(max_chars - len(long_term_text), 0)
        return (long_term_text + history[-history_budget:])[:max_chars]

    available = max(max_chars - len(long_term_text), 0)
    summary_budget = min(available // 2, len(summary))
    bounded_summary = summary[:summary_budget]
    prefix = (
        f"{long_term_text}Conversation Summary:\n{bounded_summary}"
        "\n\nRecent Messages:\n"
    )
    history_budget = max(max_chars - len(prefix), 0)
    return prefix + history[-history_budget:] if history_budget else prefix[:max_chars]


def _has_saved_user_fact(
    query: str,
    memories: list[dict[str, str]],
) -> bool:
    match = EXPLICIT_FACT_QUERY_PATTERN.match(query)
    attribute = match.group(1).strip() if match else None
    if re.fullmatch(r"\s*who\s+am\s+i\??\s*", query, re.IGNORECASE):
        attribute = "name"
    key = normalize_recall_key(attribute) if attribute else None
    return bool(
        key
        and any(
            memory.get("memory_key") == key and memory.get("memory_value")
            for memory in memories
        )
    )


def _has_explicit_user_fact(query: str, history: str) -> bool:
    match = EXPLICIT_FACT_QUERY_PATTERN.match(query)
    attribute = match.group(1).strip() if match else None
    if re.fullmatch(r"\s*who\s+am\s+i\??\s*", query, re.IGNORECASE):
        attribute = "name"
    if not attribute:
        return False

    escaped_attribute = re.escape(attribute)
    user_message_pattern = re.compile(
        rf"^user:\s+.*\bmy\s+{escaped_attribute}\s+(?:is|was)\s+\S+",
        re.IGNORECASE | re.MULTILINE,
    )
    summary_fact_pattern = re.compile(
        rf"\b(?:the\s+)?user(?:'s|’s)?\s+{escaped_attribute}\s+"
        rf"(?:is|was)\s+\S+",
        re.IGNORECASE,
    )
    return (
        user_message_pattern.search(history) is not None
        or summary_fact_pattern.search(history) is not None
    )


def _known_follow_up_resolution(query: str, history: str) -> str | None:
    normalized = " ".join(query.casefold().split()).rstrip("?")
    if normalized in {"what about conversations", "how about conversations"}:
        if re.search(r"^user:.*\b(messages?|conversations?)\b", history, re.I | re.M):
            return "How many conversations do I have?"
    return None


def needs_context_resolution(query: str, history: str) -> bool:
    if not history.strip():
        return False
    normalized = query.strip().casefold()
    return any(re.search(pattern, normalized) for pattern in CONTEXT_DEPENDENT_PATTERNS)


def _parse_resolution(content: Any, query: str) -> tuple[str, str | None]:
    if not isinstance(content, str):
        return query, None
    value = content.strip()
    if value.startswith("```") and value.endswith("```"):
        value = value.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return query, None
    if not isinstance(payload, dict):
        return query, None

    resolved_query = payload.get("resolved_query")
    context_route = payload.get("context_route")
    if not isinstance(resolved_query, str) or not resolved_query.strip():
        resolved_query = query
    if context_route not in (None, "conversation"):
        context_route = None
    return resolved_query.strip(), context_route


def build_context_resolution_prompt(query: str, history: str) -> str:
    return f"""
You resolve conversational references before an enterprise assistant routes a request.

Return exactly one JSON object and no markdown:
{{"resolved_query":"standalone user request","context_route":null}}

Set `context_route` to `"conversation"` only when the current question can be
answered directly and completely from an explicit fact in the conversation history.
Otherwise set it to null so the request can be routed to document search, web search,
calculation, or database analytics.

Rules:
- Resolve references using only the supplied conversation history.
- Preserve the current user's intent, constraints, entities, and terminology.
- Do not answer the question in `resolved_query`.
- Do not invent or infer facts absent from the history.
- A request for documents, messages, conversations, counts, aggregates, or stored
  enterprise data is not a conversation-history answer; set `context_route` to null.
- If context is insufficient, return the original query unchanged with a null route.

Recent Conversation History:
{history}

Current User Query:
{query}
"""


def context_resolver_agent(state: dict[str, Any]) -> dict[str, Any]:
    query = state["query"]
    history = state.get("history", "")
    long_term_memories = state.get("long_term_memories", [])
    memory_context = build_bounded_memory_context(
        state.get("conversation_summary", ""),
        history,
        long_term_memories=long_term_memories,
    )
    if parse_memory_command(query) is not None:
        logger.info(
            "context_timing context_resolution_ms=0 resolved=false route=memory"
        )
        return {
            "resolved_query": query,
            "context_route": "memory",
            "performance_metrics": {"context_resolution_ms": 0.0},
        }

    if is_explicit_user_fact_declaration(query):
        logger.info(
            "context_timing context_resolution_ms=0 resolved=false route=conversation"
        )
        return {
            "resolved_query": query,
            "context_route": "conversation",
            "performance_metrics": {"context_resolution_ms": 0.0},
        }

    if not needs_context_resolution(query, memory_context):
        logger.info(
            "context_timing context_resolution_ms=0 resolved=false history_present=%s",
            bool(memory_context.strip()),
        )
        return {
            "resolved_query": query,
            "context_route": None,
            "performance_metrics": {"context_resolution_ms": 0.0},
        }

    if _has_explicit_user_fact(query, memory_context):
        logger.info(
            "context_timing context_resolution_ms=0 resolved=false route=conversation"
        )
        return {
            "resolved_query": query,
            "context_route": "conversation",
            "performance_metrics": {"context_resolution_ms": 0.0},
        }

    if _has_saved_user_fact(query, long_term_memories):
        logger.info(
            "context_timing context_resolution_ms=0 resolved=false route=conversation"
        )
        return {
            "resolved_query": query,
            "context_route": "conversation",
            "performance_metrics": {"context_resolution_ms": 0.0},
        }

    known_resolution = _known_follow_up_resolution(query, memory_context)
    if known_resolution:
        logger.info(
            "context_timing context_resolution_ms=0 resolved=true route=supervisor"
        )
        return {
            "resolved_query": known_resolution,
            "context_route": None,
            "performance_metrics": {"context_resolution_ms": 0.0},
        }

    started_at = perf_counter()
    response = llm.invoke(build_context_resolution_prompt(query, memory_context))
    resolved_query, context_route = _parse_resolution(
        extract_text_content(response.content), query
    )
    elapsed_ms = (perf_counter() - started_at) * 1000
    logger.info(
        "context_timing context_resolution_ms=%.2f resolved=%s route=%s",
        elapsed_ms,
        resolved_query != query,
        context_route or "supervisor",
    )
    return {
        "resolved_query": resolved_query,
        "context_route": context_route,
        "performance_metrics": {"context_resolution_ms": elapsed_ms},
    }
