from fastapi import (
    APIRouter,
    Depends,
)
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import (
    get_db,
)
from app.schemas.responses import (
    HealthResponse,
)
from app.services.health_service import (
    HealthService,
)

router = APIRouter(tags=["System"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=200,
    summary="Check service health",
    description="Return application version and PostgreSQL connectivity status.",
)
def health(db: Session = Depends(get_db)):

    service = HealthService(db)

    return {
        "status": "healthy",
        "database": service.check_health(),
        "version": settings.app_version,
    }
