"""JWT authentication helpers for the remote MCP transport."""

from jose import JWTError, jwt

from app.config import settings
from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver.context import Context


class JWTTokenVerifier:
    """Adapt this application's JWT access tokens to the MCP token verifier API."""

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            subject = payload.get("sub")
            if not subject or not str(subject).isdigit():
                return None
            return AccessToken(
                token=token,
                client_id=f"user:{subject}",
                subject=str(subject),
                scopes=["mcp:read", "mcp:tools"],
                expires_at=payload.get("exp"),
                claims=payload,
            )
        except JWTError:
            return None


def authenticated_user_id(context: Context) -> int:
    """Return the authenticated MCP caller's user ID from HTTP request state."""
    request_context = getattr(context, "request_context", None)
    request = getattr(request_context, "request", None)
    access_token = getattr(getattr(request, "user", None), "access_token", None)
    if access_token is None or not access_token.subject:
        raise PermissionError("MCP authentication is required")
    return int(access_token.subject)
