"""Package the language database and JSON data into one bundle for hosting.

Usage: python3 backend/scripts/package_data.py [output_dir]
Prints the SHA-256 to set as SIAMSIL_DATA_BUNDLE_SHA256.
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
JSON_DIR = PROJECT_ROOT / "backend" / "data"
JSON_FILES = ["bible_verses.json", "daily_use_pairs.json", "dictionary.json", "metadata.json", "translation_pairs.json"]


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "dist"
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = out_dir / "siamsil-data.tar.gz"

    with tempfile.TemporaryDirectory() as tmp:
        # The backup API folds any pending WAL pages into a standalone copy.
        snapshot = Path(tmp) / "siamsil_language.sqlite"
        src = sqlite3.connect(f"file:{LANGUAGE_DB}?mode=ro", uri=True)
        dst = sqlite3.connect(snapshot)
        src.backup(dst)
        dst.execute("PRAGMA journal_mode=DELETE")
        dst.close()
        src.close()

        with tarfile.open(bundle, "w:gz", compresslevel=6) as tar:
            tar.add(snapshot, arcname="siamsil_language.sqlite")
            for name in JSON_FILES:
                tar.add(JSON_DIR / name, arcname=f"json/{name}")

    digest = hashlib.sha256()
    with bundle.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)

    size_mb = bundle.stat().st_size / 1_000_000
    print(f"bundle: {bundle} ({size_mb:.0f} MB)")
    print(f"SIAMSIL_DATA_BUNDLE_SHA256={digest.hexdigest()}")


if __name__ == "__main__":
    main()
