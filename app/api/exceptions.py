"""Consistent API exception handlers."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def error_response(status_code: int, code: str, message: object) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


def safe_validation_errors(exc: RequestValidationError) -> list[dict[str, str]]:
    """Return useful validation details without echoing submitted credentials."""
    errors = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", ()) if part != "body"]
        message = str(error.get("msg", "Invalid value"))
        if message.startswith("Value error, "):
            message = message.removeprefix("Value error, ")
        errors.append(
            {
                "field": ".".join(location) or "request",
                "message": message,
                "type": str(error.get("type", "validation_error")),
            }
        )
    return errors


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return error_response(exc.status_code, "http_error", exc.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return error_response(422, "validation_error", safe_validation_errors(exc))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, _: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled error for %s %s", request.method, request.url.path)
        return error_response(
            500, "internal_server_error", "An unexpected error occurred."
        )
