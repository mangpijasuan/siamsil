from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "processed" / "language" / "siamsil_language.sqlite"

FTS_UNSAFE = re.compile(r'["\'*:^(){}[\]~-]')


def fts_match(query: str) -> str | None:
    cleaned = FTS_UNSAFE.sub(" ", query)
    tokens = [token for token in cleaned.split() if token]
    if not tokens:
        return None
    parts = [f'"{token}"' for token in tokens[:-1]]
    parts.append(f'"{tokens[-1]}"*')
    return " AND ".join(parts)


def split_zomi_definition(text: str | None) -> tuple[str | None, str | None]:
    """Split 'gloss; longer Zomi definition' without inventing English text."""
    value = (text or "").strip()
    if not value:
        return None, None
    if ";" in value:
        gloss, rest = value.split(";", 1)
        gloss = gloss.strip().rstrip(".")
        rest = rest.strip()
        if gloss and rest:
            return gloss, rest
    return value, value


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


class LanguageEngine:
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
                    f"Language database missing at {self.db_path}. "
                    "Run python3 ml_pipeline/scripts/build_language_db.py"
                )
            con = sqlite3.connect(
                f"file:{self.db_path}?mode=ro",
                uri=True,
            )
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA query_only=ON")
            self._connections.connection = con
        return con

    def counts(self) -> dict[str, int]:
        if not self.available:
            return {"dictionary_entries": 0, "parallel_sentences": 0, "verified_dictionary": 0}
        con = self.connect()
        dictionary = con.execute("SELECT COUNT(*) FROM dictionary_entries").fetchone()[0]
        verified = con.execute(
            "SELECT COUNT(*) FROM dictionary_entries WHERE verification_status = 'verified'"
        ).fetchone()[0]
        parallel = con.execute("SELECT COUNT(*) FROM parallel_sentences").fetchone()[0]
        return {
            "dictionary_entries": dictionary,
            "verified_dictionary": verified,
            "parallel_sentences": parallel,
        }

    def letter_counts(self) -> list[dict[str, Any]]:
        con = self.connect()
        rows = con.execute(
            """
            SELECT letter, COUNT(*) AS count
            FROM dictionary_entries
            WHERE letter IS NOT NULL AND letter != ''
            GROUP BY letter
            ORDER BY letter
            """
        ).fetchall()
        return [{"letter": row["letter"], "count": row["count"]} for row in rows]

    def get_entry(self, entry_id: int, *, include_examples: bool = False) -> dict[str, Any] | None:
        con = self.connect()
        row = con.execute("SELECT * FROM dictionary_entries WHERE id = ?", (entry_id,)).fetchone()
        entry = self._present_entry(row)
        if entry and include_examples:
            entry["examples"] = self.search_parallel(entry["english"], limit=3)
        return entry

    def word_of_day(self, seed: int) -> dict[str, Any] | None:
        con = self.connect()
        total = con.execute(
            "SELECT COUNT(*) FROM dictionary_entries WHERE definition IS NOT NULL AND definition != ''"
        ).fetchone()[0]
        if not total:
            return None
        offset = seed % total
        row = con.execute(
            """
            SELECT * FROM dictionary_entries
            WHERE definition IS NOT NULL AND definition != ''
            ORDER BY id
            LIMIT 1 OFFSET ?
            """,
            (offset,),
        ).fetchone()
        return self._present_entry(row)

    def search_dictionary(
        self,
        query: str = "",
        *,
        letter: str | None = None,
        direction: str = "en-zom",
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        con = self.connect()
        limit = min(max(limit, 1), 100)
        offset = max(offset, 0)
        params: list[Any] = []
        where: list[str] = []

        if letter:
            where.append("letter = ?")
            params.append(letter.upper()[:1])

        if query.strip():
            needle = query.strip().lower()
            found: list[sqlite3.Row] = []
            seen: set[int] = set()

            def add_rows(rows: list[sqlite3.Row]) -> None:
                for row in rows:
                    if row["id"] in seen:
                        continue
                    seen.add(row["id"])
                    found.append(row)

            letter_sql = " AND letter = ?" if letter else ""
            letter_params: list[Any] = [letter.upper()[:1]] if letter else []

            if direction != "zom-en":
                add_rows(
                    con.execute(
                        f"""
                        SELECT * FROM dictionary_entries
                        WHERE normalized_word = ?{letter_sql}
                        ORDER BY flagged ASC, id
                        LIMIT ?
                        """,
                        [needle, *letter_params, limit],
                    ).fetchall()
                )
                if len(found) < limit:
                    add_rows(
                        con.execute(
                            f"""
                            SELECT * FROM dictionary_entries
                            WHERE normalized_word LIKE ?{letter_sql}
                            ORDER BY length(source_word) ASC, flagged ASC, id
                            LIMIT ?
                            """,
                            [f"{needle}%", *letter_params, limit],
                        ).fetchall()
                    )

            remaining = limit - len(found)
            match = fts_match(query)
            if remaining > 0 and match:
                exclude = ""
                fts_params: list[Any] = [match]
                if seen:
                    exclude = f" AND e.id NOT IN ({','.join('?' for _ in seen)})"
                    fts_params.extend(seen)
                if letter:
                    exclude += " AND e.letter = ?"
                    fts_params.append(letter.upper()[:1])
                if direction == "zom-en":
                    exclude += " AND e.definition IS NOT NULL"
                fts_params.extend([remaining, offset if not found else 0])
                add_rows(
                    con.execute(
                        f"""
                        SELECT e.*
                        FROM dictionary_fts
                        JOIN dictionary_entries e ON e.id = dictionary_fts.rowid
                        WHERE dictionary_fts MATCH ?{exclude}
                        ORDER BY e.flagged ASC, e.confidence DESC, e.id
                        LIMIT ? OFFSET ?
                        """,
                        fts_params,
                    ).fetchall()
                )

            if found:
                return [self._present_entry(row) for row in found[:limit]]

            if direction == "zom-en":
                where.append("lower(definition) LIKE ?")
                params.append(f"%{needle}%")
            else:
                where.append("(normalized_word LIKE ? OR lower(source_word) LIKE ? OR lower(definition) LIKE ?)")
                params.extend([f"{needle}%", f"{needle}%", f"%{needle}%"])

        clause = f"WHERE {' AND '.join(where)}" if where else ""
        order = "ORDER BY flagged ASC, source_word COLLATE NOCASE, id"
        rows = con.execute(
            f"SELECT * FROM dictionary_entries {clause} {order} LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        return [self._present_entry(row) for row in rows if row]

    def suggest_dictionary(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        needle = query.strip().lower()
        if not needle:
            return []
        con = self.connect()
        rows = con.execute(
            """
            SELECT id, source_word, part_of_speech, definition, verification_status
            FROM dictionary_entries
            WHERE normalized_word LIKE ? OR lower(source_word) LIKE ?
            ORDER BY length(source_word) ASC, flagged ASC, id
            LIMIT ?
            """,
            (f"{needle}%", f"{needle}%", min(max(limit, 1), 20)),
        ).fetchall()
        return [dict(row) for row in rows]

    def search_parallel(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        match = fts_match(query)
        if not match:
            return []
        con = self.connect()
        limit = min(max(limit, 1), 50)
        exact = con.execute(
            """
            SELECT * FROM parallel_sentences
            WHERE lower(normalized_source_text) = lower(?)
               OR lower(normalized_target_text) = lower(?)
            ORDER BY quality_score DESC, id
            LIMIT ?
            """,
            (query.strip(), query.strip(), limit),
        ).fetchall()
        remaining = limit - len(exact)
        fts_rows: list[sqlite3.Row] = []
        if remaining > 0:
            exact_ids = {row["id"] for row in exact}
            placeholders = ",".join("?" for _ in exact_ids) or "NULL"
            sql = f"""
                SELECT p.*
                FROM parallel_fts
                JOIN parallel_sentences p ON p.id = parallel_fts.rowid
                WHERE parallel_fts MATCH ?
                  AND p.quality_score >= 0.5
            """
            params: list[Any] = [match]
            if exact_ids:
                sql += f" AND p.id NOT IN ({placeholders})"
                params.extend(exact_ids)
            sql += " ORDER BY p.quality_score DESC, p.id LIMIT ?"
            params.append(remaining)
            fts_rows = con.execute(sql, params).fetchall()
        return [self._present_pair(row, exact=row["id"] in {r["id"] for r in exact}) for row in [*exact, *fts_rows]]

    def _present_entry(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        data = row_to_dict(row)
        if not data:
            return None
        zomi, definition = split_zomi_definition(data["definition"])
        return {
            "id": data["id"],
            "english": data["source_word"],
            "source_word": data["source_word"],
            "normalized_word": data["normalized_word"],
            "language": data["language"],
            "dialect": data["dialect"],
            "part_of_speech": data["part_of_speech"],
            "part_of_speech_full": data["part_of_speech_full"],
            "zomi": zomi,
            "definition": definition,
            "pronunciation": data["pronunciation"],
            "usage_notes": data["usage_notes"],
            "domain": None,
            "source": data["source"],
            "source_reference": data["source_reference"],
            "confidence": data["confidence"],
            "verification_status": data["verification_status"],
            "verified": data["verification_status"] == "verified",
            "flagged": bool(data["flagged"]),
            "suggested_correction": data["suggested_correction"] or None,
            "letter": data["letter"],
            "version": data["version"],
        }

    def _present_pair(self, row: sqlite3.Row, *, exact: bool) -> dict[str, Any]:
        flags = json.loads(row["quality_flags"] or "[]")
        return {
            "id": row["id"],
            "source": "parallel_corpus",
            "english": row["normalized_source_text"],
            "zomi": row["normalized_target_text"],
            "raw_english": row["raw_source_text"],
            "raw_zomi": row["raw_target_text"],
            "model": row["model"],
            "source_reference": row["source_reference"],
            "quality_score": row["quality_score"],
            "quality_flags": flags,
            "verified": bool(row["verified"]),
            "dataset_split": row["dataset_split"],
            "exact": exact,
            "label": "Machine-translated example (unverified)",
        }


@lru_cache(maxsize=1)
def get_engine() -> LanguageEngine:
    path = Path(os.getenv("SIAMSIL_LANGUAGE_DB", DEFAULT_DB))
    return LanguageEngine(path)
