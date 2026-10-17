#!/usr/bin/env python3
"""Import Bible versions from USX folders into a read-only SQLite database.

Each version is a folder holding `metadata.xml` (Digital Bible Library format) and
`USX_1/` or `USX/` with one `.usx` file per book, as in ProPresenter Bible bundles.

Reads (never modifies):
  data/raw/bible/usx/**/metadata.xml

Writes:
  data/processed/bible/bible_versions.sqlite
  data/processed/bible/manifest.json

Text is imported as published. Nothing is corrected, translated, or generated.
Usage rights are recorded per version in data/rights.json and docs/DATA_RIGHTS.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_VERSION = "1.0.0"

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "data" / "raw" / "bible" / "usx"
DEFAULT_OUT_DB = ROOT / "data" / "processed" / "bible" / "bible_versions.sqlite"
DEFAULT_MANIFEST = ROOT / "data" / "processed" / "bible" / "manifest.json"
DEFAULT_RIGHTS = ROOT / "data" / "rights.json"

# Protestant canon in order: (USFM code, English name, testament). book_id is the 1-based position.
BOOKS = [
    ("GEN", "Genesis", "old"), ("EXO", "Exodus", "old"), ("LEV", "Leviticus", "old"),
    ("NUM", "Numbers", "old"), ("DEU", "Deuteronomy", "old"), ("JOS", "Joshua", "old"),
    ("JDG", "Judges", "old"), ("RUT", "Ruth", "old"), ("1SA", "1 Samuel", "old"),
    ("2SA", "2 Samuel", "old"), ("1KI", "1 Kings", "old"), ("2KI", "2 Kings", "old"),
    ("1CH", "1 Chronicles", "old"), ("2CH", "2 Chronicles", "old"), ("EZR", "Ezra", "old"),
    ("NEH", "Nehemiah", "old"), ("EST", "Esther", "old"), ("JOB", "Job", "old"),
    ("PSA", "Psalms", "old"), ("PRO", "Proverbs", "old"), ("ECC", "Ecclesiastes", "old"),
    ("SNG", "Song of Solomon", "old"), ("ISA", "Isaiah", "old"), ("JER", "Jeremiah", "old"),
    ("LAM", "Lamentations", "old"), ("EZK", "Ezekiel", "old"), ("DAN", "Daniel", "old"),
    ("HOS", "Hosea", "old"), ("JOL", "Joel", "old"), ("AMO", "Amos", "old"),
    ("OBA", "Obadiah", "old"), ("JON", "Jonah", "old"), ("MIC", "Micah", "old"),
    ("NAM", "Nahum", "old"), ("HAB", "Habakkuk", "old"), ("ZEP", "Zephaniah", "old"),
    ("HAG", "Haggai", "old"), ("ZEC", "Zechariah", "old"), ("MAL", "Malachi", "old"),
    ("MAT", "Matthew", "new"), ("MRK", "Mark", "new"), ("LUK", "Luke", "new"),
    ("JHN", "John", "new"), ("ACT", "Acts", "new"), ("ROM", "Romans", "new"),
    ("1CO", "1 Corinthians", "new"), ("2CO", "2 Corinthians", "new"), ("GAL", "Galatians", "new"),
    ("EPH", "Ephesians", "new"), ("PHP", "Philippians", "new"), ("COL", "Colossians", "new"),
    ("1TH", "1 Thessalonians", "new"), ("2TH", "2 Thessalonians", "new"), ("1TI", "1 Timothy", "new"),
    ("2TI", "2 Timothy", "new"), ("TIT", "Titus", "new"), ("PHM", "Philemon", "new"),
    ("HEB", "Hebrews", "new"), ("JAS", "James", "new"), ("1PE", "1 Peter", "new"),
    ("2PE", "2 Peter", "new"), ("1JN", "1 John", "new"), ("2JN", "2 John", "new"),
    ("3JN", "3 John", "new"), ("JUD", "Jude", "new"), ("REV", "Revelation", "new"),
]
BOOK_INDEX = {code: (index + 1, name, testament) for index, (code, name, testament) in enumerate(BOOKS)}

# Paragraph styles that hold titles, headings, or running heads rather than verse text.
SKIP_PARA_STYLES = re.compile(r"^(mt\d*|mte\d*|h\d*|toc\w*|imt\d*|is\d*|ip|s\d*|ms\d*|mr|sr|r|d|sp|qa|cl|restore|rem)$")
VERSE_NUMBER_RE = re.compile(r"^(\d+)(?:\s*[-–]\s*(\d+))?")
WS_RE = re.compile(r"\s+")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def text_of(root: ET.Element, path: str) -> str:
    element = root.find(path)
    return WS_RE.sub(" ", element.text or "").strip() if element is not None and element.text else ""


def read_metadata(path: Path) -> dict[str, str]:
    root = ET.parse(path).getroot()
    return {
        "abbreviation": text_of(root, "identification/abbreviation"),
        "name": text_of(root, "identification/name"),
        "name_local": text_of(root, "identification/nameLocal"),
        "description": text_of(root, "identification/description"),
        "language_iso": text_of(root, "language/iso"),
        "language_name": text_of(root, "language/name"),
        "copyright": text_of(root, "copyright/fullStatement/statementContent")
        or text_of(root, "copyright/statement"),
    }


class BookParser:
    """Collects verse text from one USX 2/3 book, in document order."""

    def __init__(self) -> None:
        self.chapter = 0
        self.verse: tuple[int, str] | None = None
        self.parts: dict[tuple[int, int], list[str]] = {}
        self.labels: dict[tuple[int, int], str] = {}
        self.issues: Counter[str] = Counter()

    def _add(self, text: str | None) -> None:
        if text and self.verse and self.chapter:
            self.parts.setdefault((self.chapter, self.verse[0]), []).append(text)

    def _start_verse(self, raw: str) -> None:
        match = VERSE_NUMBER_RE.match(raw.strip())
        if not match:
            self.issues["unreadable_verse_number"] += 1
            self.verse = None
            return
        number = int(match.group(1))
        label = f"{number}-{match.group(2)}" if match.group(2) else str(number)
        if match.end() != len(raw.strip()):
            self.issues["verse_number_with_extra_marks"] += 1
        key = (self.chapter, number)
        if key in self.parts:
            self.issues["repeated_verse_number"] += 1
        self.labels[key] = label
        self.verse = (number, label)

    def walk(self, element: ET.Element, skip: bool = False) -> None:
        tag = element.tag
        if tag == "chapter":
            if element.get("number"):
                self.chapter = int(VERSE_NUMBER_RE.match(element.get("number", "0")).group(1))
                self.verse = None
            return
        if tag == "verse":
            if element.get("number"):
                self._start_verse(element.get("number", ""))
            elif element.get("eid"):
                self.verse = None
            return
        if tag in {"note", "figure", "book"}:
            return
        if tag == "para" and SKIP_PARA_STYLES.match(element.get("style", "")):
            skip = True
        if not skip:
            self._add(element.text)
        for child in element:
            self.walk(child, skip)
            if not skip:
                self._add(child.tail)

    def verses(self) -> list[tuple[int, int, str, str]]:
        rows = []
        for (chapter, verse), parts in sorted(self.parts.items()):
            text = WS_RE.sub(" ", " ".join(parts)).strip()
            if text:
                rows.append((chapter, verse, self.labels.get((chapter, verse), str(verse)), text))
            else:
                self.issues["empty_verse"] += 1
        return rows


def parse_book(path: Path) -> tuple[str, list[tuple[int, int, str, str]], Counter[str]]:
    root = ET.parse(path).getroot()
    book = root.find("book")
    code = (book.get("code") if book is not None else "") or path.stem.upper()
    parser = BookParser()
    for child in root:
        parser.walk(child)
    return code.upper(), parser.verses(), parser.issues


def find_versions(source: Path) -> list[Path]:
    folders = []
    for metadata in sorted(source.rglob("metadata.xml")):
        folder = metadata.parent
        if any((folder / name).is_dir() for name in ("USX_1", "USX")):
            folders.append(folder)
    return folders


def usx_dir(folder: Path) -> Path:
    return folder / "USX_1" if (folder / "USX_1").is_dir() else folder / "USX"


def load_rights(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("sources", {})


def import_version(folder: Path) -> dict:
    meta = read_metadata(folder / "metadata.xml")
    verses: list[tuple[int, int, int, str, str]] = []
    issues: Counter[str] = Counter()
    files = []
    unknown_books = []
    for path in sorted(usx_dir(folder).glob("*.usx")):
        code, rows, book_issues = parse_book(path)
        files.append({"file": path.name, "sha256": sha256(path)})
        if code not in BOOK_INDEX:
            unknown_books.append(code)
            continue
        issues.update(book_issues)
        book_id = BOOK_INDEX[code][0]
        verses.extend((book_id, chapter, verse, label, text) for chapter, verse, label, text in rows)
    return {
        "folder": folder,
        "meta": meta,
        "verses": verses,
        "issues": dict(issues),
        "files": files,
        "unknown_books": unknown_books,
        "books": len({row[0] for row in verses}),
        "chapters": len({(row[0], row[1]) for row in verses}),
    }


def choose(candidates: list[dict]) -> dict:
    """When two folders carry the same abbreviation, keep the one with the fewest parse issues, then the most verses."""
    return max(candidates, key=lambda c: (-sum(c["issues"].values()), len(c["verses"])))


def write_db(path: Path, versions: list[dict], rights: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript(
        """
        CREATE TABLE versions (
          id TEXT PRIMARY KEY, abbreviation TEXT NOT NULL, name TEXT NOT NULL, name_local TEXT,
          description TEXT, language_iso TEXT, language_name TEXT, copyright TEXT,
          rights_source TEXT, display_status TEXT NOT NULL, train_status TEXT NOT NULL,
          book_count INTEGER NOT NULL, verse_count INTEGER NOT NULL, sort_order INTEGER NOT NULL
        );
        CREATE TABLE books (
          book_id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, testament TEXT NOT NULL
        );
        CREATE TABLE verses (
          version_id TEXT NOT NULL REFERENCES versions(id), book_id INTEGER NOT NULL REFERENCES books(book_id),
          chapter INTEGER NOT NULL, verse INTEGER NOT NULL, label TEXT NOT NULL, text TEXT NOT NULL,
          PRIMARY KEY (version_id, book_id, chapter, verse)
        ) WITHOUT ROWID;
        """
    )
    con.executemany("INSERT INTO books VALUES (?, ?, ?, ?)", [(BOOK_INDEX[c][0], c, n, t) for c, n, t in BOOKS])
    for order, version in enumerate(versions):
        meta = version["meta"]
        version_id = version["id"]
        right = rights.get(version["rights_source"], {})
        con.execute(
            "INSERT INTO versions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                version_id, meta["abbreviation"], meta["name"], meta["name_local"], meta["description"],
                meta["language_iso"], meta["language_name"], meta["copyright"] or meta["description"],
                version["rights_source"], right.get("display", "needs_review"), right.get("train", "needs_review"),
                version["books"], len(version["verses"]), order,
            ),
        )
        con.executemany(
            "INSERT INTO verses VALUES (?, ?, ?, ?, ?, ?)",
            ((version_id, *row) for row in version["verses"]),
        )
    con.commit()
    con.execute("VACUUM")
    con.close()
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="folder searched for metadata.xml + USX")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DB)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--rights", type=Path, default=DEFAULT_RIGHTS)
    parser.add_argument("--dry-run", action="store_true", help="report what would be imported; write nothing")
    args = parser.parse_args(argv)

    folders = find_versions(args.source)
    if not folders:
        print(f"No USX Bible folders (metadata.xml + USX_1/ or USX/) under {args.source}", file=sys.stderr)
        return 1

    by_id: dict[str, list[dict]] = {}
    for folder in folders:
        version = import_version(folder)
        abbreviation = version["meta"]["abbreviation"] or folder.name
        by_id.setdefault(abbreviation.lower(), []).append(version)

    rights = load_rights(args.rights)
    versions = []
    report = []
    for version_id, candidates in by_id.items():
        chosen = choose(candidates)
        chosen["id"] = version_id
        chosen["rights_source"] = f"bible_{version_id}"
        versions.append(chosen)
        for candidate in candidates:
            report.append({
                "id": version_id,
                "folder": str(candidate["folder"].relative_to(args.source)),
                "name": candidate["meta"]["name"],
                "language_iso": candidate["meta"]["language_iso"],
                "books": candidate["books"],
                "chapters": candidate["chapters"],
                "verses": len(candidate["verses"]),
                "issues": candidate["issues"],
                "unknown_books": candidate["unknown_books"],
                "imported": candidate is chosen,
                "rights_source": chosen["rights_source"],
                "rights_recorded": chosen["rights_source"] in rights,
            })

    for row in report:
        mark = "import" if row["imported"] else "skip  "
        print(f"{mark} {row['id']:<8} {row['language_iso']:<4} {row['books']:>3} books {row['chapters']:>5} ch "
              f"{row['verses']:>6} verses  {row['name']}  [{row['folder']}]  issues={row['issues']}")
    missing = sorted({row["rights_source"] for row in report if not row["rights_recorded"]})
    if missing:
        print(f"warning: no entry in {args.rights.name} for {', '.join(missing)}; imported as needs_review",
              file=sys.stderr)
    if args.dry_run:
        return 0

    # Tedim first (newest edition first), English last; the reader's default is the first version.
    preferred = {"tdb": 0, "tb77": 1}
    versions.sort(key=lambda v: (preferred.get(v["id"], 2), v["meta"]["language_iso"] == "eng", v["id"]))
    write_db(args.out, versions, rights)
    manifest = {
        "script": "import_usx_bibles.py",
        "script_version": SCRIPT_VERSION,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "database": str(args.out.relative_to(ROOT)) if args.out.is_relative_to(ROOT) else str(args.out),
        "database_sha256": sha256(args.out),
        "versions": report,
        "sources": {
            v["id"]: {"folder": str(v["folder"].relative_to(args.source)), "files": v["files"]} for v in versions
        },
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.out} ({len(versions)} versions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
