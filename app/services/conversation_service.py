from fastapi import HTTPException

from app.repositories.conversation_repository import (
    ConversationRepository,
)
from app.repositories.message_repository import (
    MessageRepository,
)
from app.utils.pagination import (
    paginated_response,
)


class ConversationService:
    def __init__(self, db):

        self.conversation_repository = ConversationRepository(db)

        self.message_repository = MessageRepository(db)

    def create_conversation(self, user_id: int):

        conversation_id = self.conversation_repository.create_conversation(user_id)

        return {"conversation_id": conversation_id}

    def list_conversations(self, user_id: int, pagination):

        conversations = self.conversation_repository.get_conversations_by_user_id(
            user_id
        )

        items = [
            {
                "id": conversation.id,
                "title": conversation.title,
                "created_at": conversation.created_at,
            }
            for conversation in conversations
        ]

        if pagination.enabled:
            start = (pagination.page - 1) * pagination.size

            return paginated_response(
                items[start : start + pagination.size],
                len(items),
                pagination.page,
                pagination.size,
            )

        return items

    def get_conversation_messages(self, conversation_id: int, user_id: int, pagination):

        conversation = self.conversation_repository.get_conversation_by_id(
            conversation_id
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if conversation.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        messages = self.message_repository.get_messages_by_conversation_id(
            conversation_id
        )

        items = [
            {
                "role": message.role,
                "content": message.content,
                "created_at": message.created_at,
            }
            for message in messages
        ]

        if pagination.enabled:
            start = (pagination.page - 1) * pagination.size

            return paginated_response(
                items[start : start + pagination.size],
                len(items),
                pagination.page,
                pagination.size,
            )

        return items

    def delete_conversation(self, conversation_id: int, user_id: int):

        conversation = self.conversation_repository.get_conversation_by_id(
            conversation_id
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if conversation.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        self.message_repository.delete_messages_by_conversation_id(conversation_id)

        self.conversation_repository.delete_conversation_by_id(conversation_id)

        return {"message": "Conversation deleted"}

    def rename_conversation(self, conversation_id: int, title: str, user_id: int):

        conversation = self.conversation_repository.get_conversation_by_id(
            conversation_id
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if conversation.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        self.conversation_repository.update_conversation_title(conversation, title)

        return {"message": "Conversation renamed"}
