from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.rate_limit import limiter
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
)
from app.schemas.responses import (
    LoginResponse,
    MessageResponse,
    RefreshResponse,
    RegisterResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(tags=["Authentication"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=200,
    summary="Register a user",
    description=(
        "Create a new enterprise assistant user account. Usernames must start "
        "with a letter; passwords require at least eight characters, one letter, "
        "and one number."
    ),
)
@limiter.limit("5/minute")
def register(
    request: Request,
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    service = AuthService(db)

    return service.register_user(payload)


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=200,
    summary="Authenticate a user",
    description="Return short-lived access and database-backed refresh tokens.",
)
@limiter.limit("10/minute")
def login(
    request: Request,
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    service = AuthService(db)

    return service.login_user(payload)


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    status_code=200,
    summary="Refresh an access token",
    description="Exchange a valid, unexpired refresh token for a new access token.",
)
def refresh(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    service = AuthService(db)

    return service.refresh_access_token(payload)


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=200,
    summary="Log out a session",
    description="Invalidate the supplied refresh token.",
)
def logout(
    payload: LogoutRequest,
    db: Session = Depends(get_db),
):
    service = AuthService(db)

    return service.logout(payload)
