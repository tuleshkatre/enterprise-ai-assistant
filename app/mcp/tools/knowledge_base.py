"""Grounded MCP knowledge-base answering tool."""

from app.agents.response_agent import response_agent
from app.config import settings
from app.db.database import SessionLocal
from app.mcp.auth import authenticated_user_id
from app.observability.langsmith import add_trace_metadata, trace_agent
from app.rag.reranker import rerank
from app.rag.retrieval import retrieve
from mcp.server.mcpserver.context import Context


@trace_agent("mcp_ask_knowledge_base", run_type="tool", tags=["mcp", "rag"])
def ask_knowledge_base(question: str, context: Context) -> dict:
    """Answer a question using only the caller's uploaded documents."""
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("question must not be empty")

    user_id = authenticated_user_id(context)
    with SessionLocal() as db:
        documents = retrieve(
            db=db,
            query=normalized_question,
            user_id=user_id,
            top_k=settings.retrieval_top_k,
        )
        documents = rerank(
            normalized_question,
            documents,
            top_k=settings.rerank_top_k,
        )
        response = response_agent(
            {"query": normalized_question, "documents": documents}
        )

    add_trace_metadata(
        mcp_tool="ask_knowledge_base",
        document_count=len(documents),
        source_count=len(response["sources"]),
    )
    return {"answer": response["answer"], "sources": response["sources"]}
