from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from services.data_loader import DataStore


BUILTIN_TEXTS: tuple[dict[str, Any], ...] = (
    {"id": "supplied-zomi", "name": "Zomi (standardized)", "language": "zom", "abbreviation": "Zomi", "edition_group": "siamsil-supplied", "separate_edition": False, "rights_status": "unverified", "scope": "full", "attribution": "Source edition unidentified"},
    {"id": "supplied-zomi-source", "name": "Zomi (source spelling)", "language": "zom", "abbreviation": "Zomi source", "edition_group": "siamsil-supplied", "separate_edition": False, "rights_status": "unverified", "scope": "full", "attribution": "Same supplied Zomi text; original spelling"},
    {"id": "supplied-english", "name": "English (supplied text)", "language": "en", "abbreviation": "English", "edition_group": "siamsil-supplied", "separate_edition": False, "rights_status": "unverified", "scope": "full", "attribution": "Source edition unidentified"},
)
TEXT_FIELDS = {
    "supplied-zomi": "zomi_iso",
    "supplied-zomi-source": "zomi_original",
    "supplied-english": "english",
}
VERSION_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class ScriptureCatalog:
    """Read published immutable edition files; leave mutable editorial state elsewhere."""

    def __init__(self, releases_dir: Path, source: DataStore) -> None:
        self.releases_dir = releases_dir
        self.source = source

    def _release_path(self, version_id: str) -> Path | None:
        if not VERSION_ID.fullmatch(version_id):
            return None
        path = self.releases_dir / f"{version_id}.sqlite"
        return path if path.is_file() else None

    def _connect(self, path: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def versions(self) -> list[dict[str, Any]]:
        versions = [dict(item) for item in BUILTIN_TEXTS]
        if not self.releases_dir.is_dir():
            return versions
        for path in sorted(self.releases_dir.glob("*.sqlite")):
            if not VERSION_ID.fullmatch(path.stem):
                continue
            try:
                with self._connect(path) as connection:
                    row = connection.execute("SELECT id, name, language, abbreviation, edition_group, separate_edition, rights_status, scope, attribution FROM version LIMIT 1").fetchone()
                if row and row["id"] == path.stem and row["rights_status"] == "approved":
                    versions.append({**dict(row), "separate_edition": bool(row["separate_edition"])})
            except sqlite3.DatabaseError:
                continue
        return versions

    def version(self, version_id: str) -> dict[str, Any] | None:
        return next((item for item in self.versions() if item["id"] == version_id), None)

    def books(self, version_id: str) -> list[dict[str, Any]]:
        if version_id in TEXT_FIELDS:
            return self.source.bible_books()
        path = self._release_path(version_id)
        if path is None or self.version(version_id) is None:
            return []
        with self._connect(path) as connection:
            rows = connection.execute(
                "SELECT book_id, book_english, book_zomi, testament, MAX(chapter) AS chapter_count "
                "FROM verses GROUP BY book_id, book_english, book_zomi, testament ORDER BY book_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def chapter(self, version_id: str, book_id: int, chapter: int) -> list[dict[str, Any]]:
        if version_id in TEXT_FIELDS:
            field = TEXT_FIELDS[version_id]
            return [
                {"book_id": book_id, "book_english": row["book_english"], "book_zomi": row["book_zomi"],
                 "testament": row["testament"], "chapter": row["chapter"], "verse": row["verse"],
                 "reference": row["reference"], "text": row.get(field) or ""}
                for row in self.source.bible_chapter(book_id, chapter) if row.get(field)
            ]
        path = self._release_path(version_id)
        if path is None or self.version(version_id) is None:
            return []
        with self._connect(path) as connection:
            rows = connection.execute(
                "SELECT book_id, book_english, book_zomi, testament, chapter, verse, reference, text "
                "FROM verses WHERE book_id = ? AND chapter = ? ORDER BY verse", (book_id, chapter)
            ).fetchall()
        return [dict(row) for row in rows]

    def search(self, version_id: str, query: str, limit: int) -> list[dict[str, Any]]:
        if version_id in TEXT_FIELDS:
            field = TEXT_FIELDS[version_id]
            needle = query.casefold()
            results: list[dict[str, Any]] = []
            for row in self.source.bible_verses:
                content = row.get(field) or ""
                if needle in content.casefold() or needle in row["reference"].casefold():
                    results.append({
                        "book_id": row["book_id"], "book_english": row["book_english"],
                        "book_zomi": row["book_zomi"], "testament": row["testament"],
                        "chapter": row["chapter"], "verse": row["verse"],
                        "reference": row["reference"], "text": content,
                    })
                    if len(results) >= limit:
                        break
            return results
        path = self._release_path(version_id)
        if path is None or self.version(version_id) is None:
            return []
        with self._connect(path) as connection:
            rows = connection.execute(
                "SELECT book_id, book_english, book_zomi, testament, chapter, verse, reference, text "
                "FROM verses WHERE instr(lower(text), lower(?)) > 0 OR instr(lower(reference), lower(?)) > 0 "
                "ORDER BY book_id, chapter, verse LIMIT ?", (query, query, limit)
            ).fetchall()
        return [dict(row) for row in rows]
