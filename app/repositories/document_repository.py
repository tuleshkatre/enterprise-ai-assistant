from sqlalchemy import func

from app.db.models import DocumentChunk


class DocumentRepository:
    def __init__(self, db):
        self.db = db

    def get_documents_query(self, user_id: int):

        return (
            self.db.query(DocumentChunk.filename, func.count(DocumentChunk.id))
            .filter(DocumentChunk.user_id == user_id)
            .group_by(DocumentChunk.filename)
        )

    def delete_document(self, filename: str, user_id: int):

        return (
            self.db.query(DocumentChunk)
            .filter(
                DocumentChunk.filename == filename,
                DocumentChunk.user_id == user_id,
            )
            .delete(synchronize_session=False)
        )

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()
