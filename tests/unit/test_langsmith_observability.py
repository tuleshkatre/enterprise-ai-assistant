from app.config import settings
from app.observability import langsmith as observability


class _Run:
    def __init__(self):
        self.metadata = {}

    def add_metadata(self, metadata):
        self.metadata.update(metadata)


def test_trace_payload_redacts_secrets_and_database_handles(monkeypatch):
    monkeypatch.setattr(settings, "langsmith_capture_content", False)
    payload = observability.sanitize_trace_payload(
        {
            "query": "Remember that my password is secret123",
            "db": object(),
            "history": "private conversation",
            "url": "https://example.com/path?token=secret",
        }
    )

    assert "secret123" not in payload["query"]
    assert payload["db"] == "[REDACTED]"
    assert payload["history"] == {"captured": False, "size": 20}
    assert payload["url"] == "https://example.com/path"


def test_trace_content_can_be_enabled_for_controlled_debugging(monkeypatch):
    monkeypatch.setattr(settings, "langsmith_capture_content", True)

    payload = observability.sanitize_trace_payload({"content": "policy text"})

    assert payload["content"] == "policy text"


def test_trace_metadata_is_attached_to_current_span(monkeypatch):
    run = _Run()
    monkeypatch.setattr(observability, "get_current_run_tree", lambda: run)

    observability.add_trace_metadata(route="document", document_count=2)

    assert run.metadata == {"route": "document", "document_count": 2}


def test_stream_reducer_records_count_without_token_payloads():
    assert observability._reduce_stream(["one", "two"]) == {"stream_event_count": 2}
