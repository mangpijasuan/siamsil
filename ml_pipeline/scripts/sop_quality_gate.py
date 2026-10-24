#!/usr/bin/env python3
"""SOP-07/08 quality gate for Siamsil language dataset candidates.

Usage: python ml_pipeline/scripts/sop_quality_gate.py input.jsonl --report report.json
Exit 0 only when every record passes. This never approves records; it verifies
documented approvals, permitted use, and split isolation for a proposed export.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

ALLOWED_SPLITS = {"train", "validation", "test"}
APPROVED = "HUMAN_APPROVED"


def normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def candidate_key(record: dict[str, Any]) -> str:
    """Canonical pair key prevents duplicates across any splits."""
    return hashlib.sha256(
        (normalized(record["english"]) + "\0" + normalized(record["zomi"])).encode("utf-8")
    ).hexdigest()


def person(value: Any) -> str:
    """Reviewer IDs compare without case or surrounding spaces, so " C " is the same person as "c"."""
    return value.strip().casefold() if isinstance(value, str) else ""


def check_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    pair_split: dict[str, str] = {}
    # Each side on its own: the same English (or Zomi) sentence in train and test
    # leaks the answer even when the other side was translated differently.
    side_split: dict[tuple[str, str], str] = {}
    family_split: dict[str, str] = {}
    counts = {name: 0 for name in sorted(ALLOWED_SPLITS)}

    def reject(index: int, record_id: str, code: str) -> None:
        errors.append({"line": index, "id": record_id, "code": code})

    if not records:
        reject(0, "", "empty_dataset")

    for index, row in enumerate(records, 1):
        if not isinstance(row, dict):
            reject(index, "", "record_not_object")
            continue

        record_id = row.get("id")
        if not isinstance(record_id, str) or not record_id.strip():
            reject(index, "", "missing_id")
            record_id = ""
        elif record_id in seen_ids:
            reject(index, record_id, "duplicate_id")
        seen_ids.add(record_id)

        for language in ("english", "zomi"):
            value = row.get(language)
            if not isinstance(value, str) or not value.strip():
                reject(index, record_id, "missing_" + language)

        split = row.get("split")
        if split not in ALLOWED_SPLITS:
            reject(index, record_id, "invalid_split")
        else:
            counts[split] += 1

        if row.get("review_status") != APPROVED:
            reject(index, record_id, "not_human_approved")
        contributor = row.get("contributor_id")
        reviewer = row.get("reviewer_id")
        approver = row.get("approver_id")
        if not all(isinstance(v, str) and v.strip() for v in (contributor, reviewer, approver)):
            reject(index, record_id, "missing_review_identity")
        elif person(contributor) in (person(reviewer), person(approver)):
            reject(index, record_id, "self_approval")

        if not isinstance(row.get("approval_version"), str) or not row["approval_version"].strip():
            reject(index, record_id, "missing_approval_version")
        if not isinstance(row.get("source_id"), str) or not row["source_id"].strip():
            reject(index, record_id, "missing_provenance")

        # Explicit source permissions, never infer from reviewer approval.
        permissions = row.get("rights")
        if not isinstance(permissions, dict) or permissions.get("train") is not True:
            reject(index, record_id, "training_rights_not_cleared")
        if row.get("origin_language") not in ("en", "zom"):
            reject(index, record_id, "invalid_origin_language")

        if split in ALLOWED_SPLITS:
            family = row.get("split_family_id")
            if not isinstance(family, str) or not family.strip():
                reject(index, record_id, "missing_split_family_id")
            else:
                prior = family_split.setdefault(family, split)
                if prior != split:
                    reject(index, record_id, "split_family_leakage")
            if all(isinstance(row.get(lang), str) and row[lang].strip() for lang in ("english", "zomi")):
                key = candidate_key(row)
                if key in pair_split:
                    same_split = pair_split[key] == split
                    reject(index, record_id, "duplicate_pair" if same_split else "duplicate_pair_across_splits")
                else:
                    pair_split[key] = split
                    for language in ("english", "zomi"):
                        side = (language, normalized(row[language]))
                        if side_split.setdefault(side, split) != split:
                            reject(index, record_id, f"{language}_across_splits")

    return {
        "passed": not errors,
        "records": len(records),
        "splits": counts,
        "error_count": len(errors),
        "errors": errors,
        "policy": "SOP-07/08 quality-gate v1; requires independent human and rights approval",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Candidate JSONL export")
    parser.add_argument("--report", type=Path, help="Write deterministic JSON quality report")
    args = parser.parse_args(argv)
    rows = []
    try:
        with args.input.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    report = {"passed": False, "records": len(rows), "error_count": 1,
                              "errors": [{"line": line_number, "code": "invalid_json"}]}
                    break
            else:
                report = check_records(rows)
    except (OSError, UnicodeError) as exc:
        parser.error(f"Unable to read candidate dataset: {type(exc).__name__}")
    result = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(result, encoding="utf-8")
    print(result, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
