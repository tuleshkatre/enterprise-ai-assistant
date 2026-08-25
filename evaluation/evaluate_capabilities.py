"""Evaluate memory, SQL routing, and SSE behavior through public endpoints."""

import os
import uuid
from pathlib import Path
from typing import Any

from evaluation.framework import EvaluationClient, atomic_write_json, percentage

REPORT_PATH = Path("evaluation/reports/capability_evaluation_report.json")


def _result(name: str, passed: bool, **details: Any) -> dict[str, Any]:
    return {"name": name, "passed": passed, **details}


def evaluate_memory(client: EvaluationClient) -> list[dict[str, Any]]:
    if os.getenv("EVAL_ALLOW_MEMORY_MUTATION", "false").casefold() != "true":
        return [
            _result(
                "long_term_memory_suite",
                False,
                skipped=True,
                reason="Set EVAL_ALLOW_MEMORY_MUTATION=true for a dedicated eval user",
            )
        ]

    value = f"eval-{uuid.uuid4().hex[:8]}"
    first = client.create_conversation()
    second = client.create_conversation()
    third = None
    results = []
    try:
        saved = client.chat(first, f"Remember that my favorite color is {value}.")[
            "answer"
        ]
        recalled = client.chat(second, "Whats my favorite color?")["answer"]
        listed = client.chat(second, "What do you remember about me?")["answer"]
        blocked = client.chat(
            second, "Remember that my password is evaluation-secret."
        )["answer"]
        secondary_email = os.getenv("EVAL_SECONDARY_EMAIL")
        secondary_password = os.getenv("EVAL_SECONDARY_PASSWORD")
        if secondary_email and secondary_password:
            secondary = EvaluationClient(
                base_url=client.base_url,
                email=secondary_email,
                password=secondary_password,
                timeout=client.timeout,
            )
            secondary.login()
            secondary_conversation = secondary.create_conversation()
            try:
                secondary_answer = secondary.chat(
                    secondary_conversation, "Whats my favorite color?"
                )["answer"]
            finally:
                secondary.delete_conversation(secondary_conversation)
            isolation_result = _result(
                "cross_user_memory_isolation",
                value not in secondary_answer,
                answer=secondary_answer,
            )
        else:
            isolation_result = _result(
                "cross_user_memory_isolation",
                False,
                skipped=True,
                reason="Set EVAL_SECONDARY_EMAIL and EVAL_SECONDARY_PASSWORD",
            )

        forgotten = client.chat(second, "Forget my favorite color.")["answer"]
        third = client.create_conversation()
        after_forget = client.chat(third, "Whats my favorite color?")["answer"]
        results.extend(
            [
                _result("memory_save", value in saved, answer=saved),
                _result(
                    "cross_conversation_recall", value in recalled, answer=recalled
                ),
                _result("memory_list", value in listed, answer=listed),
                _result(
                    "sensitive_memory_block",
                    "cannot store" in blocked.casefold(),
                    answer=blocked,
                ),
                isolation_result,
                _result(
                    "memory_forget",
                    "forgotten" in forgotten.casefold(),
                    answer=forgotten,
                ),
                _result(
                    "memory_absent_in_new_conversation_after_forget",
                    value not in after_forget,
                    answer=after_forget,
                ),
            ]
        )
    finally:
        try:
            client.chat(second, "Forget my favorite color.")
        finally:
            client.delete_conversation(first)
            client.delete_conversation(second)
            if third is not None:
                client.delete_conversation(third)
    return results


def evaluate_sql(client: EvaluationClient) -> list[dict[str, Any]]:
    conversation_id = client.create_conversation()
    try:
        response = client.chat(conversation_id, "Group my messages by role.")
    finally:
        client.delete_conversation(conversation_id)
    answer = str(response.get("answer", ""))
    return [
        _result(
            "sql_natural_language_response",
            bool(answer)
            and "could not find" not in answer.casefold()
            and response.get("sources") == [],
            answer=answer,
            sources=response.get("sources"),
        )
    ]


def evaluate_streaming(client: EvaluationClient) -> list[dict[str, Any]]:
    conversation_id = client.create_conversation()
    try:
        body = client.stream(conversation_id, "2 + 3")
    finally:
        client.delete_conversation(conversation_id)
    return [
        _result("stream_has_answer_token", "data: 5" in body, body=body),
        _result(
            "stream_has_sources_event",
            "event: sources" in body,
            body=body,
        ),
        _result(
            "stream_has_done_event",
            "event: done\ndata: completed" in body,
            body=body,
        ),
        _result(
            "stream_does_not_expose_answer_json",
            'data: {"answer"' not in body,
            body=body,
        ),
    ]


def main() -> None:
    client = EvaluationClient.from_environment()
    client.login()
    results = [
        *evaluate_memory(client),
        *evaluate_sql(client),
        *evaluate_streaming(client),
    ]
    executed = [result for result in results if not result.get("skipped")]
    report = {
        "metrics": {
            "checks": len(results),
            "executed": len(executed),
            "passed": sum(result["passed"] for result in executed),
            "pass_rate": percentage(
                sum(result["passed"] for result in executed), len(executed)
            ),
        },
        "results": results,
    }
    atomic_write_json(REPORT_PATH, report)
    print(report["metrics"])


if __name__ == "__main__":
    main()
