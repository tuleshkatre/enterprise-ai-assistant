import logging
import time
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

import app.db.models  # noqa: F401 -- register SQLAlchemy model metadata
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.conversation import router as conversation_router
from app.api.docs import OPENAPI_TAGS, enterprise_swagger_ui
from app.api.exceptions import register_exception_handlers
from app.api.graph_chat import router as graph_router
from app.api.health import router as health_router
from app.api.upload import router as upload_router
from app.config import settings
from app.db.database import engine
from app.logging_config import configure_logging
from app.mcp.server import mcp
from app.rate_limit import limiter

configure_logging()

mcp_http_app = mcp.streamable_http_app(
    streamable_http_path="/",
    stateless_http=True,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Run lifecycle resources owned by mounted ASGI applications."""
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    async with mcp_http_app.router.lifespan_context(mcp_http_app):
        yield


app = FastAPI(
    title="Enterprise AI Assistant",
    description=(
        "Production-oriented AI platform for tenant-isolated RAG, agent routing, "
        "streaming, analytics, and conversational memory.\n\n"
        "**Core capabilities:** JWT security · PDF knowledge base · LangGraph "
        "orchestration · source citations · SQL analytics · MCP tools · observability"
    ),
    version=settings.app_version,
    contact={"name": "Tulesh Katre"},
    docs_url=None,
    redoc_url="/redoc",
    lifespan=lifespan,
    openapi_tags=OPENAPI_TAGS,
)


@app.get("/docs", include_in_schema=False)
def swagger_ui():
    return enterprise_swagger_ui(
        app.openapi_url,
        f"{app.title} · API Docs",
        settings.app_version,
        settings.app_env,
    )


# Public API routes are versioned under /api/v1.
api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(upload_router)
api_v1_router.include_router(chat_router)
api_v1_router.include_router(graph_router)
api_v1_router.include_router(conversation_router)
api_v1_router.include_router(health_router)
app.include_router(api_v1_router)

# Remote MCP endpoint. It requires the same Bearer access JWT as the API.
app.mount(
    "/mcp",
    mcp_http_app,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

register_exception_handlers(app)

logger = logging.getLogger(__name__)


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Attach baseline browser security headers to every HTTP response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.middleware("http")
async def log_requests(request, call_next):
    """Emit one completion log line per HTTP request without logging payloads."""
    started_at = time.perf_counter()
    response = await call_next(request)
    logger.info(
        "request_completed method=%s path=%s status=%s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - started_at) * 1000,
    )
    return response


if settings.metrics_enabled:
    Instrumentator(
        excluded_handlers=["/metrics"],
    ).instrument(app).expose(
        app,
        endpoint="/metrics",
        include_in_schema=False,
    )
