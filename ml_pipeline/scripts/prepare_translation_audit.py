#!/usr/bin/env python3
"""Create reproducible, local-only random and diagnostic review packets.

The random packet is uniform over the deduplicated training split and can
support a prevalence estimate after human review. The flagged packet is
purposively enriched and must never be pooled into that estimate.
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import sqlite3
from collections import Counter
from pathlib import Path

from prepare_review_pilot import select_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "processed" / "language" / "siamsil_language.sqlite"
DEFAULT_OUTPUT = ROOT / "data" / "exports" / "translation_audit_v1"


def rank(seed: str, row_id: int) -> int:
    return int.from_bytes(hashlib.sha256(f"{seed}:{row_id}".encode()).digest(), "big")


def uniform_ids(con: sqlite3.Connection, count: int, seed: str) -> tuple[list[int], int]:
    """Keep the smallest deterministic hash ranks without loading all rows."""
    heap: list[tuple[int, int]] = []
    population = 0
    for (row_id,) in con.execute("SELECT id FROM parallel_sentences WHERE dataset_split = 'train'"):
        population += 1
        item = (-rank(seed, row_id), -row_id)
        if len(heap) < count:
            heapq.heappush(heap, item)
        elif item > heap[0]:
            heapq.heapreplace(heap, item)
    if population < count:
        raise ValueError(f"Requested {count} random rows, but only {population} training rows exist")
    ids = [-item[1] for item in heap]
    return sorted(ids, key=lambda row_id: (rank(seed, row_id), row_id)), population


def load_rows(con: sqlite3.Connection, ids: list[int]) -> dict[int, sqlite3.Row]:
    rows: dict[int, sqlite3.Row] = {}
    for start in range(0, len(ids), 500):
        batch = ids[start:start + 500]
        placeholders = ",".join("?" for _ in batch)
        for row in con.execute(
            f"""SELECT id, raw_source_text, raw_target_text, source_reference, model,
                       quality_flags, quality_score, dataset_split, version
                FROM parallel_sentences WHERE id IN ({placeholders})""",
            batch,
        ):
            rows[row["id"]] = row
    return rows


def packet_record(row: sqlite3.Row, sample_kind: str) -> dict:
    return {
        "sentence_id": row["id"],
        "sample_kind": sample_kind,
        "english_source": row["raw_source_text"],
        "zomi_candidate": row["raw_target_text"],
        "model": row["model"],
        "source_reference": row["source_reference"],
        "quality_flags": json.loads(row["quality_flags"] or "[]"),
        "quality_score": row["quality_score"],
        "dataset_split": row["dataset_split"],
        "dataset_version": row["version"],
        "license_status": "needs_review",
        "review_status": "pending",
    }


def write_jsonl(path: Path, records: list[dict]) -> str:
    with path.open("x", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(db: Path, output: Path, random_count: int, flagged_count: int, seed: str) -> dict:
    if random_count < 1 or flagged_count < 1:
        raise ValueError("Both sample counts must be positive")
    if not db.is_file():
        raise FileNotFoundError(db)
    if output.exists():
        raise FileExistsError(f"Audit output already exists: {output}")

    with sqlite3.connect(f"file:{db.resolve()}?mode=ro", uri=True) as con:
        con.row_factory = sqlite3.Row
        random_ids, population = uniform_ids(con, random_count, seed + ":random")
        random_set = set(random_ids)
        flagged_pool = [
            row for row in con.execute(
                """SELECT id, quality_flags FROM parallel_sentences
                   WHERE dataset_split = 'train' AND quality_flags != '[]'"""
            ) if row["id"] not in random_set
        ]
        if len(flagged_pool) < flagged_count:
            raise ValueError(f"Requested {flagged_count} flagged rows; {len(flagged_pool)} remain")
        flagged_ids = [row["id"] for row in select_rows(flagged_pool, flagged_count, seed + ":flagged")]
        all_rows = load_rows(con, [*random_ids, *flagged_ids])
        by_model = {
            model or "unknown": count
            for model, count in con.execute(
                """SELECT model, COUNT(*) FROM parallel_sentences
                   WHERE dataset_split = 'train' GROUP BY model"""
            )
        }

    random_records = [packet_record(all_rows[row_id], "uniform_random") for row_id in random_ids]
    flagged_records = [packet_record(all_rows[row_id], "flagged_diagnostic") for row_id in flagged_ids]
    output.mkdir(parents=True, exist_ok=False)
    random_sha = write_jsonl(output / "random.jsonl", random_records)
    flagged_sha = write_jsonl(output / "flagged.jsonl", flagged_records)
    write_jsonl(output / "decisions_template.jsonl", [
        {"sentence_id": row["sentence_id"], "sample_kind": row["sample_kind"],
         "reviewer_id": "", "decision": "", "corrected_zomi": "",
         "error_tags": [], "notes": ""}
        for row in [*random_records, *flagged_records]
    ])
    manifest = {
        "dataset_version": random_records[0]["dataset_version"],
        "seed": seed,
        "population": "deduplicated training-split sentence pairs",
        "population_count": population,
        "population_by_model": by_model,
        "random": {"count": len(random_records), "sha256": random_sha, "sampling": "uniform without replacement"},
        "flagged": {
            "count": len(flagged_records), "sha256": flagged_sha,
            "sampling": "diagnostic enrichment; exclude from corpus-wide prevalence estimates",
            "flag_counts": dict(Counter(flag for row in flagged_records for flag in row["quality_flags"])),
        },
        "rights_status": "needs_review",
        "human_review_status": "not_started",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--random-count", type=int, default=600)
    parser.add_argument("--flagged-count", type=int, default=120)
    parser.add_argument("--seed", default="siamsil-translation-audit-v1")
    args = parser.parse_args()
    result = prepare(args.db, args.output, args.random_count, args.flagged_count, args.seed)
    print(f"Prepared {result['random']['count']} random and {result['flagged']['count']} flagged rows")
    print("Local, unreviewed packets only; no corpus-quality estimate or gold test exists yet")


if __name__ == "__main__":
    main()
