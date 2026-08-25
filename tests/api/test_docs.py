from tests.conftest import client


def test_custom_swagger_ui_is_available():
    response = client.get("http://testserver/docs")

    assert response.status_code == 200
    assert "Enterprise AI Assistant · API Docs" in response.text
    assert "defaultModelsExpandDepth" in response.text
    assert "background: #f5f7fb" in response.text
    assert "Internal API Developer Portal" in response.text
    assert 'class="portal-header"' in response.text
    assert '"filter"' not in response.text


def test_openapi_contains_ordered_enterprise_tags():
    response = client.get("http://testserver/openapi.json")

    assert response.status_code == 200
    assert [tag["name"] for tag in response.json()["tags"]] == [
        "Authentication",
        "Documents",
        "RAG Chat",
        "LangGraph Chat",
        "Conversations",
        "System",
    ]
