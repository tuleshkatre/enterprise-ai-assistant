import json
import logging
from time import perf_counter

from fastapi import HTTPException

from app.graph.workflow import graph, stream_graph
from app.observability.langsmith import (
    add_trace_metadata,
    trace_agent,
    trace_stream,
)
from app.rag.generator import llm
from app.rag.providers import extract_text_content
from app.repositories.conversation_repository import (
    ConversationRepository,
)
from app.repositories.message_repository import (
    MessageRepository,
)
from app.repositories.user_memory_repository import UserMemoryRepository
from app.services.conversation_memory_service import (
    ConversationMemoryService,
    update_conversation_summary,
)
from app.utils.sse import sse_data, sse_event

logger = logging.getLogger(__name__)

TIMING_FIELDS = (
    "context_resolution_ms",
    "memory_retrieval_ms",
    "summary_retrieval_ms",
    "summary_generation_ms",
    "rewrite_ms",
    "embedding_ms",
    "retrieval_ms",
    "rerank_ms",
    "sql_generation_ms",
    "sql_execution_ms",
    "web_search_ms",
    "answer_llm_ms",
    "total_request_ms",
)


def _complete_performance_metrics(
    metrics: dict[str, float],
) -> dict[str, float]:
    return {field: metrics.get(field, 0.0) for field in TIMING_FIELDS}


def _format_performance_metrics(metrics: dict[str, float]) -> str:
    lines = ["=" * 50, "PERFORMANCE METRICS", "=" * 50]
    lines.extend(f"{field}: {metrics.get(field, 0.0):.2f}" for field in TIMING_FIELDS)
    lines.append("=" * 50)
    return "\n".join(lines)


