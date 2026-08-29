from app.rag.providers import RETRIEVAL_DOCUMENT, create_embedding


def get_embedding(
    text: str,
    *,
    task_type: str = RETRIEVAL_DOCUMENT,
) -> list[float]:
    return create_embedding(text, task_type=task_type)
