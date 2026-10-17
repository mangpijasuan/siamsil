#!/usr/bin/env python3
"""Prepare and finalize a private, independently sourced Zomi gold test set.

No machine-generated candidate is ever copied into reviewer packets or gold
references. Human source collection and translations must be supplied first.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from build_language_db import english_family_key, normalize_text, normalize_word

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "processed" / "language" / "siamsil_language.sqlite"
DEFAULT_OUTPUT = ROOT / "data" / "evaluation" / "gold_private" / "v1"
LANGUAGES = {"en": "zom", "zom": "en"}


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(path)
    rows: list[dict] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            rows.append(item)
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def validate_sources(rows: list[dict]) -> list[dict]:
    if not rows:
        raise ValueError("Provide independently sourced sentences before preparing a gold test")
    ids: set[str] = set()
    texts: set[tuple[str, str]] = set()
    directions: set[str] = set()
    normalized: list[dict] = []
    forbidden = {"candidate", "zomi_candidate", "model_output", "reference_translation", "translation"}
    for row in rows:
        if forbidden.intersection(row):
            raise ValueError("Gold source input must not contain machine candidates or translations")
        source_id = str(row.get("source_id", "")).strip()
        language = str(row.get("source_language", "")).strip()
        text = normalize_text(row.get("source_text"))
        domain = str(row.get("domain", "")).strip()
        rights = str(row.get("rights_reference", "")).strip()
        origin = str(row.get("source_origin", "")).strip()
        if not all((source_id, text, domain, rights, origin)) or language not in LANGUAGES:
            raise ValueError(f"Invalid or incomplete gold source row: {source_id or '[missing id]'}")
        key = (language, normalize_word(text))
        if source_id in ids or key in texts:
            raise ValueError(f"Duplicate source ID or normalized text: {source_id}")
        ids.add(source_id)
        texts.add(key)
        directions.add(language)
        normalized.append({
            "source_id": source_id, "source_language": language,
            "target_language": LANGUAGES[language], "source_text": text,
            "domain": domain, "source_origin": origin, "rights_reference": rights,
        })
    if directions != set(LANGUAGES):
        raise ValueError("Supply independent source sentences for both English→Zomi and Zomi→English")
    return normalized


def overlapping_sources(db: Path, sources: list[dict]) -> set[str]:
    """Block normalized exact overlap with the synthetic corpus in either direction."""
    if not db.is_file():
        raise FileNotFoundError(db)
    overlaps: set[str] = set()
    zomi_keys = {normalize_word(row["source_text"]): row["source_id"] for row in sources if row["source_language"] == "zom"}
    with sqlite3.connect(f"file:{db.resolve()}?mode=ro", uri=True) as con:
        for row in sources:
            if row["source_language"] == "en" and con.execute(
                "SELECT 1 FROM parallel_sentences WHERE family_hash = ? LIMIT 1",
                (english_family_key(row["source_text"]),),
            ).fetchone():
                overlaps.add(row["source_id"])
        if zomi_keys:
            for (target,) in con.execute("SELECT normalized_target_text FROM parallel_sentences"):
                source_id = zomi_keys.get(normalize_word(target))
                if source_id:
                    overlaps.add(source_id)
                    if len(overlaps) == len(sources):
                        break
    return overlaps


def prepare(sources_path: Path, db: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(f"Gold output already exists: {output}")
    sources = validate_sources(read_jsonl(sources_path))
    overlaps = overlapping_sources(db, sources)
    if overlaps:
        raise ValueError(f"Gold sources overlap the synthetic corpus: {', '.join(sorted(overlaps))}")
    output.mkdir(parents=True, exist_ok=False)
    write_jsonl(output / "sources.jsonl", sources)
    blind = [
        {"source_id": row["source_id"], "source_language": row["source_language"],
         "target_language": row["target_language"], "source_text": row["source_text"],
         "domain": row["domain"], "reviewer_id": "", "translation": "", "notes": ""}
        for row in sources
    ]
    write_jsonl(output / "reviewer_a_blank.jsonl", blind)
    write_jsonl(output / "reviewer_b_blank.jsonl", blind)
    write_jsonl(output / "adjudicator_blank.jsonl", blind)
    manifest = {
        "source_count": len(sources),
        "by_source_language": {language: sum(row["source_language"] == language for row in sources) for language in LANGUAGES},
        "source_sha256": hashlib.sha256((output / "sources.jsonl").read_bytes()).hexdigest(),
        "reference_status": "awaiting_two_independent_translators_and_adjudication",
        "leakage_check": "normalized exact overlap with the synthetic corpus only; near-duplicate/source-family review remains manual",
        "visibility": "private_local_only",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def validated_reviews(path: Path, source_ids: set[str]) -> dict[str, dict]:
    reviews: dict[str, dict] = {}
    for row in read_jsonl(path):
        source_id = str(row.get("source_id", "")).strip()
        reviewer_id = str(row.get("reviewer_id", "")).strip()
        translation = normalize_text(row.get("translation"))
        if source_id not in source_ids or source_id in reviews or not reviewer_id or not translation:
            raise ValueError(f"Missing, duplicate, or incomplete human review in {path}: {source_id}")
        reviews[source_id] = {"reviewer_id": reviewer_id, "translation": translation, "notes": str(row.get("notes", ""))}
    if set(reviews) != source_ids:
        raise ValueError(f"Review file does not cover every source: {path}")
    return reviews


def finalize(output: Path, reviewer_a: Path, reviewer_b: Path, adjudicator: Path) -> int:
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    source_sha = hashlib.sha256((output / "sources.jsonl").read_bytes()).hexdigest()
    if source_sha != manifest["source_sha256"]:
        raise ValueError("Gold source packet changed after preparation")
    sources = validate_sources(read_jsonl(output / "sources.jsonl"))
    source_ids = {row["source_id"] for row in sources}
    a = validated_reviews(reviewer_a, source_ids)
    b = validated_reviews(reviewer_b, source_ids)
    judge = validated_reviews(adjudicator, source_ids)
    final: list[dict] = []
    for row in sources:
        source_id = row["source_id"]
        reviewers = {a[source_id]["reviewer_id"], b[source_id]["reviewer_id"], judge[source_id]["reviewer_id"]}
        if len(reviewers) != 3:
            raise ValueError(f"Reviewers and adjudicator must be distinct for {source_id}")
        final.append({
            **row, "reference_translation": judge[source_id]["translation"],
            "reviewer_a_id": a[source_id]["reviewer_id"],
            "reviewer_b_id": b[source_id]["reviewer_id"],
            "adjudicator_id": judge[source_id]["reviewer_id"],
            "adjudication_notes": judge[source_id]["notes"],
            "reference_status": "human_adjudicated",
        })
    write_jsonl(output / "gold_test.jsonl", final)
    (output / "gold_test.manifest.json").write_text(json.dumps({
        "source_sha256": source_sha,
        "gold_sha256": hashlib.sha256((output / "gold_test.jsonl").read_bytes()).hexdigest(),
        "reference_count": len(final),
        "by_source_language": {language: sum(row["source_language"] == language for row in final) for language in LANGUAGES},
        "reference_status": "human_adjudicated",
        "rights_status": "requires_independent_release_review",
        "visibility": "private_local_only",
    }, indent=2) + "\n", encoding="utf-8")
    return len(final)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    setup = sub.add_parser("prepare")
    setup.add_argument("--sources", type=Path, required=True)
    setup.add_argument("--db", type=Path, default=DEFAULT_DB)
    setup.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    finish = sub.add_parser("finalize")
    finish.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    finish.add_argument("--reviewer-a", type=Path, required=True)
    finish.add_argument("--reviewer-b", type=Path, required=True)
    finish.add_argument("--adjudicator", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.sources, args.db, args.output)
        print(f"Prepared {result['source_count']} blind, private source items; no gold references yet")
    else:
        count = finalize(args.output, args.reviewer_a, args.reviewer_b, args.adjudicator)
        print(f"Finalized {count} adjudicated references in a private local file")


if __name__ == "__main__":
    main()
