from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from http_contract import install_http_contract
from routers import ai, bible, dictionary, learning, search, translate
from services.data_loader import get_store
from services.language_engine import get_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Construct the read-only language adapter without forcing a database query.
    # Readiness performs dependency checks and reports a degraded state instead
    # of preventing the process from exposing its liveness endpoint.
    get_engine()
    yield


app = FastAPI(
    title="Siamsil API",
    description="Zomi language platform — dictionary, translation retrieval, Bible, and learning.",
    version="0.3.0",
    lifespan=lifespan,
)

install_http_contract(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3002",
        "http://127.0.0.1:3002",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

for module in (dictionary, bible, translate, learning, search, ai):
    app.include_router(module.router, prefix="/api/v1")
    app.include_router(module.router, prefix="/api")


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


@app.get("/health/live")
def liveness():
    return {"status": "ok", "version": app.version}


@app.get("/health/ready")
def readiness():
    payload, ready = readiness_payload()
    return JSONResponse(status_code=200 if ready else 503, content=payload)


@app.get("/health")
def health():
    """Backward-compatible health summary; use /health/ready for probes."""
    payload, _ = readiness_payload()
    return payload
