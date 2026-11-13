"""Approved corrections to the Zomi of parallel-corpus pairs (docs/GENERATOR_REVIEW.md).

A reviewer who finds a pair wrong can write the right Zomi in the `correction` column of a review
(corpus_reviews.py). That correction is only a proposal: it never replaces the stored text. It becomes
the pair's text through one more human step, kept in its own append-only JSON-lines file next to the
reviews (data/reviews/corpus-revisions.jsonl), the same two-person rule as the dictionary's corrections:

   {"kind": "revision", "pair_hash": "...", "before": "<Zomi the reviewer corrected>", "after": "<the fix>",
    "proposed_by": ["R01"], "approver": "E01", "approved_on": "2026-11-14", "recorded_at": "...Z",
    "batch": "corrections-1", "notes": ""}

A lead editor who did not propose the fix approves it, and only a fix a reviewer actually wrote can be approved
(the lead editor chooses between proposals; they do not type new Zomi here). A declined fix is recorded
as {"kind": "declined", "pair_hash", "after", "approver", ...} so it is not offered again.

Records are never edited or deleted, and hold the Zomi text of one sentence each, so this file stays private
with the reviews. build_language_db.py applies a revision only where the pair still holds the `before` text, and
keeps the pair's original hash, so the saved reviews still find it. The original Zomi stays in `raw_target_text`.
"""

from __future__ import annotations

import re
from pathlib import Path

from corpus_reviews import CODE, append, dumps, kind_of, load_roster, roster_problems

# Callers use these through this module, as they do for dictionary_reviews.py.
__all__ = ["CODE", "append", "dumps", "kind_of", "load_roster", "roster_problems", "validate", "load",
           "latest_revisions", "declined", "proposals", "same_text"]

KINDS = ("revision", "declined")
REQUIRED = {
    "revision": ("pair_hash", "before", "after", "proposed_by", "approver", "approved_on"),
    "declined": ("pair_hash", "after", "approver", "approved_on"),
}
PAIR_HASH = re.compile(r"^[0-9a-f]{40}$")
LINE_BREAKS = re.compile(r"[\r\n  ]")


def same_text(a: str, b: str) -> bool:
    return " ".join(str(a).split()) == " ".join(str(b).split())


def validate(record: dict) -> list[str]:
    kind = kind_of(record)
    if kind not in KINDS:
        return [f"unknown kind {kind!r}"]
    errors = [f"missing {name}" for name in REQUIRED[kind] if record.get(name) in (None, "", [])]
    if errors:
        return errors
    if not PAIR_HASH.match(str(record["pair_hash"])):
        errors.append("pair_hash must be the 40-character hash from the language database")
    if not CODE.match(str(record["approver"])):
        errors.append("approver must be a roster code such as E01, not a name")
    if not str(record["after"]).strip() or LINE_BREAKS.search(str(record["after"])):
        errors.append("the corrected Zomi must be one line of text")
    if kind == "revision":
        proposers = record["proposed_by"]
        if not isinstance(proposers, list) or not all(CODE.match(str(code)) for code in proposers):
            errors.append("proposed_by must be a list of roster codes")
        elif record["approver"] in proposers:
            errors.append("a lead editor cannot approve their own correction")
        if same_text(record["before"], record["after"]):
            errors.append("the correction does not change the Zomi")
    return errors


def load(path: Path) -> list[dict]:
    """Every record of the revisions file; a malformed line stops the caller instead of being skipped."""
    import json

    records: list[dict] = []
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


def latest_revisions(records: list[dict]) -> dict[str, dict]:
    """The newest approved revision of each pair, from a revisions file in order."""
    latest: dict[str, dict] = {}
    for record in records:
        if kind_of(record) == "revision":
            latest[record["pair_hash"]] = record
    return latest


def declined(records: list[dict]) -> set[tuple[str, str]]:
    """(pair hash, corrected text) of every correction a lead editor declined, so it is not offered again."""
    return {(r["pair_hash"], " ".join(r["after"].split())) for r in records if kind_of(r) == "declined"}


def proposals(review_records: list[dict]) -> dict[str, dict[str, list[str]]]:
    """pair hash -> corrected text -> the reviewers whose latest review proposes it."""
    latest: dict[tuple[str, str], dict] = {}
    for record in review_records:
        if kind_of(record) == "review":
            latest[(record["pair_hash"], record["reviewer"])] = record
    found: dict[str, dict[str, list[str]]] = {}
    for (pair_hash, reviewer), record in sorted(latest.items()):
        fix = " ".join(str(record.get("correction") or "").split())
        if fix:
            found.setdefault(pair_hash, {}).setdefault(fix, []).append(reviewer)
    return found
