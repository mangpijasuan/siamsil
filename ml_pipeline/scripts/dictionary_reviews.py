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

Owner-only review (working phase, owner decision 2026-11-18, docs/SZSF.md "Owner-approved records"):
the project owner may review, approve and correct as the only person. It is off unless the caller passes
the owner's roster code, and every record made that way says so:
   "approval": "owner_sole"
Such a record is valid only when its reviewer/approver is that code (and, for a correction, the only
proposer is that code). A sense the owner reviewed and approved alone is OWNER_APPROVED, never
HUMAN_APPROVED: it is the owner's final editorial decision, not an independent review, and counts apart.
Without the owner code, a file holding owner_sole records is refused, and the ordinary rules apply.
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
    append,
    dumps,
    kind_of,
    load_roster,
)

OWNER_SOLE = "owner_sole"
OWNER_APPROVED = "OWNER_APPROVED"
STATUSES = (HUMAN_APPROVED, OWNER_APPROVED, READY_FOR_APPROVAL, NEEDS_CORRECTION, REJECTED)
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
    # The database has no owner-only state, and "approved" would read as an independent review.
    OWNER_APPROVED: "in_review",
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


def owner_errors(record: dict, owner_code: str | None) -> list[str]:
    """Problems with an `approval: owner_sole` marker; none when the record has no marker."""
    marker = record.get("approval")
    if marker is None:
        return []
    if marker != OWNER_SOLE:
        return [f"approval must be '{OWNER_SOLE}' when present"]
    if not owner_code:
        return ["an owner_sole record needs the owner's roster code (--owner-code)"]
    kind = kind_of(record)
    if kind == "review":
        who = [record.get("reviewer")]
    elif kind == "revision":
        who = [record.get("approver"), *(record.get("proposed_by") or [])]
    else:
        who = [record.get("approver")]
    if any(code != owner_code for code in who):
        return [f"owner_sole is only for the owner ({owner_code}) as the only reviewer, approver and proposer"]
    return []


def validate(record: dict, owner_code: str | None = None) -> list[str]:
    kind = kind_of(record)
    if kind not in REQUIRED:
        return [f"unknown kind {kind!r}"]
    errors = [f"missing {name}" for name in REQUIRED[kind] if record.get(name) in (None, "")]
    if errors:
        return errors
    marker_errors = owner_errors(record, owner_code)
    errors += marker_errors
    owner_ok = record.get("approval") == OWNER_SOLE and not marker_errors
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
        elif record["approver"] in proposers and not owner_ok:
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


def load(path: Path, owner_code: str | None = None) -> list[dict]:
    """Every record of the decisions file; a malformed line stops the caller.

    owner_sole records are accepted only when `owner_code` is the code they name."""
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
            problems = validate(record, owner_code) if isinstance(record, dict) else ["not an object"]
            if problems:
                raise ValueError(f"{path.name} line {number}: {'; '.join(problems)}")
            records.append(record)
    return records


def roster_problems(records: list[dict], roster: dict[str, str]) -> list[str]:
    """Records whose reviewer or approver is not in the roster with the matching role.

    An owner_sole record is exempt: validate() has already tied it to the owner's code."""
    problems = []
    for number, record in enumerate(records, start=1):
        if record.get("approval") == OWNER_SOLE:
            continue
        if kind_of(record) == "review":
            code, role = record["reviewer"], "reviewer"
        else:
            code, role = record["approver"], "lead_editor"
        if roster.get(code) != role:
            problems.append(f"record {number}: {code} is not listed as a {role} in the roster")
    return problems


@dataclass
class Decision:
    status: str
    reviewers: tuple[str, ...]
    approver: str | None = None
    corrections: dict[str, str] = field(default_factory=dict)


def decide(records: list[dict], min_reviewers: int = 1, owner_code: str | None = None) -> dict[str, Decision]:
    """One status per sense id, from the records in file order.

    The owner, given as `owner_code`, may approve a sense they reviewed only through a record marked
    owner_sole; the sense is then OWNER_APPROVED, not HUMAN_APPROVED."""
    reviews: dict[str, dict[str, tuple[str, str, int]]] = {}
    approvals: dict[str, tuple[int, str, str, bool]] = {}
    for position, record in enumerate(records):
        sense = record["sense_id"]
        if kind_of(record) == "review":
            reviews.setdefault(sense, {})[record["reviewer"]] = (
                record["decision"], str(record.get("correction") or "").strip(), position)
        elif kind_of(record) == "approval":
            approvals[sense] = (position, record["decision"], record["approver"],
                                record.get("approval") == OWNER_SOLE and record["approver"] == owner_code)

    decisions = {}
    for sense, by_reviewer in reviews.items():
        latest_review = max(position for _, _, position in by_reviewer.values())
        approval = approvals.get(sense)
        owner_only = bool(approval and approval[3] and approval[2] in by_reviewer)
        if approval and (approval[0] < latest_review or (approval[2] in by_reviewer and not approval[3])):
            approval = None
        choices = [choice for choice, _, _ in by_reviewer.values()]
        ready = len(by_reviewer) >= min_reviewers and all(choice == "correct" for choice in choices)
        if any(choice in ("not_tedim", "wrong") for choice in choices) or (approval and approval[1] == "reject"):
            status = REJECTED
        elif ready and approval:
            status = OWNER_APPROVED if owner_only else HUMAN_APPROVED
        elif ready:
            status = READY_FOR_APPROVAL
        else:
            status = NEEDS_CORRECTION
        corrections = {code: fix for code, (choice, fix, _) in by_reviewer.items() if choice == "fix"}
        decisions[sense] = Decision(status, tuple(sorted(by_reviewer)), approval[2] if approval else None, corrections)
    return decisions
