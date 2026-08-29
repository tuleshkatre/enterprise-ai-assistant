"""Provider factories for chat generation and embedding services."""

from functools import lru_cache
from typing import Any

import ollama
from google import genai
from google.genai import types
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama

from app.config import settings

RETRIEVAL_DOCUMENT = "RETRIEVAL_DOCUMENT"
RETRIEVAL_QUERY = "RETRIEVAL_QUERY"


def create_chat_model() -> BaseChatModel:
    """Create the configured chat model without changing caller semantics."""
    if settings.ai_provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=settings.gemini_llm_model,
            google_api_key=settings.google_api_key,
            temperature=0,
            max_output_tokens=settings.llm_max_output_tokens,
        )

    return ChatOllama(
        model=settings.llm_model,
        base_url=settings.ollama_base_url,
        temperature=0,
        reasoning=False,
        num_predict=settings.llm_max_output_tokens,
        num_ctx=settings.llm_context_window,
        keep_alive="30m",
    )


@lru_cache(maxsize=1)
def _gemini_client() -> genai.Client:
    return genai.Client(api_key=settings.google_api_key)


def create_embedding(text: str, *, task_type: str) -> list[float]:
    """Embed text in the configured provider's 768-dimensional vector space."""
    if settings.ai_provider == "gemini":
        response = _gemini_client().models.embed_content(
            model=settings.gemini_embedding_model,
            contents=text,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=settings.embedding_dimension,
            ),
        )
        values = response.embeddings[0].values
    else:
        response: dict[str, Any] = ollama.embeddings(
            model=settings.embedding_model,
            prompt=text,
        )
        values = response["embedding"]

    vector = list(values)
    if len(vector) != settings.embedding_dimension:
        raise ValueError(
            "Embedding provider returned "
            f"{len(vector)} dimensions; expected {settings.embedding_dimension}"
        )
    return vector
