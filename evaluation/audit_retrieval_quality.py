"""Measure retrieval, rewrite, rerank, multi-document, and no-answer quality."""

import json
import re
from copy import deepcopy
from pathlib import Path

from app.agents.response_agent import NO_ANSWER, response_agent
from app.agents.rewrite_agent import rewrite_agent
from app.config import settings
from app.db.database import SessionLocal
from app.rag.reranker import rerank
from app.rag.retrieval import retrieve
from evaluation.framework import filename_matches, load_dataset_cases

DATASET_DIR = Path("evaluation/datasets")
REPORT_PATH = Path("evaluation/reports/retrieval_quality_audit.json")
USER_ID = 1

NO_ANSWER_QUESTIONS = [
    "What is the employee dress code on Fridays?",
    "Does the company provide pet insurance?",
    "What is the cryptocurrency reimbursement policy?",
    "How many free meals are provided each day?",
    "What is the paid sabbatical entitlement?",
    "How many reserved parking spaces does each employee receive?",
]


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold().replace("-", " ")).strip()


def contains_answer(document: dict, expected_answer: str) -> bool:
    return normalize(expected_answer) in normalize(document["content"])


def is_expected_document(document: dict, expected_filename: str) -> bool:
    return filename_matches(document["filename"], expected_filename)


def relevant(document: dict, expected_answer: str, expected_filename: str) -> bool:
    return contains_answer(document, expected_answer) and is_expected_document(
        document, expected_filename
    )


def rank_of_relevant(
    documents: list[dict], expected_answer: str, expected_filename: str
) -> int | None:
    for rank, document in enumerate(documents, start=1):
        if relevant(document, expected_answer, expected_filename):
            return rank
    return None


def load_cases() -> list[dict]:
    return load_dataset_cases(DATASET_DIR)


def audit_case(db, case: dict) -> dict:
    raw = retrieve(
        db,
        case["evaluation_question"],
        USER_ID,
        top_k=settings.retrieval_top_k,
    )
    reranked = rerank(
        case["evaluation_question"], deepcopy(raw), top_k=settings.rerank_top_k
    )
    raw_rank = rank_of_relevant(raw, case["expected_answer"], case["expected_filename"])
    rerank_rank = rank_of_relevant(
        reranked, case["expected_answer"], case["expected_filename"]
    )
    false_positives = [
        {
            "rank": rank,
            "file": document["filename"],
            "page": document["page_number"],
            "score": round(document["score"], 4),
        }
        for rank, document in enumerate(raw, start=1)
        if not relevant(document, case["expected_answer"], case["expected_filename"])
    ]
    return {
        **case,
        "raw_relevant_rank": raw_rank,
        "reranked_relevant_rank": rerank_rank,
        "retrieved_count": len(raw),
        "false_positive_count": len(false_positives),
        "false_positives": false_positives,
        "reranker_helped": raw_rank is not None
        and rerank_rank is not None
        and rerank_rank < raw_rank,
        "reranker_hurt": raw_rank is not None
        and (rerank_rank is None or rerank_rank > raw_rank),
        "cross_document_top1": bool(raw)
        and not is_expected_document(raw[0], case["expected_filename"]),
        "reranked_top": (
            {
                "file": reranked[0]["filename"],
                "page": reranked[0]["page_number"],
                "rerank_score": round(reranked[0]["rerank_score"], 4),
            }
            if reranked
            else None
        ),
    }


def audit_rewrites(db, cases: list[dict]) -> list[dict]:
    results = []
    for case in cases[::5]:
        history = f"user: {case['question']}\nassistant: Prior answer\n"
        original = "What about that?"
        rewritten = rewrite_agent({"query": original, "history": history})[
            "retrieval_query"
        ]
        original_docs = retrieve(db, original, USER_ID)
        rewritten_docs = retrieve(db, rewritten, USER_ID)
        original_rank = rank_of_relevant(
            original_docs, case["expected_answer"], case["expected_filename"]
        )
        rewritten_rank = rank_of_relevant(
            rewritten_docs, case["expected_answer"], case["expected_filename"]
        )
        results.append(
            {
                "domain": case["domain"],
                "history_query": case["question"],
                "original_query": original,
                "rewritten_query": rewritten,
                "original_relevant_rank": original_rank,
                "rewritten_relevant_rank": rewritten_rank,
                "rewrite_hurt": original_rank is not None
                and (rewritten_rank is None or rewritten_rank > original_rank),
            }
        )
    return results


def audit_no_answer(db) -> list[dict]:
    results = []
    for question in NO_ANSWER_QUESTIONS:
        raw = retrieve(db, question, USER_ID)
        documents = rerank(question, raw, top_k=settings.rerank_top_k)
        response = response_agent({"query": question, "documents": documents})
        results.append(
            {
                "question": question,
                "retrieved_count": len(raw),
                "answer": response["answer"],
                "fallback_triggered": response["answer"] == NO_ANSWER,
                "sources_returned": len(response["sources"]),
            }
        )
    return results


def percentage(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 2) if denominator else 0.0


def main() -> None:
    cases = load_cases()
    with SessionLocal() as db:
        results = [audit_case(db, case) for case in cases]
        rewrites = audit_rewrites(db, cases)
        no_answer = audit_no_answer(db)

    total = len(results)
    report = {
        "configuration": {
            "user_id": USER_ID,
            "retrieval_top_k": settings.retrieval_top_k,
            "rerank_top_k": settings.rerank_top_k,
            "retrieval_score_threshold": settings.retrieval_score_threshold,
        },
        "metrics": {
            "questions": total,
            "retrieval_success_rate": percentage(
                sum(item["raw_relevant_rank"] is not None for item in results),
                total,
            ),
            "raw_top_1_accuracy": percentage(
                sum(item["raw_relevant_rank"] == 1 for item in results), total
            ),
            "raw_top_3_accuracy": percentage(
                sum(
                    item["raw_relevant_rank"] is not None
                    and item["raw_relevant_rank"] <= 3
                    for item in results
                ),
                total,
            ),
            "reranked_top_1_accuracy": percentage(
                sum(item["reranked_relevant_rank"] == 1 for item in results),
                total,
            ),
            "reranked_top_2_recall": percentage(
                sum(item["reranked_relevant_rank"] is not None for item in results),
                total,
            ),
            "cross_document_top_1_rate": percentage(
                sum(item["cross_document_top1"] for item in results), total
            ),
            "irrelevant_result_rate": percentage(
                sum(item["false_positive_count"] for item in results),
                sum(item["retrieved_count"] for item in results),
            ),
            "reranker_helped_cases": sum(item["reranker_helped"] for item in results),
            "reranker_hurt_cases": sum(item["reranker_hurt"] for item in results),
            "rewrite_hurt_cases": sum(item["rewrite_hurt"] for item in rewrites),
            "no_answer_fallback_rate": percentage(
                sum(item["fallback_triggered"] for item in no_answer),
                len(no_answer),
            ),
        },
        "results": results,
        "rewrite_results": rewrites,
        "no_answer_results": no_answer,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2))


if __name__ == "__main__":
    main()
