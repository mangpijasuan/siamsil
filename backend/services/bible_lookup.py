"""Bible passages for Siamsil AI, read from the same bible_versions.sqlite as the Bible reader.

A message names a passage ("John 3:16", "Johan 3:16-17", "Laisiangtho Late 23") or asks for words in a
verse. The Zomi text comes from the first Zomi version whose display right is cleared (TDB 2011), and the
English beside it from the World English Bible. Nothing is translated or rewritten.
"""
from __future__ import annotations

import re
from typing import Any

from services.bible_versions import BibleVersions

# Words that ask for the Bible rather than name a book or a search term.
BIBLE_WORDS = {
    "laisiangtho", "bible", "verse", "verses", "chapter", "show", "read", "me", "the", "in", "a", "what",
    "does", "say", "says", "find", "where", "is", "about", "of", "please",
}
BIBLE_REQUEST = {"laisiangtho", "bible", "verse", "verses", "chapter"}
ENGLISH_ORDER = ("web", "kjv")
MAX_VERSES = 3

REFERENCE = re.compile(
    r"(?P<book>(?:[1-3]\s*)?[^\W\d_][\w' .]*?)\s*(?P<chapter>\d{1,3})"
    r"(?:\s*[:.]\s*(?P<verse>\d{1,3})(?:\s*[-–]\s*(?P<end>\d{1,3}))?)?(?!\d)",
)


def _key(name: str) -> str:
    return re.sub(r"[^0-9a-z]", "", name.lower())


