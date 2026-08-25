import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db.database import SessionLocal
from app.db.models import RefreshToken
from tests.conftest import client


def test_register():

    response = client.post(
        "/register",
        json={
            "username": f"user_{uuid.uuid4().hex[:8]}",
            "email": f"{uuid.uuid4().hex}@test.com",
            "password": "pytest123",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "message" in data


def test_register_rejects_swagger_placeholder_payload():
    response = client.post(
        "/register",
        json={"username": "string", "email": "string", "password": "string"},
    )

    assert response.status_code == 422
    assert "input" not in response.text
    assert "password" in response.text


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("not-an-email", "Secure123"),
        ("valid@example.com", "onlyletters"),
        ("valid@example.com", "12345678"),
        ("valid@example.com", "Short1"),
    ],
)
def test_register_rejects_invalid_credentials(email, password):
    response = client.post(
        "/register",
        json={
            "username": f"valid_{uuid.uuid4().hex[:8]}",
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 422


def test_register_rejects_duplicate_username():
    username = f"duplicate_{uuid.uuid4().hex[:8]}"
    first = client.post(
        "/register",
        json={
            "username": username,
            "email": f"{uuid.uuid4().hex}@test.com",
            "password": "pytest123",
        },
    )
    second = client.post(
        "/register",
        json={
            "username": username,
            "email": f"{uuid.uuid4().hex}@test.com",
            "password": "pytest123",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json()["error"]["message"] == "Username already exists"


def test_login():

    email = f"{uuid.uuid4().hex}@test.com"

    username = f"user_{uuid.uuid4().hex[:8]}"

    password = "pytest123"

    register_response = client.post(
        "/register", json={"username": username, "email": email, "password": password}
    )

    assert register_response.status_code == 200

    response = client.post("/login", json={"email": email, "password": password})

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data

    assert "token_type" in data


def test_invalid_login():

    response = client.post(
        "/login", json={"email": "notfound@test.com", "password": "wrong_password"}
    )

    assert response.status_code == 401


def login_and_get_refresh_token():
    value = uuid.uuid4().hex
    response = client.post(
        "/register",
        json={
            "username": f"refresh_{value[:8]}",
            "email": f"{value}@test.com",
            "password": "pytest123",
        },
    )
    assert response.status_code == 200

    response = client.post(
        "/login",
        json={"email": f"{value}@test.com", "password": "pytest123"},
    )
    assert response.status_code == 200
    assert "refresh_token" in response.json()
    return response.json()["refresh_token"]


def test_refresh_returns_a_new_access_token():
    refresh_token = login_and_get_refresh_token()

    response = client.post("/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["token_type"] == "bearer"


def test_invalid_refresh_token_is_rejected():
    response = client.post("/refresh", json={"refresh_token": "invalid-token"})

    assert response.status_code == 401


def test_expired_refresh_token_is_rejected():
    refresh_token = login_and_get_refresh_token()
    db = SessionLocal()
    try:
        db.query(RefreshToken).filter(
            RefreshToken.refresh_token == refresh_token
        ).update({"expires_at": datetime.now(UTC) - timedelta(seconds=1)})
        db.commit()
    finally:
        db.close()

    response = client.post("/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 401


def test_logout_invalidates_refresh_token():
    refresh_token = login_and_get_refresh_token()

    logout_response = client.post("/logout", json={"refresh_token": refresh_token})
    assert logout_response.status_code == 200

    refresh_response = client.post("/refresh", json={"refresh_token": refresh_token})
    assert refresh_response.status_code == 401
