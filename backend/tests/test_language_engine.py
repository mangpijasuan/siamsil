from __future__ import annotations

import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT / "services"))
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))

from language_engine import LanguageEngine, fts_match  # type: ignore  # noqa: E402
from build_language_db import (  # type: ignore  # noqa: E402
    dataset_split_for,
    normalize_text,
    normalize_word,
    quality_flags,
    quality_score,
)


class NormalizationTests(unittest.TestCase):
    def test_normalize_collapses_whitespace_and_bom(self) -> None:
        self.assertEqual(normalize_text("\ufeff  Ka  nu \n"), "Ka nu")

    def test_normalize_word_is_lowercase(self) -> None:
        self.assertEqual(normalize_word("Hello, World!"), "hello world")

    def test_identical_pair_is_flagged(self) -> None:
        flags = quality_flags("hello there", "hello there")
        self.assertIn("identical", flags)
        self.assertLess(quality_score(flags), 1.0)

    def test_html_is_flagged(self) -> None:
        flags = quality_flags("hello", "<script>alert(1)</script>")
        self.assertIn("html_or_script", flags)

    def test_split_is_stable(self) -> None:
        self.assertEqual(dataset_split_for("The same sentence."), dataset_split_for("The same sentence."))


class FtsTests(unittest.TestCase):
    def test_fts_match_strips_operators(self) -> None:
        self.assertEqual(fts_match('hope" OR 1=1'), '"hope" AND "OR" AND "1=1"*')

    def test_engine_searches_temp_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.sqlite"
            con = sqlite3.connect(db)
            con.executescript(
                """
                CREATE TABLE dictionary_entries (
                    id INTEGER PRIMARY KEY,
                    source_word TEXT,
                    normalized_word TEXT,
                    language TEXT,
                    dialect TEXT,
                    part_of_speech TEXT,
                    part_of_speech_full TEXT,
                    definition TEXT,
                    pronunciation TEXT,
                    usage_notes TEXT,
                    source TEXT,
                    source_reference TEXT,
                    confidence REAL,
                    verification_status TEXT,
                    flagged INTEGER,
                    suggested_correction TEXT,
                    letter TEXT,
                    version TEXT,
                    created_at TEXT
                );
                CREATE VIRTUAL TABLE dictionary_fts USING fts5(source_word, definition, part_of_speech);
                """
            )
            con.execute(
                """
                INSERT INTO dictionary_entries (
                    id, source_word, normalized_word, language, dialect, part_of_speech,
                    part_of_speech_full, definition, pronunciation, usage_notes, source,
                    source_reference, confidence, verification_status, flagged,
                    suggested_correction, letter, version, created_at
                ) VALUES (1,'hope','hope','en',NULL,'n.','noun','lam-etna',NULL,NULL,'test','1',0.9,'verified',0,NULL,'H','v1','now')
                """
            )
            con.execute(
                "INSERT INTO dictionary_fts (source_word, definition, part_of_speech) VALUES ('hope','lam-etna','n.')"
            )
            con.commit()
            con.close()
            engine = LanguageEngine(db)
            results = engine.search_dictionary("hope")
            self.assertEqual(results[0]["english"], "hope")
            self.assertEqual(results[0]["definition"], "lam-etna")
            self.assertTrue(results[0]["verified"])

    def test_engine_uses_one_read_connection_per_thread(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.sqlite"
            sqlite3.connect(db).close()
            engine = LanguageEngine(db)
            barrier = threading.Barrier(4)

            def connection_id() -> int:
                con = engine.connect()
                barrier.wait(timeout=2)
                return id(con)

            with ThreadPoolExecutor(max_workers=4) as executor:
                connection_ids = set(executor.map(lambda _: connection_id(), range(4)))

            self.assertEqual(len(connection_ids), 4)


if __name__ == "__main__":
    unittest.main()
