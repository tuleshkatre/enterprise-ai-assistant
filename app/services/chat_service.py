from app.rag.generator import (
    generate_answer,
    generate_answer_stream,
)
from app.rag.retrieval import retrieve


class ChatService:
    def __init__(self, db):
        self.db = db

    def generate_chat_response(self, query: str, user_id: int):

        docs = retrieve(db=self.db, query=query, user_id=user_id)

        answer = generate_answer(query, docs)

        if answer.strip() == ("I could not find the answer in the provided documents."):
            return {"answer": answer, "citations": []}

        citations = []
        seen = set()

        for doc in docs:
            key = (doc["filename"], doc["page_number"])

            if key not in seen:
                seen.add(key)

                citations.append(
                    {
                        "filename": doc["filename"],
                        "page_number": doc["page_number"],
                        "chunk_index": doc["chunk_index"],
                    }
                )

        return {"answer": answer, "citations": citations}

    def stream_chat_response(self, query: str, user_id: int):

        docs = retrieve(db=self.db, query=query, user_id=user_id)

        return generate_answer_stream(query, docs)
