import logging
from dataclasses import dataclass
from time import perf_counter

from sqlalchemy import text

from app.agents.prompt_builder import build_conversation_summary_prompt
from app.config import settings
from app.db.database import SessionLocal
from app.observability.langsmith import add_trace_metadata, trace_agent
from app.rag.generator import llm
from app.repositories.conversation_summary_repository import (
    ConversationSummaryRepository,
)
from app.repositories.message_repository import MessageRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConversationMemoryContext:
    summary: str
    recent_messages: list
    performance_metrics: dict[str, float]


class ConversationMemoryService:
    def __init__(self, db):
        self.db = db
        self.message_repository = MessageRepository(db)
        self.summary_repository = ConversationSummaryRepository(db)

    @trace_agent("summary_memory_retrieval", tags=["memory", "summary"])
    def load_context(self, conversation_id: int) -> ConversationMemoryContext:
        started_at = perf_counter()
        summary_record = self.summary_repository.get_by_conversation_id(conversation_id)
        summary = summary_record.summary if summary_record else ""
        recent_messages = self.message_repository.get_recent_messages(
            conversation_id,
            limit=settings.conversation_history_limit,
        )
        summary_retrieval_ms = (perf_counter() - started_at) * 1000
        add_trace_metadata(
            conversation_id=conversation_id,
            summary_present=bool(summary),
            summary_chars=len(summary),
            recent_message_count=len(recent_messages),
            summary_retrieval_ms=summary_retrieval_ms,
        )
        return ConversationMemoryContext(
            summary=summary,
            recent_messages=recent_messages,
            performance_metrics={
                "summary_generation_ms": 0.0,
                "summary_retrieval_ms": summary_retrieval_ms,
            },
        )

    @trace_agent("summary_memory_generation", tags=["memory", "summary"])
    def update_summary(self, conversation_id: int) -> dict[str, float]:
        summary_record = self.summary_repository.get_by_conversation_id(conversation_id)
        summary = summary_record.summary if summary_record else ""
        summarized_through_id = (
            summary_record.summarized_through_message_id if summary_record else 0
        )
        unsummarized = self.message_repository.get_messages_after(
            conversation_id,
            summarized_through_id,
        )

        summary_generation_ms = 0.0
        summary_input_message_count = 0
        trigger = settings.conversation_summary_trigger_messages
        keep_recent = settings.conversation_summary_keep_recent_messages
        if len(unsummarized) >= trigger and len(unsummarized) > keep_recent:
            eligible_messages = unsummarized[:-keep_recent]
            messages_to_summarize = eligible_messages[
                : settings.conversation_summary_batch_messages
            ]
            started_at = perf_counter()
            try:
                message_lines = []
                input_chars = 0
                for message in messages_to_summarize:
                    line = f"{message.role}: {message.content}\n"
                    remaining = (
                        settings.conversation_summary_input_max_chars - input_chars
                    )
                    if remaining <= 0:
                        break
                    message_lines.append(line[:remaining])
                    input_chars += len(message_lines[-1])
                    summary_input_message_count += 1
                    if len(line) > remaining:
                        break

                messages_to_summarize = messages_to_summarize[
                    :summary_input_message_count
                ]
                message_text = "".join(message_lines)
                generated = llm.invoke(
                    build_conversation_summary_prompt(
                        summary,
                        message_text,
                        settings.conversation_summary_max_chars,
                    )
                ).content.strip()
                if not generated:
                    raise ValueError("Conversation summary was empty")
                if len(generated) > settings.conversation_summary_max_chars:
                    raise ValueError("Conversation summary exceeded configured limit")

                summary_record = self.summary_repository.upsert(
                    conversation_id,
                    generated,
                    messages_to_summarize[-1].id,
                )
                summary = summary_record.summary
            except Exception:
                self.db.rollback()
                logger.exception(
                    "conversation_summary update_failed=true conversation_id=%d",
                    conversation_id,
                )
            summary_generation_ms = (perf_counter() - started_at) * 1000

        logger.info(
            "memory_timing summary_generation_ms=%.2f "
            "summary_input_message_count=%d summary_present=%s",
            summary_generation_ms,
            summary_input_message_count,
            bool(summary),
        )
        add_trace_metadata(
            conversation_id=conversation_id,
            summary_generation_ms=summary_generation_ms,
            summary_input_message_count=summary_input_message_count,
            summary_present=bool(summary),
            summary_chars=len(summary),
        )
        return {
            "summary_generation_ms": summary_generation_ms,
            "summary_input_message_count": float(summary_input_message_count),
        }


@trace_agent("summary_memory_background_update", tags=["memory", "background"])
def update_conversation_summary(conversation_id: int) -> None:
    """Run a best-effort summary update outside the response-critical path."""
    db = SessionLocal()
    lock_key = 847000000 + conversation_id
    locked = False
    try:
        locked = bool(
            db.execute(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": lock_key},
            ).scalar()
        )
        if not locked:
            logger.info(
                "conversation_summary update_skipped=concurrent conversation_id=%d",
                conversation_id,
            )
            return
        ConversationMemoryService(db).update_summary(conversation_id)
    except Exception:
        db.rollback()
        logger.exception(
            "conversation_summary background_update_failed=true conversation_id=%d",
            conversation_id,
        )
    finally:
        if locked:
            try:
                db.execute(
                    text("SELECT pg_advisory_unlock(:lock_key)"),
                    {"lock_key": lock_key},
                )
            except Exception:
                logger.exception(
                    "conversation_summary unlock_failed=true conversation_id=%d",
                    conversation_id,
                )
        db.close()
