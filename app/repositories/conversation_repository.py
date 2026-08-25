from app.db.models import Conversation


class ConversationRepository:
    def __init__(self, db):
        self.db = db

    def create_conversation(self, user_id: int):
        conversation = Conversation(title="New Chat", user_id=user_id)

        self.db.add(conversation)

        self.db.commit()

        self.db.refresh(conversation)

        return conversation.id

    def get_conversation_by_id(self, conversation_id: int):
        return (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )

    def get_conversations_by_user_id(self, user_id: int):
        return (
            self.db.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(Conversation.id.desc())
            .all()
        )

    def update_conversation_title(self, conversation: Conversation, title: str):
        conversation.title = title

        self.db.commit()

        self.db.refresh(conversation)

        return conversation

    def delete_conversation_by_id(self, conversation_id: int):
        (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .delete(synchronize_session=False)
        )

        self.db.commit()

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()
