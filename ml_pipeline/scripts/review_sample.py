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
  approval-sheet --database DB --out F  list pairs reviewers found acceptable, for the lead editor
  approve SHEET --approver E01          save the lead editor's approve/reject decisions

Reviewer and lead-editor codes must be in the private roster (data/reviews/roster.csv:
columns code, role = reviewer or lead_editor, optional name). A pair is HUMAN_APPROVED
only after a reviewer rated it acceptable and a different lead editor approved it.

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
from datetime import date, datetime, timezone
from pathlib import Path

import corpus_reviews
from build_language_db import ROOT, pair_key

DEFAULT_SEED = "siamsil-generator-review-v1"
REVIEW_COLUMNS = ["sample_id", "english", "zomi", "meaning", "fluency", "correction", "notes"]
APPROVAL_COLUMNS = [
    "item_id", "english", "zomi", "reviews", "reviewer_notes", "corrections",
    "decision", "notes", "pair_hash", "text_sha256",
]
KEY_COLUMNS = ["sample_id", "parallel_id", "model", "pair_hash", "text_sha256"]
DEFAULT_REVIEWS = ROOT / "data" / "reviews" / "corpus-reviews.jsonl"
DEFAULT_ROSTER = ROOT / "data" / "reviews" / "roster.csv"
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
            review_writer.writerow([sample_id, english, zomi, "", "", "", ""])
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
    roster: dict[str, str],
    recorded_at: str = "",
    con: sqlite3.Connection | None = None,
) -> tuple[list[dict], list[str], int]:
    """Turn a completed review.csv into review records. Returns (new records, errors, unchanged).

    The reviewer must be listed in the roster with the reviewer role. A correction
    the reviewer writes is kept with the rating for the lead editor; it never
    replaces the stored text.

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
        (r["pair_hash"], r["reviewer"], r.get("batch", "")):
            (r["meaning"], r["fluency"], r.get("notes", ""), r.get("correction", ""))
        for r in existing
        if corpus_reviews.kind_of(r) == "review"
    }
    records: list[dict] = []
    errors: list[str] = []
    unchanged = 0
    if roster.get(reviewer) != "reviewer":
        return [], [f"{reviewer!r} is not listed as a reviewer in the roster"], 0

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
        correction = (row.get("correction") or "").strip()
        scores = (int(meaning), int(fluency))
        if saved.get((pair_hash, reviewer, batch)) == (*scores, notes, correction):
            unchanged += 1
            continue
        saved[(pair_hash, reviewer, batch)] = (*scores, notes, correction)
        records.append(
            {
                "kind": "review",
                "pair_hash": pair_hash,
                "meaning": scores[0],
                "fluency": scores[1],
                "reviewer": reviewer,
                "reviewed_on": reviewed_on,
                "recorded_at": recorded_at,
                "batch": batch,
                "notes": notes,
                "correction": correction,
            }
        )
    return records, errors, unchanged


def approval_sheet(records: list[dict], con: sqlite3.Connection, min_reviewers: int = 1) -> list[dict]:
    """Rows for the lead editor: every pair reviewers found acceptable and nobody has approved yet."""
    decisions = corpus_reviews.decide(records, min_reviewers)
    latest: dict[tuple[str, str], dict] = {}
    for record_ in records:
        if corpus_reviews.kind_of(record_) == "review":
            latest[(record_["pair_hash"], record_["reviewer"])] = record_
    rows = []
    for pair_hash, decision in sorted(decisions.items()):
        if decision.status != corpus_reviews.READY_FOR_APPROVAL:
            continue
        found = con.execute(
            "SELECT normalized_source_text, normalized_target_text FROM parallel_sentences WHERE pair_hash = ?",
            (pair_hash,),
        ).fetchone()
        if found is None:
            continue
        reviews = [latest[(pair_hash, code)] for code in decision.reviewers]
        rows.append(
            {
                "item_id": f"A{len(rows) + 1:05d}",
                "english": found[0],
                "zomi": found[1],
                "reviews": "; ".join(f"{r['reviewer']} meaning {r['meaning']} fluency {r['fluency']}" for r in reviews),
                "reviewer_notes": "; ".join(f"{r['reviewer']}: {r['notes']}" for r in reviews if r.get("notes")),
                "corrections": "; ".join(f"{r['reviewer']}: {r['correction']}" for r in reviews if r.get("correction")),
                "decision": "",
                "notes": "",
                "pair_hash": pair_hash,
                "text_sha256": exported_text_digest(found[0], found[1]),
            }
        )
    return rows


def approve(
    rows: list[dict],
    *,
    approver: str,
    roster: dict[str, str],
    existing: list[dict],
    approved_on: str,
    batch: str,
    recorded_at: str = "",
    min_reviewers: int = 1,
) -> tuple[list[dict], list[str]]:
    """Turn the lead editor's approval sheet into approval records. Returns (new records, errors).

    Blank decisions are skipped. The approver must be a roster lead editor and must
    not have reviewed the pair; the pair must still be READY_FOR_APPROVAL; the
    English and Zomi must be exactly what the sheet was made with.
    """
    if roster.get(approver) != "lead_editor":
        return [], [f"{approver!r} is not listed as a lead_editor in the roster"]
    decisions = corpus_reviews.decide(existing, min_reviewers)
    records, errors = [], []
    for row in rows:
        item_id = (row.get("item_id") or "").strip() or "<blank>"
        decision = (row.get("decision") or "").strip().lower()
        if not decision:
            continue
        if decision not in corpus_reviews.DECISIONS:
            errors.append(f"{item_id}: decision must be approve or reject, not {decision!r}")
            continue
        pair_hash = (row.get("pair_hash") or "").strip()
        english, zomi = row.get("english") or "", row.get("zomi") or ""
        if exported_text_digest(english, zomi) != (row.get("text_sha256") or "").strip() or pair_key(english, zomi) != pair_hash:
            errors.append(f"{item_id}: English or Zomi text differs from the sheet as made; decide on the original text")
            continue
        current = decisions.get(pair_hash)
        if current is None or current.status != corpus_reviews.READY_FOR_APPROVAL:
            status = current.status if current else "not reviewed"
            errors.append(f"{item_id}: not ready for approval (now {status}); make a new approval sheet")
            continue
        if approver in current.reviewers:
            errors.append(f"{item_id}: {approver} reviewed this pair; a different lead editor must approve it")
            continue
        records.append(
            {
                "kind": "approval",
                "pair_hash": pair_hash,
                "decision": decision,
                "approver": approver,
                "approved_on": approved_on,
                "recorded_at": recorded_at,
                "batch": batch,
                "notes": (row.get("notes") or "").strip(),
            }
        )
    return records, errors


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_inputs(reviews: Path, roster: Path) -> tuple[list[dict], dict[str, str]]:
    if not roster.exists():
        sys.exit(f"Roster not found: {roster} (CSV with columns code, role; see docs/GENERATOR_REVIEW.md)")
    try:
        return (corpus_reviews.load(reviews) if reviews.exists() else []), corpus_reviews.load_roster(roster)
    except ValueError as error:
        sys.exit(f"Nothing was saved: {error}")


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


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
    existing, roster = load_inputs(args.reviews, args.roster)
    con = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True) if args.database else None
    try:
        records, errors, unchanged = record(
            read_csv(args.review),
            read_csv(args.key),
            reviewer=args.reviewer,
            reviewed_on=args.date,
            batch=args.batch or args.key.parent.name,
            existing=existing,
            roster=roster,
            recorded_at=utc_timestamp(),
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


def cmd_approval_sheet(args: argparse.Namespace) -> int:
    if not args.reviews.exists():
        sys.exit(f"Reviews file not found: {args.reviews}")
    try:
        records = corpus_reviews.load(args.reviews)
    except ValueError as error:
        sys.exit(str(error))
    con = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
    try:
        rows = approval_sheet(records, con, args.min_reviewers)
    finally:
        con.close()
    write_csv(args.out, APPROVAL_COLUMNS, rows)
    print(f"wrote {len(rows)} pairs ready for approval to {args.out}")
    print("lead editor: write approve or reject in the decision column; leave blank to decide later")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    existing, roster = load_inputs(args.reviews, args.roster)
    records, errors = approve(
        read_csv(args.sheet),
        approver=args.approver,
        roster=roster,
        existing=existing,
        approved_on=args.date,
        batch=args.batch or args.sheet.stem,
        recorded_at=utc_timestamp(),
        min_reviewers=args.min_reviewers,
    )
    for error in errors:
        print(f"error: {error}")
    if errors:
        print("nothing saved; fix the rows above and run again")
        return 1
    corpus_reviews.append(args.reviews, records)
    approved = sum(1 for r in records if r["decision"] == "approve")
    print(f"saved {approved} approvals and {len(records) - approved} rejections by {args.approver} to {args.reviews}")
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
    record_parser.add_argument("--roster", type=Path, default=DEFAULT_ROSTER, help="private CSV: code, role[, name]")
    record_parser.add_argument("--date", default=date.today().isoformat(), help="day the ratings were made")
    record_parser.add_argument("--batch", help="name of this review batch (default: the key file's folder)")
    record_parser.add_argument("--database", type=Path, help="only for key files without a pair_hash column")
    record_parser.set_defaults(run=cmd_record)

    sheet_parser = commands.add_parser("approval-sheet", help="pairs reviewers found acceptable, for the lead editor")
    sheet_parser.add_argument("--database", type=Path, required=True)
    sheet_parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    sheet_parser.add_argument("--out", type=Path, required=True)
    sheet_parser.add_argument("--min-reviewers", type=int, default=1)
    sheet_parser.set_defaults(run=cmd_approval_sheet)

    approve_parser = commands.add_parser("approve", help="save a lead editor's approve/reject decisions")
    approve_parser.add_argument("sheet", type=Path)
    approve_parser.add_argument("--approver", required=True, help="roster code of the lead editor, e.g. E01")
    approve_parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    approve_parser.add_argument("--roster", type=Path, default=DEFAULT_ROSTER)
    approve_parser.add_argument("--date", default=date.today().isoformat())
    approve_parser.add_argument("--batch", help="name of this approval batch (default: the sheet's file name)")
    approve_parser.add_argument("--min-reviewers", type=int, default=1)
    approve_parser.set_defaults(run=cmd_approve)

    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
