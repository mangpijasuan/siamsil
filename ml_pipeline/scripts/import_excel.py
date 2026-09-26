#!/usr/bin/env python3
"""Import Zomi Bible Excel workbook into Siamsil processed JSON datasets."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "ml_pipeline" / "raw_data" / "Zomi_Bible_Final_v14.xlsx"
DEFAULT_OUTPUT = ROOT / "ml_pipeline" / "processed_data"
BACKEND_DATA = ROOT / "backend" / "data"


def clean_str(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def is_numeric_id(value: object) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return str(value).replace(".", "", 1).isdigit()


def import_bible(path: Path) -> list[dict]:
    df = pd.read_excel(path, sheet_name="Bible Data (ISO)")
    records: list[dict] = []

    for _, row in df.iterrows():
        book_english = clean_str(row["Book (English)"])
        chapter = int(row["Chapter"])
        verse = int(row["Verse"])
        records.append(
            {
                "testament": clean_str(row["Testament"]),
                "book_id": int(row["Book ID"]),
                "book_english": book_english,
                "book_zomi": clean_str(row["Book (Zomi)"]),
                "chapter": chapter,
                "verse": verse,
                "reference": f"{book_english} {chapter}:{verse}",
                "english": clean_str(row["KJV English"]),
                "zomi_original": clean_str(row["Original ZSF Text"]),
                "zomi_iso": clean_str(row["ISO Improved Text"]),
                "changes_applied": clean_str(row["Changes Applied"]),
            }
        )

    return records


def import_dictionary(path: Path) -> list[dict]:
    df = pd.read_excel(path, sheet_name="Zomi Dictionary", skiprows=2)
    df.columns = [
        "#",
        "english",
        "part_of_speech",
        "domain",
        "zomi",
        "definition",
        "verified",
        "source",
    ]

    records: list[dict] = []
    for _, row in df.iterrows():
        if not is_numeric_id(row["#"]):
            continue

        records.append(
            {
                "id": int(row["#"]),
                "english": clean_str(row["english"]),
                "part_of_speech": clean_str(row["part_of_speech"]),
                "domain": clean_str(row["domain"]),
                "zomi": clean_str(row["zomi"]),
                "definition": clean_str(row["definition"]),
                "verified": clean_str(row["verified"]) is not None,
                "source": clean_str(row["source"]),
            }
        )

    return records


def import_daily_use(path: Path) -> list[dict]:
    df = pd.read_excel(path, sheet_name="Daily Use (Ms. Nem)", skiprows=2)
    df.columns = [
        "id",
        "category",
        "sub_category",
        "english",
        "zomi",
        "notes",
        "verified",
        "source",
    ]

    records: list[dict] = []
    for _, row in df.iterrows():
        english = clean_str(row["english"])
        zomi = clean_str(row["zomi"])
        if not english or not zomi or english.lower() == "english":
            continue

        entry_id = row["id"]
        if not is_numeric_id(entry_id):
            continue

        records.append(
            {
                "id": int(entry_id),
                "category": clean_str(row["category"]),
                "sub_category": clean_str(row["sub_category"]),
                "english": english,
                "zomi": zomi,
                "notes": clean_str(row["notes"]),
                "verified": clean_str(row["verified"]) is not None,
                "source": clean_str(row["source"]),
            }
        )

    return records


def import_translation_pairs(path: Path) -> list[dict]:
    df = pd.read_excel(path, sheet_name="Translation Pairs", skiprows=2)
    df.columns = [
        "id",
        "domain",
        "sub_topic",
        "english",
        "zomi",
        "status",
        "notes",
    ]

    records: list[dict] = []
    for _, row in df.iterrows():
        english = clean_str(row["english"])
        if not english or english.lower() == "english sentence":
            continue

        records.append(
            {
                "id": clean_str(row["id"]),
                "domain": clean_str(row["domain"]),
                "sub_topic": clean_str(row["sub_topic"]),
                "english": english,
                "zomi": clean_str(row["zomi"]),
                "status": clean_str(row["status"]) or "Not started",
                "notes": clean_str(row["notes"]),
            }
        )

    return records


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--sync-backend",
        action="store_true",
        default=True,
        help="Copy processed JSON into backend/data for the API server.",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input file not found: {args.input}")

    bible = import_bible(args.input)
    dictionary = import_dictionary(args.input)
    daily_use = import_daily_use(args.input)
    translation_pairs = import_translation_pairs(args.input)

    metadata = {
        "source_file": args.input.name,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "bible_verses": len(bible),
            "dictionary_entries": len(dictionary),
            "daily_use_pairs": len(daily_use),
            "translation_pairs": len(translation_pairs),
            "translation_pairs_done": sum(
                1 for item in translation_pairs if item.get("zomi")
            ),
        },
    }

    outputs = {
        "metadata.json": metadata,
        "bible_verses.json": bible,
        "dictionary.json": dictionary,
        "daily_use_pairs.json": daily_use,
        "translation_pairs.json": translation_pairs,
    }

    for filename, payload in outputs.items():
        write_json(args.output / filename, payload)
        if args.sync_backend:
            write_json(BACKEND_DATA / filename, payload)

    print(f"Imported {metadata['counts']['bible_verses']} Bible verses")
    print(f"Imported {metadata['counts']['dictionary_entries']} dictionary entries")
    print(f"Imported {metadata['counts']['daily_use_pairs']} daily-use pairs")
    print(
        "Imported "
        f"{metadata['counts']['translation_pairs_done']}/"
        f"{metadata['counts']['translation_pairs']} translation pairs"
    )
    print(f"Wrote processed data to {args.output}")


if __name__ == "__main__":
    main()
