import json

from evaluation.framework import (
    load_dataset_cases,
    score_answer,
    score_sources,
)


def test_placeholder_answers_are_not_scored_as_wrong():
    score = score_answer("Policy Statement 1", "Actual grounded policy text")
    assert score["answer_evaluable"] is False
    assert score["answer_correct"] is None


def test_short_ground_truth_is_found_in_complete_answer():
    score = score_answer(
        "3 working days",
        "Leave requests must be submitted at least 3 working days in advance.",
    )
    assert score["answer_correct"] is True


def test_numeric_range_and_frequency_paraphrases_are_equivalent():
    assert (
        score_answer("3-7 business days", "Shipping takes 3 to 7 business days.")[
            "answer_correct"
        ]
        is True
    )
    assert (
        score_answer("every month", "Safety inspections are conducted monthly.")[
            "answer_correct"
        ]
        is True
    )


def test_source_requires_expected_file_and_page_in_same_item():
    score = score_sources(
        [
            {"file": "uploads/banking_policy.pdf", "page": 2},
            {"file": "uploads/other.pdf", "page": 1},
        ],
        "banking_policy.pdf",
        1,
    )
    assert score["source_document_correct"] is True
    assert score["source_page_correct"] is True
    assert score["source_correct"] is False


def test_all_dataset_filename_variants_are_discovered(tmp_path):
    (tmp_path / "banking_dataset.json").write_text(
        json.dumps(
            [
                {
                    "question": "q",
                    "expected_answer": "a",
                    "expected_page": 1,
                }
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "logistics_dataset_100_questions.json").write_text(
        json.dumps(
            [
                {
                    "question": "q",
                    "expected_answer": "Policy Statement 1",
                    "expected_page": 1,
                }
            ]
        ),
        encoding="utf-8",
    )

    cases = load_dataset_cases(tmp_path)

    assert len(cases) == 2
    assert {case["domain"] for case in cases} == {"banking", "logistics"}
    banking = next(case for case in cases if case["domain"] == "banking")
    logistics = next(case for case in cases if case["domain"] == "logistics")
    assert banking["evaluation_question"] == "According to the banking policy, q"
    assert logistics["evaluation_question"] == "q"
