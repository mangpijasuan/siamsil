"""Package the language and Bible databases into one bundle for hosting (docs/DEPLOY.md).

Usage: python3 backend/scripts/package_data.py [output_dir]
Prints the SHA-256 to set as SIAMSIL_DATA_BUNDLE_SHA256.

The bundle unpacks into the API's data volume (/data) as:
  siamsil_language.sqlite   dictionary, corpus and search indexes (build_language_db.py)
  bible_versions.sqlite     the Bible versions cleared for display (import_usx_bibles.py)
  json/                     the reviewed phrase lists, when present in backend/data
It holds text Siamsil may show but not redistribute: keep the uploaded file private.
"""
from __future__ import annotations

import hashlib
import sqlite3
import sys
import tarfile
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
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


def package(out_dir: Path, language_db: Path = LANGUAGE_DB, bible_db: Path = BIBLE_DB,
            json_dir: Path = JSON_DIR) -> tuple[Path, str]:
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
                snapshot(source, copy)
                tar.add(copy, arcname=source.name)
            for name in JSON_FILES:
                if (json_dir / name).exists():
                    tar.add(json_dir / name, arcname=f"json/{name}")

    digest = hashlib.sha256()
    with bundle.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return bundle, digest.hexdigest()


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "dist"
    try:
        bundle, sha256 = package(out_dir)
    except FileNotFoundError as error:
        sys.exit(f"Nothing was packaged: {error}")
    print(f"bundle: {bundle} ({bundle.stat().st_size / 1_000_000:.0f} MB)")
    print("Upload it to the private bucket as siamsil-data.tar.gz, then set on the API:")
    print(f"SIAMSIL_DATA_BUNDLE_SHA256={sha256}")


if __name__ == "__main__":
    main()
