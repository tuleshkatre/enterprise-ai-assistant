from tests.conftest import client


def test_health():

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"
    assert data["version"] == "1.0.0"


def test_security_headers():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["version"] == "1.0.0"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
