"""End-to-end RAG answer and citation evaluation through the public API."""

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any

from evaluation.framework import (
    EvaluationClient,
    atomic_write_json,
    load_dataset_cases,
    percentage,
    score_answer,
    score_sources,
)

DATASET_DIR = Path("evaluation/datasets")
REPORT_PATH = Path("evaluation/reports/rag_evaluation_report.json")


def evaluate_case(client: EvaluationClient, case: dict[str, Any]) -> dict[str, Any]:
    conversation_id = client.create_conversation()
    try:
        response = client.chat(conversation_id, case["evaluation_question"])
    finally:
        client.delete_conversation(conversation_id)

    answer = str(response.get("answer", "")).strip()
    sources = response.get("sources", [])
    if not isinstance(sources, list):
        sources = []
    return {
        **case,
        "actual_answer": answer,
        **score_answer(case["expected_answer"], answer),
        **score_sources(
            sources,
            case["expected_filename"],
            case["expected_page"],
        ),
        "returned_sources": sources,
    }


def build_report(results: list[dict[str, Any]]) -> dict[str, Any]:
    evaluable = [result for result in results if result["answer_evaluable"]]
    by_dataset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        by_dataset[result["dataset"]].append(result)

    return {
        "metrics": {
            "total_questions": len(results),
            "answer_evaluable_questions": len(evaluable),
            "answer_accuracy": percentage(
                sum(result["answer_correct"] is True for result in evaluable),
                len(evaluable),
            ),
            "citation_file_and_page_accuracy": percentage(
                sum(result["source_correct"] for result in results), len(results)
            ),
            "citation_document_accuracy": percentage(
                sum(result["source_document_correct"] for result in results),
                len(results),
            ),
            "citation_page_accuracy": percentage(
                sum(result["source_page_correct"] for result in results),
                len(results),
            ),
        },
        "dataset_breakdown": {
            dataset: {
                "questions": len(items),
                "answer_evaluable": sum(item["answer_evaluable"] for item in items),
                "answer_accuracy": percentage(
                    sum(item["answer_correct"] is True for item in items),
                    sum(item["answer_evaluable"] for item in items),
                ),
                "citation_accuracy": percentage(
                    sum(item["source_correct"] for item in items), len(items)
                ),
            }
            for dataset, items in sorted(by_dataset.items())
        },
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    cases = load_dataset_cases(args.dataset_dir)
    if args.limit is not None:
        cases = cases[: args.limit]
    client = EvaluationClient.from_environment()
    client.login()

    results = []
    for case in cases:
        results.append(evaluate_case(client, case))
        atomic_write_json(args.report, build_report(results))

    report = build_report(results)
    atomic_write_json(args.report, report)
    print(report["metrics"])


if __name__ == "__main__":
    main()
