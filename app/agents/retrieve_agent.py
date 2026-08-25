import logging
from time import perf_counter

from app.config import settings
from app.observability.langsmith import add_trace_metadata
from app.rag.reranker import rerank
from app.rag.retrieval import retrieve

logger = logging.getLogger(__name__)


def retrieve_agent(state):
    performance_metrics: dict[str, float] = {}
    retrieval_query = (
        state.get("retrieval_query") or state.get("resolved_query") or state["query"]
    )
    docs = retrieve(
        db=state["db"],
        query=retrieval_query,
        user_id=state["user_id"],
        top_k=settings.retrieval_top_k,
        performance_metrics=performance_metrics,
    )

    retrieved_count = len(docs)
    rerank_started_at = perf_counter()
    docs = rerank(
        query=retrieval_query,
        docs=docs,
        top_k=settings.rerank_top_k,
    )
    rerank_ms = (perf_counter() - rerank_started_at) * 1000
    performance_metrics["rerank_ms"] = rerank_ms
    logger.info(
        "rag_timing rerank_ms=%.2f reranked_count=%d generated_context_count=%d",
        rerank_ms,
        retrieved_count,
        len(docs),
    )

    document_ids = [document.get("document_id") for document in docs]
    add_trace_metadata(
        retrieval_query=retrieval_query,
        retrieved_chunk_count=retrieved_count,
        reranked_chunk_count=len(docs),
        reranked_document_ids=document_ids,
        **performance_metrics,
    )
    return {
        "documents": docs,
        "performance_metrics": performance_metrics,
        "observability": {
            "retrieval_query": retrieval_query,
            "retrieved_chunk_count": retrieved_count,
            "reranked_chunk_count": len(docs),
            "reranked_document_ids": document_ids,
        },
    }
