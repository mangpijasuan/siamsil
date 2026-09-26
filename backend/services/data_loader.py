from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data"


class DataStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.metadata: dict[str, Any] = {}
        self.bible_verses: list[dict[str, Any]] = []
        self.dictionary: list[dict[str, Any]] = []
        self.daily_use_pairs: list[dict[str, Any]] = []
        self.translation_pairs: list[dict[str, Any]] = []
        # Indexes built at load time for O(1) / fast lookups
        self._bible_by_reference: dict[str, dict[str, Any]] = {}
        self._bible_by_book_chapter: dict[tuple[int, int], list[dict[str, Any]]] = {}
        self._dict_by_id: dict[int, dict[str, Any]] = {}
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return

        self.metadata = self._read_json("metadata.json", default={})
        self.bible_verses = self._read_json("bible_verses.json", default=[])
        self.dictionary = []
        self.daily_use_pairs = self._read_json("daily_use_pairs.json", default=[])
        self.translation_pairs = self._read_json("translation_pairs.json", default=[])

        # Build Bible indexes
        self._bible_by_reference = {
            verse["reference"].lower(): verse for verse in self.bible_verses
        }
        for verse in self.bible_verses:
            key = (verse["book_id"], verse["chapter"])
            self._bible_by_book_chapter.setdefault(key, []).append(verse)

        # Build dictionary ID index
        self._dict_by_id = {entry["id"]: entry for entry in self.dictionary}

        self._loaded = True

    def _read_json(self, filename: str, default: Any | None = None) -> Any:
        path = self.data_dir / filename
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(
                f"Missing {path}. Run ml_pipeline/scripts/import_excel.py first."
            )
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)

    def bible_books(self) -> list[dict[str, Any]]:
        seen_ids: set[int] = set()
        seen_names: set[str] = set()
        books: list[dict[str, Any]] = []
        for verse in self.bible_verses:
            book_id = verse["book_id"]
            name_key = (verse.get("book_english") or "").strip().lower()
            if book_id in seen_ids:
                continue
            # Source data assigns multiple book_ids to the same English title
            if name_key and name_key in seen_names:
                continue
            seen_ids.add(book_id)
            if name_key:
                seen_names.add(name_key)
            books.append(
                {
                    "book_id": book_id,
                    "book_english": verse["book_english"],
                    "book_zomi": verse["book_zomi"],
                    "testament": verse["testament"],
                }
            )
        return books

    def bible_chapter(self, book_id: int, chapter: int) -> list[dict[str, Any]]:
        return self._bible_by_book_chapter.get((book_id, chapter), [])

    def search_bible(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        needle = query.lower()
        results: list[dict[str, Any]] = []
        for verse in self.bible_verses:
            english = (verse.get("english") or "").lower()
            zomi = (verse.get("zomi_iso") or "").lower()
            reference = verse["reference"].lower()
            if needle in english or needle in zomi or needle in reference:
                results.append(verse)
                if len(results) >= limit:
                    break
        return results

    def search_dictionary(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        needle = query.lower()
        results: list[dict[str, Any]] = []
        for entry in self.dictionary:
            english = (entry.get("english") or "").lower()
            zomi = (entry.get("zomi") or "").lower()
            definition = (entry.get("definition") or "").lower()
            if needle in english or needle in zomi or needle in definition:
                results.append(entry)
                if len(results) >= limit:
                    break
        return results

    def get_dictionary_entry(self, entry_id: int) -> dict[str, Any] | None:
        return self._dict_by_id.get(entry_id)

    def search_translate(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        needle = query.lower()
        results: list[dict[str, Any]] = []

        def add_result(source: str, english: str | None, zomi: str | None, extra: dict[str, Any]) -> None:
            if len(results) >= limit:
                return
            if not english or not zomi:
                return
            if needle in english.lower() or needle in zomi.lower():
                results.append(
                    {
                        "source": source,
                        "english": english,
                        "zomi": zomi,
                        **extra,
                    }
                )

        for entry in self.daily_use_pairs:
            add_result(
                "daily_use",
                entry.get("english"),
                entry.get("zomi"),
                {"category": entry.get("category"), "verified": entry.get("verified")},
            )

        for entry in self.translation_pairs:
            add_result(
                "translation_pair",
                entry.get("english"),
                entry.get("zomi"),
                {"id": entry.get("id"), "status": entry.get("status")},
            )

        for verse in self.bible_verses:
            add_result(
                "bible",
                verse.get("english"),
                verse.get("zomi_iso"),
                {"reference": verse.get("reference")},
            )

        return results[:limit]

    def learning_groups(self) -> dict[str, list[dict[str, Any]]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for entry in self.daily_use_pairs:
            category = entry.get("category") or "General"
            groups.setdefault(category, []).append(entry)
        return groups

    def random_verse(self, seed: int | None = None) -> dict[str, Any] | None:
        if not self.bible_verses:
            return None
        import random
        return random.Random(seed).choice(self.bible_verses)

    def word_of_day(self, seed: int | None = None) -> dict[str, Any] | None:
        if not self.dictionary:
            return None
        import random
        return random.Random(seed).choice(self.dictionary)


@lru_cache(maxsize=1)
def get_store() -> DataStore:
    data_dir = Path(os.getenv("SIAMSIL_DATA_DIR", DEFAULT_DATA_DIR))
    store = DataStore(data_dir)
    store.load()
    return store
