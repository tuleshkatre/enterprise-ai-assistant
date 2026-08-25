from app.agents import response_agent as response_module
from app.agents import response_stream_agent as stream_module


class _Response:
    def __init__(self, content: str):
        self.content = content


class _LLM:
    def invoke(self, _prompt: str):
        return _Response("There are 12 conversations.")

    def stream(self, _prompt: str):
        yield _Response("There are ")
        yield _Response("12 conversations.")


def test_normal_sql_response_has_no_sources(monkeypatch):
    monkeypatch.setattr(response_module, "llm", _LLM())

    result = response_module.response_agent(
        {
            "query": "How many conversations do I have?",
            "sql_output": [{"conversation_count": 12}],
        }
    )

    assert result["answer"] == "There are 12 conversations."
    assert result["sources"] == []


def test_sql_response_streams_natural_language(monkeypatch):
    monkeypatch.setattr(stream_module, "llm", _LLM())
    chunks = []

    result = stream_module.response_stream_agent(
        {
            "query": "How many conversations do I have?",
            "sql_output": [{"conversation_count": 12}],
        },
        writer=chunks.append,
    )

    assert "".join(chunks) == "There are 12 conversations."
    assert result["answer"] == "There are 12 conversations."
    assert result["sources"] == []


def test_sql_error_is_safe_and_does_not_call_llm(monkeypatch):
    class _UnexpectedLLM:
        def invoke(self, _prompt):
            raise AssertionError("SQL errors must not call the response LLM")

    monkeypatch.setattr(response_module, "llm", _UnexpectedLLM())

    result = response_module.response_agent(
        {
            "query": "Show a missing table",
            "sql_output": [],
            "sql_error": "The database question could not be completed.",
        }
    )

    assert result == {
        "answer": "The database question could not be completed.",
        "sources": [],
        "performance_metrics": {"answer_llm_ms": 0.0},
    }


def test_nonempty_sql_result_cannot_be_narrated_as_no_data(monkeypatch):
    class _WrongLLM:
        def invoke(self, _prompt):
            return _Response("No matching data was found.")

    monkeypatch.setattr(response_module, "llm", _WrongLLM())

    result = response_module.response_agent(
        {
            "query": "List my five most recent conversations",
            "sql_output": [
                {
                    "id": 1,
                    "title": "Who Approves Leave Requests?",
                    "created_at": "2026-08-23T22:14:05",
                }
            ],
        }
    )

    assert result["answer"] != "No matching data was found."
    assert "Who Approves Leave Requests?" in result["answer"]
    assert "id: 1" not in result["answer"]


def test_empty_sql_result_returns_deterministic_no_data(monkeypatch):
    class _UnexpectedLLM:
        def invoke(self, _prompt):
            raise AssertionError("Empty results must not call the LLM")

    monkeypatch.setattr(response_module, "llm", _UnexpectedLLM())

    result = response_module.response_agent(
        {"query": "List conversations", "sql_output": []}
    )

    assert result["answer"] == "No matching data was found."


def test_stream_suppresses_false_no_data_for_nonempty_result(monkeypatch):
    class _WrongStreamingLLM:
        def stream(self, _prompt):
            yield _Response("No matching ")
            yield _Response("data was found.")

    monkeypatch.setattr(stream_module, "llm", _WrongStreamingLLM())
    chunks = []

    result = stream_module.response_stream_agent(
        {
            "query": "List my recent conversations",
            "sql_output": [{"id": 1, "title": "Leave policy"}],
        },
        writer=chunks.append,
    )

    streamed = "".join(chunks)
    assert "No matching data" not in streamed
    assert "Leave policy" in streamed
    assert result["answer"] == streamed
