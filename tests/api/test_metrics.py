from tests.conftest import client


def test_prometheus_metrics_endpoint_is_available():
    response = client.get("http://testserver/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "http_requests" in response.text


def test_prometheus_metrics_endpoint_is_hidden_from_openapi():
    response = client.get("http://testserver/openapi.json")

    assert response.status_code == 200
    assert "/metrics" not in response.json()["paths"]
