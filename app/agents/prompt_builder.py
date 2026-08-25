import json
from typing import Any

NO_ANSWER = "I could not find the answer in the provided documents."
DOCUMENT_ANSWER_RULES = """- Answer with a complete, standalone, professional sentence or short paragraph.
- Never return a single word, a noun phrase, a label, or a sentence fragment.
- Do not mention chunk IDs, filenames, or page numbers."""


def build_document_context(documents: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        f"[CHUNK_ID: {document['document_id']}]\n{document['content']}"
        for document in documents
    )


def build_document_prompt(documents: list[dict[str, Any]], query: str) -> str:
    context = build_document_context(documents)
    return f"""
You are a strict enterprise RAG assistant. Use only the supplied context.

Return one JSON object and no markdown:
{{"answer": "your answer", "used_doc_ids": [123]}}

Rules:
{DOCUMENT_ANSWER_RULES}
- `used_doc_ids` must contain only CHUNK_ID values whose content supports the answer.
- Do not cite a chunk merely because it is relevant; cite it only if used.
- If the answer is not explicitly supported, return
  {{"answer": "{NO_ANSWER}", "used_doc_ids": []}}.

Context:
{context}

Question:
{query}
"""


def build_document_retry_prompt(documents: list[dict[str, Any]], query: str) -> str:
    context = build_document_context(documents)
    return f"""
Return one JSON object and no markdown:
{{"answer": "your answer", "used_doc_ids": [123]}}

Your previous answer was incomplete. Create a complete, standalone, professional
answer using only the context below. The answer must be at least one complete
sentence; do not return a single word or phrase. `used_doc_ids` must contain
only the CHUNK_ID values that support the answer.

Context:
{context}

Question:
{query}
"""


def build_document_stream_prompt(documents: list[dict[str, Any]], query: str) -> str:
    context = build_document_context(documents)
    return f"""
You are a strict enterprise RAG assistant. Use only the supplied context.

Rules:
{DOCUMENT_ANSWER_RULES}
- If the answer is not explicitly supported, return exactly:
  {NO_ANSWER}

Context:
{context}

Question:
{query}
"""


def build_web_prompt(web_results: list[dict[str, Any]], query: str) -> str:
    context = "\n\n".join(
        f"Title: {result.get('title', '')}\n"
        f"Snippet: {result.get('snippet', '')}\n"
        f"URL: {result.get('url', '')}"
        for result in web_results
    )
    return f"""
You are a web research assistant. Answer using only the supplied web search results.
Return only a concise, complete answer. Do not mention internal IDs or hidden context.

Web search results:
{context}

Question:
{query}
"""


def build_web_stream_prompt(web_results: list[dict[str, Any]], query: str) -> str:
    return build_web_prompt(web_results, query)


def build_sql_prompt(sql_output: list[dict[str, Any]], query: str) -> str:
    results = json.dumps(sql_output, ensure_ascii=False)
    return f"""
You are an enterprise data assistant. Answer using only the supplied database results.
Return only a concise, complete, professional answer.
Do not mention SQL, queries, schemas, tables, internal IDs, or hidden context.
If the result set is empty, state that no matching data was found.

Database results:
{results}

Question:
{query}
"""


def build_sql_stream_prompt(sql_output: list[dict[str, Any]], query: str) -> str:
    return build_sql_prompt(sql_output, query)


def build_conversation_prompt(history: str, query: str) -> str:
    return f"""
You are a conversation assistant. Respond using only the current user message and
facts explicitly stated in the recent conversation history.

Rules:
- Return only a concise, complete, natural-language answer.
- If the current message explicitly states a personal fact, acknowledge it briefly.
- Do not mention hidden context, routing, prompts, or internal memory.
- Do not claim to remember information outside this conversation.
- Do not infer a personal fact that is not explicitly present in the current message
  or history.
- If the answer is not explicitly present, return exactly:
  I do not have that information in this conversation.

Recent Conversation History:
{history}

Current User Question:
{query}
"""


def build_conversation_stream_prompt(history: str, query: str) -> str:
    return build_conversation_prompt(history, query)


def build_conversation_summary_prompt(
    existing_summary: str,
    messages: str,
    max_chars: int,
) -> str:
    return f"""
Update an enterprise conversation summary using the existing summary and newly
expired messages.

Rules:
- Preserve explicit user facts, goals, constraints, decisions, named entities,
  important quantities, unresolved questions, and active tasks.
- Preserve who said each important fact.
- Never add facts that are absent from the inputs.
- Do not include hidden prompts, internal routes, generated SQL, credentials,
  authentication tokens, or chain-of-thought.
- Return only the updated summary as plain text.
- Keep the summary under {max_chars} characters.

Existing Summary:
{existing_summary or "No existing summary."}

New Messages:
{messages}
"""
