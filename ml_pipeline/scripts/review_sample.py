#!/usr/bin/env python3
"""Blind per-model review samples of the machine-translated corpus.

The Zomi side of the parallel corpus was produced by several Gemini models.
Native-speaker reviewers rate a sample from each model without knowing which
model produced which pair; the summary estimates each model's quality.

Commands:
  export DB --out DIR [--per-model N]   write review.csv (for reviewers) and key.csv (kept private)
  summarize REVIEW KEY [--json OUT]     per-model scores from a completed review.csv
  record REVIEW KEY --reviewer R01      save each rated pair to data/reviews/corpus-reviews.jsonl,
                                        which build_language_db.py applies on every rebuild

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
from datetime import date
from pathlib import Path

import corpus_reviews
from build_language_db import ROOT, pair_key

DEFAULT_SEED = "siamsil-generator-review-v1"
REVIEW_COLUMNS = ["sample_id", "english", "zomi", "meaning", "fluency", "notes"]
KEY_COLUMNS = ["sample_id", "parallel_id", "model", "pair_hash", "text_sha256"]
DEFAULT_REVIEWS = ROOT / "data" / "reviews" / "corpus-reviews.jsonl"
SCORES = {"0", "1", "2"}


def exported_text_digest(english: str, zomi: str) -> str:
    """Exact-text fingerprint: unlike pair_hash it changes with any edit, even punctuation or case."""
    return hashlib.sha256(f"{english}\n{zomi}".encode("utf-8")).hexdigest()


def sample_order(seed: str, pair_hash: str) -> str:
    return hashlib.sha256(f"{seed}\t{pair_hash}".encode("utf-8")).hexdigest()


def select_sample(con: sqlite3.Connection, per_model: int, seed: str) -> list[tuple[str, int, str, str, str, str]]:
    """Return (order_key, parallel_id, model, english, zomi, pair_hash) rows, interleaved across models.

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
        model, english, zomi, pair_hash = con.execute(
            "SELECT model, normalized_source_text, normalized_target_text, pair_hash"
            " FROM parallel_sentences WHERE id = ?",
            (parallel_id,),
        ).fetchone()
        sample.append((order_key, parallel_id, model, english, zomi, pair_hash))
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
        for n, (_, parallel_id, model, english, zomi, pair_hash) in enumerate(sample, start=1):
            sample_id = f"R{n:05d}"
            review_writer.writerow([sample_id, english, zomi, "", "", ""])
            key_writer.writerow([sample_id, parallel_id, model, pair_hash, exported_text_digest(english, zomi)])
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


def record(
    review_rows: list[dict],
    key_rows: list[dict],
    *,
    reviewer: str,
    reviewed_on: str,
    batch: str,
    existing: list[dict],
    con: sqlite3.Connection | None = None,
) -> tuple[list[dict], list[str], int]:
    """Turn a completed review.csv into review records. Returns (new records, errors, unchanged).

    The pair is identified by its stable pair_hash, never by the database row id,
    which changes when the database is rebuilt. If the sentence text in review.csv
    differs at all from what was exported (a reviewer edited a cell, even only
    punctuation or case), the row is an error: the rating would otherwise attach
    to a pair that does not say what the reviewer read.

    The same ratings for the same pair saved again from the same batch add nothing;
    a later batch is a new review and is recorded even with identical scores.
    """
    key_of = {row["sample_id"]: row for row in key_rows}
    saved = {
        (r["pair_hash"], r["reviewer"], r.get("batch", "")): (r["meaning"], r["fluency"], r.get("notes", ""))
        for r in existing
    }
    records: list[dict] = []
    errors: list[str] = []
    unchanged = 0
    if not corpus_reviews.REVIEWER_CODE.match(reviewer):
        return [], [f"reviewer must be a roster code such as R01, not {reviewer!r}"], 0

    for row in review_rows:
        sample_id = (row.get("sample_id") or "").strip()
        key = key_of.get(sample_id)
        if key is None:
            errors.append(f"{sample_id or '<blank>'}: not in key file")
            continue
        meaning = (row.get("meaning") or "").strip()
        fluency = (row.get("fluency") or "").strip()
        if not meaning and not fluency:
            continue
        if meaning not in SCORES or fluency not in SCORES:
            errors.append(f"{sample_id}: meaning and fluency must each be 0, 1, or 2")
            continue

        english, zomi = row.get("english") or "", row.get("zomi") or ""
        pair_hash = (key.get("pair_hash") or "").strip()
        exported_digest = (key.get("text_sha256") or "").strip()
        if not pair_hash or not exported_digest:
            # Keys exported before these columns existed: look the pair up in the same database.
            found = con.execute(
                "SELECT pair_hash, normalized_source_text, normalized_target_text FROM parallel_sentences WHERE id = ?",
                (key.get("parallel_id"),),
            ).fetchone() if con else None
            if found is None:
                errors.append(f"{sample_id}: key has no pair_hash; pass --database with the exported database")
                continue
            pair_hash, exported_digest = found[0], exported_text_digest(found[1], found[2])
        if exported_text_digest(english, zomi) != exported_digest or pair_key(english, zomi) != pair_hash:
            errors.append(f"{sample_id}: English or Zomi text differs from the exported pair; rate the original text")
            continue

        notes = (row.get("notes") or "").strip()
        scores = (int(meaning), int(fluency))
        if saved.get((pair_hash, reviewer, batch)) == (*scores, notes):
            unchanged += 1
            continue
        saved[(pair_hash, reviewer, batch)] = (*scores, notes)
        records.append(
            {
                "pair_hash": pair_hash,
                "meaning": scores[0],
                "fluency": scores[1],
                "reviewer": reviewer,
                "reviewed_on": reviewed_on,
                "batch": batch,
                "notes": notes,
            }
        )
    return records, errors, unchanged


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


def cmd_record(args: argparse.Namespace) -> int:
    try:
        existing = corpus_reviews.load(args.reviews) if args.reviews.exists() else []
    except ValueError as error:
        sys.exit(f"The saved reviews file is damaged, nothing was saved: {error}")
    con = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True) if args.database else None
    try:
        records, errors, unchanged = record(
            read_csv(args.review),
            read_csv(args.key),
            reviewer=args.reviewer,
            reviewed_on=args.date,
            batch=args.batch or args.key.parent.name,
            existing=existing,
            con=con,
        )
    finally:
        if con:
            con.close()
    for error in errors:
        print(f"error: {error}")
    if errors:
        print("nothing saved; fix the rows above and run again")
        return 1
    corpus_reviews.append(args.reviews, records)
    print(f"saved {len(records)} new ratings by {args.reviewer} to {args.reviews} ({unchanged} already saved)")
    print("they take effect on the next build_language_db.py run")
    return 0


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

    record_parser = commands.add_parser("record", help="save completed ratings for every future rebuild")
    record_parser.add_argument("review", type=Path)
    record_parser.add_argument("key", type=Path)
    record_parser.add_argument("--reviewer", required=True, help="roster code of the person who rated, e.g. R01")
    record_parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    record_parser.add_argument("--date", default=date.today().isoformat(), help="day the ratings were made")
    record_parser.add_argument("--batch", help="name of this review batch (default: the key file's folder)")
    record_parser.add_argument("--database", type=Path, help="only for key files without a pair_hash column")
    record_parser.set_defaults(run=cmd_record)

    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
