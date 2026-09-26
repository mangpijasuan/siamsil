from __future__ import annotations

import logging
import re
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("siamsil.api")

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def request_id_for(request: Request) -> str:
    value = request.headers.get(REQUEST_ID_HEADER, "").strip()
    return value if REQUEST_ID_RE.fullmatch(value) else str(uuid4())


def error_payload(
    request: Request,
    *,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", None),
    }
    if details:
        error["details"] = details
    return {"error": error}


def install_http_contract(app: FastAPI) -> None:
    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request.state.request_id = request_id_for(request)
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request.state.request_id
        return response

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        message = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(
                request,
                code=f"http_{exc.status_code}",
                message=message,
            ),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(request: Request, exc: RequestValidationError):
        details = [
            {
                "location": [str(item) for item in error["loc"]],
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_payload(
                request,
                code="validation_error",
                message="The request contains invalid or missing values.",
                details=details,
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        logger.exception("Unhandled API error request_id=%s", request_id, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=error_payload(
                request,
                code="internal_error",
                message="An unexpected error occurred.",
            ),
        )
