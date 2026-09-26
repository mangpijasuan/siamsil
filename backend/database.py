from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from settings import Settings, get_settings


def sqlalchemy_database_url(url: str) -> str:
    """Select psycopg 3 explicitly when a generic PostgreSQL URL is supplied."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


@lru_cache(maxsize=1)
def get_database_engine() -> Engine | None:
    settings = get_settings()
    if not settings.database_url:
        return None
    return create_engine(
        sqlalchemy_database_url(settings.database_url),
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        connect_args={"connect_timeout": settings.database_connect_timeout_seconds},
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session] | None:
    engine = get_database_engine()
    if engine is None:
        return None
    return sessionmaker(bind=engine, expire_on_commit=False)


@dataclass(frozen=True)
class DatabaseReadiness:
    ready: bool
    detail: dict[str, Any]


def check_application_database(
    *,
    settings: Settings | None = None,
    engine: Engine | None = None,
) -> DatabaseReadiness:
    config = settings or get_settings()
    if not config.database_url:
        return DatabaseReadiness(
            ready=not config.database_required,
            detail={
                "status": "not_configured",
                "required": config.database_required,
            },
        )

    try:
        database_engine = engine or get_database_engine()
        if database_engine is None:
            raise RuntimeError("database engine was not created")
        with database_engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar_one()
        if result != 1:
            raise RuntimeError("database probe returned an unexpected result")
        return DatabaseReadiness(
            ready=True,
            detail={"status": "ok", "required": config.database_required},
        )
    except Exception as exc:  # readiness reports failure without leaking connection details
        return DatabaseReadiness(
            ready=False,
            detail={
                "status": "error",
                "required": config.database_required,
                "error": type(exc).__name__,
            },
        )
