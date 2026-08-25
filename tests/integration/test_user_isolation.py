import uuid

from tests.conftest import client


def create_user_and_login():

    unique = uuid.uuid4().hex[:8]

    email = f"{unique}@test.com"

    client.post(
        "/register",
        json={"username": f"user_{unique}", "email": email, "password": "test1234"},
    )

    response = client.post("/login", json={"email": email, "password": "test1234"})

    token = response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


def test_user_document_isolation():

    user1_headers = create_user_and_login()

    user2_headers = create_user_and_login()

    with open("tests/data/sample.pdf", "rb") as f:
        upload_response = client.post(
            "/upload",
            files={"file": ("sample.pdf", f, "application/pdf")},
            headers=user1_headers,
        )

    assert upload_response.status_code == 200

    response = client.post(
        "/chat",
        json={"query": "How many sick leave days are available?"},
        headers=user2_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["answer"] == "I could not find the answer in the provided documents."

    assert data["citations"] == []
