from app.db.models import ConversationSummary


class ConversationSummaryRepository:
    def __init__(self, db):
        self.db = db

    def get_by_conversation_id(self, conversation_id: int):
        return (
            self.db.query(ConversationSummary)
            .filter(ConversationSummary.conversation_id == conversation_id)
            .first()
        )

    def upsert(
        self,
        conversation_id: int,
        summary: str,
        summarized_through_message_id: int,
    ):
        record = self.get_by_conversation_id(conversation_id)
        if record is None:
            record = ConversationSummary(
                conversation_id=conversation_id,
                summary=summary,
                summarized_through_message_id=summarized_through_message_id,
                version=1,
            )
            self.db.add(record)
        else:
            record.summary = summary
            record.summarized_through_message_id = summarized_through_message_id
            record.version += 1

        self.db.commit()
        self.db.refresh(record)
        return record

    def delete_by_conversation_id(self, conversation_id: int) -> None:
        (
            self.db.query(ConversationSummary)
            .filter(ConversationSummary.conversation_id == conversation_id)
            .delete(synchronize_session=False)
        )
        self.db.commit()
