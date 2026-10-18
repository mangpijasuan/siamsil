from __future__ import annotations

import sqlite3
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from settings import get_settings

# Only versions whose display right is cleared in data/rights.json are served.
VISIBLE_DISPLAY_STATUSES = {"cleared"}


class BibleVersions:
    """Read-only access to bible_versions.sqlite, built by ml_pipeline/scripts/import_usx_bibles.py."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._connections = threading.local()

    @property
    def available(self) -> bool:
        return self.db_path.exists()

    def _file_identity(self) -> tuple[int, int]:
        stat = self.db_path.stat()
        return stat.st_ino, stat.st_mtime_ns

    def connect(self) -> sqlite3.Connection:
        if not self.available:
            raise FileNotFoundError(
                f"Bible versions database missing at {self.db_path}. "
                "Run python3 ml_pipeline/scripts/import_usx_bibles.py"
            )
        identity = self._file_identity()
        con: sqlite3.Connection | None = getattr(self._connections, "connection", None)
        # The importer replaces the file when it rebuilds; reopen so rights changes apply at once.
        if con is not None and getattr(self._connections, "identity", None) != identity:
            con.close()
            con = None
        if con is None:
            con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA query_only=ON")
            self._connections.connection = con
            self._connections.identity = identity
        return con

    def versions(self) -> list[dict[str, Any]]:
        rows = self.connect().execute(
            """
            SELECT id, abbreviation, name, name_local, description, language_iso, language_name,
                   copyright, source_name, source_language_iso, display_status, book_count, verse_count
            FROM versions ORDER BY sort_order
            """
        )
        return [dict(row) for row in rows if row["display_status"] in VISIBLE_DISPLAY_STATUSES]

    def version(self, version_id: str) -> dict[str, Any] | None:
        return next((v for v in self.versions() if v["id"] == version_id), None)

    def _local_book_names(self, version_id: str) -> dict[int, str]:
        """The version's own book names; databases built before book_names existed have none."""
        con = self.connect()
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'book_names'").fetchone():
            return {}
        rows = con.execute("SELECT book_id, name FROM book_names WHERE version_id = ?", (version_id,))
        return {row["book_id"]: row["name"] for row in rows}

    def books(self, version_id: str) -> list[dict[str, Any]]:
        rows = self.connect().execute(
            """
            SELECT b.book_id, b.code, b.name, b.testament, GROUP_CONCAT(c.chapter) AS chapters
            FROM (SELECT DISTINCT book_id, chapter FROM verses WHERE version_id = ? ORDER BY book_id, chapter) c
            JOIN books b ON b.book_id = c.book_id
            GROUP BY b.book_id ORDER BY b.book_id
            """,
            (version_id,),
        )
        local_names = self._local_book_names(version_id)
        books = []
        for row in rows:
            chapters = sorted(int(number) for number in row["chapters"].split(","))
            books.append({
                "book_id": row["book_id"], "code": row["code"], "name": row["name"],
                "name_local": local_names.get(row["book_id"]), "testament": row["testament"],
                "chapter_count": len(chapters), "chapters": chapters,
            })
        return books

    def chapter(self, version_id: str, book_id: int, chapter: int) -> list[dict[str, Any]]:
        rows = self.connect().execute(
            "SELECT verse, label, text FROM verses WHERE version_id = ? AND book_id = ? AND chapter = ? ORDER BY verse",
            (version_id, book_id, chapter),
        )
        return [dict(row) for row in rows]

    def search(
        self, version_id: str, query: str, *, book_id: int | None = None, phrase: bool = False,
        limit: int = 20, offset: int = 0,
    ) -> tuple[int, list[dict[str, Any]]]:
        """Verses containing every word of `query` (or the exact phrase), in canonical order.

        Matching is a case-insensitive substring match on the stored text; nothing is rewritten.
        Returns (total matches, one page of results).
        """
        terms = [query.strip()] if phrase else query.split()
        terms = [term for term in terms if term][:MAX_SEARCH_TERMS]
        if not terms:
            return 0, []
        # Fixed SQL text: every term slot is a bound LIKE pattern; unused slots match anything ("%").
        patterns = [f"%{_escape_like(term)}%" for term in terms] + ["%"] * (MAX_SEARCH_TERMS - len(terms))
        params: list[Any] = [version_id, book_id, book_id, *patterns]
        con = self.connect()
        total = con.execute(SEARCH_COUNT_SQL, params).fetchone()[0]
        rows = con.execute(SEARCH_PAGE_SQL, [*params, limit, offset])
        local_names = self._local_book_names(version_id)
        results = [{**dict(row), "name_local": local_names.get(row["book_id"])} for row in rows]
        return total, results


MAX_SEARCH_TERMS = 8

# One LIKE per term slot (MAX_SEARCH_TERMS of them); the query text never contains user input.
_SEARCH_WHERE = """
    v.version_id = ?
    AND (? IS NULL OR v.book_id = ?)
    AND v.text LIKE ? ESCAPE '\\' AND v.text LIKE ? ESCAPE '\\'
    AND v.text LIKE ? ESCAPE '\\' AND v.text LIKE ? ESCAPE '\\'
    AND v.text LIKE ? ESCAPE '\\' AND v.text LIKE ? ESCAPE '\\'
    AND v.text LIKE ? ESCAPE '\\' AND v.text LIKE ? ESCAPE '\\'
"""
SEARCH_COUNT_SQL = "SELECT COUNT(*) FROM verses v WHERE" + _SEARCH_WHERE
SEARCH_PAGE_SQL = (
    "SELECT v.book_id, b.code, b.name, v.chapter, v.verse, v.label, v.text"
    " FROM verses v JOIN books b ON b.book_id = v.book_id WHERE"
    + _SEARCH_WHERE
    + " ORDER BY v.book_id, v.chapter, v.verse LIMIT ? OFFSET ?"
)


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@lru_cache(maxsize=1)
def get_bible_versions() -> BibleVersions:
    return BibleVersions(get_settings().bible_versions_db)
