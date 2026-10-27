from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app  # noqa: E402
from services.word_suggest import build_word_list  # noqa: E402

# Placeholder words only: these tests check counting and ranking, not Zomi.
TEXTS = {
    "one": ["Qamo qamo’ qamel ki-qam.", "qamo qamel QAMO'", "zu ‘qamel’"],
    "two": ["Qamo zu-ve qamelpi"],
}


class WordListTests(unittest.TestCase):
    def setUp(self) -> None:
        self.words = build_word_list(TEXTS)

    def test_completions_are_ranked_by_use_and_keep_the_usual_written_form(self) -> None:
        self.assertEqual(self.words.complete("qa", 10), [
            {"word": "Qamo", "count": 5},
            {"word": "qamel", "count": 3},
            {"word": "qamelpi", "count": 1},
        ])
        self.assertEqual(self.words.sources, ("one", "two"))

    def test_the_possessive_apostrophe_is_folded_into_its_word(self) -> None:
        self.assertNotIn("qamo'", self.words.keys)
        self.assertEqual(self.words.complete("Qamo’", 3)[0], {"word": "Qamo", "count": 5})

    def test_hyphenated_words_limits_and_empty_prefixes(self) -> None:
        self.assertEqual(self.words.complete("ki", 5), [{"word": "ki-qam", "count": 1}])
        self.assertEqual(len(self.words.complete("q", 2)), 2)
        self.assertEqual(self.words.complete("  ", 5), [])
        self.assertEqual(self.words.complete("xyz", 5), [])


class FakeWords:
    def __init__(self, available: bool) -> None:
        self.available = available
        self.words = build_word_list(TEXTS)

    def complete(self, prefix: str, limit: int = 8):
        return self.words.complete(prefix, limit), self.words.sources


class WordEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_suggestions(self) -> None:
        with patch("routers.words.get_zomi_words", return_value=FakeWords(True)):
            response = self.client.get("/api/v1/words/suggest", params={"prefix": "qam", "limit": 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "prefix": "qam", "language": "ctd", "sources": ["one", "two"],
            "words": [{"word": "Qamo", "count": 5}, {"word": "qamel", "count": 3}],
        })

    def test_missing_database_and_bad_input(self) -> None:
        with patch("routers.words.get_zomi_words", return_value=FakeWords(False)):
            self.assertEqual(self.client.get("/api/v1/words/suggest", params={"prefix": "qa"}).status_code, 503)
        for params in ({}, {"prefix": ""}, {"prefix": "q" * 41}, {"prefix": "qa", "limit": 0}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get("/api/v1/words/suggest", params=params).status_code, 422)


if __name__ == "__main__":
    unittest.main()
