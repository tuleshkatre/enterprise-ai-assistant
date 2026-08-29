import logging
import re
from time import perf_counter

from sqlalchemy import text

from app.config import settings
from app.observability.langsmith import add_trace_metadata, trace_agent
from app.rag.embeddings import get_embedding
from app.rag.providers import RETRIEVAL_QUERY

logger = logging.getLogger(__name__)

POLICY_PAGE_PATTERN = re.compile(
    r"\bpolicy\s+statement\s+(?:on\s+)?page\s+(\d+)\b",
    re.IGNORECASE,
)
LEXICAL_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "be",
    "before",
    "can",
    "do",
    "does",
    "how",
    "in",
    "is",
    "many",
    "must",
    "of",
    "on",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}
GENERIC_SOURCE_TERMS = {
    "corpus",
    "document",
    "enterprise",
    "file",
    "pdf",
    "policy",
    "rag",
    "test",
    "uploads",
}


def _policy_statement_pattern(query: str) -> str | None:
    """Return an exact corpus label pattern for explicit policy-page queries."""
    match = POLICY_PAGE_PATTERN.search(query)
    if match is None:
        return None
    return f"%Policy Statement {int(match.group(1))}:%"


def _lexical_tsquery(query: str) -> str:
    """Build a safe OR query for lexical filename/content ranking."""
    terms = {
        term.casefold()
        for term in re.findall(r"[A-Za-z0-9]+", query)
        if len(term) > 1 and term.casefold() not in LEXICAL_STOP_WORDS
    }
    return " | ".join(sorted(terms))


def _explicit_source_match(query: str, filename: str) -> bool:
    query_terms = {term.casefold() for term in re.findall(r"[A-Za-z]+", query)}
    source_terms = {
        term.casefold()
        for term in re.findall(r"[A-Za-z]+", filename)
        if len(term) > 2 and term.casefold() not in GENERIC_SOURCE_TERMS
    }
    return bool(query_terms & source_terms)


@trace_agent("vector_retrieval", run_type="retriever", tags=["rag", "vector"])
def retrieve(
    db,
    query: str,
    user_id: int,
    top_k: int | None = None,
    score_threshold: float | None = None,
    performance_metrics: dict[str, float] | None = None,
):

    if score_threshold is None:
        score_threshold = settings.retrieval_score_threshold
    if top_k is None:
        top_k = settings.retrieval_top_k

    embedding_started_at = perf_counter()
    query_embedding = get_embedding(query, task_type=RETRIEVAL_QUERY)
    embedding_ms = (perf_counter() - embedding_started_at) * 1000

    retrieval_started_at = perf_counter()
    exact_pattern = _policy_statement_pattern(query)
    result = db.execute(
        text("""
        SELECT
            id,
            filename,
            page_number,
            chunk_index,
            chunk_text,
            1 - (embedding <=> CAST(:embedding AS vector)) AS score,
            ts_rank_cd(
                to_tsvector(
                    'simple',
                    regexp_replace(filename, '[^[:alnum:]]+', ' ', 'g')
                    || ' ' || chunk_text
                ),
                to_tsquery('simple', :lexical_query)
            ) AS lexical_score,
            (
                CAST(:exact_pattern AS text) IS NOT NULL
                AND chunk_text ILIKE :exact_pattern
            ) AS exact_match
        FROM document_chunks
        WHERE user_id = :user_id
        ORDER BY
            exact_match DESC,
            lexical_score DESC,
            embedding <=> CAST(:embedding AS vector)
        LIMIT :top_k
        """),
        {
            "embedding": str(query_embedding),
            "lexical_query": _lexical_tsquery(query),
            "exact_pattern": exact_pattern,
            "user_id": user_id,
            "top_k": top_k,
        },
    )

    rows = result.fetchall()

    documents = []
    seen_content = set()

    for row in rows:
        score = float(row[5])
        lexical_score = float(row[6])
        exact_match = bool(row[7])
        content = row[4].strip()
        content_key = " ".join(content.split()).casefold()

        if (
            (score < score_threshold and lexical_score <= 0 and not exact_match)
            or not content
            or content_key in seen_content
        ):
            continue

        seen_content.add(content_key)
        documents.append(
            {
                "document_id": row[0],
                "filename": row[1],
                "page_number": row[2],
                "chunk_index": row[3],
                "content": content,
                "score": score,
                "lexical_score": lexical_score,
                "source_match": _explicit_source_match(query, str(row[1])),
            }
        )

    retrieval_ms = (perf_counter() - retrieval_started_at) * 1000
    if performance_metrics is not None:
        performance_metrics.update(
            {"embedding_ms": embedding_ms, "retrieval_ms": retrieval_ms}
        )
    logger.info(
        "rag_timing embedding_ms=%.2f retrieval_ms=%.2f retrieved_count=%d returned_count=%d",
        embedding_ms,
        retrieval_ms,
        len(rows),
        len(documents),
    )
    add_trace_metadata(
        retrieval_query=query,
        database_candidate_count=len(rows),
        returned_chunk_count=len(documents),
        returned_document_ids=[doc["document_id"] for doc in documents],
        embedding_ms=embedding_ms,
        retrieval_ms=retrieval_ms,
    )
    return documents
