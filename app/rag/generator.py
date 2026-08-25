from langchain_ollama import ChatOllama

from app.config import settings
from app.observability.langsmith import trace_agent

llm = ChatOllama(
    model=settings.llm_model,
    temperature=0,
    reasoning=False,
    num_predict=settings.llm_max_output_tokens,
    num_ctx=settings.llm_context_window,
    keep_alive="30m",
)


@trace_agent("generate_answer", tags=["legacy", "generation"])
def generate_answer(query: str, docs: list):

    context = "\n\n".join([doc["content"] for doc in docs])

    # No retrieved context
    if not context.strip():
        return "I could not find the answer in the provided documents."

    prompt = f"""
    You are a strict enterprise RAG assistant.

    Use ONLY the provided context.

    Rules:
    1. Answer only from the context.
    2. Do not use outside knowledge.
    3. Do not make assumptions.
    4. Do not infer missing information.
    5. For broad questions, provide a concise summary from the context.
    6. If the answer is not explicitly present in the context, reply exactly:

    I could not find the answer in the provided documents.

    Context:
    {context}

    Question:
    {query}

    Answer:
    """

    response = llm.invoke(prompt)

    answer = response.content.strip()

    if "could not find" in answer.lower() or "not found" in answer.lower():
        return "I could not find the answer in the provided documents."

    return answer


def generate_answer_stream(query: str, docs: list):

    context = "\n\n".join([doc["content"] for doc in docs])

    if not context.strip():
        yield ("I could not find the answer in the provided documents.")

        return

    prompt = f"""
    You are a strict enterprise RAG assistant.

    Use ONLY the provided context.

    Rules:
    1. Answer only from the context.
    2. Do not use outside knowledge.
    3. Do not make assumptions.
    4. Do not infer missing information.

    Context:
    {context}

    Question:
    {query}

    Answer:
    """

    for chunk in llm.stream(prompt):
        if chunk.content:
            print(chunk.content, end="", flush=True)
            yield chunk.content
