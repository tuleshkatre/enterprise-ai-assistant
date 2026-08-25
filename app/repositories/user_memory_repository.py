from datetime import UTC, datetime

from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import insert

from app.db.models import UserMemory


class UserMemoryRepository:
    def __init__(self, db):
        self.db = db

    def list_active(self, user_id: int):
        now = datetime.now(UTC)
        return (
            self.db.query(UserMemory)
            .filter(
                UserMemory.user_id == user_id,
                UserMemory.status == "active",
                or_(UserMemory.expires_at.is_(None), UserMemory.expires_at > now),
            )
            .order_by(UserMemory.memory_key.asc())
            .all()
        )

    def upsert(
        self,
        user_id: int,
        memory_key: str,
        memory_value: str,
        memory_type: str,
        source_conversation_id: int | None,
        source_message_id: int | None,
    ):
        now = datetime.now(UTC)
        statement = insert(UserMemory).values(
            user_id=user_id,
            memory_key=memory_key,
            memory_value=memory_value,
            memory_type=memory_type,
            source_conversation_id=source_conversation_id,
            source_message_id=source_message_id,
            status="active",
            expires_at=None,
            created_at=now,
            updated_at=now,
        )
        statement = statement.on_conflict_do_update(
            index_elements=["user_id", "memory_key"],
            set_={
                "memory_value": memory_value,
                "memory_type": memory_type,
                "source_conversation_id": source_conversation_id,
                "source_message_id": source_message_id,
                "status": "active",
                "expires_at": None,
                "updated_at": now,
            },
        )
        self.db.execute(statement)
        self.db.commit()
        return (
            self.db.query(UserMemory)
            .filter(
                UserMemory.user_id == user_id,
                UserMemory.memory_key == memory_key,
            )
            .one()
        )

    def forget(self, user_id: int, memory_key: str) -> bool:
        memory = (
            self.db.query(UserMemory)
            .filter(
                UserMemory.user_id == user_id,
                UserMemory.memory_key == memory_key,
                UserMemory.status == "active",
            )
            .first()
        )
        if memory is None:
            return False
        memory.memory_value = ""
        memory.status = "deleted"
        self.db.commit()
        return True

    def forget_all(self, user_id: int) -> int:
        memories = (
            self.db.query(UserMemory)
            .filter(
                UserMemory.user_id == user_id,
                UserMemory.status == "active",
            )
            .all()
        )
        for memory in memories:
            memory.memory_value = ""
            memory.status = "deleted"
        self.db.commit()
        return len(memories)
