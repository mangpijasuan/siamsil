from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT / "services"))

from language_engine import LanguageEngine  # type: ignore  # noqa: E402
from main import app  # type: ignore  # noqa: E402
from services.data_loader import DataStore  # type: ignore  # noqa: E402

# Placeholder text stands in for Zomi; no Zomi language data is invented here.
PAIRS = [
    (1, "the road is closed", "ZOMI_PLACEHOLDER_ALPHA"),
    (2, "a different sentence", "ZOMI_PLACEHOLDER_BETA road"),
]


def build_corpus(db: Path) -> None:
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE parallel_sentences (
            id INTEGER PRIMARY KEY,
            raw_source_text TEXT, raw_target_text TEXT,
            normalized_source_text TEXT, normalized_target_text TEXT,
            model TEXT, source_reference TEXT, quality_flags TEXT,
            quality_score REAL, verified INTEGER, dataset_split TEXT
        );
        CREATE VIRTUAL TABLE parallel_fts USING fts5(normalized_source_text, normalized_target_text);
        """
    )
    for pair_id, english, zomi in PAIRS:
        con.execute(
            "INSERT INTO parallel_sentences VALUES (?,?,?,?,?,'test','test','[]',1.0,0,'train')",
            (pair_id, english, zomi, english, zomi),
        )
        con.execute("INSERT INTO parallel_fts (rowid, normalized_source_text, normalized_target_text) VALUES (?,?,?)",
                    (pair_id, english, zomi))
    con.commit()
    con.close()


class CorpusDirectionTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "language.sqlite"
        build_corpus(db)
        self.engine = LanguageEngine(db)

    def ids(self, query: str, direction: str | None) -> list[int]:
        return [pair["id"] for pair in self.engine.search_parallel(query, direction=direction)]

    def test_english_to_zomi_searches_only_english(self) -> None:
        self.assertEqual(self.ids("road", "en-zom"), [1])

    def test_zomi_to_english_searches_only_zomi(self) -> None:
        self.assertEqual(self.ids("road", "zom-en"), [2])

    def test_no_direction_searches_both_sides(self) -> None:
        self.assertEqual(sorted(self.ids("road", None)), [1, 2])

    def test_exact_match_respects_direction(self) -> None:
        hits = self.engine.search_parallel("ZOMI_PLACEHOLDER_ALPHA", direction="zom-en")
        self.assertEqual([(hit["id"], hit["exact"]) for hit in hits], [(1, True)])
        self.assertEqual(self.ids("ZOMI_PLACEHOLDER_ALPHA", "en-zom"), [])


class WorkbookDirectionTests(unittest.TestCase):
    def test_overlay_matches_only_the_side_translated_from(self) -> None:
        store = DataStore.__new__(DataStore)
        store.daily_use_pairs = [{"english": "road", "zomi": "ZOMI_PLACEHOLDER_ALPHA"}]
        store.translation_pairs = [{"english": "other", "zomi": "ZOMI_PLACEHOLDER_BETA road"}]
        store.bible_verses = []
        self.assertEqual([r["source"] for r in store.search_translate("road", direction="en-zom")], ["daily_use"])
        self.assertEqual([r["source"] for r in store.search_translate("road", direction="zom-en")], ["translation_pair"])
        self.assertEqual(len(store.search_translate("road")), 2)


class TranslateEndpointDirectionTests(unittest.TestCase):
    def request(self, payload: dict) -> tuple[Mock, Mock, int]:
        engine = Mock(available=True)
        engine.search_dictionary.return_value = []
        engine.search_parallel.return_value = []
        engine.release.return_value = "v2"
        store = Mock()
        store.search_translate.return_value = []
        with patch("routers.translate.get_engine", return_value=engine), patch(
            "routers.translate.get_store", return_value=store
        ):
            response = TestClient(app).post("/api/v1/translate", json=payload)
        return engine, store, response.status_code

    def test_requested_direction_reaches_every_source(self) -> None:
        engine, store, status = self.request({"text": "hello", "direction": "zom-en"})
        self.assertEqual(status, 200)
        self.assertEqual(engine.search_parallel.call_args.kwargs["direction"], "zom-en")
        self.assertEqual(engine.search_dictionary.call_args.kwargs["direction"], "zom-en")
        self.assertEqual(store.search_translate.call_args.args[2], "zom-en")

    def test_default_direction_is_english_to_zomi(self) -> None:
        engine, _, status = self.request({"text": "hello"})
        self.assertEqual(status, 200)
        self.assertEqual(engine.search_parallel.call_args.kwargs["direction"], "en-zom")

    def test_unknown_direction_is_rejected(self) -> None:
        _, _, status = self.request({"text": "hello", "direction": "fr-zom"})
        self.assertEqual(status, 422)


if __name__ == "__main__":
    unittest.main()
