"""Database-backed refresh token lifecycle operations."""

import secrets
from datetime import UTC, datetime, timedelta

from app.config import settings
from app.db.models import RefreshToken


def create_refresh_token(user_id: int) -> RefreshToken:
    return RefreshToken(
        user_id=user_id,
        refresh_token=secrets.token_urlsafe(48),
        expires_at=datetime.now(UTC)
        + timedelta(days=settings.refresh_token_expire_days),
    )


def is_expired(refresh_token: RefreshToken) -> bool:
    expires_at = refresh_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= datetime.now(UTC)
