from __future__ import annotations
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ml_pipeline" / "scripts"))
from dictionary_builder import collect


class DictionaryBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "language.sqlite"
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TABLE dictionary_entries (source_word TEXT)")
            db.execute("CREATE TABLE parallel_sentences (id INTEGER, normalized_source_text TEXT, source_language TEXT, dataset_split TEXT)")
            db.execute("INSERT INTO dictionary_entries VALUES ('orchard')")
            db.executemany("INSERT INTO parallel_sentences VALUES (?, ?, ?, ?)", [
                (1, "The farmers harvest apples today.", "en", "train"),
                (2, "Our farmers harvest apples tomorrow.", "en", "train"),
                (3, "Many farmers harvest apples weekly.", "en", "validation"),
                (4, "The farmers harvest apples privately.", "en", "eval_holdout"),
                (5, "The farmers harvest apples again.", "zom", "train"),
                (6, "The orchard harvest apples often.", "en", "test"),
            ])
    def tearDown(self):
        self.temp.cleanup()
    def test_drafts_only_and_no_invented_translations(self):
        result = collect(self.db, target=10, min_frequency=3)
        self.assertTrue(result)
        self.assertEqual(result[0]["headword"], "apples")
        self.assertTrue(all(x["review_status"] == "DRAFT" and not x["human_verified"] for x in result))
        self.assertTrue(all(x["proposed_zomi"] is None and x["definition"] is None for x in result))
    def test_excludes_existing_dictionary_and_holdouts(self):
        result = collect(self.db, target=100, min_frequency=1)
        words = {x["headword"] for x in result}
        self.assertNotIn("orchard", words)
        self.assertNotIn("privately", words)
        self.assertNotIn("again", words)
    def test_count_limit_and_stability(self):
        first = collect(self.db, target=2, min_frequency=1)
        self.assertEqual(len(first), 2)
        self.assertEqual(first, collect(self.db, target=2, min_frequency=1))
    def test_invalid_config(self):
        with self.assertRaises(ValueError):
            collect(self.db, target=0)


if __name__ == "__main__":
    unittest.main()
