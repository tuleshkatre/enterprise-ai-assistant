import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

DOMAIN_FILES = {
    "banking": "banking_policy.pdf",
    "ecommerce": "ecommerce_policy.pdf",
    "healthcare": "healthcare_policy.pdf",
    "hr": "enterprise_rag_test_corpus.pdf",
    "logistics": "logistics_supply_chain_100_page_corpus.pdf",
    "manufacturing": "manufacturing_policy.pdf",
    "saas": "saas_policy.pdf",
}
PLACEHOLDER_ANSWER_PATTERN = re.compile(r"^policy statement \d+$", re.I)


def normalize(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"(?<=\d)\s*[-–—]\s*(?=\d)", " to ", value)
    value = value.replace("-", " ")
    value = re.sub(r"\bevery\s+month\b", "monthly", value)
    value = re.sub(r"[^\w.]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def token_f1(expected: str, actual: str) -> float:
    expected_tokens = normalize(expected).split()
    actual_tokens = normalize(actual).split()
    if not expected_tokens or not actual_tokens:
        return 0.0
    remaining = actual_tokens.copy()
    overlap = 0
    for token in expected_tokens:
        if token in remaining:
            overlap += 1
            remaining.remove(token)
    precision = overlap / len(actual_tokens)
    recall = overlap / len(expected_tokens)
    return 2 * precision * recall / (precision + recall) if overlap else 0.0


def score_answer(expected: str, actual: str) -> dict[str, Any]:
    evaluable = not PLACEHOLDER_ANSWER_PATTERN.fullmatch(expected.strip())
    expected_normalized = normalize(expected)
    actual_normalized = normalize(actual)
    contains = bool(expected_normalized) and expected_normalized in actual_normalized
    f1 = token_f1(expected, actual)
    return {
        "answer_evaluable": evaluable,
        "answer_correct": (contains or f1 >= 0.8) if evaluable else None,
        "answer_contains_expected": contains if evaluable else None,
        "answer_token_f1": round(f1, 4) if evaluable else None,
    }


def filename_matches(actual: str, expected: str) -> bool:
    return actual.replace("\\", "/").casefold().endswith(expected.casefold())


def score_sources(
    sources: list[dict[str, Any]], expected_filename: str, expected_page: int
) -> dict[str, Any]:
    page_match = any(source.get("page") == expected_page for source in sources)
    document_match = any(
        filename_matches(str(source.get("file", "")), expected_filename)
        for source in sources
    )
    exact_match = any(
        source.get("page") == expected_page
        and filename_matches(str(source.get("file", "")), expected_filename)
        for source in sources
    )
    return {
        "source_page_correct": page_match,
        "source_document_correct": document_match,
        "source_correct": exact_match,
    }


def dataset_domain(path: Path) -> str:
    return path.stem.split("_dataset", 1)[0]


def load_dataset_cases(dataset_dir: Path) -> list[dict[str, Any]]:
    cases = []
    for path in sorted(dataset_dir.glob("*_dataset*.json")):
        domain = dataset_domain(path)
        expected_filename = DOMAIN_FILES.get(domain)
        if expected_filename is None:
            raise ValueError(f"No expected document configured for dataset: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"Dataset must contain a JSON list: {path}")
        for index, item in enumerate(payload):
            required = {"question", "expected_answer", "expected_page"}
            if not isinstance(item, dict) or not required <= item.keys():
                raise ValueError(f"Invalid case {index} in {path}")
            cases.append(
                {
                    **item,
                    "dataset": path.stem,
                    "domain": domain,
                    "expected_filename": expected_filename,
                    "evaluation_question": (
                        item["question"]
                        if domain == "logistics"
                        else f"According to the {domain} policy, "
                        f"{item['question'][0].lower()}{item['question'][1:]}"
                    ),
                }
            )
    return cases


def percentage(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 2) if denominator else 0.0


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


@dataclass
class EvaluationClient:
    base_url: str
    email: str
    password: str
    timeout: float = 120.0

    @classmethod
    def from_environment(cls) -> "EvaluationClient":
        load_dotenv(".env.evaluation", override=False)
        email = os.getenv("EVAL_EMAIL")
        password = os.getenv("EVAL_PASSWORD")
        if not email or not password:
            raise RuntimeError("Set EVAL_EMAIL and EVAL_PASSWORD before evaluation")
        return cls(
            base_url=os.getenv("EVAL_BASE_URL", "http://localhost:8000"),
            email=email,
            password=password,
            timeout=float(os.getenv("EVAL_TIMEOUT_SECONDS", "120")),
        )

    def __post_init__(self) -> None:
        self.session = requests.Session()

    def login(self) -> None:
        response = self.session.post(
            f"{self.base_url}/api/v1/login",
            json={"email": self.email, "password": self.password},
            timeout=self.timeout,
        )
        response.raise_for_status()
        self.session.headers["Authorization"] = (
            f"Bearer {response.json()['access_token']}"
        )

    def create_conversation(self) -> int:
        response = self.session.post(
            f"{self.base_url}/api/v1/conversation", timeout=self.timeout
        )
        response.raise_for_status()
        return int(response.json()["conversation_id"])

    def delete_conversation(self, conversation_id: int) -> None:
        response = self.session.delete(
            f"{self.base_url}/api/v1/conversation_delete/{conversation_id}",
            timeout=self.timeout,
        )
        response.raise_for_status()

    def chat(self, conversation_id: int, query: str) -> dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}/api/v1/graph-chat",
            json={"conversation_id": conversation_id, "query": query},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def stream(self, conversation_id: int, query: str) -> str:
        response = self.session.post(
            f"{self.base_url}/api/v1/graph-chat/stream",
            json={"conversation_id": conversation_id, "query": query},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.text
