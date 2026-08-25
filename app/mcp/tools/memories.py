"""Consent-based long-term memory MCP tools."""

from app.agents.memory_agent import memory_agent
from app.agents.memory_policy import ATTRIBUTE_ALIASES
from app.db.database import SessionLocal
from app.mcp.auth import authenticated_user_id
from app.observability.langsmith import add_trace_metadata, trace_agent
from mcp.server.mcpserver.context import Context

SUPPORTED_MEMORY_ATTRIBUTES = tuple(sorted(ATTRIBUTE_ALIASES))


def _validate_attribute(attribute: str) -> str:
    normalized = " ".join(attribute.casefold().strip().split())
    if normalized not in ATTRIBUTE_ALIASES:
        supported = ", ".join(SUPPORTED_MEMORY_ATTRIBUTES)
        raise ValueError(f"Unsupported memory attribute. Supported values: {supported}")
    return normalized


@trace_agent("mcp_remember_user_fact", run_type="tool", tags=["mcp", "memory"])
def remember_user_fact(attribute: str, value: str, context: Context) -> dict:
    """Save or update an explicitly provided, non-sensitive user fact."""
    normalized_attribute = _validate_attribute(attribute)
    if not value.strip():
        raise ValueError("value must not be empty")
    user_id = authenticated_user_id(context)
    query = f"Remember that my {normalized_attribute} is {value.strip()}."
    with SessionLocal() as db:
        result = memory_agent(
            {
                "query": query,
                "user_id": user_id,
                "conversation_id": None,
                "current_message_id": None,
                "db": db,
            }
        )
    status = result.get("observability", {}).get("memory_status", "rejected")
    add_trace_metadata(
        mcp_tool="remember_user_fact",
        memory_attribute=normalized_attribute,
        status=status,
    )
    return {"status": status, "message": result["memory_output"]}


@trace_agent("mcp_forget_user_fact", run_type="tool", tags=["mcp", "memory"])
def forget_user_fact(attribute: str, context: Context) -> dict:
    """Forget one saved user fact for the authenticated caller."""
    normalized_attribute = _validate_attribute(attribute)
    user_id = authenticated_user_id(context)
    with SessionLocal() as db:
        result = memory_agent(
            {
                "query": f"Forget my {normalized_attribute}",
                "user_id": user_id,
                "db": db,
            }
        )
    status = result.get("observability", {}).get("memory_status", "not_found")
    add_trace_metadata(
        mcp_tool="forget_user_fact",
        memory_attribute=normalized_attribute,
        status=status,
    )
    return {"status": status, "message": result["memory_output"]}
