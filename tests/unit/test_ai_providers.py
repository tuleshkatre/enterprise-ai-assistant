from types import SimpleNamespace

import app.rag.providers as providers


def _settings(provider: str) -> SimpleNamespace:
    return SimpleNamespace(
        ai_provider=provider,
        google_api_key="test-key",
        gemini_llm_model="gemini-3.6-flash",
        gemini_embedding_model="gemini-embedding-2",
        embedding_dimension=768,
        ollama_base_url="http://localhost:11434",
        embedding_model="nomic-embed-text",
        llm_model="qwen3:4b-instruct",
        llm_max_output_tokens=512,
        llm_context_window=8192,
    )


def test_gemini_embedding_uses_query_task_and_fixed_dimension(monkeypatch):
    captured = {}

    class _Models:
        def embed_content(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1] * 768)])

    monkeypatch.setattr(providers, "settings", _settings("gemini"))
    monkeypatch.setattr(
        providers,
        "_gemini_client",
        lambda: SimpleNamespace(models=_Models()),
    )

    vector = providers.create_embedding(
        "leave policy",
        task_type=providers.RETRIEVAL_QUERY,
    )

    assert len(vector) == 768
    assert captured["model"] == "gemini-embedding-2"
    assert captured["config"].task_type == providers.RETRIEVAL_QUERY
    assert captured["config"].output_dimensionality == 768


def test_ollama_embedding_behavior_is_preserved(monkeypatch):
    captured = {}

    def fake_embeddings(**kwargs):
        captured.update(kwargs)
        return {"embedding": [0.2] * 768}

    monkeypatch.setattr(providers, "settings", _settings("ollama"))
    monkeypatch.setattr(providers.ollama, "embeddings", fake_embeddings)

    vector = providers.create_embedding(
        "leave policy",
        task_type=providers.RETRIEVAL_DOCUMENT,
    )

    assert len(vector) == 768
    assert captured == {"model": "nomic-embed-text", "prompt": "leave policy"}


def test_extract_text_content_supports_strings_and_structured_blocks():
    content = [
        {"type": "text", "text": "Enterprise "},
        {"type": "thinking", "thinking": "hidden"},
        {"type": "text", "text": "answer"},
    ]

    assert providers.extract_text_content("plain text") == "plain text"
    assert providers.extract_text_content(content) == "Enterprise answer"
    assert providers.extract_text_content(None) == ""
