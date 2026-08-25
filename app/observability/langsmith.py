"""Safe, consistent LangSmith tracing helpers for application spans."""

import re
from collections.abc import Callable
from inspect import signature
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from langsmith import get_current_run_tree, traceable

from app.config import settings

MAX_TRACE_TEXT_CHARS = 2000
SENSITIVE_KEY_PARTS = (
    "api_key",
    "authorization",
    "credential",
    "db",
    "password",
    "secret",
    "token",
)
CONTENT_KEYS = {
    "answer",
    "content",
    "conversation_context",
    "conversation_summary",
    "generated_sql",
    "history",
    "memory_output",
    "memory_value",
    "original_query",
    "prompt",
    "query",
    "resolved_query",
    "retrieval_query",
    "rewritten_query",
    "snippet",
    "sql_output",
}
SENSITIVE_TEXT_PATTERN = re.compile(
    r"(?i)\b(password|api[ _-]?key|access[ _-]?token|refresh[ _-]?token|"
    r"secret|otp|pin)\b\s*(?:is|=|:)?\s*\S+"
)
CARD_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


def _sanitize_text(key: str, value: str) -> str:
    redacted = SENSITIVE_TEXT_PATTERN.sub(r"\1 [REDACTED]", value)
    redacted = CARD_PATTERN.sub("[REDACTED CARD]", redacted)
    if key.casefold() in {"url", "urls"}:
        parts = urlsplit(redacted)
        if parts.scheme and parts.netloc:
            redacted = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    return redacted[:MAX_TRACE_TEXT_CHARS]


def _safe_value(key: str, value: Any) -> Any:
    normalized_key = key.casefold()
    if any(part in normalized_key for part in SENSITIVE_KEY_PARTS):
        return "[REDACTED]"
    if normalized_key in CONTENT_KEYS and not settings.langsmith_capture_content:
        if isinstance(value, (str, list, tuple, dict)):
            return {"captured": False, "size": len(value)}
        return "[CONTENT REDACTED]"
    if isinstance(value, str):
        return _sanitize_text(key, value)
    if isinstance(value, dict):
        return {str(k): _safe_value(str(k), v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_value(key, item) for item in value[:20]]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return f"<{type(value).__name__}>"


def sanitize_trace_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _safe_value(str(key), value) for key, value in payload.items()}


def trace_agent(
    name: str,
    *,
    run_type: str = "chain",
    tags: list[str] | None = None,
) -> Callable:
    tracer = traceable(
        name=name,
        run_type=run_type,
        project_name=settings.langsmith_project,
        tags=tags or ["enterprise-ai-assistant"],
        process_inputs=sanitize_trace_payload,
        process_outputs=sanitize_trace_payload,
    )

    def decorator(func: Callable) -> Callable:
        wrapped = tracer(func)
        # Keep framework-only ``config`` out of public schemas such as MCP.
        wrapped.__signature__ = signature(func)
        return wrapped

    return decorator


def _reduce_stream(chunks: list[Any]) -> dict[str, Any]:
    return {"stream_event_count": len(chunks)}


def trace_stream(name: str) -> Callable:
    tracer = traceable(
        name=name,
        run_type="chain",
        project_name=settings.langsmith_project,
        tags=["enterprise-ai-assistant", "streaming", "request"],
        process_inputs=sanitize_trace_payload,
        process_outputs=sanitize_trace_payload,
        reduce_fn=_reduce_stream,
    )

    def decorator(func: Callable) -> Callable:
        wrapped = tracer(func)
        wrapped.__signature__ = signature(func)
        return wrapped

    return decorator


def add_trace_metadata(**metadata: Any) -> None:
    run = get_current_run_tree()
    if run is not None:
        run.add_metadata(sanitize_trace_payload(metadata))
