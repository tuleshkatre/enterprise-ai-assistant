from app.agents import response_agent as response_module
from app.agents import response_stream_agent as stream_module
from app.agents.conversation_agent import conversation_agent
from app.agents.supervisor_agent import supervisor_agent


class _Response:
    def __init__(self, content: str):
        self.content = content


class _LLM:
    def invoke(self, prompt: str):
        assert "My name is Tulesh" in prompt
        return _Response("Your name is Tulesh.")

    def stream(self, prompt: str):
        assert "My name is Tulesh" in prompt
        yield _Response("Your name ")
        yield _Response("is Tulesh.")


def test_supervisor_routes_resolved_sql_follow_up():
    result = supervisor_agent(
        {
            "query": "What about conversations?",
            "resolved_query": "How many conversations do I have?",
            "context_route": None,
        }
    )
    assert result == {"route": "sql"}


def test_supervisor_honors_conversation_route():
    assert supervisor_agent(
        {
            "query": "What is my name?",
            "resolved_query": "What is my name?",
            "context_route": "conversation",
        }
    ) == {"route": "conversation"}


def test_conversation_agent_bounds_history():
    result = conversation_agent(
        {"history": "user: My name is Tulesh.\n", "query": "What is my name?"}
    )
    assert result == {"conversation_context": "user: My name is Tulesh.\n"}


def test_conversation_agent_returns_exact_saved_fact_without_llm():
    result = conversation_agent(
        {
            "query": "What is my favorite color?",
            "history": "",
            "long_term_memories": [
                {
                    "memory_key": "favorite_color",
                    "memory_value": "eval-f2cc5253",
                    "memory_type": "preference",
                }
            ],
        }
    )

    assert result["conversation_answer"] == ("Your favorite color is eval-f2cc5253.")

    normal = response_module.response_agent(result)
    chunks = []
    streamed = stream_module.response_stream_agent(result, writer=chunks.append)

    assert normal["answer"] == "Your favorite color is eval-f2cc5253."
    assert normal["sources"] == []
    assert chunks == ["Your favorite color is eval-f2cc5253."]
    assert streamed["answer"] == normal["answer"]


def test_normal_conversation_response_preserves_schema(monkeypatch):
    monkeypatch.setattr(response_module, "llm", _LLM())
    result = response_module.response_agent(
        {
            "query": "What is my name?",
            "conversation_context": "user: My name is Tulesh.\n",
        }
    )

    assert result["answer"] == "Your name is Tulesh."
    assert result["sources"] == []


def test_personal_fact_statement_is_handled_without_sources(monkeypatch):
    class _AcknowledgingLLM:
        def invoke(self, prompt: str):
            assert "Current User Question:\nMy name is Tulesh." in prompt
            return _Response("Nice to meet you, Tulesh.")

    monkeypatch.setattr(response_module, "llm", _AcknowledgingLLM())
    result = response_module.response_agent(
        {
            "query": "My name is Tulesh.",
            "conversation_context": "",
        }
    )

    assert result["answer"] == "Nice to meet you, Tulesh."
    assert result["sources"] == []


def test_conversation_response_true_streaming(monkeypatch):
    monkeypatch.setattr(stream_module, "llm", _LLM())
    chunks = []
    result = stream_module.response_stream_agent(
        {
            "query": "What is my name?",
            "conversation_context": "user: My name is Tulesh.\n",
        },
        writer=chunks.append,
    )

    assert chunks == ["Your name ", "is Tulesh."]
    assert result["answer"] == "Your name is Tulesh."
    assert result["sources"] == []
