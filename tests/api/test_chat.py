from tests.conftest import client


def test_chat_requires_auth():

    response = client.post("/chat", json={"query": "test"})

    assert response.status_code == 401


def test_chat_no_documents(auth_headers):

    response = client.post(
        "/chat", json={"query": "test question"}, headers=auth_headers
    )

    assert response.status_code == 200

    data = response.json()

    assert "answer" in data
    assert "citations" in data


def test_chat_with_document(auth_headers):

    with open("tests/data/sample.pdf", "rb") as f:
        upload_response = client.post(
            "/upload",
            files={"file": ("sample.pdf", f, "application/pdf")},
            headers=auth_headers,
        )

    assert upload_response.status_code == 200

    response = client.post(
        "/chat",
        json={"query": "How many sick leave days are available?"},
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    print(data)

    assert "answer" in data
    assert "citations" in data

    assert isinstance(data["citations"], list)

    if data["answer"] != "I could not find the answer in the provided documents.":
        assert len(data["citations"]) > 0


def test_chat_stream(auth_headers):

    response = client.post(
        "/chat/stream",
        json={"query": "How many sick leave days are available?"},
        headers=auth_headers,
    )

    assert response.status_code == 200

    assert response.text is not None
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: done\ndata: completed" in response.text


def test_chat_response_structure(auth_headers):

    response = client.post("/chat", json={"query": "test"}, headers=auth_headers)

    assert response.status_code == 200

    data = response.json()

    assert "answer" in data
    assert "citations" in data

    assert isinstance(data["answer"], str)

    assert isinstance(data["citations"], list)
