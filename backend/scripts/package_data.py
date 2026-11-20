"""Package the language and Bible databases into one bundle for hosting (docs/DEPLOY.md).

Usage: python3 backend/scripts/package_data.py [output_dir] [--include-corpus]
Prints the SHA-256 to set as SIAMSIL_DATA_BUNDLE_SHA256.

The bundle unpacks into the API's data volume (/data) as:
  siamsil_language.sqlite   the dictionary and its search index, with EMPTY corpus tables (a "lean" copy made from
                            the full build); with --include-corpus, the full database including the parallel corpus
  bible_versions.sqlite     the Bible versions cleared for display (import_usx_bibles.py)
  json/                     the reviewed phrase lists, when present in backend/data
  bundle.json               what the lean bundle holds and the checks it passed (lean bundles only)
The corpus is left out by default: it is blocked in data/rights.json and the API hides it, so there is no reason to put it
on a server. --include-corpus refuses unless data/rights.json clears the parallel corpus for display.
It holds text Siamsil may show but not redistribute: keep the uploaded file private.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import tarfile
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))
LANGUAGE_DB = PROJECT_ROOT / "data" / "processed" / "language" / "siamsil_language.sqlite"
BIBLE_DB = PROJECT_ROOT / "data" / "processed" / "bible" / "bible_versions.sqlite"
JSON_DIR = PROJECT_ROOT / "backend" / "data"
# bible_verses.json, the workbook's "ISO Improved Text" (data/rights.json: bible_iso_improved), is left out:
# its authorship is unknown and it is not cleared for display. The Bible comes from bible_versions.sqlite.
JSON_FILES = ["daily_use_pairs.json", "dictionary.json", "metadata.json", "translation_pairs.json"]


def snapshot(source: Path, target: Path) -> None:
    """A standalone copy: the backup API folds any pending WAL pages in."""
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    dst = sqlite3.connect(target)
    src.backup(dst)
    dst.execute("PRAGMA journal_mode=DELETE")
    dst.close()
    src.close()


CORPUS_TABLES = {"parallel_sentences", "parallel_fts"}
DICTIONARY_TABLES = {"dataset_versions", "dictionary_entries", "dictionary_fts"}


def _table_names(con: sqlite3.Connection) -> set[str]:
    """User tables, without the shadow tables an FTS5 index keeps."""
    names = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    fts = {n for n in names if n.endswith(("_fts", "_fts_config", "_fts_content", "_fts_data", "_fts_docsize", "_fts_idx"))}
    shadows = {n for n in fts if not n.endswith("_fts") and n.rsplit("_fts", 1)[0] + "_fts" in names}
    return names - shadows


def lean_snapshot(source: Path, target: Path) -> dict:
    """A copy of the language database with the dictionary kept and the corpus left empty.

    The tables are built from the same schema as build_language_db.py, so the API opens it like the full one;
    parallel_sentences and parallel_fts exist but hold no rows. Refuses a database that has tables this copy
    does not know about, rather than guessing what to keep.
    """
    from build_language_db import create_schema  # type: ignore

    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        tables = _table_names(src)
        missing = (DICTIONARY_TABLES | CORPUS_TABLES) - tables
        extra = tables - DICTIONARY_TABLES - CORPUS_TABLES
        if missing or extra:
            raise ValueError("the language database does not look like a build_language_db.py database "
                             f"(missing: {sorted(missing) or 'none'}; unexpected: {sorted(extra) or 'none'})")
        dst = sqlite3.connect(target)
        try:
            create_schema(dst)
            columns = [row[1] for row in src.execute("PRAGMA table_info(dictionary_entries)")]
            marks = ",".join("?" * len(columns))
            names = ",".join(columns)
            batch: list = []
            for row in src.execute(f"SELECT {names} FROM dictionary_entries ORDER BY id"):
                batch.append(row)
                if len(batch) >= 10_000:
                    dst.executemany(f"INSERT INTO dictionary_entries ({names}) VALUES ({marks})", batch)
                    batch = []
            if batch:
                dst.executemany(f"INSERT INTO dictionary_entries ({names}) VALUES ({marks})", batch)
            dst.executemany(
                "INSERT INTO dictionary_fts (rowid, source_word, definition, part_of_speech) VALUES (?, ?, ?, ?)",
                src.execute("SELECT rowid, source_word, definition, part_of_speech FROM dictionary_fts"))
            for row in src.execute("SELECT id, name, version, created_at, script_version, source_files FROM dataset_versions"):
                try:
                    files = json.loads(row[5])
                except ValueError:
                    files = {}
                files.pop("parallel_csv", None)
                files["parallel"] = "not included (lean bundle)"
                dst.execute("INSERT INTO dataset_versions (id, name, version, created_at, script_version, source_files) "
                            "VALUES (?, ?, ?, ?, ?, ?)", (*row[:5], json.dumps(files)))
            dst.commit()
            expected = src.execute("SELECT COUNT(*) FROM dictionary_entries").fetchone()[0]
            got = dst.execute("SELECT COUNT(*) FROM dictionary_entries").fetchone()[0]
            indexed = dst.execute("SELECT COUNT(*) FROM dictionary_fts").fetchone()[0]
            leaked = dst.execute("SELECT COUNT(*) FROM parallel_sentences").fetchone()[0] + \
                dst.execute("SELECT COUNT(*) FROM parallel_fts").fetchone()[0]
            if got != expected or indexed != expected:
                raise ValueError(f"the lean copy lost dictionary rows ({got:,} of {expected:,}; index {indexed:,})")
            if leaked:
                raise ValueError("the lean copy still holds corpus rows")
            dst.execute("PRAGMA journal_mode=DELETE")
            dst.execute("VACUUM")
            dst.close()
        finally:
            try:
                dst.close()
            except sqlite3.Error:
                pass
    finally:
        src.close()
    return {"dictionary_entries": expected, "parallel_sentences": 0}


def package(out_dir: Path, language_db: Path = LANGUAGE_DB, bible_db: Path = BIBLE_DB,
            json_dir: Path = JSON_DIR, lean: bool = False) -> tuple[Path, str]:
    missing = [path for path in (language_db, bible_db) if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "build these first: " + ", ".join(str(path) for path in missing)
            + " (ml_pipeline/scripts/build_language_db.py, ml_pipeline/scripts/import_usx_bibles.py)")
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = out_dir / "siamsil-data.tar.gz"
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(bundle, "w:gz", compresslevel=6) as tar:
            for source in (language_db, bible_db):
                copy = Path(tmp) / source.name
                if lean and source == language_db:
                    stats = lean_snapshot(source, copy)
                else:
                    snapshot(source, copy)
                tar.add(copy, arcname=source.name)
            if lean:
                info = Path(tmp) / "bundle.json"
                info.write_text(json.dumps({
                    "lean": True,
                    "corpus_rows": 0,
                    "dictionary_entries": stats["dictionary_entries"],
                    "note": "The parallel corpus is not in this bundle (data/rights.json: blocked).",
                }, indent=2) + "\n", encoding="utf-8")
                tar.add(info, arcname="bundle.json")
            for name in JSON_FILES:
                if (json_dir / name).exists():
                    tar.add(json_dir / name, arcname=f"json/{name}")

    digest = hashlib.sha256()
    with bundle.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return bundle, digest.hexdigest()


def corpus_allowed() -> tuple[bool, str]:
    """Whether data/rights.json clears the parallel corpus for display (rights_policy.py)."""
    import rights_policy  # type: ignore

    decision = rights_policy.authorize(rights_policy.load_rights(PROJECT_ROOT / "data" / "rights.json"),
                                       "parallel_corpus", "display")
    return decision.allowed, decision.reason


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out_dir", nargs="?", type=Path, default=PROJECT_ROOT / "dist")
    parser.add_argument("--include-corpus", action="store_true",
                        help="package the full database with the parallel corpus (only if its rights are cleared)")
    args = parser.parse_args(argv)
    if args.include_corpus:
        allowed, reason = corpus_allowed()
        if not allowed:
            sys.exit(f"Nothing was packaged: the parallel corpus may not be shown ({reason}). "
                     "Leave out --include-corpus, or clear it in data/rights.json first.")
    try:
        bundle, sha256 = package(args.out_dir, lean=not args.include_corpus)
    except (FileNotFoundError, ValueError) as error:
        sys.exit(f"Nothing was packaged: {error}")
    print(f"bundle: {bundle} ({bundle.stat().st_size / 1_000_000:.0f} MB, "
          f"{'with the parallel corpus' if args.include_corpus else 'lean: no parallel corpus'})")
    print("Upload it to the private bucket as siamsil-data.tar.gz, then set on the API:")
    print(f"SIAMSIL_DATA_BUNDLE_SHA256={sha256}")


if __name__ == "__main__":
    main()
