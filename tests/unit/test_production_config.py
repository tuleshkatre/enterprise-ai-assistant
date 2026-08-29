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


def test_gemini_provider_requires_api_key():
    with pytest.raises(ValidationError, match="GOOGLE_API_KEY"):
        Settings(AI_PROVIDER="gemini", GOOGLE_API_KEY="")


def test_gemini_provider_configuration():
    settings = Settings(
        AI_PROVIDER="gemini",
        GOOGLE_API_KEY="test-key",
        GEMINI_LLM_MODEL="gemini-3.6-flash",
        GEMINI_EMBEDDING_MODEL="gemini-embedding-2",
    )

    assert settings.ai_provider == "gemini"
    assert settings.embedding_dimension == 768
