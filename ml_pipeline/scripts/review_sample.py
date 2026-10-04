#!/usr/bin/env python3
"""Blind per-model review samples of the machine-translated corpus.

The Zomi side of the parallel corpus was produced by several Gemini models.
Native-speaker reviewers rate a sample from each model without knowing which
model produced which pair; the summary estimates each model's quality.

Commands:
  export DB --out DIR [--per-model N]   write review.csv (for reviewers) and key.csv (kept private)
  summarize REVIEW KEY [--json OUT]     per-model scores from a completed review.csv

Rating scale (see docs/GENERATOR_REVIEW.md):
  meaning  0 wrong or missing · 1 partly right · 2 fully right
  fluency  0 not readable Zomi · 1 understandable with errors · 2 natural
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import heapq
import json
import math
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

DEFAULT_SEED = "siamsil-generator-review-v1"
REVIEW_COLUMNS = ["sample_id", "english", "zomi", "meaning", "fluency", "notes"]
KEY_COLUMNS = ["sample_id", "parallel_id", "model"]
SCORES = {"0", "1", "2"}


def sample_order(seed: str, pair_hash: str) -> str:
    return hashlib.sha256(f"{seed}\t{pair_hash}".encode("utf-8")).hexdigest()


def select_sample(con: sqlite3.Connection, per_model: int, seed: str) -> list[tuple[str, int, str, str, str]]:
    """Return (order_key, parallel_id, model, english, zomi) rows, interleaved across models.

    Deterministic for a given database and seed. Pairs held out for human
    evaluation are never sampled.
    """
    models = [
        row[0]
        for row in con.execute(
            "SELECT DISTINCT model FROM parallel_sentences WHERE model IS NOT NULL AND model != '' ORDER BY model"
        )
    ]
    picked: list[tuple[str, int]] = []
    for model in models:
        rows = con.execute(
            "SELECT id, pair_hash FROM parallel_sentences WHERE model = ? AND dataset_split != 'eval_holdout'",
            (model,),
        )
        picked.extend(heapq.nsmallest(per_model, ((sample_order(seed, h), i) for i, h in rows)))

    sample = []
    for order_key, parallel_id in sorted(picked):
        model, english, zomi = con.execute(
            "SELECT model, normalized_source_text, normalized_target_text FROM parallel_sentences WHERE id = ?",
            (parallel_id,),
        ).fetchone()
        sample.append((order_key, parallel_id, model, english, zomi))
    return sample


def export(database: Path, out_dir: Path, per_model: int, seed: str) -> tuple[Path, Path, int]:
    con = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        sample = select_sample(con, per_model, seed)
    finally:
        con.close()

    out_dir.mkdir(parents=True, exist_ok=True)
    review_path = out_dir / "review.csv"
    key_path = out_dir / "key.csv"
    with review_path.open("w", encoding="utf-8", newline="") as review, key_path.open(
        "w", encoding="utf-8", newline=""
    ) as key:
        review_writer = csv.writer(review)
        key_writer = csv.writer(key)
        review_writer.writerow(REVIEW_COLUMNS)
        key_writer.writerow(KEY_COLUMNS)
        for n, (_, parallel_id, model, english, zomi) in enumerate(sample, start=1):
            sample_id = f"R{n:05d}"
            review_writer.writerow([sample_id, english, zomi, "", "", ""])
            key_writer.writerow([sample_id, parallel_id, model])
    return review_path, key_path, len(sample)


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def summarize(review_rows: list[dict], key_rows: list[dict]) -> tuple[dict, list[str]]:
    """Return (per-model summary, errors). Unrated rows are skipped, not errors."""
    model_of = {row["sample_id"]: row["model"] for row in key_rows}
    errors: list[str] = []
    ratings: dict[str, list[tuple[int, int]]] = defaultdict(list)
    unrated: dict[str, int] = defaultdict(int)

    for row in review_rows:
        sample_id = (row.get("sample_id") or "").strip()
        model = model_of.get(sample_id)
        if model is None:
            errors.append(f"{sample_id or '<blank>'}: not in key file")
            continue
        meaning = (row.get("meaning") or "").strip()
        fluency = (row.get("fluency") or "").strip()
        if not meaning and not fluency:
            unrated[model] += 1
            continue
        if meaning not in SCORES or fluency not in SCORES:
            errors.append(f"{sample_id}: meaning and fluency must each be 0, 1, or 2")
            continue
        ratings[model].append((int(meaning), int(fluency)))

    summary = {}
    for model in sorted(set(model_of.values())):
        rated = ratings.get(model, [])
        acceptable = sum(1 for meaning, fluency in rated if meaning == 2 and fluency >= 1)
        low, high = wilson_interval(acceptable, len(rated))
        summary[model] = {
            "rated": len(rated),
            "unrated": unrated.get(model, 0),
            "mean_meaning": round(sum(m for m, _ in rated) / len(rated), 3) if rated else None,
            "mean_fluency": round(sum(f for _, f in rated) / len(rated), 3) if rated else None,
            "acceptable_share": round(acceptable / len(rated), 3) if rated else None,
            "acceptable_95ci": [round(low, 3), round(high, 3)] if rated else None,
        }
    return summary, errors


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        sys.exit(f"File not found: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def cmd_export(args: argparse.Namespace) -> int:
    if not args.database.exists():
        sys.exit(f"Language database not found: {args.database}")
    review_path, key_path, count = export(args.database, args.out, args.per_model, args.seed)
    print(f"wrote {count} samples to {review_path}")
    print(f"wrote {key_path} (keep this away from reviewers)")
    return 0


def cmd_summarize(args: argparse.Namespace) -> int:
    summary, errors = summarize(read_csv(args.review), read_csv(args.key))
    for error in errors:
        print(f"error: {error}")
    print(f"{'model':32} {'rated':>6} {'meaning':>8} {'fluency':>8} {'acceptable (95% CI)':>24}")
    for model, s in summary.items():
        if s["rated"]:
            ci = f"{s['acceptable_share']:.2f} ({s['acceptable_95ci'][0]:.2f}-{s['acceptable_95ci'][1]:.2f})"
            print(f"{model:32} {s['rated']:>6} {s['mean_meaning']:>8.2f} {s['mean_fluency']:>8.2f} {ci:>24}")
        else:
            print(f"{model:32} {0:>6} {'-':>8} {'-':>8} {'-':>24}")
    if args.json:
        args.json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.json}")
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    export_parser = commands.add_parser("export")
    export_parser.add_argument("database", type=Path)
    export_parser.add_argument("--out", type=Path, required=True)
    export_parser.add_argument("--per-model", type=int, default=200)
    export_parser.add_argument("--seed", default=DEFAULT_SEED)
    export_parser.set_defaults(run=cmd_export)

    summarize_parser = commands.add_parser("summarize")
    summarize_parser.add_argument("review", type=Path)
    summarize_parser.add_argument("key", type=Path)
    summarize_parser.add_argument("--json", type=Path)
    summarize_parser.set_defaults(run=cmd_summarize)

    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
