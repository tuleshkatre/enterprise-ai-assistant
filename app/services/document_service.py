import logging
import os
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.config import settings
from app.rag.indexing import index_document
from app.repositories.document_repository import DocumentRepository
from app.utils.pagination import paginated_response

logger = logging.getLogger(__name__)

UPLOAD_DIR = settings.upload_dir


class DocumentService:
    def __init__(self, db):
        self.db = db
        self.repository = DocumentRepository(db)

    async def upload_document(self, file: UploadFile, user_id: int):

        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")

        content = await file.read()

        if not content:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        if len(content) > settings.max_upload_size_bytes:
            raise HTTPException(status_code=400, detail="File size exceeds 10 MB")

        upload_directory = Path(UPLOAD_DIR)
        upload_directory.mkdir(parents=True, exist_ok=True)
        path = str(upload_directory / f"{user_id}_{uuid4()}_{file.filename}")

        with open(path, "wb") as f:
            f.write(content)

        try:
            result = index_document(db=self.db, file_path=path, user_id=user_id)
        except Exception:
            logger.exception("Document indexing failed for %s", path)

            if os.path.exists(path):
                os.remove(path)

            raise

        return {
            "filename": file.filename,
            "chunks": result["chunks"],
            "message": "File uploaded successfully",
        }

    def delete_document(self, filename: str, user_id: int):

        stored_filename = (
            filename
            if filename.startswith(f"{UPLOAD_DIR}/")
            else f"{UPLOAD_DIR}/{Path(filename).name}"
        )

        try:
            deleted = self.repository.delete_document(stored_filename, user_id)

            if deleted == 0:
                self.repository.rollback()

                raise HTTPException(status_code=404, detail="Document not found")

            self.repository.commit()

        except Exception:
            self.repository.rollback()
            raise

        if os.path.exists(stored_filename):
            try:
                os.remove(stored_filename)
            except OSError:
                logger.exception("Document file cleanup failed for %s", stored_filename)

        return {"message": "Document deleted"}

    def list_documents(self, user_id: int, pagination):

        query = self.repository.get_documents_query(user_id)

        total = query.count()

        if pagination.enabled:
            documents = (
                query.offset((pagination.page - 1) * pagination.size)
                .limit(pagination.size)
                .all()
            )
        else:
            documents = query.all()

        items = [{"filename": doc[0], "chunks": doc[1]} for doc in documents]

        if pagination.enabled:
            return paginated_response(items, total, pagination.page, pagination.size)

        return items