class GraphChatService:
    def __init__(self, db):

        self.db = db

        self.conversation_repository = ConversationRepository(db)

        self.message_repository = MessageRepository(db)

        self.memory_service = ConversationMemoryService(db)
        self.user_memory_repository = UserMemoryRepository(db)

    @trace_agent("long_term_memory_retrieval", tags=["memory", "long-term"])
    def _load_long_term_memories(
        self, user_id: int
    ) -> tuple[list[dict[str, str]], float]:
        started_at = perf_counter()
        memories = [
            {
                "memory_key": memory.memory_key,
                "memory_value": memory.memory_value,
                "memory_type": memory.memory_type,
            }
            for memory in self.user_memory_repository.list_active(user_id)
        ]
        memory_retrieval_ms = (perf_counter() - started_at) * 1000
        add_trace_metadata(
            user_id=user_id,
            retrieved_memory_count=len(memories),
            retrieved_memory_keys=[memory["memory_key"] for memory in memories],
            memory_retrieval_ms=memory_retrieval_ms,
        )
        return memories, memory_retrieval_ms

    @trace_agent("graph_chat_request", tags=["request", "normal"])
    def chat(
        self,
        conversation_id: int,
        query: str,
        user_id: int,
        background_tasks=None,
    ):

        request_started_at = perf_counter()

        conversation = self.conversation_repository.get_conversation_by_id(
            conversation_id
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if conversation.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        memory_context = self.memory_service.load_context(conversation_id)
        history = memory_context.recent_messages

        if len(history) == 0:
            title = extract_text_content(
                llm.invoke(
                    f"""
                    Generate a short conversation title.

                    Maximum 5 words.

                    User Query:
                    {query}

                    Return only the title.
                    """
                ).content
            ).strip()

            self.conversation_repository.update_conversation_title(conversation, title)

        history_text = ""

        for message in history:
            history_text += f"{message.role}: {message.content}\n"

        current_message = self.message_repository.save_message(
            conversation_id, "user", query
        )

        long_term_memories, memory_retrieval_ms = self._load_long_term_memories(user_id)
        initial_metrics = dict(memory_context.performance_metrics)
        initial_metrics["memory_retrieval_ms"] = memory_retrieval_ms
        result = graph.invoke(
            {
                "query": query,
                "user_id": user_id,
                "conversation_id": conversation_id,
                "history": history_text,
                "conversation_summary": memory_context.summary,
                "long_term_memories": long_term_memories,
                "current_message_id": current_message.id,
                "db": self.db,
                "performance_metrics": initial_metrics,
            }
        )

        answer = result["answer"]

        self.message_repository.save_message(conversation_id, "assistant", answer)
        if background_tasks is not None:
            background_tasks.add_task(
                update_conversation_summary,
                conversation_id,
            )

        # return {
        #     "answer": answer
        # }

        answer = result["answer"]

        sources = result.get("sources", [])

        response = {"answer": answer, "sources": sources}
        total_request_ms = (perf_counter() - request_started_at) * 1000
        performance_metrics = dict(result.get("performance_metrics", {}))
        performance_metrics["total_request_ms"] = total_request_ms
        trace_metrics = _complete_performance_metrics(performance_metrics)
        add_trace_metadata(
            conversation_id=conversation_id,
            user_id=user_id,
            route=result.get("route"),
            source_count=len(sources),
            **trace_metrics,
        )
        logger.info("%s", _format_performance_metrics(performance_metrics))
        return response

    def chat_stream(
        self,
        conversation_id: int,
        query: str,
        user_id: int,
        background_tasks=None,
    ):
        request_started_at = perf_counter()
        conversation = self.conversation_repository.get_conversation_by_id(
            conversation_id
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conversation.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        memory_context = self.memory_service.load_context(conversation_id)
        history = memory_context.recent_messages
        if len(history) == 0:
            title = extract_text_content(
                llm.invoke(
                    f"""
                    Generate a short conversation title.

                    Maximum 5 words.

                    User Query:
                    {query}

                    Return only the title.
                    """
                ).content
            ).strip()
            self.conversation_repository.update_conversation_title(conversation, title)

        history_text = "".join(
            f"{message.role}: {message.content}\n" for message in history
        )
        current_message = self.message_repository.save_message(
            conversation_id, "user", query
        )

        long_term_memories, memory_retrieval_ms = self._load_long_term_memories(user_id)
        initial_metrics = dict(memory_context.performance_metrics)
        initial_metrics["memory_retrieval_ms"] = memory_retrieval_ms
        initial_state = {
            "query": query,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "history": history_text,
            "conversation_summary": memory_context.summary,
            "long_term_memories": long_term_memories,
            "current_message_id": current_message.id,
            "db": self.db,
            "performance_metrics": initial_metrics,
        }
        if background_tasks is not None:
            background_tasks.add_task(
                update_conversation_summary,
                conversation_id,
            )

        @trace_stream("graph_chat_stream_request")
        def event_stream():
            final_result = None
            for mode, data in stream_graph.stream(
                initial_state,
                stream_mode=["custom", "values"],
            ):
                if mode == "custom":
                    yield sse_data(data)
                elif mode == "values" and "answer" in data:
                    final_result = data

            if final_result is None:
                raise RuntimeError("Streaming graph completed without an answer")

            self.message_repository.save_message(
                conversation_id, "assistant", final_result["answer"]
            )

            total_request_ms = (perf_counter() - request_started_at) * 1000
            performance_metrics = dict(final_result.get("performance_metrics", {}))
            performance_metrics["total_request_ms"] = total_request_ms
            trace_metrics = _complete_performance_metrics(performance_metrics)
            add_trace_metadata(
                conversation_id=conversation_id,
                user_id=user_id,
                route=final_result.get("route"),
                source_count=len(final_result.get("sources", [])),
                **trace_metrics,
            )
            logger.info("%s", _format_performance_metrics(performance_metrics))
            yield sse_event("sources", json.dumps(final_result.get("sources", [])))
            yield sse_event("done", "completed")

        return event_stream()
