#!/usr/bin/env python3
"""Optional: unpack siamsil-data's originals into data/raw (the older layout).

The build scripts now read siamsil-data directly (data/source_files.json), so this is only
needed for tools that still expect data/raw. Pass --raw data/raw to build_language_db.py to
build from it.

  python ml_pipeline/scripts/restore_private_data.py --data-repo ../siamsil-data

Copies, without changing their content:
  dictionary/Zomi_Standard_Dictionary_AI_Cleaned.xlsx (the master)
      -> data/raw/dictionary/Zomi_Standard_Dictionary_AI_Cleaned.xlsx
  parallel/zomi_english_sentences.part-*.csv.gz (joined in order, one header)
      -> data/raw/parallel/zomi_english_sentences.csv
  bible/Chin-Bible.zip     -> data/raw/bible/usx/chin/
  bible/engwebu_usfm.zip   -> data/raw/bible/usx/web/

Existing files and folders are never overwritten; they are reported and skipped.
Works the same on Windows, macOS and Linux. Afterwards run build_language_db.py
and import_usx_bibles.py.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW = ROOT / "data" / "raw"

DICTIONARY = ("dictionary/Zomi_Standard_Dictionary_AI_Cleaned.xlsx", "dictionary/Zomi_Standard_Dictionary_AI_Cleaned.xlsx")
BIBLE_ZIPS = (("bible/Chin-Bible.zip", "bible/usx/chin"), ("bible/engwebu_usfm.zip", "bible/usx/web"))
PARALLEL_OUT = "parallel/zomi_english_sentences.csv"


def restore_dictionary(data_repo: Path, raw: Path) -> str:
    source, target = data_repo / DICTIONARY[0], raw / DICTIONARY[1]
    if target.exists():
        return f"skip   {target} (already there)"
    if not source.exists():
        return f"miss   {source}"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return f"copied {target}"


def restore_parallel(data_repo: Path, raw: Path) -> str:
    target = raw / PARALLEL_OUT
    if target.exists():
        return f"skip   {target} (already there)"
    parts = sorted((data_repo / "parallel").glob("zomi_english_sentences.part-*.csv.gz"))
    if not parts:
        return f"miss   {data_repo / 'parallel'} parts"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".csv.tmp")
    rows = 0
    header: list[str] | None = None
    with tmp.open("w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        for part in parts:
            with gzip.open(part, "rt", encoding="utf-8", newline="") as handle:
                reader = csv.reader(handle)
                part_header = next(reader)
                if header is None:
                    header = part_header
                    writer.writerow(header)
                elif part_header != header:
                    tmp.unlink()
                    raise ValueError(f"{part.name} has a different header")
                for row in reader:
                    writer.writerow(row)
                    rows += 1
    manifest = data_repo / "parallel" / "manifest.json"
    expected = json.loads(manifest.read_text(encoding="utf-8")).get("total_rows") if manifest.exists() else None
    if expected is not None and rows != expected:
        tmp.unlink()
        raise ValueError(f"joined {rows:,} rows but manifest.json expects {expected:,}")
    tmp.replace(target)
    return f"joined {target} ({rows:,} rows from {len(parts)} parts)"


def safe_extract(archive: Path, target: Path) -> int:
    """Extract a zip, refusing entries that would land outside the target folder."""
    root = target.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            destination = (target / member.filename).resolve()
            if root != destination and root not in destination.parents:
                raise ValueError(f"{archive.name}: unsafe path {member.filename!r}")
        bundle.extractall(target)
        return len(bundle.infolist())


def restore_bibles(data_repo: Path, raw: Path) -> list[str]:
    messages = []
    for source_name, target_name in BIBLE_ZIPS:
        source, target = data_repo / source_name, raw / target_name
        if target.exists() and any(target.iterdir()):
            messages.append(f"skip   {target} (already there)")
            continue
        if not source.exists():
            messages.append(f"miss   {source}")
            continue
        target.mkdir(parents=True, exist_ok=True)
        messages.append(f"unzip  {target} ({safe_extract(source, target)} entries)")
    return messages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-repo", type=Path, required=True, help="clone of the private siamsil-data repository")
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW, help="where the app expects raw data (default: data/raw)")
    args = parser.parse_args(argv)
    if not (args.data_repo / "README.md").exists():
        sys.exit(f"{args.data_repo} does not look like a siamsil-data clone")
    messages = [restore_dictionary(args.data_repo, args.raw), restore_parallel(args.data_repo, args.raw)]
    messages += restore_bibles(args.data_repo, args.raw)
    for message in messages:
        print(message)
    print("next: python ml_pipeline/scripts/build_language_db.py && python ml_pipeline/scripts/import_usx_bibles.py")
    return 1 if any(message.startswith("miss") for message in messages) else 0


if __name__ == "__main__":
    raise SystemExit(main())
