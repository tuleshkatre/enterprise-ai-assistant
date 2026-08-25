from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.schemas.responses import (
    ConversationCreatedResponse,
    ConversationMessageResponse,
    ConversationResponse,
    MessageResponse,
    PaginatedResponse,
)
from app.services.conversation_service import (
    ConversationService,
)
from app.utils.pagination import (
    PaginationParams,
)

router = APIRouter(tags=["Conversations"])


class RenameConversationRequest(BaseModel):
    title: str


@router.post(
    "/conversation",
    response_model=ConversationCreatedResponse,
    status_code=200,
    summary="Create a conversation",
    description="Create an empty conversation for the authenticated user.",
)
def new_conversation(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    service = ConversationService(db)

    return service.create_conversation(int(user_id))


@router.get(
    "/conversations",
    response_model=(
        list[ConversationResponse] | PaginatedResponse[ConversationResponse]
    ),
    status_code=200,
    summary="List conversations",
    description="List the authenticated user's conversations; pagination is optional.",
)
def list_conversations(
    user_id: str = Depends(get_current_user),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):

    service = ConversationService(db)

    return service.list_conversations(int(user_id), pagination)


@router.get(
    "/conversation_messages/{conversation_id}/messages",
    response_model=(
        list[ConversationMessageResponse]
        | PaginatedResponse[ConversationMessageResponse]
    ),
    status_code=200,
    summary="List conversation messages",
    description="Return messages from a user-owned conversation; pagination is optional.",
)
def conversation_messages(
    conversation_id: int,
    user_id: str = Depends(get_current_user),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):

    service = ConversationService(db)

    return service.get_conversation_messages(
        conversation_id=conversation_id, user_id=int(user_id), pagination=pagination
    )


@router.delete(
    "/conversation_delete/{conversation_id}",
    response_model=MessageResponse,
    status_code=200,
    summary="Delete a conversation",
    description="Delete a user-owned conversation and all associated messages.",
)
def remove_conversation(
    conversation_id: int,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    service = ConversationService(db)

    return service.delete_conversation(
        conversation_id=conversation_id, user_id=int(user_id)
    )


@router.patch(
    "/conversation_rename/{conversation_id}",
    response_model=MessageResponse,
    status_code=200,
    summary="Rename a conversation",
    description="Update the title of a user-owned conversation.",
)
def rename_conversation(
    conversation_id: int,
    request: RenameConversationRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    service = ConversationService(db)

    return service.rename_conversation(
        conversation_id=conversation_id, title=request.title, user_id=int(user_id)
    )
