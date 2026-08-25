from app.rag import reranker as reranker_module
from app.rag.reranker import _rerank_text


def test_reranker_text_includes_filename_and_content():
    value = _rerank_text(
        {
            "filename": "uploads/1_uuid_saas_policy.pdf",
            "content": "Production deployments require validation.",
        }
    )

    assert value == (
        "Source: 1_uuid_saas_policy.pdf\nProduction deployments require validation."
    )


def test_explicit_source_match_has_priority_after_reranking(monkeypatch):
    class _Model:
        def predict(self, _pairs):
            return [10.0, 1.0]

    monkeypatch.setattr(reranker_module, "reranker", _Model())
    documents = [
        {"filename": "enterprise.pdf", "content": "duplicate"},
        {
            "filename": "saas_policy.pdf",
            "content": "duplicate",
            "source_match": True,
        },
    ]

    result = reranker_module.rerank("According to SaaS policy", documents)

    assert result[0]["filename"] == "saas_policy.pdf"
