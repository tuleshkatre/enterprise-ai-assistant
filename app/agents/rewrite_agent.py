import logging
import re
from time import perf_counter

from app.agents.context_resolver_agent import build_bounded_memory_context
from app.observability.langsmith import add_trace_metadata
from app.rag.generator import llm
from app.rag.providers import extract_text_content

logger = logging.getLogger(__name__)

FOLLOW_UP_PATTERNS = (
    r"\b(it|this|that|they|them|those|these|one|ones)\b",
    r"\b(also|instead|again|then|there|previous|above)\b",
    r"\b(what about|how about|and what|why not)\b",
    r"^\s*and\b",
    r"\b(how many|how much)\s+(are|were|can|could|do|does|did)\b",
)
MAX_REWRITE_HISTORY_CHARS = 4000


def _should_rewrite(query: str, history: str) -> bool:
    """Rewrite only conversational references that lack standalone context."""
    if not history.strip():
        return False

    return any(
        re.search(pattern, query.strip().lower()) is not None
        for pattern in FOLLOW_UP_PATTERNS
    )


def rewrite_agent(state):
    query = state.get("resolved_query") or state["query"]
    history = build_bounded_memory_context(
        state.get("conversation_summary", ""),
        state.get("history", ""),
        MAX_REWRITE_HISTORY_CHARS,
        state.get("long_term_memories", []),
    )

    if not _should_rewrite(query, history):
        logger.info(
            "rag_timing rewrite_ms=0 rewritten=false history_present=%s",
            bool(history.strip()),
        )
        add_trace_metadata(
            original_query=query,
            rewritten_query=query,
            rewrite_applied=False,
            rewrite_ms=0.0,
        )
        return {
            "retrieval_query": query,
            "performance_metrics": {"rewrite_ms": 0.0},
            "observability": {
                "original_query": query,
                "rewritten_query": query,
                "rewrite_applied": False,
            },
        }

    started_at = perf_counter()
    rewritten_query = extract_text_content(
        llm.invoke(
            f"""
            Rewrite an ambiguous conversational follow-up into one standalone
            query for enterprise search and retrieval.

            Rules:
            - Resolve references using only the conversation history.
            - Preserve the user's intent, constraints, entities, and terminology.
            - Do not answer the question.
            - Do not add facts that are absent from the query or history.
            - If the query is already standalone or context is insufficient,
              return the original query unchanged.
            - Return only one standalone query with no labels or explanation.

            Recent Conversation History:
            {history}

            Current User Query:
            {query}
            """
        ).content
    ).strip()
    rewrite_ms = (perf_counter() - started_at) * 1000
    logger.info(
        "rag_timing rewrite_ms=%.2f rewritten=%s",
        rewrite_ms,
        bool(rewritten_query and rewritten_query != query),
    )

    final_query = rewritten_query or query
    add_trace_metadata(
        original_query=query,
        rewritten_query=final_query,
        rewrite_applied=final_query != query,
        rewrite_ms=rewrite_ms,
    )
    return {
        "retrieval_query": final_query,
        "performance_metrics": {"rewrite_ms": rewrite_ms},
        "observability": {
            "original_query": query,
            "rewritten_query": final_query,
            "rewrite_applied": final_query != query,
        },
    }
