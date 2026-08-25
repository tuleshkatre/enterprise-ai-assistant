import re
from typing import Any

from app.agents.context_resolver_agent import build_bounded_memory_context
from app.agents.memory_policy import normalize_recall_key
from app.observability.langsmith import add_trace_metadata


def _direct_memory_answer(query: str, memories: list[dict[str, str]]) -> str | None:
    """Return an explicitly saved fact without LLM reinterpretation."""
    match = re.fullmatch(
        r"\s*(?:what\s+(?:is|was)|what['’]?s)\s+my\s+(.+?)\??\s*",
        query,
        re.IGNORECASE,
    )
    attribute = match.group(1).strip() if match else None
    if re.fullmatch(r"\s*who\s+am\s+i\??\s*", query, re.IGNORECASE):
        attribute = "name"
    key = normalize_recall_key(attribute) if attribute else None
    if not key:
        return None

    for memory in memories:
        if memory.get("memory_key") == key and memory.get("memory_value"):
            label = key.replace("_", " ")
            return f"Your {label} is {memory['memory_value']}."
    return None


def conversation_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Prepare bounded history for response generation without external retrieval."""
    memories = state.get("long_term_memories", [])
    result = {
        "conversation_context": build_bounded_memory_context(
            state.get("conversation_summary", ""),
            state.get("history", ""),
            long_term_memories=memories,
        )
    }
    direct_answer = _direct_memory_answer(state["query"], memories)
    if direct_answer is not None:
        result["conversation_answer"] = direct_answer
    add_trace_metadata(
        recent_history_chars=len(state.get("history", "")),
        summary_chars=len(state.get("conversation_summary", "")),
        retrieved_memory_count=len(memories),
        deterministic_memory_answer=direct_answer is not None,
    )
    return result
