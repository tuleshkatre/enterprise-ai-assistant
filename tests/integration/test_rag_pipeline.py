from tests.conftest import client


def test_complete_rag_pipeline(auth_headers):

    with open("tests/data/sample.pdf", "rb") as f:
        response = client.post(
            "/upload",
            files={"file": ("sample.pdf", f, "application/pdf")},
            headers=auth_headers,
        )

    assert response.status_code == 200

    response = client.post(
        "/chat",
        json={"query": "How many sick leave days are available?"},
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert "answer" in data
    assert "citations" in data
