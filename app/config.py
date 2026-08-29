"""Centralized application configuration loaded from environment variables."""

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Application
    app_env: str = "development"
    app_version: str = "1.0.0"
    upload_dir: str = "uploads"
    max_upload_size_bytes: int = 10 * 1024 * 1024
    log_level: str = "INFO"

    # Database
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "enterprise_ai"
    db_user: str = "postgres"
    db_password: str = "postgres"

    # Authentication and security
    secret_key: str = "super-secret-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 55
    refresh_token_expire_days: int = 7

    # MCP
    mcp_issuer_url: str = "http://localhost:8000"
    mcp_resource_server_url: str = "http://localhost:8000/mcp"

    # AI provider selection
    ai_provider: str = "ollama"

    # Local Ollama provider
    ollama_base_url: str = "http://host.docker.internal:11434"
    embedding_model: str = "nomic-embed-text"
    llm_model: str = "qwen3:4b-instruct"

    # Hosted Gemini provider
    google_api_key: str | None = None
    gemini_llm_model: str = "gemini-3.6-flash"
    gemini_embedding_model: str = "gemini-embedding-2"

    # Shared model limits and vector schema
    embedding_dimension: int = Field(default=768, ge=1)
    llm_context_window: int = Field(default=8192, ge=2048)
    llm_max_output_tokens: int = Field(default=512, ge=1)

    # Retrieval and reranking
    retrieval_score_threshold: float = 0.55
    retrieval_top_k: int = 6
    rerank_top_k: int = 2

    # Conversation and summary memory
    conversation_history_limit: int = 30
    conversation_summary_trigger_messages: int = 30
    conversation_summary_keep_recent_messages: int = 20
    conversation_summary_max_chars: int = 6000
    conversation_summary_batch_messages: int = 20
    conversation_summary_input_max_chars: int = 16000

    # Observability
    metrics_enabled: bool = True
    langsmith_project: str = "enterprise-ai-assistant"
    langsmith_capture_content: bool = False
    langsmith_use_system_ca_store: bool = True

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Fail startup when production is configured with unsafe defaults."""
        self.ai_provider = self.ai_provider.casefold().strip()
        if self.ai_provider not in {"ollama", "gemini"}:
            raise ValueError("AI_PROVIDER must be either 'ollama' or 'gemini'")
        if self.ai_provider == "gemini" and not self.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required when AI_PROVIDER=gemini")
        if self.embedding_dimension != 768:
            raise ValueError(
                "EMBEDDING_DIMENSION must remain 768 for the current pgvector schema"
            )
        if self.llm_max_output_tokens >= self.llm_context_window:
            raise ValueError(
                "LLM_MAX_OUTPUT_TOKENS must be smaller than LLM_CONTEXT_WINDOW"
            )
        if self.app_env.casefold() != "production":
            return self

        errors: list[str] = []
        if len(self.secret_key) < 32 or self.secret_key == "super-secret-key":
            errors.append("SECRET_KEY must be a unique random value of 32+ characters")
        if not self.database_url and self.db_password == "postgres":
            errors.append("configure DATABASE_URL or a non-default DB_PASSWORD")
        if not self.mcp_issuer_url.startswith("https://"):
            errors.append("MCP_ISSUER_URL must use HTTPS")
        if not self.mcp_resource_server_url.startswith("https://"):
            errors.append("MCP_RESOURCE_SERVER_URL must use HTTPS")
        if self.langsmith_capture_content:
            errors.append("LANGSMITH_CAPTURE_CONTENT must remain false in production")
        if errors:
            raise ValueError("Unsafe production configuration: " + "; ".join(errors))
        return self

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or URL.create(
            drivername="postgresql+psycopg2",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        ).render_as_string(
            hide_password=False,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

if settings.langsmith_use_system_ca_store:
    import truststore

    truststore.inject_into_ssl()

if not settings.langsmith_capture_content:
    os.environ["LANGSMITH_HIDE_INPUTS"] = "true"
    os.environ["LANGSMITH_HIDE_OUTPUTS"] = "true"

# Compatibility exports for existing modules.
DB_HOST, DB_PORT, DB_NAME = settings.db_host, str(settings.db_port), settings.db_name
DB_USER, DB_PASSWORD = settings.db_user, settings.db_password
OLLAMA_BASE_URL = settings.ollama_base_url
EMBEDDING_MODEL, LLM_MODEL = settings.embedding_model, settings.llm_model
