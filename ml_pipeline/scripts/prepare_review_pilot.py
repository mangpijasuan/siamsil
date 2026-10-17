#!/usr/bin/env python3
"""Create a local-only, deterministic packet of flagged training rows for review."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "processed" / "language" / "siamsil_language.sqlite"
DEFAULT_OUTPUT = ROOT / "data" / "exports" / "review_pilot_100.jsonl"


def stable_key(seed: str, row_id: int) -> str:
    return hashlib.sha256(f"{seed}:{row_id}".encode()).hexdigest()


def select_rows(rows: list[sqlite3.Row], count: int, seed: str) -> list[sqlite3.Row]:
    """Include two examples per flag, then fill proportionally from the pool."""
    by_flag: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        for flag in json.loads(row["quality_flags"]):
            by_flag[flag].append(row)
    chosen: dict[int, sqlite3.Row] = {}
    for flag in sorted(by_flag):
        for row in sorted(by_flag[flag], key=lambda item: stable_key(seed, item["id"])):
            if row["id"] not in chosen:
                chosen[row["id"]] = row
            if sum(flag in json.loads(item["quality_flags"]) for item in chosen.values()) >= 2:
                break
            if len(chosen) >= count:
                break
        if len(chosen) >= count:
            break
    for row in sorted(rows, key=lambda item: stable_key(seed, item["id"])):
        if len(chosen) >= count:
            break
        chosen[row["id"]] = row
    return sorted(chosen.values(), key=lambda item: stable_key(seed, item["id"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed", default="siamsil-review-pilot-v1")
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be positive")
    if not args.db.is_file():
        parser.error(f"Language release not found: {args.db}")

    with sqlite3.connect(f"file:{args.db.resolve()}?mode=ro", uri=True) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT id, raw_source_text, raw_target_text, source_reference, model,
                   quality_flags, quality_score, dataset_split, version
            FROM parallel_sentences
            WHERE dataset_split = 'train' AND quality_flags != '[]'
            ORDER BY id
            """
        ).fetchall()
    if len(rows) < args.count:
        parser.error(f"Only {len(rows)} flagged training rows are available")

    selected = select_rows(rows, args.count, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        for row in selected:
            record = {
                "sentence_id": row["id"],
                "english_source": row["raw_source_text"],
                "zomi_candidate": row["raw_target_text"],
                "source_reference": row["source_reference"],
                "model": row["model"],
                "quality_flags": json.loads(row["quality_flags"]),
                "quality_score": row["quality_score"],
                "dataset_split": row["dataset_split"],
                "dataset_version": row["version"],
                "license_status": "needs_review",
                "review_status": "pending",
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"Wrote {len(selected)} pending-review rows to {args.output}")
    print("Local diagnostic sample only; not licensed, verified, or suitable as a hidden evaluation set.")


if __name__ == "__main__":
    main()
