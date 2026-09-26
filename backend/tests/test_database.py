from __future__ import annotations

import sys
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from pydantic import ValidationError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from database import (  # type: ignore  # noqa: E402
    check_application_database,
    get_database_engine,
    sqlalchemy_database_url,
)
from models import Base  # type: ignore  # noqa: E402
from settings import Settings  # type: ignore  # noqa: E402


class SettingsTests(unittest.TestCase):
    def test_required_database_must_have_url(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(database_required=True, database_url=None, _env_file=None)

    def test_production_requires_database(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(environment="production", database_url=None, _env_file=None)

    def test_non_postgres_database_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(database_url="sqlite:///test.sqlite", _env_file=None)


class DatabaseTests(unittest.TestCase):
    def test_generic_postgres_url_selects_psycopg(self) -> None:
        self.assertEqual(
            sqlalchemy_database_url("postgresql://user:password@localhost/siamsil"),
            "postgresql+psycopg://user:password@localhost/siamsil",
        )

    def test_optional_unconfigured_database_is_ready(self) -> None:
        settings = Settings(database_required=False, database_url=None, _env_file=None)
        status = check_application_database(settings=settings)

        self.assertTrue(status.ready)
        self.assertEqual(status.detail["status"], "not_configured")

    def test_database_probe_succeeds(self) -> None:
        settings = Settings(
            database_required=True,
            database_url="postgresql+psycopg://user:password@localhost/siamsil",
            _env_file=None,
        )
        engine = MagicMock()
        connection = engine.connect.return_value.__enter__.return_value
        connection.execute.return_value.scalar_one.return_value = 1

        status = check_application_database(settings=settings, engine=engine)

        self.assertTrue(status.ready)
        self.assertEqual(status.detail, {"status": "ok", "required": True})

    def test_database_probe_hides_connection_details_on_failure(self) -> None:
        settings = Settings(
            database_required=True,
            database_url="postgresql+psycopg://user:secret@localhost/siamsil",
            _env_file=None,
        )
        engine = MagicMock()
        engine.connect.side_effect = RuntimeError("postgresql://user:secret@localhost/siamsil")

        status = check_application_database(settings=settings, engine=engine)

        self.assertFalse(status.ready)
        self.assertEqual(status.detail["error"], "RuntimeError")
        self.assertNotIn("secret", str(status.detail))

    def test_foundation_metadata_contains_identity_and_audit_tables(self) -> None:
        self.assertEqual(
            {
                "users",
                "external_identities",
                "devices",
                "user_roles",
                "consents",
                "audit_events",
                "user_sessions",
            },
            set(Base.metadata.tables),
        )

    @unittest.skipUnless(os.getenv("SIAMSIL_DATABASE_URL"), "application database is not configured")
    def test_configured_database_is_reachable(self) -> None:
        status = check_application_database(engine=get_database_engine())

        self.assertTrue(status.ready, status.detail)


if __name__ == "__main__":
    unittest.main()
