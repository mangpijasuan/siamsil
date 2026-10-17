from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from main import app  # type: ignore  # noqa: E402
from scripts.import_bible_version import import_version  # type: ignore  # noqa: E402
from services.data_loader import get_store  # type: ignore  # noqa: E402
from services.scripture_catalog import ScriptureCatalog  # type: ignore  # noqa: E402


class BibleVersionTests(unittest.TestCase):
    def test_builtin_texts_are_not_misrepresented_as_published_editions(self) -> None:
        response = TestClient(app).get("/api/v1/bible/versions")
        self.assertEqual(response.status_code, 200)
        versions = response.json()["versions"]
        self.assertTrue(all(not item["separate_edition"] for item in versions if item["id"].startswith("supplied-")))
        self.assertTrue(all(item["rights_status"] == "unverified" for item in versions if item["id"].startswith("supplied-")))

    def test_versioned_chapter_uses_canonical_book_across_source_splits(self) -> None:
        response = TestClient(app).get("/api/v1/bible/versions/supplied-zomi/chapter?book_id=5&chapter=18")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["verse_count"], 22)
        self.assertEqual(response.json()["verses"][0]["reference"], "Deuteronomy 18:1")
        search = TestClient(app).get("/api/v1/bible/versions/supplied-zomi/search?q=Deuteronomy%2018:1")
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()["results"][0]["reference"], "Deuteronomy 18:1")

    def test_import_is_hidden_until_rights_are_attested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "verses.jsonl"
            source.write_text(json.dumps({"book_id": 1, "chapter": 1, "verse": 1, "text": "Beginning"}) + "\n", encoding="utf-8")
            args = argparse.Namespace(input=source, id="test-edition", name="Test Edition", language="en",
                                      abbreviation="TEST", attribution="Test source", rights_evidence=None,
                                      approved_for_display=False, scope="partial", output_dir=root)
            target, count = import_version(args)
            self.assertEqual(count, 1)
            self.assertTrue(target.exists())
            catalog = ScriptureCatalog(root, get_store())
            self.assertIsNone(catalog.version("test-edition"))
            self.assertEqual(catalog.chapter("test-edition", 1, 1), [])

    def test_published_import_is_served_and_duplicate_verse_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "verses.jsonl"
            row = json.dumps({"book_id": 1, "chapter": 1, "verse": 1, "text": "Beginning"})
            source.write_text(row + "\n", encoding="utf-8")
            args = argparse.Namespace(input=source, id="test-edition", name="Test Edition", language="en",
                                      abbreviation="TEST", attribution="Test source", rights_evidence="permission-1",
                                      approved_for_display=True, scope="partial", output_dir=root)
            import_version(args)
            catalog = ScriptureCatalog(root, get_store())
            self.assertEqual(catalog.chapter("test-edition", 1, 1)[0]["text"], "Beginning")
            self.assertEqual(catalog.search("test-edition", "begin", 10)[0]["text"], "Beginning")
            args.id = "test-duplicate"
            source.write_text(row + "\n" + row + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate verse"):
                import_version(args)
            self.assertFalse((root / "test-duplicate.sqlite").exists())

    def test_full_scope_requires_all_canonical_chapters_and_rights_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "verses.jsonl"
            source.write_text(json.dumps({"book_id": 1, "chapter": 1, "verse": 1, "text": "Beginning"}) + "\n", encoding="utf-8")
            args = argparse.Namespace(input=source, id="incomplete-edition", name="Incomplete", language="en",
                                      abbreviation="INC", attribution="Test source", rights_evidence=None,
                                      approved_for_display=True, scope="full", output_dir=root)
            with self.assertRaisesRegex(ValueError, "rights-evidence"):
                import_version(args)
            args.rights_evidence = "permission-1"
            with self.assertRaisesRegex(ValueError, "missing .* canonical chapters"):
                import_version(args)
            self.assertFalse((root / "incomplete-edition.sqlite").exists())


if __name__ == "__main__":
    unittest.main()
