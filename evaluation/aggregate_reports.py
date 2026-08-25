"""Create a concise summary from canonical evaluation reports."""

import json
from pathlib import Path
from typing import Any

from evaluation.framework import atomic_write_json

REPORTS_DIR = Path("evaluation/reports")
OUTPUT_PATH = REPORTS_DIR / "aggregate_report.json"


def _read(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def aggregate_reports() -> dict[str, Any]:
    report_specs = {
        "rag": REPORTS_DIR / "rag_evaluation_report.json",
        "retrieval": REPORTS_DIR / "retrieval_quality_audit.json",
        "capabilities": REPORTS_DIR / "capability_evaluation_report.json",
    }
    reports = {
        name: payload
        for name, path in report_specs.items()
        if (payload := _read(path)) is not None
    }
    summary = {
        "reports_available": sorted(reports),
        "metrics": {
            name: report.get("metrics", {}) for name, report in reports.items()
        },
    }
    atomic_write_json(OUTPUT_PATH, summary)
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    aggregate_reports()
