from __future__ import annotations

import json
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
sys.path.insert(0, str(BACKEND_ROOT / "tests"))
sys.path.insert(0, str(BACKEND_ROOT.parent / "ml_pipeline" / "scripts"))

from language_engine import LanguageEngine, exact_forms  # type: ignore  # noqa: E402
from main import app  # type: ignore  # noqa: E402
from services.bible_lookup import BibleLookup  # type: ignore  # noqa: E402
from services.bible_versions import BibleVersions  # type: ignore  # noqa: E402
from test_bible_versions import USFM_JOHN, write_version  # type: ignore  # noqa: E402
from test_translate_direction import build_corpus  # type: ignore  # noqa: E402
from import_usx_bibles import main as import_main  # type: ignore  # noqa: E402

# Placeholder text stands in for Zomi; no Zomi language data is invented here.
MORE_PAIRS = [
    (10, "Thank you for the long walk on the winding road.", "ZOMI_PLACEHOLDER_LONG"),
    (11, "Thank you.", "ZOMI_PLACEHOLDER_EXACT"),
    (12, "I thank you.", "ZOMI_PLACEHOLDER_SHORT"),
]


class PhraseRankingTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "language.sqlite"
        build_corpus(db)
        con = sqlite3.connect(db)
        for pair_id, english, zomi in MORE_PAIRS:
            con.execute("INSERT INTO parallel_sentences VALUES (?,?,?,?,?,'test','test','[]',1.0,0,'train')",
                        (pair_id, english, zomi, english, zomi))
            con.execute("INSERT INTO parallel_fts (rowid, normalized_source_text, normalized_target_text) VALUES (?,?,?)",
                        (pair_id, english, zomi))
        con.commit()
        con.close()
        self.engine = LanguageEngine(db)

    def test_exact_match_ignores_closing_punctuation(self) -> None:
        self.assertEqual(exact_forms(" Thank you! "), ["thank you", "thank you.", "thank you!", "thank you?"])
        hits = self.engine.search_parallel("Thank you", direction="en-ctd")
        self.assertEqual(hits[0]["id"], 11)
        self.assertTrue(hits[0]["exact"])

    def test_closest_sentences_come_before_long_ones(self) -> None:
        self.assertEqual([hit["id"] for hit in self.engine.search_parallel("thank you", direction="en-ctd")], [11, 12, 10])
        self.assertEqual([hit["id"] for hit in self.engine.search_parallel("thank you")], [11, 12, 10])


class BibleLookupTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        source = root / "src"
        write_version(source, "a", "TST", "ctd")
        (source / "usfm").mkdir()
        (source / "usfm" / "43-JHN.usfm").write_text(USFM_JOHN, encoding="utf-8")
        rights = root / "rights.json"
        rights.write_text(json.dumps({"sources": {"bible_tst": {"display": "cleared"}, "bible_teb": {"display": "cleared"}}}))
        config = root / "bible_versions.json"
        config.write_text(json.dumps({"versions": {
            "tst": {"name": "Zomi Test", "language_name": "Zomi", "language_iso": "ctd", "book_names": {"JHN": "Fixture Jhn"}},
            "teb": {"name": "English Test", "language_name": "English", "language_iso": "eng"},
        }}))
        db = root / "out" / "bible_versions.sqlite"
        with patch("sys.stdout"), patch("sys.stderr"):
            self.assertEqual(import_main(["--source", str(source), "--out", str(db), "--manifest",
                                          str(db.parent / "manifest.json"), "--rights", str(rights), "--config", str(config)]), 0)
        self.versions = BibleVersions(db)
        self.lookup = BibleLookup(self.versions)

    def refs(self, message: str, search: bool = False) -> tuple[str, list[str]]:
        found, verses = self.lookup.passage(message, search=search)
        return found, [verse["reference"] for verse in verses]

    def test_a_verse_by_english_or_local_book_name(self) -> None:
        found, verses = self.lookup.passage("John 1:1")
        self.assertEqual(found, "reference")
        self.assertEqual(verses[0]["reference"], "Fixture Jhn 1:1 (John 1:1)")
        self.assertTrue(verses[0]["zomi"].startswith("alpha beta"))
        self.assertEqual(verses[0]["english"], "In the beginning was the word. Poetry line")
        self.assertEqual(verses[0]["source"], "Zomi Test · English Test")
        self.assertEqual(self.refs("fixture jhn 1:2"), ("reference", ["Fixture Jhn 1:2 (John 1:2)"]))

    def test_a_chapter_gives_its_first_verses(self) -> None:
        self.assertEqual(self.refs("Laisiangtho John 1"),
                         ("reference", ["Fixture Jhn 1:1 (John 1:1)", "Fixture Jhn 1:2 (John 1:2)"]))

    def test_words_that_only_look_like_a_reference(self) -> None:
        self.assertEqual(self.refs("john 1"), ("none", []))  # lower case, no verse, no request for the Bible
        self.assertEqual(self.refs("bible john 1")[0], "reference")
        self.assertEqual(self.refs("John 2"), ("none", []))  # the Zomi version has no chapter 2
        self.assertEqual(self.refs("What does hope mean?"), ("none", []))

    def test_words_in_a_verse_when_no_book_is_named(self) -> None:
        self.assertEqual(self.refs("bible verse range text", search=True), ("search", ["Fixture Jhn 1:2 (John 1:2)"]))
        self.assertEqual(self.refs("bible verse range text"), ("none", []))

    def test_siamsil_ai_answers_a_reference_from_the_bible(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "language.sqlite"
            build_corpus(db)
            with patch("routers.ai.get_engine", return_value=LanguageEngine(db)), \
                    patch("routers.ai.get_bible_versions", return_value=self.versions):
                body = TestClient(app).post("/api/v1/ai/ask", json={"message": "John 1:1"}).json()
        self.assertEqual((body["intent"], body["confidence"]), ("bible", "high"))
        self.assertEqual([(s["type"], s["reference"]) for s in body["sources"]], [("bible", "Fixture Jhn 1:1 (John 1:1)")])
        self.assertIn("Fixture Jhn 1:1 (John 1:1)", body["answer"])

    def test_translate_takes_verses_from_the_cleared_bible_and_ranks_them_by_closeness(self) -> None:
        legacy = Mock()
        # The workbook's edited Bible column (bible_iso_improved) must never be shown.
        legacy.search_translate.return_value = [
            {"source": "bible", "english": "the legacy verse", "zomi": "ZOMI_PLACEHOLDER_ISO", "reference": "X 1:1"},
        ]
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "language.sqlite"
            build_corpus(db)
            with patch("routers.translate.get_engine", return_value=LanguageEngine(db)), \
                    patch("routers.translate.get_bible_versions", return_value=self.versions), \
                    patch("routers.translate.get_store", return_value=legacy):
                body = TestClient(app).get("/api/v1/translate/search", params={"q": "the", "direction": "en-ctd"}).json()
        shown = [(r["source"], r["english"]) for r in body["results"]]
        self.assertNotIn(("bible", "the legacy verse"), shown)
        # The short corpus sentence comes before the longer verse.
        self.assertEqual(shown, [("parallel_corpus", "the road is closed"),
                                 ("bible", "In the beginning was the word. Poetry line")])
        verse = body["results"][1]
        self.assertEqual((verse["label"], verse["verified"], verse["reference"]),
                         ("Bible: Zomi Test · English Test", False, "Fixture Jhn 1:1 (John 1:1)"))


if __name__ == "__main__":
    unittest.main()
