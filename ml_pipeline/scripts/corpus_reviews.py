"""Saved human review decisions for parallel-corpus pairs (SOP-07).

Machine-generated pairs are never approved automatically. A pair becomes
HUMAN_APPROVED only in two human steps, kept in one append-only JSON-lines file
outside the database so they survive every rebuild:

1. A qualified reviewer rates it (review_sample.py record):
   {"kind": "review", "pair_hash": "...", "meaning": 2, "fluency": 1,
    "reviewer": "R01", "reviewed_on": "2026-10-25", "recorded_at": "...Z",
    "batch": "generator-review-v1", "notes": "", "correction": ""}
2. A lead editor, who did not review that pair, approves or rejects it
   (review_sample.py approve):
   {"kind": "approval", "pair_hash": "...", "decision": "approve",
    "approver": "E01", "approved_on": "2026-10-26", "recorded_at": "...Z",
    "batch": "approval-1", "notes": ""}

Records are never edited or deleted. A reviewer who rates a pair again adds a new
record and their latest one counts; an approval counts only if it is newer than
every review it rests on. Corrections are kept for editors and never replace the
stored text. Status per pair, using the SOP manual's names:

  REJECTED            a reviewer's latest meaning is 0, or the latest approval rejects it
  HUMAN_APPROVED      enough reviewers rated it acceptable (meaning 2, fluency >= 1), and
                      a lead editor who is not one of them approved it afterwards
  READY_FOR_APPROVAL  enough acceptable reviews, no valid approval yet
  NEEDS_CORRECTION    anything else that has been reviewed

Codes are checked against a private roster (CSV with columns code, role, and
optionally name) so only listed reviewers and lead editors can be recorded. The
reviews file holds no sentence text and no names.
"""

from __future__ import annotations

import csv
import json
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

try:
    import fcntl
except ImportError:  # Windows: no advisory locks; appends and exports are not coordinated there.
    fcntl = None

SCORES = (0, 1, 2)
CODE = re.compile(r"^[A-Z]{1,3}[0-9]{2,4}$")
REVIEWER_CODE = CODE  # kept for callers that check format only
ROLES = ("reviewer", "lead_editor")
DECISIONS = ("approve", "reject")

HUMAN_APPROVED = "HUMAN_APPROVED"
READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
NEEDS_CORRECTION = "NEEDS_CORRECTION"
REJECTED = "REJECTED"
STATUSES = (HUMAN_APPROVED, READY_FOR_APPROVAL, NEEDS_CORRECTION, REJECTED)

REQUIRED = {
    "review": ("pair_hash", "meaning", "fluency", "reviewer", "reviewed_on"),
    "approval": ("pair_hash", "decision", "approver", "approved_on"),
}


def acceptable(meaning: int, fluency: int) -> bool:
    """The acceptance rule shared with review_sample.py summarize (docs/GENERATOR_REVIEW.md)."""
    return meaning == 2 and fluency >= 1


def kind_of(record: dict) -> str:
    # Records saved before approvals existed are reviews.
    return record.get("kind", "review")


def validate(record: dict) -> list[str]:
    kind = kind_of(record)
    if kind not in REQUIRED:
        return [f"unknown kind {kind!r}"]
    errors = [f"missing {field}" for field in REQUIRED[kind] if record.get(field) in (None, "")]
    if errors:
        return errors
    if not re.fullmatch(r"[0-9a-f]{40}", str(record["pair_hash"])):
        errors.append("pair_hash must be the 40-character hash from the language database")
    if kind == "review":
        # type() rather than `in SCORES` alone: JSON true and false would pass as 1 and 0.
        if any(type(record[field]) is not int or record[field] not in SCORES for field in ("meaning", "fluency")):
            errors.append("meaning and fluency must each be 0, 1, or 2")
        if not CODE.match(str(record["reviewer"])):
            errors.append("reviewer must be a roster code such as R01, not a name")
    else:
        if record["decision"] not in DECISIONS:
            errors.append("decision must be approve or reject")
        if not CODE.match(str(record["approver"])):
            errors.append("approver must be a roster code such as E01, not a name")
    return errors


def load(path: Path) -> list[dict]:
    """Read every record; a malformed line stops the caller instead of being skipped."""
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


def dumps(record: dict) -> str:
    """One line of the decisions file."""
    return json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"


@contextmanager
def locked(folder: Path) -> Iterator[None]:
    """Hold an exclusive lock on the folder of a decisions file while it is written.

    The folder, not the file, is locked: an export replaces the file, and a lock on the
    replaced file would no longer protect anything.
    """
    folder.mkdir(parents=True, exist_ok=True)
    if fcntl is None:
        yield
        return
    descriptor = os.open(folder, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def append(path: Path, records: list[dict]) -> None:
    with locked(path.parent):
        with path.open("a", encoding="utf-8") as handle:
            handle.writelines(dumps(record) for record in records)


def load_roster(path: Path) -> dict[str, str]:
    """code -> role from the private roster CSV (columns: code, role[, name])."""
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    roster = {}
    for number, row in enumerate(rows, start=2):
        code, role = (row.get("code") or "").strip(), (row.get("role") or "").strip()
        if not CODE.match(code) or role not in ROLES:
            raise ValueError(f"{path.name} line {number}: needs a code like R01 and a role of {' or '.join(ROLES)}")
        if code in roster:
            raise ValueError(f"{path.name} line {number}: code {code} listed twice")
        roster[code] = role
    return roster


def roster_problems(records: list[dict], roster: dict[str, str]) -> list[str]:
    """Records whose reviewer or approver is not in the roster with the matching role."""
    problems = []
    for number, record in enumerate(records, start=1):
        if kind_of(record) == "review":
            code, role = record["reviewer"], "reviewer"
        else:
            code, role = record["approver"], "lead_editor"
        if roster.get(code) != role:
            problems.append(f"record {number}: {code} is not listed as a {role} in the roster")
    return problems


@dataclass(frozen=True)
class Decision:
    status: str
    reviewers: tuple[str, ...]
    approver: str | None = None


def decide(records: list[dict], min_reviewers: int = 1) -> dict[str, Decision]:
    """One SOP status per pair hash, from the records in file order."""
    reviews: dict[str, dict[str, tuple[int, int, int]]] = {}
    approvals: dict[str, tuple[int, str, str]] = {}
    for position, record in enumerate(records):
        pair = record["pair_hash"]
        if kind_of(record) == "review":
            reviews.setdefault(pair, {})[record["reviewer"]] = (record["meaning"], record["fluency"], position)
        else:
            approvals[pair] = (position, record["decision"], record["approver"])

    decisions = {}
    for pair, by_reviewer in reviews.items():
        reviewers = tuple(sorted(by_reviewer))
        latest_review = max(position for _, _, position in by_reviewer.values())
        approval = approvals.get(pair)
        # An approval only counts for the reviews it saw, and never from one of the reviewers.
        if approval and (approval[0] < latest_review or approval[2] in by_reviewer):
            approval = None
        ready = len(by_reviewer) >= min_reviewers and all(acceptable(m, f) for m, f, _ in by_reviewer.values())
        if any(meaning == 0 for meaning, _, _ in by_reviewer.values()) or (approval and approval[1] == "reject"):
            status = REJECTED
        elif ready and approval:
            status = HUMAN_APPROVED
        elif ready:
            status = READY_FOR_APPROVAL
        else:
            status = NEEDS_CORRECTION
        decisions[pair] = Decision(status, reviewers, approval[2] if approval else None)
    return decisions
