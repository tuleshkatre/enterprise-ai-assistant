import pytest
from pydantic import ValidationError

from app.config import Settings


def test_production_rejects_unsafe_defaults():
    with pytest.raises(ValidationError, match="Unsafe production configuration"):
        Settings(
            APP_ENV="production",
            SECRET_KEY="super-secret-key",
            MCP_ISSUER_URL="http://localhost:8000",
            MCP_RESOURCE_SERVER_URL="http://localhost:8000/mcp",
        )


def test_production_accepts_secure_required_settings():
    settings = Settings(
        APP_ENV="production",
        DATABASE_URL="postgresql://app:strong-password@db:5432/enterprise_ai",
        SECRET_KEY="a-unique-production-secret-with-more-than-32-characters",
        MCP_ISSUER_URL="https://api.example.com",
        MCP_RESOURCE_SERVER_URL="https://api.example.com/mcp",
        LANGSMITH_CAPTURE_CONTENT=False,
    )

    assert settings.app_env == "production"


def test_llm_token_limits_are_configurable():
    settings = Settings(
        LLM_CONTEXT_WINDOW=16384,
        LLM_MAX_OUTPUT_TOKENS=1024,
    )

    assert settings.llm_context_window == 16384
    assert settings.llm_max_output_tokens == 1024
