import ollama

from app.config import EMBEDDING_MODEL


def get_embedding(text: str):

    response = ollama.embeddings(model=EMBEDDING_MODEL, prompt=text)

    return response["embedding"]
