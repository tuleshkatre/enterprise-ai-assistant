from types import SimpleNamespace

from app.agents import rewrite_agent
from app.tools import web_search
from app.tools.calculator import calculator


def test_calculator_success_and_failure():
    assert calculator.invoke({"expression": "2 + 3 * 4"}) == "14"
    assert "Calculation error:" in calculator.invoke({"expression": "invalid"})


def test_web_search_formats_results(monkeypatch):
    class FakeSearch:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def text(self, *_args, **_kwargs):
            return [
                {"title": "Result", "body": "Summary", "href": "https://example.com"}
            ]

    monkeypatch.setattr(web_search, "DDGS", FakeSearch)
    result = web_search.web_search.invoke({"query": "test"})
    assert "Title: Result" in result
    assert "URL: https://example.com" in result


def test_web_search_handles_empty_results_and_errors(monkeypatch):
    class EmptySearch:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def text(self, *_args, **_kwargs):
            return []

    monkeypatch.setattr(web_search, "DDGS", EmptySearch)
    assert web_search.web_search.invoke({"query": "test"}) == "No results found."

    class FailedSearch:
        def __init__(self):
            raise RuntimeError("offline")

    monkeypatch.setattr(web_search, "DDGS", FailedSearch)
    assert "Search error: offline" in web_search.web_search.invoke({"query": "test"})


def test_rewrite_agent_resolves_follow_up_as_standalone_query(monkeypatch):
    fake_llm = SimpleNamespace(
        invoke=lambda _: SimpleNamespace(content="annual leave policy")
    )
    monkeypatch.setattr(rewrite_agent, "llm", fake_llm)

    result = rewrite_agent.rewrite_agent(
        {
            "query": "What about annual ones?",
            "history": "user: Tell me about leave\nassistant: Which leave type?\n",
            "conversation_summary": "",
            "long_term_memories": [],
        }
    )

    assert result["retrieval_query"] == "annual leave policy"
    assert result["observability"]["rewrite_applied"] is True
