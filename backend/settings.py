from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    """Validated runtime configuration loaded from SIAMSIL_* variables."""

    model_config = SettingsConfigDict(
        env_prefix="SIAMSIL_",
        env_file=(PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "staging", "production"] = "development"
    data_dir: Path = BACKEND_ROOT / "data"
    language_db: Path = PROJECT_ROOT / "data" / "processed" / "language" / "siamsil_language.sqlite"

    database_url: str | None = None
    database_required: bool = False
    database_connect_timeout_seconds: int = Field(default=3, ge=1, le=30)
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=10, ge=0, le=100)

    oidc_enabled: bool = False
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_http_timeout_seconds: int = Field(default=3, ge=1, le=30)
    oidc_jwks_cache_seconds: int = Field(default=300, ge=60, le=3600)
    oidc_clock_skew_seconds: int = Field(default=30, ge=0, le=300)
    bootstrap_admin_subjects: list[str] = Field(default_factory=list)

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3002",
            "http://127.0.0.1:3002",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def empty_database_url_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        allowed = ("postgresql://", "postgresql+psycopg://")
        if not value.startswith(allowed):
            raise ValueError("database_url must use PostgreSQL with the psycopg driver")
        return value

    @model_validator(mode="after")
    def require_database_when_configured(self) -> "Settings":
        if self.database_required and not self.database_url:
            raise ValueError("SIAMSIL_DATABASE_URL is required when SIAMSIL_DATABASE_REQUIRED=true")
        if self.environment in {"staging", "production"} and not self.database_url:
            raise ValueError("SIAMSIL_DATABASE_URL is required in staging and production")
        if self.oidc_enabled:
            missing = [
                name
                for name, value in (
                    ("SIAMSIL_OIDC_ISSUER", self.oidc_issuer),
                    ("SIAMSIL_OIDC_AUDIENCE", self.oidc_audience),
                    ("SIAMSIL_OIDC_JWKS_URL", self.oidc_jwks_url),
                )
                if not value
            ]
            if missing:
                raise ValueError(f"OIDC is enabled but required settings are missing: {', '.join(missing)}")
            if self.environment in {"staging", "production"}:
                insecure = [
                    name
                    for name, value in (
                        ("SIAMSIL_OIDC_ISSUER", self.oidc_issuer),
                        ("SIAMSIL_OIDC_JWKS_URL", self.oidc_jwks_url),
                    )
                    if value and not value.startswith("https://")
                ]
                if insecure:
                    raise ValueError(
                        f"OIDC endpoints must use HTTPS outside development: {', '.join(insecure)}"
                    )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
