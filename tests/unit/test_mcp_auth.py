import asyncio
from types import SimpleNamespace

import pytest

from app.auth.jwt_handler import create_access_token
from app.mcp.auth import JWTTokenVerifier, authenticated_user_id
from app.mcp.client import mcp_access_token, resolve_access_token


def test_mcp_jwt_verifier_returns_authenticated_subject():
    token = create_access_token({"sub": "123"})

    access_token = asyncio.run(JWTTokenVerifier().verify_token(token))

    assert access_token is not None
    assert access_token.subject == "123"
    assert "mcp:read" in access_token.scopes


def test_mcp_jwt_verifier_rejects_invalid_token():
    assert asyncio.run(JWTTokenVerifier().verify_token("invalid")) is None


def test_authenticated_user_id_comes_from_request_context():
    request = SimpleNamespace(
        user=SimpleNamespace(access_token=SimpleNamespace(subject="42"))
    )
    context = SimpleNamespace(request_context=SimpleNamespace(request=request))

    assert authenticated_user_id(context) == 42


def test_authenticated_user_id_rejects_missing_principal():
    context = SimpleNamespace(
        request_context=SimpleNamespace(request=SimpleNamespace())
    )

    with pytest.raises(PermissionError):
        authenticated_user_id(context)


def test_mcp_client_requires_an_access_token(monkeypatch):
    monkeypatch.delenv("MCP_ACCESS_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="MCP_ACCESS_TOKEN"):
        mcp_access_token()


def test_mcp_client_prefers_explicit_access_token(monkeypatch):
    monkeypatch.setenv("MCP_ACCESS_TOKEN", "existing-token")

    assert asyncio.run(resolve_access_token()) == "existing-token"
