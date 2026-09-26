from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from main import app  # type: ignore  # noqa: E402


class ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_liveness_includes_request_id(self) -> None:
        response = self.client.get("/health/live")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertTrue(response.headers["X-Request-ID"])

    def test_valid_request_id_is_preserved(self) -> None:
        response = self.client.get("/health/live", headers={"X-Request-ID": "test-request-123"})

        self.assertEqual(response.headers["X-Request-ID"], "test-request-123")

    def test_readiness_reports_dependency_checks(self) -> None:
        engine = Mock()
        engine.available = True
        engine.db_path = Path("/test/siamsil_language.sqlite")
        engine.counts.return_value = {
            "dictionary_entries": 20_826,
            "parallel_sentences": 1_775_043,
            "verified_dictionary": 0,
        }
        store = Mock()
        store.metadata = {"dataset": "test"}

        with patch("main.get_engine", return_value=engine), patch("main.get_store", return_value=store):
            response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["checks"]["language_database"]["status"], "ok")
        self.assertEqual(payload["checks"]["content_data"]["status"], "ok")

    def test_validation_errors_use_standard_envelope(self) -> None:
        response = self.client.get("/api/v1/search", headers={"X-Request-ID": "validation-test"})

        self.assertEqual(response.status_code, 422)
        payload = response.json()["error"]
        self.assertEqual(payload["code"], "validation_error")
        self.assertEqual(payload["request_id"], "validation-test")
        self.assertTrue(payload["details"])

    def test_not_found_uses_standard_envelope(self) -> None:
        response = self.client.get("/does-not-exist", headers={"X-Request-ID": "missing-test"})

        self.assertEqual(response.status_code, 404)
        payload = response.json()["error"]
        self.assertEqual(payload["code"], "http_404")
        self.assertEqual(payload["request_id"], "missing-test")


if __name__ == "__main__":
    unittest.main()
