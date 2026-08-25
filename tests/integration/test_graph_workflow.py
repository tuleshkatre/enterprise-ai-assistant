from tests.conftest import client


def test_graph_chat_workflow(auth_headers):

    conversation_response = client.post("/conversation", headers=auth_headers)

    assert conversation_response.status_code == 200

    conversation_id = conversation_response.json()["conversation_id"]

    response = client.post(
        "/graph-chat",
        json={"conversation_id": conversation_id, "query": "Hello"},
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert "answer" in data

    messages_response = client.get(
        f"/conversation_messages/{conversation_id}/messages", headers=auth_headers
    )

    assert messages_response.status_code == 200

    messages = messages_response.json()

    assert len(messages) >= 2
