import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.rate_limit import limiter
from app.schemas.responses import ChatResponse
from app.services.chat_service import ChatService
from app.utils.sse import sse_data, sse_event

router = APIRouter(tags=["RAG Chat"])

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    query: str


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=200,
    summary="Generate a RAG answer",
    description="Retrieve the authenticated user's documents and return an answer with citations.",
)
@limiter.limit("30/minute")
def chat(
    request: Request,
    payload: ChatRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    service = ChatService(db)

    return service.generate_chat_response(query=payload.query, user_id=int(user_id))


@router.post(
    "/chat/stream",
    response_class=StreamingResponse,
    status_code=200,
    summary="Stream a RAG answer",
    description="Stream answer chunks as Server-Sent Events and finish with a done event.",
    responses={200: {"description": "SSE stream (text/event-stream)."}},
)
@limiter.limit("20/minute")
def chat_stream(
    request: Request,
    payload: ChatRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    service = ChatService(db)

    def event_stream():

        try:
            for chunk in service.stream_chat_response(
                query=payload.query, user_id=int(user_id)
            ):
                yield sse_data(chunk)

            yield sse_event("done", "completed")

        except Exception:
            logger.exception("Chat stream failed for user_id=%s", user_id)

            yield sse_event("error", "Unable to complete the chat stream.")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
