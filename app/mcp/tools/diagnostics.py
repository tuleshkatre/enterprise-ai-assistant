"""Redacted operational diagnostics MCP tool."""

import os

import ollama
from sqlalchemy import text

from app.config import settings
from app.db.database import SessionLocal
from app.mcp.auth import authenticated_user_id
from app.observability.langsmith import add_trace_metadata, trace_agent
from mcp.server.mcpserver.context import Context


@trace_agent("mcp_system_diagnostics", run_type="tool", tags=["mcp", "diagnostics"])
def system_diagnostics(context: Context) -> dict:
    """Return safe dependency and configuration health without exposing secrets."""
    authenticated_user_id(context)

    database_status = "healthy"
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        database_status = "unavailable"

    ollama_status = "healthy"
    try:
        ollama.Client(host=settings.ollama_base_url, timeout=2.0).list()
    except Exception:
        ollama_status = "unavailable"

    status = (
        "healthy"
        if database_status == "healthy" and ollama_status == "healthy"
        else "degraded"
    )
    result = {
        "status": status,
        "database": database_status,
        "ollama": ollama_status,
        "app_version": settings.app_version,
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
        "langsmith_tracing": (
            os.getenv(
                "LANGSMITH_TRACING_V2", os.getenv("LANGCHAIN_TRACING_V2", "false")
            ).casefold()
            == "true"
        ),
        "retrieval_top_k": settings.retrieval_top_k,
        "rerank_top_k": settings.rerank_top_k,
    }
    add_trace_metadata(mcp_tool="system_diagnostics", status=status)
    return result
