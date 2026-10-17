from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.data_loader import DataStore  # noqa: E402


class BibleDataTests(unittest.TestCase):
    def test_split_source_ids_share_one_book_and_all_chapters(self) -> None:
        verses = [
            {"book_id": 5, "book_english": "Deuteronomy", "book_zomi": "Thu Hilhkikna",
             "testament": "Old Testament", "chapter": 1, "verse": 1, "reference": "Deuteronomy 1:1"},
            {"book_id": 6, "book_english": "Deuteronomy", "book_zomi": "Thu Hilhkikna",
             "testament": "Old Testament", "chapter": 18, "verse": 1, "reference": "Deuteronomy 18:1"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / "bible_verses.json").write_text(json.dumps(verses), encoding="utf-8")
            store = DataStore(data_dir)
            store.load()
            books = store.bible_books()
            self.assertEqual(len(books), 1)
            self.assertEqual(books[0]["book_id"], 5)
            self.assertEqual(books[0]["chapter_count"], 18)
            self.assertEqual(store.bible_chapter(5, 18), [verses[1]])
            self.assertEqual(store.bible_chapter(6, 18), [verses[1]])
            self.assertEqual(store.bible_chapter(5, 19), [])


if __name__ == "__main__":
    unittest.main()
