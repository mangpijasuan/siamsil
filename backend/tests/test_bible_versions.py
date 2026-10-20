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
  <para style="p"><verse number="1" style="v" />alpha <char style="wj">beta</char>,<note caller="+" style="f"><char style="ft">footnote</char></note> gamma</para>
  <para style="q1">delta continues verse one</para>
  <para style="s1">Heading after a verse</para>
  <para style="p">the <char style="nd">LORD</char>'s word</para>
  <para style="p"><verse number="2-3" style="v" />range text</para>
  <chapter number="3" style="c" />
  <para style="p"><verse number="1" style="v" />third chapter; chapter two is missing</para>
</usx>"""


def write_version(root: Path, folder: str, abbr: str, iso: str, john: str = JOHN) -> None:
    usx = root / folder / "USX_1"
    usx.mkdir(parents=True)
    (root / folder / "metadata.xml").write_text(METADATA.format(abbr=abbr, iso=iso), encoding="utf-8")
    (usx / "JHN.usx").write_text(john, encoding="utf-8")


USFM_JOHN = """\\id JHN 43-JHN-tst.sfm Test English Bible (TEB)
\\h John
\\mt1 John
\\c 1
\\s1 A heading
\\p
\\v 1 \\w In|strong="G1722"\\w* the beginning\\f + \\fr 1:1 \\ft a note
that spans lines\\f* was the word.
\\q1 \\wj \\+w Poetry|strong="G1"\\+w* line\\wj*
\\v 2 Second verse.
\\c 2
\\p
\\v 1 Chapter two.
"""


class ImportUsxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "src"
        self.db = self.root / "out" / "bible_versions.sqlite"
        self.rights = self.root / "rights.json"
        self.rights.write_text(json.dumps({"sources": {
            "bible_hid": {"display": "blocked", "train": "blocked"},
            "bible_tst": {"display": "cleared"}, "bible_eng": {"display": "cleared"}, "bible_teb": {"display": "cleared"},
        }}))
        write_version(self.source, "a", "TST", "ctd")
        write_version(self.source, "b", "ENG", "eng")
        write_version(self.source, "c", "HID", "ctd")
        (self.source / "usfm").mkdir()
        (self.source / "usfm" / "43-JHN.usfm").write_text(USFM_JOHN, encoding="utf-8")
        # A second, damaged copy of TST: the clean copy must win.
        write_version(self.source, "d", "TST", "ctd", JOHN.replace('number="2-3"', 'number="#"'))
        self.config = self.root / "bible_versions.json"
        self.config.write_text(json.dumps({"versions": {
            "tst": {"name": "Zomi Test", "language_name": "Zomi", "language_iso": "zom", "book_names": {"JHN": "FIXTURE JOHN"}},
            "teb": {"language_name": "English", "language_iso": "eng", "copyright": "Public domain."},
        }}))
        self.assertEqual(self.build(self.source, self.db), 0)
        self.versions = BibleVersions(self.db)

    def build(self, source: Path, db: Path) -> int:
        with patch("sys.stdout"), patch("sys.stderr"):
            return import_main([
                "--source", str(source), "--out", str(db),
                "--manifest", str(db.parent / "manifest.json"), "--rights", str(self.rights),
                "--config", str(self.config),
            ])

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_verse_text_skips_headings_and_notes(self) -> None:
        verses = self.versions.chapter("tst", 43, 1)
        # No space is added at markup boundaries ("beta," and "LORD's"); headings mid-verse are dropped.
        self.assertEqual(verses[0]["text"], "alpha beta, gamma delta continues verse one the LORD's word")
        self.assertEqual((verses[1]["verse"], verses[1]["label"], verses[1]["text"]), (2, "2-3", "range text"))
        self.assertEqual(self.versions.chapter("tst", 43, 3)[0]["text"], "third chapter; chapter two is missing")

    def test_configured_book_names_are_served_per_version(self) -> None:
        self.assertEqual([(b["name"], b["name_local"]) for b in self.versions.books("tst")], [("John", "FIXTURE JOHN")])
        self.assertEqual([b["name_local"] for b in self.versions.books("eng")], [None])

    def test_unknown_book_code_in_config_is_an_error(self) -> None:
        self.config.write_text(json.dumps({"versions": {"tst": {"book_names": {"XYZ": "Nope"}}}}))
        with self.assertRaisesRegex(ValueError, "XYZ"):
            self.build(self.source, self.root / "out4" / "bible_versions.sqlite")

    def test_only_cleared_versions_are_served(self) -> None:
        source = self.root / "src2"
        write_version(source, "n", "NR", "ctd")  # no rights entry: needs_review
        write_version(source, "c", "TST", "ctd")
        db = self.root / "out2" / "bible_versions.sqlite"
        self.assertEqual(self.build(source, db), 0)
        self.assertEqual([v["id"] for v in BibleVersions(db).versions()], ["tst"])

    def test_unreadable_chapter_and_unsafe_abbreviation_do_not_abort(self) -> None:
        source = self.root / "src3"
        write_version(source, "x", "My Bible!", "ctd", JOHN.replace('chapter number="3"', 'chapter number="#"'))
        db = self.root / "out3" / "bible_versions.sqlite"
        self.assertEqual(self.build(source, db), 0)
        manifest = json.loads((db.parent / "manifest.json").read_text())
        self.assertEqual(manifest["versions"][0]["id"], "my-bible")
        self.assertEqual(manifest["versions"][0]["issues"], {"unreadable_chapter_number": 1})

    def test_rebuilt_database_is_reopened(self) -> None:
        self.assertEqual(len(self.versions.versions()), 3)
        self.rights.write_text(json.dumps({"sources": {"bible_tst": {"display": "cleared"}}}))
        self.assertEqual(self.build(self.source, self.db), 0)
        self.assertEqual([v["id"] for v in self.versions.versions()], ["tst"])

    def test_blocked_versions_are_hidden_and_order_puts_english_last(self) -> None:
        self.assertEqual([v["id"] for v in self.versions.versions()], ["tst", "eng", "teb"])

    def test_usfm_strips_markup_notes_and_headings(self) -> None:
        version = self.versions.version("teb")
        self.assertEqual((version["name"], version["language_iso"], version["copyright"]), ("Test English Bible", "eng", "Public domain."))
        self.assertEqual(
            [v["text"] for v in self.versions.chapter("teb", 43, 1)],
            ["In the beginning was the word. Poetry line", "Second verse."],
        )
        self.assertEqual(self.versions.chapter("teb", 43, 2)[0]["text"], "Chapter two.")

    def test_configured_name_keeps_publisher_source(self) -> None:
        version = self.versions.version("tst")
        self.assertEqual((version["name"], version["language_iso"], version["language_name"]), ("Zomi Test", "zom", "Zomi"))
        self.assertEqual((version["source_name"], version["source_language_iso"]), ("Test Version TST", "ctd"))
        self.assertEqual(self.versions.version("eng")["name"], "Test Version ENG")

    def test_books_list_the_chapters_present(self) -> None:
        self.assertEqual(self.versions.books("tst"), [
            {"book_id": 43, "code": "JHN", "name": "John", "name_local": "FIXTURE JOHN", "testament": "new", "chapter_count": 2, "chapters": [1, 3]},
        ])

    def test_manifest_records_skipped_duplicate(self) -> None:
        manifest = json.loads((self.root / "out" / "manifest.json").read_text())
        tst = [row for row in manifest["versions"] if row["id"] == "tst"]
        self.assertEqual(sorted((row["folder"], row["imported"]) for row in tst), [("a", True), ("d", False)])

    def test_search_matches_all_words_in_order_without_rewriting_text(self) -> None:
        total, hits = self.versions.search("tst", "gamma ALPHA")
        self.assertEqual(total, 1)
        self.assertEqual((hits[0]["book_id"], hits[0]["chapter"], hits[0]["verse"]), (43, 1, 1))
        self.assertEqual(hits[0]["text"], "alpha beta, gamma delta continues verse one the LORD's word")
        self.assertEqual(hits[0]["name_local"], "FIXTURE JOHN")

    def test_search_phrase_book_filter_and_paging(self) -> None:
        self.assertEqual(self.versions.search("tst", "beta, gamma", phrase=True)[0], 1)
        self.assertEqual(self.versions.search("tst", "gamma beta", phrase=True)[0], 0)
        self.assertEqual(self.versions.search("tst", "alpha", book_id=1)[0], 0)
        total, page = self.versions.search("tst", "e", limit=1, offset=1)
        self.assertEqual((total, len(page)), (3, 1))
        self.assertEqual(page[0]["verse"], 2)

    def test_search_treats_like_wildcards_literally(self) -> None:
        self.assertEqual(self.versions.search("tst", "%%")[0], 0)
        self.assertEqual(self.versions.search("tst", "a_p")[0], 0)
        self.assertEqual(self.versions.search("tst", "   ")[0], 0)

    def test_search_api(self) -> None:
        client = TestClient(app)
        with patch("routers.bible.get_bible_versions", return_value=self.versions):
            body = client.get("/api/v1/bible/versions/tst/search", params={"q": "range text"}).json()
            self.assertEqual((body["total"], body["results"][0]["label"]), (1, "2-3"))
            self.assertEqual(client.get("/api/v1/bible/versions/hid/search", params={"q": "alpha"}).status_code, 404)
            self.assertEqual(client.get("/api/v1/bible/versions/tst/search", params={"q": "a"}).status_code, 422)
            self.assertEqual(client.get("/api/v1/bible/versions/tst/search", params={"q": "alpha", "limit": 500}).status_code, 422)

    def test_api_routes(self) -> None:
        client = TestClient(app)
        with patch("routers.bible.get_bible_versions", return_value=self.versions):
            listing = client.get("/api/v1/bible/versions").json()
            self.assertEqual([v["id"] for v in listing["versions"]], ["tst", "eng", "teb"])
            chapter = client.get("/api/v1/bible/versions/tst/chapter", params={"book_id": 43, "chapter": 1})
            self.assertEqual(chapter.status_code, 200)
            self.assertEqual(chapter.json()["book"]["chapters"], [1, 3])
            self.assertEqual(
                client.get("/api/v1/bible/versions/tst/chapter", params={"book_id": 43, "chapter": 2}).status_code, 404
            )
            self.assertEqual(client.get("/api/v1/bible/versions/hid/books").status_code, 404)
            self.assertEqual(
                client.get("/api/v1/bible/versions/tst/chapter", params={"book_id": 1, "chapter": 1}).status_code, 404
            )

    def test_unreadable_database_is_503(self) -> None:
        broken = self.root / "broken.sqlite"
        broken.write_bytes(b"not a database")
        client = TestClient(app)
        with patch("routers.bible.get_bible_versions", return_value=BibleVersions(broken)), self.assertLogs("siamsil.bible"):
            self.assertEqual(client.get("/api/v1/bible/versions").status_code, 503)

    def test_missing_database_is_503(self) -> None:
        client = TestClient(app)
        with patch("routers.bible.get_bible_versions", return_value=BibleVersions(self.root / "missing.sqlite")):
            self.assertEqual(client.get("/api/v1/bible/versions").status_code, 503)


if __name__ == "__main__":
    unittest.main()
