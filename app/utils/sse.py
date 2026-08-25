"""Helpers for formatting Server-Sent Events (SSE)."""

from __future__ import annotations

from typing import Any


def sse_data(data: Any) -> str:
    """Format a default SSE data message."""
    return f"data: {data}\n\n"


def sse_event(event: str, data: Any) -> str:
    """Format a named SSE event."""
    return f"event: {event}\ndata: {data}\n\n"
