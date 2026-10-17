from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))

from import_usx_bibles import main as import_main  # type: ignore  # noqa: E402
from main import app  # type: ignore  # noqa: E402
from services.bible_versions import BibleVersions  # type: ignore  # noqa: E402

# Synthetic fixture text, not real scripture.
METADATA = """<?xml version="1.0" encoding="utf-8"?>
<DBLMetadata><identification><name>Test Version {abbr}</name><abbreviation>{abbr}</abbreviation>
<description>Fixture {abbr}</description></identification>
<language><iso>{iso}</iso><name>Fixture language</name></language></DBLMetadata>"""

JOHN = """<?xml version="1.0" encoding="utf-8"?>
<usx version="2.0">
  <book code="JHN" style="id">John</book>
  <para style="mt">Title that is not a verse</para>
  <chapter number="1" style="c" />
  <para style="s1">Section heading</para>
  <para style="p"><verse number="1" style="v" />alpha <char style="wj">beta</char><note caller="+" style="f"><char style="ft">footnote</char></note> gamma</para>
  <para style="q1">delta continues verse one</para>
  <para style="p"><verse number="2-3" style="v" />range text</para>
  <chapter number="2" style="c" />
  <para style="p"><verse number="1" style="v" />second chapter</para>
</usx>"""


def write_version(root: Path, folder: str, abbr: str, iso: str, john: str = JOHN) -> None:
    usx = root / folder / "USX_1"
    usx.mkdir(parents=True)
    (root / folder / "metadata.xml").write_text(METADATA.format(abbr=abbr, iso=iso), encoding="utf-8")
    (usx / "JHN.usx").write_text(john, encoding="utf-8")


class ImportUsxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "src"
        self.db = self.root / "out" / "bible_versions.sqlite"
        self.rights = self.root / "rights.json"
        self.rights.write_text(json.dumps({"sources": {"bible_hid": {"display": "blocked", "train": "blocked"}}}))
        write_version(self.source, "a", "TST", "ctd")
        write_version(self.source, "b", "ENG", "eng")
        write_version(self.source, "c", "HID", "ctd")
        # A second, damaged copy of TST: the clean copy must win.
        write_version(self.source, "d", "TST", "ctd", JOHN.replace('number="2-3"', 'number="#"'))
        with patch("sys.stdout"), patch("sys.stderr"):
            code = import_main([
                "--source", str(self.source), "--out", str(self.db),
                "--manifest", str(self.root / "out" / "manifest.json"), "--rights", str(self.rights),
            ])
        self.assertEqual(code, 0)
        self.versions = BibleVersions(self.db)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_verse_text_skips_headings_and_notes(self) -> None:
        verses = self.versions.chapter("tst", 43, 1)
        self.assertEqual(verses[0]["text"], "alpha beta gamma delta continues verse one")
        self.assertEqual((verses[1]["verse"], verses[1]["label"], verses[1]["text"]), (2, "2-3", "range text"))
        self.assertEqual(self.versions.chapter("tst", 43, 2)[0]["text"], "second chapter")

    def test_blocked_versions_are_hidden_and_order_puts_english_last(self) -> None:
        self.assertEqual([v["id"] for v in self.versions.versions()], ["tst", "eng"])

    def test_books_report_chapter_counts(self) -> None:
        self.assertEqual(self.versions.books("tst"), [
            {"book_id": 43, "code": "JHN", "name": "John", "testament": "new", "chapter_count": 2},
        ])

    def test_manifest_records_skipped_duplicate(self) -> None:
        manifest = json.loads((self.root / "out" / "manifest.json").read_text())
        tst = [row for row in manifest["versions"] if row["id"] == "tst"]
        self.assertEqual(sorted((row["folder"], row["imported"]) for row in tst), [("a", True), ("d", False)])

    def test_api_routes(self) -> None:
        client = TestClient(app)
        with patch("routers.bible.get_bible_versions", return_value=self.versions):
            listing = client.get("/api/v1/bible/versions").json()
            self.assertEqual([v["id"] for v in listing["versions"]], ["tst", "eng"])
            chapter = client.get("/api/v1/bible/versions/tst/chapter", params={"book_id": 43, "chapter": 1})
            self.assertEqual(chapter.status_code, 200)
            self.assertEqual(chapter.json()["book"]["chapter_count"], 2)
            self.assertEqual(client.get("/api/v1/bible/versions/hid/books").status_code, 404)
            self.assertEqual(
                client.get("/api/v1/bible/versions/tst/chapter", params={"book_id": 1, "chapter": 1}).status_code, 404
            )

    def test_missing_database_is_503(self) -> None:
        client = TestClient(app)
        with patch("routers.bible.get_bible_versions", return_value=BibleVersions(self.root / "missing.sqlite")):
            self.assertEqual(client.get("/api/v1/bible/versions").status_code, 503)


if __name__ == "__main__":
    unittest.main()
