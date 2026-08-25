from types import SimpleNamespace

from app.agents.context_resolver_agent import build_bounded_memory_context
from app.services import conversation_memory_service as memory_module


class _Response:
    def __init__(self, content: str):
        self.content = content


class _LLM:
    def __init__(self, content: str = "Updated summary"):
        self.content = content
        self.prompts = []

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        return _Response(self.content)


class _MessageRepository:
    def __init__(self, messages):
        self.messages = messages
        self.recent_limit = None

    def get_messages_after(self, _conversation_id, _message_id):
        return self.messages

    def get_recent_messages(self, _conversation_id, limit):
        self.recent_limit = limit
        return self.messages[-limit:]


class _SummaryRepository:
    def __init__(self, record=None):
        self.record = record
        self.upserts = []

    def get_by_conversation_id(self, _conversation_id):
        return self.record

    def upsert(self, conversation_id, summary, summarized_through_message_id):
        self.upserts.append((conversation_id, summary, summarized_through_message_id))
        self.record = SimpleNamespace(
            summary=summary,
            summarized_through_message_id=summarized_through_message_id,
        )
        return self.record


class _DB:
    def __init__(self):
        self.rollback_count = 0

    def rollback(self):
        self.rollback_count += 1


def _service(messages, summary_record=None):
    service = memory_module.ConversationMemoryService.__new__(
        memory_module.ConversationMemoryService
    )
    service.db = _DB()
    service.message_repository = _MessageRepository(messages)
    service.summary_repository = _SummaryRepository(summary_record)
    return service


def _messages(count):
    return [
        SimpleNamespace(id=index, role="user", content=f"message {index}")
        for index in range(1, count + 1)
    ]


def test_prepare_uses_configured_thirty_message_window(monkeypatch):
    monkeypatch.setattr(memory_module.settings, "conversation_history_limit", 30)
    monkeypatch.setattr(
        memory_module.settings, "conversation_summary_trigger_messages", 40
    )
    service = _service(_messages(35))

    context = service.load_context(7)

    assert len(context.recent_messages) == 30
    assert service.message_repository.recent_limit == 30
    assert context.summary == ""


def test_incremental_summary_keeps_recent_messages_verbatim(monkeypatch):
    monkeypatch.setattr(
        memory_module.settings, "conversation_summary_trigger_messages", 40
    )
    monkeypatch.setattr(
        memory_module.settings, "conversation_summary_keep_recent_messages", 30
    )
    llm = _LLM("User is working on a logistics audit.")
    monkeypatch.setattr(memory_module, "llm", llm)
    service = _service(_messages(40))

    metrics = service.update_summary(7)

    assert service.summary_repository.record.summary == (
        "User is working on a logistics audit."
    )
    assert service.summary_repository.upserts == [
        (7, "User is working on a logistics audit.", 10)
    ]
    assert "message 10" in llm.prompts[0]
    assert "message 11" not in llm.prompts[0]
    assert metrics["summary_input_message_count"] == 10.0


def test_summary_failure_preserves_existing_summary(monkeypatch):
    class _FailingLLM:
        def invoke(self, _prompt):
            raise RuntimeError("model unavailable")

    monkeypatch.setattr(memory_module, "llm", _FailingLLM())
    previous = SimpleNamespace(
        summary="Existing safe summary",
        summarized_through_message_id=0,
    )
    service = _service(_messages(40), previous)

    service.update_summary(7)

    assert service.summary_repository.record.summary == "Existing safe summary"
    assert service.db.rollback_count == 1
    assert service.summary_repository.upserts == []


def test_bounded_context_preserves_summary_and_latest_history():
    context = build_bounded_memory_context(
        "User's name is Tulesh.",
        "x" * 5000 + "LATEST",
        max_chars=100,
    )

    assert "User's name is Tulesh." in context
    assert context.endswith("LATEST")
    assert len(context) <= 100


def test_default_summary_overlap_prevents_memory_gap():
    assert memory_module.settings.conversation_history_limit == 30
    assert memory_module.settings.conversation_summary_trigger_messages == 30
    assert memory_module.settings.conversation_summary_keep_recent_messages == 20


def test_large_backlog_is_summarized_in_bounded_batches(monkeypatch):
    monkeypatch.setattr(
        memory_module.settings, "conversation_summary_batch_messages", 20
    )
    monkeypatch.setattr(
        memory_module.settings, "conversation_summary_input_max_chars", 16000
    )
    llm = _LLM("Bounded summary")
    monkeypatch.setattr(memory_module, "llm", llm)
    service = _service(_messages(200))

    metrics = service.update_summary(7)

    assert service.summary_repository.upserts == [(7, "Bounded summary", 20)]
    assert metrics["summary_input_message_count"] == 20.0
    assert len(llm.prompts[0]) < 17000
