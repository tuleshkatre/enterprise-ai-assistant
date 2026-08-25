from tests.conftest import client


def test_create_conversation(auth_headers):

    response = client.post("/conversation", headers=auth_headers)

    assert response.status_code == 200

    data = response.json()

    assert "conversation_id" in data


def test_list_conversations(auth_headers):

    client.post("/conversation", headers=auth_headers)

    response = client.get("/conversations", headers=auth_headers)

    assert response.status_code == 200

    assert isinstance(response.json(), list)


def test_rename_conversation(auth_headers):

    create_response = client.post("/conversation", headers=auth_headers)

    conversation_id = create_response.json()["conversation_id"]

    response = client.patch(
        f"/conversation_rename/{conversation_id}",
        json={"title": "Test Chat"},
        headers=auth_headers,
    )

    assert response.status_code == 200

    assert response.json() == {"message": "Conversation renamed"}


def test_delete_conversation(auth_headers):

    create_response = client.post("/conversation", headers=auth_headers)

    conversation_id = create_response.json()["conversation_id"]

    response = client.delete(
        f"/conversation_delete/{conversation_id}", headers=auth_headers
    )

    assert response.status_code == 200

    assert response.json() == {"message": "Conversation deleted"}


def test_conversation_requires_auth():

    response = client.get("/conversations")

    assert response.status_code == 401
