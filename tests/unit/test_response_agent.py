import json

from app.agents import response_agent as response_module


class _Response:
    def __init__(self, content: str):
        self.content = content


class _LLM:
    def __init__(self, content: str):
        self.content = content

    def invoke(self, _prompt: str):
        return _Response(self.content)


def test_response_agent_returns_only_cited_unique_pages(monkeypatch):
    monkeypatch.setattr(
        response_module,
        "llm",
        _LLM(
            json.dumps(
                {
                    "answer": "Leave approval is required.",
                    "used_doc_ids": [12, 10, 11, 999],
                }
            )
        ),
    )
    documents = [
        {
            "document_id": 10,
            "filename": "policy.pdf",
            "page_number": 1,
            "content": "lower score",
            "rerank_score": 0.2,
        },
        {
            "document_id": 11,
            "filename": "policy.pdf",
            "page_number": 1,
            "content": "highest score",
            "rerank_score": 0.9,
        },
        {
            "document_id": 12,
            "filename": "policy.pdf",
            "page_number": 2,
            "content": "page two",
            "rerank_score": 0.8,
        },
    ]

    result = response_module.response_agent(
        {"query": "Who approves leave?", "documents": documents}
    )

    assert result["answer"] == "Leave approval is required."
    assert result["sources"] == [
        {"file": "policy.pdf", "page": 1, "snippet": "highest score"},
        {"file": "policy.pdf", "page": 2, "snippet": "page two"},
    ]


def test_response_agent_drops_invalid_ids_and_malformed_output(monkeypatch):
    documents = [
        {
            "document_id": 1,
            "filename": "policy.pdf",
            "page_number": 1,
            "content": "text",
            "rerank_score": 1.0,
        }
    ]
    monkeypatch.setattr(
        response_module, "llm", _LLM('{"answer": "Supported", "used_doc_ids": [999]}')
    )
    assert (
        response_module.response_agent({"query": "q", "documents": documents})[
            "sources"
        ]
        == []
    )

    monkeypatch.setattr(response_module, "llm", _LLM("not JSON"))
    result = response_module.response_agent({"query": "q", "documents": documents})
    assert result["answer"] == response_module.NO_ANSWER
    assert result["sources"] == []
    assert result["performance_metrics"]["answer_llm_ms"] >= 0
