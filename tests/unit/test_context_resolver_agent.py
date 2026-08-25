import json

import pytest

from app.agents import context_resolver_agent as resolver_module


class _Response:
    def __init__(self, content: str):
        self.content = content


class _LLM:
    def __init__(self, payload):
        self.payload = payload
        self.prompts = []

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        return _Response(json.dumps(self.payload))


def test_standalone_query_bypasses_resolution_llm(monkeypatch):
    llm = _LLM({"resolved_query": "unexpected", "context_route": None})
    monkeypatch.setattr(resolver_module, "llm", llm)

    result = resolver_module.context_resolver_agent(
        {
            "query": "How many documents have I uploaded?",
            "history": "user: My name is Tulesh.\n",
        }
    )

    assert result["resolved_query"] == "How many documents have I uploaded?"
    assert result["context_route"] is None
    assert result["performance_metrics"] == {"context_resolution_ms": 0.0}
    assert llm.prompts == []


def test_personal_fact_declaration_uses_conversation_route_without_history(
    monkeypatch,
):
    llm = _LLM({"resolved_query": "unexpected", "context_route": None})
    monkeypatch.setattr(resolver_module, "llm", llm)

    result = resolver_module.context_resolver_agent(
        {"query": "My name is Tulesh.", "history": ""}
    )

    assert result["resolved_query"] == "My name is Tulesh."
    assert result["context_route"] == "conversation"
    assert result["performance_metrics"] == {"context_resolution_ms": 0.0}
    assert llm.prompts == []


def test_sql_follow_up_is_resolved_before_routing(monkeypatch):
    llm = _LLM(
        {
            "resolved_query": "How many conversations do I have?",
            "context_route": None,
        }
    )
    monkeypatch.setattr(resolver_module, "llm", llm)

    result = resolver_module.context_resolver_agent(
        {
            "query": "What about conversations?",
            "history": (
                "user: Group my messages by role.\n"
                "assistant: Messages were grouped by role.\n"
            ),
        }
    )

    assert result["resolved_query"] == "How many conversations do I have?"
    assert result["context_route"] is None
    assert llm.prompts == []


@pytest.mark.parametrize(
    "query",
    ["What is my name?", "What's my name?", "whats my name"],
)
def test_history_fact_selects_conversation_route(monkeypatch, query):
    llm = _LLM(
        {
            "resolved_query": "What is my name?",
            "context_route": "conversation",
        }
    )
    monkeypatch.setattr(resolver_module, "llm", llm)

    result = resolver_module.context_resolver_agent(
        {
            "query": query,
            "history": "user: My name is Tulesh.\n",
        }
    )

    assert result["context_route"] == "conversation"
    assert result["resolved_query"] == query
    assert llm.prompts == []


def test_summarized_user_fact_selects_conversation_route(monkeypatch):
    llm = _LLM({"resolved_query": "unexpected", "context_route": None})
    monkeypatch.setattr(resolver_module, "llm", llm)

    result = resolver_module.context_resolver_agent(
        {
            "query": "whats my name",
            "history": "",
            "conversation_summary": "The user's name is Tulesh.",
        }
    )

    assert result["context_route"] == "conversation"
    assert llm.prompts == []


def test_invalid_model_output_falls_back_safely(monkeypatch):
    class _InvalidLLM:
        def invoke(self, _prompt):
            return _Response("not-json")

    monkeypatch.setattr(resolver_module, "llm", _InvalidLLM())
    result = resolver_module.context_resolver_agent(
        {
            "query": "What about those?",
            "history": "user: Explain emergency leave.\n",
        }
    )

    assert result["resolved_query"] == "What about those?"
    assert result["context_route"] is None


def test_only_bounded_recent_history_is_sent(monkeypatch):
    llm = _LLM({"resolved_query": "What is it?", "context_route": None})
    monkeypatch.setattr(resolver_module, "llm", llm)
    old_history = "x" * (resolver_module.MAX_CONTEXT_HISTORY_CHARS + 50)

    resolver_module.context_resolver_agent(
        {"query": "What is it?", "history": old_history}
    )

    assert old_history not in llm.prompts[0]
    assert "x" * resolver_module.MAX_CONTEXT_HISTORY_CHARS in llm.prompts[0]
