from app.db.models import DocumentChunk
from app.rag.embeddings import get_embedding
from app.rag.loader import load_pdf
from app.rag.splitter import split_documents


def index_document(db, file_path: str, user_id: int):

    docs = load_pdf(file_path)

    chunks = split_documents(docs)

    try:
        db.query(DocumentChunk).filter(
            DocumentChunk.filename == file_path,
            DocumentChunk.user_id == user_id,
        ).delete(synchronize_session=False)

        for idx, chunk in enumerate(chunks):
            vector = get_embedding(chunk.page_content)

            row = DocumentChunk(
                user_id=user_id,
                filename=file_path,
                page_number=chunk.metadata.get("page", 0) + 1,
                chunk_index=idx,
                chunk_text=chunk.page_content,
                embedding=vector,
            )

            db.add(row)

        db.commit()

    except Exception:
        db.rollback()

        raise

    return {"filename": file_path, "chunks": len(chunks)}
