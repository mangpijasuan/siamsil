"""Saved human review decisions for parallel-corpus pairs (SOP-07).

Reviewers rate pairs with review_sample.py (meaning and fluency, each 0-2).
`review_sample.py record` appends each rating to a JSON-lines file kept
outside the database, so ratings survive every rebuild:

  {"pair_hash": "...", "meaning": 2, "fluency": 1, "reviewer": "R01",
   "reviewed_on": "2026-10-24", "batch": "generator-review-v1", "notes": ""}

Records are never edited or deleted. A reviewer who rates a pair again adds a
new record, and their latest one counts. build_language_db.py turns the
records into one decision per pair:

  rejected  any reviewer's latest meaning is 0 (wrong or missing meaning)
  accepted  at least `min_reviewers` reviewers, and every latest rating is
            acceptable: meaning 2 and fluency at least 1
  partial   anything else; the pair stays unverified

The file holds no sentence text, only pair hashes, scores, reviewer codes and
notes. Reviewer codes map to names in a private roster, never in this file.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

SCORES = (0, 1, 2)
REVIEWER_CODE = re.compile(r"^[A-Z]{1,3}[0-9]{2,4}$")
REQUIRED_FIELDS = ("pair_hash", "meaning", "fluency", "reviewer", "reviewed_on")


def acceptable(meaning: int, fluency: int) -> bool:
    """The acceptance rule shared with review_sample.py summarize (docs/GENERATOR_REVIEW.md)."""
    return meaning == 2 and fluency >= 1


def validate(record: dict) -> list[str]:
    errors = [f"missing {field}" for field in REQUIRED_FIELDS if record.get(field) in (None, "")]
    if errors:
        return errors
    if record["meaning"] not in SCORES or record["fluency"] not in SCORES:
        errors.append("meaning and fluency must each be 0, 1, or 2")
    if not REVIEWER_CODE.match(str(record["reviewer"])):
        errors.append("reviewer must be a roster code such as R01, not a name")
    if not re.fullmatch(r"[0-9a-f]{40}", str(record["pair_hash"])):
        errors.append("pair_hash must be the 40-character hash from the language database")
    return errors


def load(path: Path) -> list[dict]:
    """Read every record; a malformed line stops the build instead of being skipped."""
    records = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path.name} line {number}: not JSON ({error.msg})") from None
            problems = validate(record) if isinstance(record, dict) else ["not an object"]
            if problems:
                raise ValueError(f"{path.name} line {number}: {'; '.join(problems)}")
            records.append(record)
    return records


def append(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


@dataclass(frozen=True)
class Decision:
    status: str  # accepted, rejected or partial
    reviewers: int


def decide(records: list[dict], min_reviewers: int = 1) -> dict[str, Decision]:
    """One decision per pair hash, from each reviewer's latest record (file order)."""
    latest: dict[str, dict[str, tuple[int, int]]] = {}
    for record in records:
        latest.setdefault(record["pair_hash"], {})[record["reviewer"]] = (record["meaning"], record["fluency"])

    decisions = {}
    for pair_hash, by_reviewer in latest.items():
        ratings = list(by_reviewer.values())
        if any(meaning == 0 for meaning, _ in ratings):
            status = "rejected"
        elif len(ratings) >= min_reviewers and all(acceptable(m, f) for m, f in ratings):
            status = "accepted"
        else:
            status = "partial"
        decisions[pair_hash] = Decision(status, len(ratings))
    return decisions
