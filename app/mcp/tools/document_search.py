"""Tenant-scoped MCP document retrieval tool."""

from app.config import settings
from app.db.database import SessionLocal
from app.mcp.auth import authenticated_user_id
from app.observability.langsmith import add_trace_metadata, trace_agent
from app.rag.reranker import rerank
from app.rag.retrieval import retrieve
from mcp.server.mcpserver.context import Context

MAX_MCP_SEARCH_RESULTS = 10
MAX_MCP_SNIPPET_CHARS = 500


@trace_agent("mcp_search_documents", run_type="tool", tags=["mcp", "rag"])
def search_documents(
    query: str,
    context: Context,
    top_k: int = 5,
) -> dict:
    """Return relevant, reranked chunks from the caller's uploaded documents."""
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("query must not be empty")
    if not 1 <= top_k <= MAX_MCP_SEARCH_RESULTS:
        raise ValueError(f"top_k must be between 1 and {MAX_MCP_SEARCH_RESULTS}")

    user_id = authenticated_user_id(context)
    with SessionLocal() as db:
        candidates = retrieve(
            db=db,
            query=normalized_query,
            user_id=user_id,
            top_k=max(settings.retrieval_top_k, top_k),
        )
        documents = rerank(normalized_query, candidates, top_k=top_k)

    results = [
        {
            "document_id": document["document_id"],
            "file": document["filename"],
            "page": document["page_number"],
            "snippet": document["content"][:MAX_MCP_SNIPPET_CHARS],
            "score": round(float(document.get("score", 0.0)), 4),
            "rerank_score": round(float(document.get("rerank_score", 0.0)), 4),
        }
        for document in documents
    ]
    add_trace_metadata(
        mcp_tool="search_documents",
        candidate_count=len(candidates),
        result_count=len(results),
    )
    return {"query": normalized_query, "results": results}
