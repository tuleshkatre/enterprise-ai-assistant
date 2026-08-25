"""Safe tenant-scoped SQL analytics MCP tool."""

from app.agents.response_agent import response_agent
from app.agents.sql_agent import sql_agent
from app.db.database import SessionLocal
from app.mcp.auth import authenticated_user_id
from app.observability.langsmith import add_trace_metadata, trace_agent
from mcp.server.mcpserver.context import Context


@trace_agent("mcp_run_safe_analytics", run_type="tool", tags=["mcp", "sql"])
def run_safe_analytics(question: str, context: Context) -> dict:
    """Execute a validated SELECT-only analytics request for the caller."""
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("question must not be empty")

    user_id = authenticated_user_id(context)
    with SessionLocal() as db:
        sql_result = sql_agent(
            {"query": normalized_question, "db": db, "user_id": user_id}
        )
        if sql_result.get("sql_error"):
            add_trace_metadata(
                mcp_tool="run_safe_analytics",
                status="rejected_or_failed",
                row_count=0,
            )
            return {
                "status": "error",
                "message": str(sql_result["sql_error"]),
                "results": [],
            }

        response = response_agent(
            {
                "query": normalized_question,
                "sql_output": sql_result.get("sql_output", []),
                "sql_error": None,
            }
        )

    rows = sql_result.get("sql_output", [])
    add_trace_metadata(
        mcp_tool="run_safe_analytics",
        status="success",
        row_count=len(rows),
    )
    return {"status": "success", "answer": response["answer"], "results": rows}
