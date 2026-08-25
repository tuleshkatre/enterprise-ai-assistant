from app.db.models import Message


class MessageRepository:
    def __init__(self, db):
        self.db = db

    def save_message(self, conversation_id: int, role: str, content: str):

        message = Message(conversation_id=conversation_id, role=role, content=content)

        self.db.add(message)

        self.db.commit()

        self.db.refresh(message)

        return message

    def get_messages_by_conversation_id(self, conversation_id: int):
        return (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.id.asc())
            .all()
        )

    def get_recent_messages(self, conversation_id: int, limit: int = 10):

        messages = (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(limit)
            .all()
        )

        return list(reversed(messages))

    def get_messages_after(
        self,
        conversation_id: int,
        message_id: int,
    ):
        return (
            self.db.query(Message)
            .filter(
                Message.conversation_id == conversation_id,
                Message.id > message_id,
            )
            .order_by(Message.id.asc())
            .all()
        )

    def get_history(self, conversation_id: int):
        return (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .all()
        )

    def delete_messages_by_conversation_id(self, conversation_id: int):

        (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .delete(synchronize_session=False)
        )

        self.db.commit()
