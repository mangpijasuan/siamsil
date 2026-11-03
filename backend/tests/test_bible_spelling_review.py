"""Synthetic tests for the Bible spelling reviewer export."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "scripts"))
from bible_spelling_review import scan, write_csv


class ReviewExportTests(unittest.TestCase):
    def test_candidates_are_unverified_and_have_no_verse_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            db = folder / "test.sqlite"
            con = sqlite3.connect(db)
            con.execute("CREATE TABLE versions(id TEXT, display_status TEXT, language_iso TEXT)")
            con.execute("CREATE TABLE verses(version_id TEXT, book_id INT, chapter INT, verse INT, text TEXT)")
            con.execute("INSERT INTO versions VALUES ('zomi','cleared','ctd')")
            con.execute("INSERT INTO verses VALUES ('zomi',1,1,1,'qa qo')")
            con.commit()
            con.close()
            checks = folder / "checks.json"
            checks.write_text(json.dumps({"checks": [{"id": "example", "variants": [["qa qo", "qaqo"]]}]}))
            rows = scan(db, checks, 10)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "needs_human_review")
            self.assertNotIn("text", rows[0])
            output = folder / "review.csv"
            write_csv(rows, output)
            self.assertTrue(output.exists())
            with self.assertRaises(FileExistsError):
                write_csv(rows, output)


if __name__ == "__main__":
    unittest.main()
