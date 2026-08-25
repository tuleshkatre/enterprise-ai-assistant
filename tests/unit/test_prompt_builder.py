from app.agents.prompt_builder import (
    build_document_prompt,
    build_document_retry_prompt,
    build_web_prompt,
)


def test_document_prompt_is_unchanged():
    documents = [{"document_id": 7, "content": "Policy text"}]

    assert (
        build_document_prompt(documents, "What is the policy?")
        == """
You are a strict enterprise RAG assistant. Use only the supplied context.

Return one JSON object and no markdown:
{"answer": "your answer", "used_doc_ids": [123]}

Rules:
- Answer with a complete, standalone, professional sentence or short paragraph.
- Never return a single word, a noun phrase, a label, or a sentence fragment.
- Do not mention chunk IDs, filenames, or page numbers.
- `used_doc_ids` must contain only CHUNK_ID values whose content supports the answer.
- Do not cite a chunk merely because it is relevant; cite it only if used.
- If the answer is not explicitly supported, return
  {"answer": "I could not find the answer in the provided documents.", "used_doc_ids": []}.

Context:
[CHUNK_ID: 7]
Policy text

Question:
What is the policy?
"""
    )


def test_document_retry_prompt_is_unchanged():
    documents = [{"document_id": 7, "content": "Policy text"}]

    assert (
        build_document_retry_prompt(documents, "Question")
        == """
Return one JSON object and no markdown:
{"answer": "your answer", "used_doc_ids": [123]}

Your previous answer was incomplete. Create a complete, standalone, professional
answer using only the context below. The answer must be at least one complete
sentence; do not return a single word or phrase. `used_doc_ids` must contain
only the CHUNK_ID values that support the answer.

Context:
[CHUNK_ID: 7]
Policy text

Question:
Question
"""
    )


def test_web_prompt_is_unchanged():
    results = [{"title": "Title", "snippet": "Snippet", "url": "https://example.test"}]

    assert (
        build_web_prompt(results, "Question")
        == """
You are a web research assistant. Answer using only the supplied web search results.
Return only a concise, complete answer. Do not mention internal IDs or hidden context.

Web search results:
Title: Title
Snippet: Snippet
URL: https://example.test

Question:
Question
"""
    )
