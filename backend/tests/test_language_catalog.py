from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app  # type: ignore  # noqa: E402


class LanguageCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_catalog_does_not_claim_burmese_translation(self) -> None:
        with patch("routers.languages.get_engine") as get_engine:
            get_engine.return_value.available = True
            response = self.client.get("/api/v1/languages")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual({(p["source_language"], p["target_language"]) for p in payload["translation_pairs"]},
                         {("en", "ctd"), ("ctd", "en")})
        # Zomi is ctd (docs/DATA_RIGHTS.md, "Language code"); zom is Zou and is never returned.
        self.assertNotIn("zom", {lang["code"] for lang in payload["languages"]})
        self.assertEqual(next(lang for lang in payload["languages"] if lang["code"] == "my")["role"],
                         "learning_content")

    def test_unsupported_pair_is_rejected_before_search(self) -> None:
        response = self.client.get(
            "/api/v1/translate/search",
            params={"q": "hello", "source_language": "en", "target_language": "my"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("not available", response.json()["error"]["message"])

    def test_pair_must_be_complete(self) -> None:
        response = self.client.get(
            "/api/v1/translate/search", params={"q": "hello", "source_language": "en"},
        )
        self.assertEqual(response.status_code, 422)

    def test_reverse_pair_is_sent_to_dictionary_engine(self) -> None:
        # Older links say zom; it is read as ctd (Zomi), the code Siamsil uses.
        engine = Mock(available=True)
        engine.search_dictionary.return_value = []
        engine.search_parallel.return_value = []
        store = Mock()
        store.search_translate.return_value = []
        with patch("routers.translate.get_engine", return_value=engine), patch(
            "routers.translate.get_store", return_value=store
        ):
            response = self.client.get(
                "/api/v1/translate/search",
                params={"q": "ka", "source_language": "zom", "target_language": "en"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source_language"], "ctd")
        engine.search_dictionary.assert_called_once_with("ka", direction="ctd-en", limit=8)


if __name__ == "__main__":
    unittest.main()
