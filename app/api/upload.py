import logging

from fastapi import APIRouter, Depends, Request, UploadFile
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.rate_limit import limiter
from app.schemas.responses import (
    DocumentResponse,
    MessageResponse,
    PaginatedResponse,
    UploadResponse,
)
from app.services.document_service import DocumentService
from app.utils.pagination import (
    PaginationParams,
)

router = APIRouter(tags=["Documents"])

logger = logging.getLogger(__name__)


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=200,
    summary="Upload and index a PDF",
    description="Validate, store, and index a PDF for the authenticated user.",
)
@limiter.limit("10/minute")
async def upload_pdf(
    request: Request,
    file: UploadFile,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = DocumentService(db)

    return await service.upload_document(
        file=file,
        user_id=int(user_id),
    )


@router.delete(
    "/documents/{filename}",
    response_model=MessageResponse,
    status_code=200,
    summary="Delete a document",
    description="Delete a user-owned document and its indexed chunks.",
)
def delete_document(
    filename: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = DocumentService(db)

    return service.delete_document(
        filename=filename,
        user_id=int(user_id),
    )


@router.get(
    "/documents",
    response_model=list[DocumentResponse] | PaginatedResponse[DocumentResponse],
    status_code=200,
    summary="List documents",
    description="List indexed documents for the authenticated user; pagination is optional.",
)
def list_documents(
    user_id: str = Depends(get_current_user),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    service = DocumentService(db)

    return service.list_documents(
        user_id=int(user_id),
        pagination=pagination,
    )
