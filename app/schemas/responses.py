"""Pydantic response contracts for public API endpoints."""

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class MessageResponse(BaseModel):
    message: str


class RegisterResponse(MessageResponse):
    pass


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str


class CitationResponse(BaseModel):
    filename: str
    page_number: int
    chunk_index: int


class ChatResponse(BaseModel):
    answer: str
    citations: list[CitationResponse] = Field(default_factory=list)


class UploadResponse(MessageResponse):
    filename: str
    chunks: int


class DocumentResponse(BaseModel):
    filename: str
    chunks: int


class ConversationResponse(BaseModel):
    id: int
    title: str | None
    created_at: datetime


class ConversationCreatedResponse(BaseModel):
    conversation_id: int


class ConversationMessageResponse(BaseModel):
    role: str
    content: str
    created_at: datetime


class SourceItem(BaseModel):
    file: str
    page: int
    snippet: str


class WebSource(BaseModel):
    title: str
    snippet: str
    url: str


class GraphChatResponse(BaseModel):
    answer: str

    sources: list[SourceItem | WebSource] = Field(default_factory=list)


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    page: int
    size: int
    total: int
    total_pages: int


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str
