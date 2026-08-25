import pytest

from app.agents import rewrite_agent as rewrite_module


class _Response:
    def __init__(self, content: str):
        self.content = content


class _LLM:
    def __init__(self, content: str):
        self.content = content
        self.prompts = []

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        return _Response(self.content)


def test_rewrite_is_skipped_without_history():
    assert not rewrite_module._should_rewrite("What about emergency ones?", "")


def test_standalone_short_query_is_not_contaminated_by_history(monkeypatch):
    llm = _LLM("unexpected")
    monkeypatch.setattr(rewrite_module, "llm", llm)

    result = rewrite_module.rewrite_agent(
        {
            "query": "Explain refund policy",
            "history": "user: What is the leave policy?\nassistant: Leave details.",
        }
    )

    assert result["retrieval_query"] == "Explain refund policy"
    assert result["performance_metrics"] == {"rewrite_ms": 0.0}
    assert llm.prompts == []


@pytest.mark.parametrize(
    ("follow_up", "standalone"),
    [
        (
            "What about emergency ones?",
            "How many emergency leave days are allowed by the company leave policy?",
        ),
        (
            "And the second policy?",
            "What does the second data-retention policy require?",
        ),
        (
            "How many are allowed?",
            "How many annual paid leave days are employees allowed?",
        ),
    ],
)
def test_ambiguous_follow_up_becomes_standalone_query(
    monkeypatch, follow_up, standalone
):
    llm = _LLM(standalone)
    monkeypatch.setattr(rewrite_module, "llm", llm)
    history = (
        "user: Explain the company policies.\n"
        "assistant: The first covers leave and the second covers data retention."
    )

    result = rewrite_module.rewrite_agent({"query": follow_up, "history": history})

    assert result["retrieval_query"] == standalone
    assert result["performance_metrics"]["rewrite_ms"] >= 0.0
    assert "Recent Conversation History:" in llm.prompts[0]
    assert history in llm.prompts[0]
    assert "Previous user question:" not in result["retrieval_query"]
    assert "Follow-up question:" not in result["retrieval_query"]


def test_empty_rewrite_falls_back_to_original_query(monkeypatch):
    monkeypatch.setattr(rewrite_module, "llm", _LLM("   "))

    result = rewrite_module.rewrite_agent(
        {
            "query": "What about those?",
            "history": "user: Explain emergency leave.",
        }
    )

    assert result["retrieval_query"] == "What about those?"
