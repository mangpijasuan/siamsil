from __future__ import annotations

import logging
import re
import time
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


def access_logger() -> logging.Logger:
    log = logging.getLogger("siamsil.access")
    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False
    return log


def route_template(request: Request) -> str:
    """The matched route pattern, e.g. /api/v1/dictionary/{entry_id}.

    Never the raw path or query string: those can carry what a user typed.
    """
    route = request.scope.get("route")
    pattern = getattr(route, "path", None)
    if not pattern:
        return "<unmatched>"
    # The matched route's pattern lacks its include_router prefix (e.g. /api/v1).
    # Recover the static prefix by removing the filled-in pattern from the end of the path.
    path = request.scope.get("path", "")
    try:
        filled = getattr(route, "path_format", pattern).format(**request.scope.get("path_params", {}))
    except (KeyError, IndexError, ValueError):
        return pattern
    if filled and path.endswith(filled):
        return path[: len(path) - len(filled)] + pattern
    return pattern


def install_http_contract(app: FastAPI) -> None:
    log = access_logger()

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request.state.request_id = request_id_for(request)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers[REQUEST_ID_HEADER] = request.state.request_id
            return response
        finally:
            # Privacy: log the route pattern only, never query strings or bodies.
            log.info(
                "request_id=%s method=%s route=%s status=%s duration_ms=%.1f",
                request.state.request_id,
                request.method,
                route_template(request),
                status,
                (time.perf_counter() - started) * 1000,
            )

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
