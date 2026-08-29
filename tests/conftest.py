import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, base_url="http://testserver/api/v1")


class _FakeResponse:
    def __init__(self, content: str):
        self.content = content


class _FakeLLM:
    def invoke(self, prompt):
        prompt_text = str(prompt)
        if "Return exactly one JSON object" in prompt_text:
            return _FakeResponse(
                '{"resolved_query":"test question","context_route":null}'
            )
        if "Return one JSON object and no markdown" in prompt_text:
            return _FakeResponse('{"answer":"Test response","used_doc_ids":[]}')
        return _FakeResponse("Test response")

    def stream(self, _prompt):
        yield _FakeResponse("Test ")
        yield _FakeResponse("response")


@pytest.fixture(autouse=True)
def mock_external_llm_and_embedding_services(monkeypatch):
    """Keep tests deterministic and independent of a running Ollama instance."""
    import app.agents.context_resolver_agent as context_resolver
    import app.agents.response_agent as response_agent
    import app.agents.response_stream_agent as response_stream_agent
    import app.agents.rewrite_agent as rewrite_agent
    import app.agents.sql_agent as sql_agent
    import app.rag.embeddings as embeddings
    import app.rag.generator as generator
    import app.rag.retrieval as retrieval
    import app.services.conversation_memory_service as conversation_memory
    import app.services.graph_chat_service as graph_chat_service
    from app.rate_limit import limiter

    limiter.reset()

    monkeypatch.setattr(
        retrieval,
        "get_embedding",
        lambda *_args, **_kwargs: [0.0] * 768,
    )
    monkeypatch.setattr(generator, "llm", _FakeLLM())
    monkeypatch.setattr(
        embeddings,
        "create_embedding",
        lambda *_args, **_kwargs: [0.0] * 768,
    )
    monkeypatch.setattr(context_resolver, "llm", _FakeLLM())
    monkeypatch.setattr(rewrite_agent, "llm", _FakeLLM())
    monkeypatch.setattr(response_agent, "llm", _FakeLLM())
    monkeypatch.setattr(response_stream_agent, "llm", _FakeLLM())
    monkeypatch.setattr(sql_agent, "llm", _FakeLLM())
    monkeypatch.setattr(conversation_memory, "llm", _FakeLLM())
    monkeypatch.setattr(graph_chat_service, "llm", _FakeLLM())


@pytest.fixture
def test_user():

    email = f"{uuid.uuid4().hex}@test.com"

    username = f"user_{uuid.uuid4().hex[:8]}"

    password = "pytest123"

    response = client.post(
        "/register", json={"username": username, "email": email, "password": password}
    )

    assert response.status_code in [200, 400]

    return {"email": email, "password": password}


@pytest.fixture
def auth_headers(test_user):

    response = client.post(
        "/login", json={"email": test_user["email"], "password": test_user["password"]}
    )

    assert response.status_code == 200

    token = response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}
