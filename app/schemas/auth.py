import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
PLACEHOLDER_VALUES = {"string", "username", "email", "password", "changeme"}


class RegisterRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$",
        examples=["tulesh.katre"],
    )
    email: str = Field(max_length=254, examples=["tulesh@example.com"])
    password: str = Field(
        min_length=8,
        max_length=72,
        examples=["SecurePass2026!"],
    )

    @field_validator("username")
    @classmethod
    def reject_placeholder_username(cls, value: str) -> str:
        if value.casefold() in PLACEHOLDER_VALUES:
            raise ValueError("username cannot be a placeholder value")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.casefold()
        if normalized in PLACEHOLDER_VALUES or not EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("enter a valid email address")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if value.casefold() in PLACEHOLDER_VALUES:
            raise ValueError("password cannot be a placeholder value")
        if len(value.encode("utf-8")) > 72:
            raise ValueError("password must not exceed 72 UTF-8 bytes")
        if not any(character.isalpha() for character in value):
            raise ValueError("password must contain a letter")
        if not any(character.isdigit() for character in value):
            raise ValueError("password must contain a number")
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.casefold()


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str
