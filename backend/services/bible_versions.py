from __future__ import annotations

import sqlite3
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from settings import get_settings

# Versions whose display right is blocked are never served.
HIDDEN_DISPLAY_STATUSES = {"blocked"}


class BibleVersions:
    """Read-only access to bible_versions.sqlite, built by ml_pipeline/scripts/import_usx_bibles.py."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._connections = threading.local()

    @property
    def available(self) -> bool:
        return self.db_path.exists()

    def connect(self) -> sqlite3.Connection:
        con: sqlite3.Connection | None = getattr(self._connections, "connection", None)
        if con is None:
            if not self.available:
                raise FileNotFoundError(
                    f"Bible versions database missing at {self.db_path}. "
                    "Run python3 ml_pipeline/scripts/import_usx_bibles.py"
                )
            con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA query_only=ON")
            self._connections.connection = con
        return con

    def versions(self) -> list[dict[str, Any]]:
        rows = self.connect().execute(
            """
            SELECT id, abbreviation, name, name_local, description, language_iso, language_name,
                   copyright, source_name, source_language_iso, display_status, book_count, verse_count
            FROM versions ORDER BY sort_order
            """
        )
        return [dict(row) for row in rows if row["display_status"] not in HIDDEN_DISPLAY_STATUSES]

    def version(self, version_id: str) -> dict[str, Any] | None:
        return next((v for v in self.versions() if v["id"] == version_id), None)

    def books(self, version_id: str) -> list[dict[str, Any]]:
        rows = self.connect().execute(
            """
            SELECT b.book_id, b.code, b.name, b.testament, MAX(v.chapter) AS chapter_count
            FROM verses v JOIN books b ON b.book_id = v.book_id
            WHERE v.version_id = ?
            GROUP BY b.book_id ORDER BY b.book_id
            """,
            (version_id,),
        )
        return [dict(row) for row in rows]

    def chapter(self, version_id: str, book_id: int, chapter: int) -> list[dict[str, Any]]:
        rows = self.connect().execute(
            "SELECT verse, label, text FROM verses WHERE version_id = ? AND book_id = ? AND chapter = ? ORDER BY verse",
            (version_id, book_id, chapter),
        )
        return [dict(row) for row in rows]


@lru_cache(maxsize=1)
def get_bible_versions() -> BibleVersions:
    return BibleVersions(get_settings().bible_versions_db)
