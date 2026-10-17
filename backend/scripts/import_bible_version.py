"""Build one immutable, read-only Bible edition release from licensed JSONL text.

Each input line: {"book_id": 1, "chapter": 1, "verse": 1, "text": "..."}.
The source book IDs are mapped to Siamsil's canonical 66-book IDs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "backend" / "data" / "bible_verses.json"
DEFAULT_OUTPUT = ROOT / "data" / "versions" / "scripture"
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def canonical_books() -> dict[int, dict[str, object]]:
    with SOURCE.open(encoding="utf-8") as handle:
        rows = json.load(handle)
    first_by_name: dict[tuple[str, str], int] = {}
    by_id: dict[int, dict[str, object]] = {}
    for row in rows:
        key = (row["testament"].strip().lower(), row["book_english"].strip().lower())
        first_by_name.setdefault(key, row["book_id"])
        by_id[row["book_id"]] = {
            "book_id": first_by_name[key], "book_english": row["book_english"],
            "book_zomi": row["book_zomi"], "testament": row["testament"],
        }
    return by_id


def canonical_chapters(books: dict[int, dict[str, object]]) -> set[tuple[int, int]]:
    with SOURCE.open(encoding="utf-8") as handle:
        rows = json.load(handle)
    return {(int(books[row["book_id"]]["book_id"]), row["chapter"]) for row in rows}


def import_version(args: argparse.Namespace) -> tuple[Path, int]:
    if not SLUG.fullmatch(args.id) or args.id.startswith("supplied-"):
        raise ValueError("Version ID must be a lowercase slug and cannot use the supplied- prefix")
    if args.approved_for_display and not args.rights_evidence:
        raise ValueError("Publishing requires --rights-evidence with a reviewable permission reference")
    if not all(isinstance(value, str) and value.strip() for value in
               (args.name, args.language, args.abbreviation, args.attribution)):
        raise ValueError("Version name, language, abbreviation, and attribution are required")
    if not args.input.is_file():
        raise ValueError(f"Input file does not exist: {args.input}")
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{args.id}.sqlite"
    if target.exists():
        raise FileExistsError(f"Release already exists: {target}. Use a new version ID.")

    books = canonical_books()
    fd, temp_name = tempfile.mkstemp(prefix=f".{args.id}-", suffix=".sqlite", dir=output_dir)
    os.close(fd)
    temporary = Path(temp_name)
    count = 0
    covered_chapters: set[tuple[int, int]] = set()
    try:
        with sqlite3.connect(temporary) as connection:
            connection.executescript("""
                CREATE TABLE version (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, language TEXT NOT NULL,
                    abbreviation TEXT NOT NULL, edition_group TEXT NOT NULL,
                    separate_edition INTEGER NOT NULL, rights_status TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    attribution TEXT NOT NULL, rights_evidence TEXT,
                    imported_at TEXT NOT NULL
                );
                CREATE TABLE verses (
                    book_id INTEGER NOT NULL, book_english TEXT NOT NULL,
                    book_zomi TEXT NOT NULL, testament TEXT NOT NULL,
                    chapter INTEGER NOT NULL, verse INTEGER NOT NULL,
                    reference TEXT NOT NULL, text TEXT NOT NULL,
                    PRIMARY KEY (book_id, chapter, verse)
                );
                CREATE INDEX ix_verses_reference ON verses (reference);
            """)
            connection.execute(
                "INSERT INTO version VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (args.id, args.name, args.language, args.abbreviation, args.id, 1,
                 "approved" if args.approved_for_display else "pending", args.scope, args.attribution,
                 args.rights_evidence, datetime.now(timezone.utc).isoformat()),
            )
            with args.input.open(encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    try:
                        item = json.loads(line)
                        book_id, chapter, verse = item["book_id"], item["chapter"], item["verse"]
                        content = item["text"]
                        if (type(book_id) is not int or book_id not in books or type(chapter) is not int
                                or chapter < 1 or type(verse) is not int or verse < 1
                                or not isinstance(content, str) or not content.strip()):
                            raise ValueError("invalid book ID, chapter, verse, or text")
                        book = books[book_id]
                        connection.execute(
                            "INSERT INTO verses VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (book["book_id"], book["book_english"], book["book_zomi"],
                             book["testament"], chapter, verse,
                             f"{book['book_english']} {chapter}:{verse}", content.strip()),
                        )
                        count += 1
                        covered_chapters.add((int(book["book_id"]), chapter))
                    except (ValueError, KeyError, TypeError, sqlite3.IntegrityError) as exc:
                        raise ValueError(f"Invalid or duplicate verse on line {line_number}: {exc}") from exc
            if count == 0:
                raise ValueError("Edition contains no verses")
            if args.scope == "full":
                missing = canonical_chapters(books) - covered_chapters
                if missing:
                    raise ValueError(f"Full edition is missing {len(missing)} canonical chapters")
        if target.exists():
            raise FileExistsError(f"Release already exists: {target}")
        temporary.replace(target)
        return target, count
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Licensed UTF-8 JSONL verse file")
    parser.add_argument("--id", required=True, help="Immutable edition/release slug")
    parser.add_argument("--name", required=True)
    parser.add_argument("--language", required=True, help="BCP-47 language code")
    parser.add_argument("--abbreviation", required=True)
    parser.add_argument("--attribution", required=True)
    parser.add_argument("--scope", choices=("full", "partial"), required=True,
                        help="Full requires all 66-book canonical chapters; partial is labeled in the API")
    parser.add_argument("--rights-evidence", help="Permission record or license reference")
    parser.add_argument("--approved-for-display", action="store_true", help="Human attestation: display rights reviewed")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    target, count = import_version(args)
    print(f"Imported {count} verses into {target} ({'published' if args.approved_for_display else 'pending'})")


if __name__ == "__main__":
    main()
