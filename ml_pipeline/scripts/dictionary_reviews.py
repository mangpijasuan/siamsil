"""Saved human review decisions for editorial dictionary senses (docs/DICTIONARY.md).

The same two human steps as corpus reviews (corpus_reviews.py), in their own append-only
JSON-lines file in the private siamsil-data repository (reviews/dictionary-reviews.jsonl):

1. A reviewer judges the sense's Zomi:
   {"kind": "review", "sense_id": "ZD-000123", "decision": "correct", "correction": "",
    "shown": "<sha1 of the Zomi the reviewer saw>", "reviewer": "R01",
    "reviewed_on": "2026-11-02", "recorded_at": "...Z", "batch": "dict-R01-0001", "notes": ""}
   decision is one of
     correct    the Zomi is right and natural Tedim for this meaning
     fix        something should change; the reviewer's full corrected Zomi is in `correction`
     not_tedim  another Chin language (Hakha, Falam, Mizo, ...) or not Zomi at all
     wrong      the Zomi does not mean this
2. A lead editor, who did not review that sense, approves or rejects senses every reviewer
   found correct:
   {"kind": "approval", "sense_id": "...", "decision": "approve", "approver": "E01",
    "approved_on": "...", "recorded_at": "...Z", "batch": "...", "notes": ""}

Records are never edited or deleted; a reviewer's latest record counts, and an approval
counts only if it is newer than every review it rests on. Corrections are kept for editors
and never replace the stored text automatically. Status per sense:

  REJECTED            a reviewer's latest decision is not_tedim or wrong, or the approval rejects it
  HUMAN_APPROVED      enough reviewers found it correct, and a lead editor who is not one of
                      them approved it afterwards
  READY_FOR_APPROVAL  enough reviewers found it correct, no valid approval yet
  NEEDS_CORRECTION    a reviewer asked for a fix (or too few reviewers so far)

Reviewer and approver codes are checked against the private roster (corpus_reviews.load_roster).

Corrections become text only through a third record, in reviews/dictionary-revisions.jsonl: a lead
editor who did not propose it approves one reviewer's fix, and the revision records the Zomi before
and after, who proposed it, and who approved it.
   {"kind": "revision", "sense_id": "ZD-000123", "before": "...", "after": "...",
    "proposed_by": ["R01"], "approver": "E01", "approved_on": "2026-11-03", "recorded_at": "...Z",
    "batch": "dict-corrections-0001", "notes": ""}
A declined correction is recorded as {"kind": "declined", "sense_id", "after", "approver", ...}, so
it is not offered again; the sense stays open for review.
Revisions are applied to the editorial database (dictionary_review.py apply) and to the language
release (build_language_db.py) only where the sense still holds the `before` text.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from corpus_reviews import (  # noqa: F401  (re-exported for callers)
    CODE,
    HUMAN_APPROVED,
    NEEDS_CORRECTION,
    READY_FOR_APPROVAL,
    REJECTED,
    STATUSES,
    append,
    dumps,
    kind_of,
    load_roster,
    roster_problems,
)

REVIEW_DECISIONS = ("correct", "fix", "not_tedim", "wrong")
APPROVAL_DECISIONS = ("approve", "reject")
SENSE_ID = re.compile(r"^(ZD|ZS)-[0-9]{6,}$")
REQUIRED = {
    "review": ("sense_id", "decision", "shown", "reviewer", "reviewed_on"),
    "approval": ("sense_id", "decision", "approver", "approved_on"),
    "revision": ("sense_id", "before", "after", "proposed_by", "approver", "approved_on"),
    "declined": ("sense_id", "after", "approver", "approved_on"),
}
# Database review_status for each decision status (models/dictionary.py REVIEW_STATUSES).
REVIEW_STATUS = {
    HUMAN_APPROVED: "approved",
    READY_FOR_APPROVAL: "in_review",
    NEEDS_CORRECTION: "needs_correction",
    REJECTED: "rejected",
}


def same_text(a: str, b: str) -> bool:
    return " ".join(str(a).split()) == " ".join(str(b).split())


def latest_revisions(records: list[dict]) -> dict[str, dict]:
    """The newest revision of each sense, from a revisions file in order."""
    latest: dict[str, dict] = {}
    for record in records:
        if kind_of(record) == "revision":
            latest[record["sense_id"]] = record
    return latest


def shown_digest(zomi: str) -> str:
    """Fingerprint of the Zomi a reviewer saw, so a review of older text can be detected."""
    return hashlib.sha1(" ".join(zomi.split()).encode("utf-8")).hexdigest()


def validate(record: dict) -> list[str]:
    kind = kind_of(record)
    if kind not in REQUIRED:
        return [f"unknown kind {kind!r}"]
    errors = [f"missing {name}" for name in REQUIRED[kind] if record.get(name) in (None, "")]
    if errors:
        return errors
    if not SENSE_ID.match(str(record["sense_id"])):
        errors.append("sense_id must look like ZD-000123 or ZS-000123")
    if kind == "review":
        if record["decision"] not in REVIEW_DECISIONS:
            errors.append(f"decision must be one of {', '.join(REVIEW_DECISIONS)}")
        elif record["decision"] == "fix" and not str(record.get("correction") or "").strip():
            errors.append("a fix needs the corrected Zomi")
        if not CODE.match(str(record["reviewer"])):
            errors.append("reviewer must be a roster code such as R01, not a name")
    elif kind == "revision":
        proposers = record["proposed_by"]
        if not isinstance(proposers, list) or not all(CODE.match(str(code)) for code in proposers):
            errors.append("proposed_by must be a list of roster codes")
        elif record["approver"] in proposers:
            errors.append("a lead editor cannot approve their own correction")
        if not CODE.match(str(record["approver"])):
            errors.append("approver must be a roster code such as E01, not a name")
        if same_text(record["before"], record["after"]):
            errors.append("the correction does not change the Zomi")
    elif kind == "declined":
        if not CODE.match(str(record["approver"])):
            errors.append("approver must be a roster code such as E01, not a name")
    else:
        if record["decision"] not in APPROVAL_DECISIONS:
            errors.append("decision must be approve or reject")
        if not CODE.match(str(record["approver"])):
            errors.append("approver must be a roster code such as E01, not a name")
    return errors


def load(path: Path) -> list[dict]:
    """Every record of the decisions file; a malformed line stops the caller."""
    import json

    records = []
    if not path.exists():
        return records
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


@dataclass
class Decision:
    status: str
    reviewers: tuple[str, ...]
    approver: str | None = None
    corrections: dict[str, str] = field(default_factory=dict)


def decide(records: list[dict], min_reviewers: int = 1) -> dict[str, Decision]:
    """One status per sense id, from the records in file order."""
    reviews: dict[str, dict[str, tuple[str, str, int]]] = {}
    approvals: dict[str, tuple[int, str, str]] = {}
    for position, record in enumerate(records):
        sense = record["sense_id"]
        if kind_of(record) == "review":
            reviews.setdefault(sense, {})[record["reviewer"]] = (
                record["decision"], str(record.get("correction") or "").strip(), position)
        elif kind_of(record) == "approval":
            approvals[sense] = (position, record["decision"], record["approver"])

    decisions = {}
    for sense, by_reviewer in reviews.items():
        latest_review = max(position for _, _, position in by_reviewer.values())
        approval = approvals.get(sense)
        if approval and (approval[0] < latest_review or approval[2] in by_reviewer):
            approval = None
        choices = [choice for choice, _, _ in by_reviewer.values()]
        ready = len(by_reviewer) >= min_reviewers and all(choice == "correct" for choice in choices)
        if any(choice in ("not_tedim", "wrong") for choice in choices) or (approval and approval[1] == "reject"):
            status = REJECTED
        elif ready and approval:
            status = HUMAN_APPROVED
        elif ready:
            status = READY_FOR_APPROVAL
        else:
            status = NEEDS_CORRECTION
        corrections = {code: fix for code, (choice, fix, _) in by_reviewer.items() if choice == "fix"}
        decisions[sense] = Decision(status, tuple(sorted(by_reviewer)), approval[2] if approval else None, corrections)
    return decisions
