from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Request,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
)
from app.db.database import (
    get_db,
)
from app.rate_limit import limiter
from app.schemas.responses import (
    GraphChatResponse,
)
from app.services.graph_chat_service import (
    GraphChatService,
)

router = APIRouter(tags=["LangGraph Chat"])


class ChatRequest(BaseModel):
    conversation_id: int
    query: str


@router.post(
    "/graph-chat",
    response_model=GraphChatResponse,
    status_code=200,
    tags=["LangGraph Chat"],
    summary="Run graph-based chat",
    description="Execute the LangGraph workflow in the requested user conversation.",
)
@limiter.limit("2000/minute")
def graph_chat(
    request: Request,
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    service = GraphChatService(db)

    return service.chat(
        conversation_id=payload.conversation_id,
        query=payload.query,
        user_id=int(user_id),
        background_tasks=background_tasks,
    )


@router.post(
    "/graph-chat/stream",
    status_code=200,
    tags=["LangGraph Chat"],
)
def graph_chat_stream(
    request: Request,
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    service = GraphChatService(db)

    return StreamingResponse(
        service.chat_stream(
            conversation_id=payload.conversation_id,
            query=payload.query,
            user_id=int(user_id),
            background_tasks=background_tasks,
        ),
        media_type="text/event-stream",
    )
