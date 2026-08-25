from sentence_transformers import CrossEncoder

from app.observability.langsmith import add_trace_metadata, trace_agent

reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")


def _rerank_text(doc: dict) -> str:
    """Include source identity so explicit document requests remain scoped."""
    filename = str(doc.get("filename", "")).replace("\\", "/").rsplit("/", 1)[-1]
    return f"Source: {filename}\n{doc['content']}"


@trace_agent("reranker", run_type="retriever", tags=["rag", "rerank"])
def rerank(query: str, docs: list, top_k: int = 3):

    if not docs:
        return []

    pairs = [[query, _rerank_text(doc)] for doc in docs]

    scores = reranker.predict(pairs)

    for doc, score in zip(
        docs,
        scores,
        strict=True,
    ):
        doc["rerank_score"] = float(score)

    docs.sort(
        key=lambda x: (bool(x.get("source_match")), x["rerank_score"]), reverse=True
    )

    reranked = docs[:top_k]
    add_trace_metadata(
        input_chunk_count=len(docs),
        output_chunk_count=len(reranked),
        output_document_ids=[doc.get("document_id") for doc in reranked],
    )
    return reranked
