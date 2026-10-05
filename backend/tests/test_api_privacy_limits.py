from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from main import app  # type: ignore  # noqa: E402
from rate_limit import FixedWindowLimiter, limiter  # type: ignore  # noqa: E402


def empty_engine(release: str | None = "v2") -> Mock:
    engine = Mock()
    engine.available = True
    engine.search_dictionary.return_value = []
    engine.search_parallel.return_value = []
    engine.release.return_value = release
    return engine


def empty_store() -> Mock:
    store = Mock()
    store.search_translate.return_value = []
    return store


class AccessLogTests(unittest.TestCase):
    def test_logs_route_pattern_never_user_text(self) -> None:
        client = TestClient(app)
        with patch("routers.translate.get_engine", return_value=empty_engine()), patch(
            "routers.translate.get_store", return_value=empty_store()
        ), self.assertLogs("siamsil.access", level="INFO") as logs:
            response = client.get("/api/v1/translate/search", params={"q": "private-words-typed-by-a-user"})
        self.assertEqual(response.status_code, 200)
        line = logs.output[-1]
        self.assertIn("route=/api/v1/translate/search", line)
        self.assertIn("status=200", line)
        self.assertNotIn("private-words", line)

    def test_unmatched_paths_are_not_logged_verbatim(self) -> None:
        client = TestClient(app)
        with self.assertLogs("siamsil.access", level="INFO") as logs:
            client.get("/some/secret-looking/path?token=abc")
        self.assertIn("route=<unmatched>", logs.output[-1])
        self.assertNotIn("secret-looking", logs.output[-1])
        self.assertNotIn("token", logs.output[-1])


class VersionedRoutesTests(unittest.TestCase):
    def test_unversioned_aliases_are_gone(self) -> None:
        client = TestClient(app)
        self.assertEqual(client.get("/api/translate/search", params={"q": "x"}).status_code, 404)
        self.assertFalse([path for path in app.openapi()["paths"] if path.startswith("/api/") and not path.startswith("/api/v1/")])


class TranslationProvenanceTests(unittest.TestCase):
    def test_translate_names_system_and_release(self) -> None:
        client = TestClient(app)
        engine = empty_engine("v2")
        with patch("routers.translate.get_engine", return_value=engine), patch(
            "routers.translate.get_store", return_value=empty_store()
        ):
            response = client.post("/api/v1/translate", json={"text": "hello"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["system"], "retrieval")
        self.assertEqual(body["system_version"], "1")
        self.assertEqual(body["language_release"], "v2")


class RateLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        limiter._counts.clear()
        self.addCleanup(limiter._counts.clear)

    def request_search(self, client: TestClient, limit: int):
        with patch("rate_limit.get_settings", return_value=SimpleNamespace(rate_limit_per_minute=limit)), patch(
            "routers.translate.get_engine", return_value=empty_engine()
        ), patch("routers.translate.get_store", return_value=empty_store()):
            return client.get("/api/v1/translate/search", params={"q": "x"})

    def test_over_limit_returns_429_with_retry_after(self) -> None:
        client = TestClient(app)
        statuses = [self.request_search(client, 2).status_code for _ in range(3)]
        self.assertEqual(statuses, [200, 200, 429])
        response = self.request_search(client, 2)
        self.assertEqual(response.json()["error"]["code"], "http_429")
        self.assertGreaterEqual(int(response.headers["Retry-After"]), 1)

    def test_disabled_by_default(self) -> None:
        client = TestClient(app)
        statuses = {self.request_search(client, 0).status_code for _ in range(5)}
        self.assertEqual(statuses, {200})

    def test_buckets_and_windows_are_separate(self) -> None:
        local = FixedWindowLimiter()
        self.assertIsNone(local.hit("a", "translate", 1, now=0))
        self.assertIsNotNone(local.hit("a", "translate", 1, now=1))
        self.assertIsNone(local.hit("a", "search", 1, now=1))
        self.assertIsNone(local.hit("b", "translate", 1, now=1))
        self.assertIsNone(local.hit("a", "translate", 1, now=61))
        self.assertEqual(local.hit("a", "translate", 1, now=62), 58)


if __name__ == "__main__":
    unittest.main()
