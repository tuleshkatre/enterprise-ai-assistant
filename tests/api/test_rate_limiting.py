import uuid

from tests.conftest import client


def register_payload() -> dict[str, str]:
    value = uuid.uuid4().hex
    return {
        "username": f"rate_limit_{value[:8]}",
        "email": f"{value}@test.com",
        "password": "pytest123",
    }


def test_register_succeeds_under_client_ip_limit():
    for _ in range(5):
        response = client.post("/register", json=register_payload())
        assert response.status_code == 200


def test_register_returns_429_after_client_ip_limit():
    for _ in range(5):
        response = client.post("/register", json=register_payload())
        assert response.status_code == 200

    response = client.post("/register", json=register_payload())

    assert response.status_code == 429
    assert "error" in response.json()
