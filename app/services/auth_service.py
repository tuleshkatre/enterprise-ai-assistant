from fastapi import HTTPException

from app.auth.jwt_handler import create_access_token
from app.auth.refresh_tokens import create_refresh_token, is_expired
from app.auth.security import hash_password, verify_password
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, db):
        self.user_repo = UserRepository(db)
        self.refresh_repo = RefreshTokenRepository(db)

    def register_user(self, payload):

        existing = self.user_repo.get_by_email(payload.email)

        if existing:
            raise HTTPException(status_code=400, detail="Email already exists")

        if self.user_repo.get_by_username(payload.username):
            raise HTTPException(
                status_code=400,
                detail="Username already exists",
            )

        self.user_repo.create_user(
            username=payload.username,
            email=payload.email,
            hashed_password=hash_password(payload.password),
        )

        return {"message": "User registered"}

    def login_user(self, payload):

        user = self.user_repo.get_by_email(payload.email)

        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not verify_password(payload.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        access_token = create_access_token({"sub": str(user.id)})

        refresh_token = create_refresh_token(user.id)

        self.refresh_repo.create(refresh_token)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token.refresh_token,
            "token_type": "bearer",
        }

    def refresh_access_token(self, payload):

        stored_token = self.refresh_repo.get_by_token(payload.refresh_token)

        if not stored_token:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        if is_expired(stored_token):
            self.refresh_repo.delete(stored_token)

            raise HTTPException(status_code=401, detail="Refresh token expired")

        return {
            "access_token": create_access_token({"sub": str(stored_token.user_id)}),
            "token_type": "bearer",
        }

    def logout(self, payload):

        stored_token = self.refresh_repo.get_by_token(payload.refresh_token)

        if not stored_token:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        self.refresh_repo.delete(stored_token)

        return {"message": "Logged out successfully"}
