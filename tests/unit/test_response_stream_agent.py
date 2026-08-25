from app.agents import response_stream_agent as response_stream_module
from app.agents.prompt_builder import build_document_stream_prompt


class _Chunk:
    def __init__(self, content: str):
        self.content = content


class _StreamingLLM:
    def __init__(self, chunks=None):
        self.prompt = None
        self.chunks = chunks or ["The answer", " is complete."]

    def stream(self, prompt: str):
        self.prompt = prompt
        for chunk in self.chunks:
            yield _Chunk(chunk)


def test_document_response_streams_with_shared_prompt(monkeypatch):
    streaming_llm = _StreamingLLM()
    monkeypatch.setattr(response_stream_module, "llm", streaming_llm)
    documents = [
        {
            "document_id": 7,
            "content": "Policy text",
            "filename": "policy.pdf",
            "page_number": 1,
            "rerank_score": 1.0,
        }
    ]
    chunks = []

    result = response_stream_module.response_stream_agent(
        {"query": "Question", "documents": documents},
        writer=chunks.append,
    )

    assert "".join(chunks) == "The answer is complete."
    assert streaming_llm.prompt == build_document_stream_prompt(documents, "Question")
    assert '"used_doc_ids"' not in streaming_llm.prompt
    assert "Return one JSON object" not in streaming_llm.prompt
    assert result["answer"] == "The answer is complete."


def test_calculator_response_streams_result_without_calling_llm(monkeypatch):
    class _UnexpectedLLM:
        def stream(self, _prompt):
            raise AssertionError("Calculator responses must not call the LLM")

    monkeypatch.setattr(response_stream_module, "llm", _UnexpectedLLM())
    chunks = []

    result = response_stream_module.response_stream_agent(
        {"query": "25 * 4", "calculator_output": "100"},
        writer=chunks.append,
    )

    assert chunks == ["100"]
    assert result["answer"] == "100"
    assert result["sources"] == []
    assert result["performance_metrics"] == {"answer_llm_ms": 0.0}


def test_no_answer_response_streams_fallback_without_calling_llm(monkeypatch):
    class _UnexpectedLLM:
        def stream(self, _prompt):
            raise AssertionError("An empty response must not call the LLM")

    monkeypatch.setattr(response_stream_module, "llm", _UnexpectedLLM())
    chunks = []

    result = response_stream_module.response_stream_agent(
        {"query": "Unknown question"}, writer=chunks.append
    )

    assert chunks == [response_stream_module.NO_ANSWER]
    assert result["answer"] == response_stream_module.NO_ANSWER
    assert result["sources"] == []


def test_multiple_pdfs_stream_plain_text_and_rank_sources(monkeypatch):
    streaming_llm = _StreamingLLM(["Combined", " policy answer."])
    monkeypatch.setattr(response_stream_module, "llm", streaming_llm)
    documents = [
        {
            "document_id": 1,
            "content": "Alpha policy",
            "filename": "alpha.pdf",
            "page_number": 1,
            "rerank_score": 0.7,
        },
        {
            "document_id": 2,
            "content": "Beta policy",
            "filename": "beta.pdf",
            "page_number": 4,
            "rerank_score": 0.9,
        },
        {
            "document_id": 3,
            "content": "Gamma policy",
            "filename": "gamma.pdf",
            "page_number": 2,
            "rerank_score": 0.8,
        },
        {
            "document_id": 4,
            "content": "Lower-ranked duplicate page",
            "filename": "beta.pdf",
            "page_number": 4,
            "rerank_score": 0.1,
        },
    ]
    chunks = []

    result = response_stream_module.response_stream_agent(
        {"query": "Compare policies", "documents": documents},
        writer=chunks.append,
    )

    assert "".join(chunks) == "Combined policy answer."
    assert [source["file"] for source in result["sources"]] == [
        "beta.pdf",
        "gamma.pdf",
        "alpha.pdf",
    ]
    assert "Alpha policy" in streaming_llm.prompt
    assert "Beta policy" in streaming_llm.prompt
    assert "Gamma policy" in streaming_llm.prompt
    assert "used_doc_ids" not in streaming_llm.prompt


def test_large_101_page_document_streams_and_caps_sources(monkeypatch):
    streaming_llm = _StreamingLLM(["Large document answer."])
    monkeypatch.setattr(response_stream_module, "llm", streaming_llm)
    documents = [
        {
            "document_id": page,
            "content": f"Unique content from page {page}",
            "filename": "large.pdf",
            "page_number": page,
            "rerank_score": page / 101,
        }
        for page in range(1, 102)
    ]
    chunks = []

    result = response_stream_module.response_stream_agent(
        {"query": "Summarize the document", "documents": documents},
        writer=chunks.append,
    )

    assert "".join(chunks) == "Large document answer."
    assert "Unique content from page 1" in streaming_llm.prompt
    assert "Unique content from page 101" in streaming_llm.prompt
    assert len(result["sources"]) == response_stream_module.MAX_SOURCES
    assert [source["page"] for source in result["sources"]] == [101, 100, 99]


def test_document_stream_corrects_split_unsupported_negative_quantity(monkeypatch):
    streaming_llm = _StreamingLLM(
        ["Returns are processed within -", "5", " business", " days."]
    )
    monkeypatch.setattr(response_stream_module, "llm", streaming_llm)
    documents = [
        {
            "document_id": 1,
            "content": "Returns are processed within 5 business days.",
            "filename": "logistics.pdf",
            "page_number": 1,
            "rerank_score": 1.0,
        }
    ]
    chunks = []

    result = response_stream_module.response_stream_agent(
        {"query": "How long do returns take?", "documents": documents},
        writer=chunks.append,
    )

    assert "".join(chunks) == "Returns are processed within 5 business days."
    assert result["answer"] == "Returns are processed within 5 business days."