class BibleLookup:
    def __init__(self, versions: BibleVersions) -> None:
        self.versions = versions

    def _chosen(self) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        visible = self.versions.versions()
        zomi = next((v for v in visible if v["language_iso"] == "ctd"), None)
        english = next((v for wanted in ENGLISH_ORDER for v in visible if v["id"] == wanted), None) or next(
            (v for v in visible if v["language_iso"] == "eng"), None
        )
        return zomi, english

    def _book_index(self, version_ids: list[str]) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        for version_id in version_ids:
            for book in self.versions.books(version_id):
                for name in (book["name"], book["code"], book["name_local"]):
                    if name:
                        index.setdefault(_key(name), book)
        return index

    def find_reference(self, message: str, index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
        asks_for_bible = any(word in BIBLE_REQUEST for word in re.findall(r"\w+", message.lower()))
        for match in REFERENCE.finditer(message):
            words = match.group("book").split()
            # Drop leading request words ("Laisiangtho", "show me") until the rest names a book.
            for start in range(len(words)):
                name = " ".join(words[start:])
                book = index.get(_key(name))
                # Book names that are also words ("late", "mark", "job") count only as a reference:
                # with a verse, a capital letter or number first, or a request for the Bible.
                if book and (match.group("verse") or asks_for_bible or not name[0].islower()):
                    chapter = int(match.group("chapter"))
                    if chapter not in book["chapters"]:
                        return None
                    verse = int(match.group("verse")) if match.group("verse") else None
                    end = int(match.group("end")) if match.group("end") else verse
                    return {"book": book, "chapter": chapter, "verse": verse, "end": end}
        return None

    def passage(self, message: str, *, search: bool = True) -> tuple[str, list[dict[str, Any]]]:
        """("reference", "search" or "none", verses): a named passage, else verses with the message's words."""
        if not self.versions.available:
            return "none", []
        zomi, english = self._chosen()
        if zomi is None:
            return "none", []
        ids = [zomi["id"], *([english["id"]] if english else [])]
        reference = self.find_reference(message, self._book_index(ids))
        if reference:
            return "reference", self._verses(zomi, english, reference)
        terms = [word for word in re.findall(r"[\w'’-]+", message) if word.lower() not in BIBLE_WORDS]
        if not search or not terms:
            return "none", []
        for version in (zomi, english):
            if version is None:
                continue
            _, hits = self.versions.search(version["id"], " ".join(terms), limit=MAX_VERSES)
            if hits:
                return "search", [
                    self._verse(zomi, english, hit["book_id"], hit["chapter"], hit["verse"]) for hit in hits
                ]
        return "none", []

    def search_side(self, query: str, language: str, limit: int = MAX_VERSES) -> list[dict[str, Any]]:
        """Verses whose Zomi ("ctd") or English ("eng") text holds the query as a phrase, for Translate."""
        if not self.versions.available or not query.strip():
            return []
        zomi, english = self._chosen()
        version = zomi if language == "ctd" else english
        if zomi is None or version is None:
            return []
        _, hits = self.versions.search(version["id"], query, phrase=True, limit=limit)
        return [self._verse(zomi, english, hit["book_id"], hit["chapter"], hit["verse"]) for hit in hits]

    def _verses(self, zomi: dict, english: dict | None, ref: dict[str, Any]) -> list[dict[str, Any]]:
        book = ref["book"]
        rows = self.versions.chapter(zomi["id"], book["book_id"], ref["chapter"])
        first = ref["verse"] or 1
        last = min(ref["end"] or first, first + MAX_VERSES - 1) if ref["verse"] else first + MAX_VERSES - 1
        wanted = [row["verse"] for row in rows if first <= row["verse"] <= last]
        return [self._verse(zomi, english, book["book_id"], ref["chapter"], verse) for verse in wanted]

    def _verse(self, zomi: dict, english: dict | None, book_id: int, chapter: int, verse: int) -> dict[str, Any]:
        zomi_books = {b["book_id"]: b for b in self.versions.books(zomi["id"])}
        book = zomi_books.get(book_id, {})
        local, name = book.get("name_local"), book.get("name", "")

        def text(version: dict | None) -> str | None:
            if version is None:
                return None
            row = next((r for r in self.versions.chapter(version["id"], book_id, chapter) if r["verse"] == verse), None)
            return row["text"] if row else None

        place = f"{chapter}:{verse}"
        reference = f"{local} {place} ({name} {place})" if local and local != name else f"{name} {place}"
        source = zomi["name"] + (f" · {english['name']}" if english else "")
        return {"reference": reference, "zomi": text(zomi), "english": text(english), "source": source,
                "book_id": book_id, "book_name": name, "book_local": local, "testament": book.get("testament", ""),
                "chapter": chapter, "verse": verse}

    def daily(self, seed: int) -> dict[str, Any] | None:
        """One verse of the Zomi version, the same all day for the same seed."""
        if not self.versions.available:
            return None
        zomi, english = self._chosen()
        if zomi is None:
            return None
        con = self.versions.connect()
        count = con.execute("SELECT COUNT(*) FROM verses WHERE version_id = ?", (zomi["id"],)).fetchone()[0]
        if not count:
            return None
        row = con.execute(
            "SELECT book_id, chapter, verse FROM verses WHERE version_id = ? ORDER BY book_id, chapter, verse "
            "LIMIT 1 OFFSET ?", (zomi["id"], seed % count)).fetchone()
        return self._verse(zomi, english, row["book_id"], row["chapter"], row["verse"])

    def search_words(self, query: str, limit: int = MAX_VERSES) -> list[dict[str, Any]]:
        """Verses holding the query, in the Zomi text first, else in the English."""
        for language in ("ctd", "eng"):
            verses = [verse for verse in self.search_side(query, language, limit) if verse["zomi"]]
            if verses:
                return verses
        return []


def as_bible_verse(verse: dict[str, Any]) -> dict[str, Any]:
    """A verse in the older BibleVerse shape that /bible/random and /search return.

    zomi_original and zomi_iso both carry the cleared Zomi version's text (TDB 2011); the names
    come from the workbook Bible this shape was made for, which is no longer served.
    """
    return {
        "testament": verse["testament"], "book_id": verse["book_id"], "book_english": verse["book_name"],
        "book_zomi": verse["book_local"] or verse["book_name"], "chapter": verse["chapter"],
        "verse": verse["verse"], "reference": verse["reference"], "english": verse["english"],
        "zomi_original": verse["zomi"], "zomi_iso": verse["zomi"], "changes_applied": None,
    }
