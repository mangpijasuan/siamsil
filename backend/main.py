from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api_schemas import HealthResponse, LivenessResponse
from database import check_application_database
from http_contract import install_http_contract
from identity import router as identity
from routers import ai, bible, dictionary, learning, search, translate
from services.data_loader import get_store
from services.language_engine import get_engine
from settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Construct the read-only language adapter without forcing a database query.
    # Readiness performs dependency checks and reports a degraded state instead
    # of preventing the process from exposing its liveness endpoint.
    get_settings()
    get_engine()
    yield


app = FastAPI(
    title="Siamsil API",
    description="Zomi language platform — dictionary, translation retrieval, Bible, and learning.",
    version="0.4.0",
    lifespan=lifespan,
)

install_http_contract(app)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

for module in (dictionary, bible, translate, learning, search, ai, identity):
    app.include_router(module.router, prefix="/api/v1")


def readiness_payload() -> tuple[dict[str, Any], bool]:
    checks: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    ready = True

    engine = get_engine()
    try:
        language = engine.counts()
        language_ready = engine.available
        checks["language_database"] = {
            "status": "ok" if language_ready else "unavailable",
            "path": str(engine.db_path),
        }
        ready = ready and language_ready
    except Exception as exc:  # readiness must report failure without crashing
        language = {"dictionary_entries": 0, "parallel_sentences": 0, "verified_dictionary": 0}
        checks["language_database"] = {"status": "error", "error": type(exc).__name__}
        ready = False

    try:
        store = get_store()
        metadata = store.metadata
        checks["content_data"] = {"status": "ok"}
    except Exception as exc:  # readiness must report failure without crashing
        checks["content_data"] = {"status": "error", "error": type(exc).__name__}
        ready = False

    database = check_application_database()
    checks["application_database"] = database.detail
    ready = ready and database.ready
    checks["identity"] = {
        "status": "configured" if settings.oidc_enabled else "disabled",
    }

    payload = {
        "status": "ok" if ready else "degraded",
        "version": app.version,
        "metadata": metadata,
        "language": {
            "database": engine.available,
            **language,
        },
        "checks": checks,
    }
    return payload, ready


@app.get("/health/live", response_model=LivenessResponse)
def liveness():
    return {"status": "ok", "version": app.version}


@app.get("/health/ready", response_model=HealthResponse)
def readiness():
    payload, ready = readiness_payload()
    return JSONResponse(status_code=200 if ready else 503, content=payload)


@app.get("/health", response_model=HealthResponse)
def health():
    """Backward-compatible health summary; use /health/ready for probes."""
    payload, _ = readiness_payload()
    return payload
