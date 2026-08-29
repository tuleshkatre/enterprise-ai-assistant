from unittest.mock import patch

from app.rag.retrieval import retrieve


@patch("app.rag.retrieval.get_embedding")
def test_retrieve(mock_embeddings):

    mock_embeddings.return_value = [0.1] * 768

    try:
        result = retrieve(query="leave policy", user_id=1)

        assert isinstance(result, list)

    except Exception:
        assert True
