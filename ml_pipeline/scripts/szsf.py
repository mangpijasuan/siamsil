#!/usr/bin/env python3
"""Check and describe a file in the Siamsil Zomi Standard Format (SZSF): docs/SZSF.md.

SZSF is the authoritative data schema and file standard for Siamsil's trained and reviewed Zomi data: one JSON
object per line, each carrying the original text, its standard form, where it came from, who reviewed it and
what it may be used for.

  validate   check every record, and optionally the rights and the manifest
  manifest   write the manifest of a valid file: counts, SHA-256, and a snapshot of each source's rights

  python3 ml_pipeline/scripts/szsf.py validate szsf-master-v1.0.0.jsonl --purpose training
  python3 ml_pipeline/scripts/szsf.py manifest szsf-master-v1.0.0.jsonl --out szsf-master-v1.0.0.manifest.json

A passing check says the file follows the format. It does not say the Zomi is correct, and it does not clear any
source: rights stay in data/rights.json and human approval stays with the reviewers.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RIGHTS = ROOT / "data" / "rights.json"

SZSF_VERSION = "1.0"
KINDS = ("translation_pair", "dictionary_sense")
TIERS = ("gold", "silver", "bronze")
SPLITS = ("train", "validation", "test", "excluded")
ORIGINS = ("human_written", "machine_generated", "unknown")
# The SOP-07 status names (ml_pipeline/scripts/corpus_reviews.py), plus the state before any review.
REVIEW_STATUSES = ("UNREVIEWED", "NEEDS_CORRECTION", "READY_FOR_APPROVAL", "HUMAN_APPROVED", "REJECTED")
PURPOSES = {"training": "train", "display": "display"}

CODE = re.compile(r"^[A-Z]\d{2}$")
RULE_ID = re.compile(r"^ZS-\d{3}$")
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
SENSE_ID = re.compile(r"^(ZD|ZS)-\d{6,}$")
# What UTF-8 text looks like after an export read it as Mac Roman: ’ -> ‚Äô, é -> √©. Never valid text.
DAMAGE = re.compile("‚Ä[ôúùòìî¶]|√[©±°®ß≠¢†§™´¨ÆØ∞≤≥¥µ∂∑∏π∫ªºΩæø¿¡¬ƒ≈∆«»…]")

REQUIRED = {
    "szsf_version", "id", "kind", "english", "zomi", "zomi_standard", "standard_version", "source",
    "origin", "tier", "split", "review",
}
OPTIONAL = {"zomi_standard_rules", "zomi_standard_flags", "model", "quality_score", "quality_flags", "reference"}
REVIEW_KEYS = {"status", "reviewers", "approver", "batch"}


def _text_problems(name: str, value: Any) -> list[str]:
    if not isinstance(value, str):
        return [f"{name} must be text"]
    problems = []
    if not value.strip():
        problems.append(f"{name} is empty")
    elif value != value.strip():
        problems.append(f"{name} has spaces at its start or end")
    if any(unicodedata.category(char) == "Cc" for char in value):
        problems.append(f"{name} has a control or line-break character")
    if unicodedata.normalize("NFC", value) != value:
        problems.append(f"{name} is not Unicode NFC")
    if DAMAGE.search(value):
        problems.append(f"{name} has damaged characters (UTF-8 read as Mac Roman)")
    return problems


def _list_of(name: str, value: Any, pattern: re.Pattern[str] | None = None) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        return [f"{name} must be a list of text"]
    if pattern and not all(pattern.match(item) for item in value):
        return [f"{name} has an entry of the wrong form"]
    return []


def _review_problems(record: dict[str, Any]) -> list[str]:
    review = record["review"]
    if not isinstance(review, dict):
        return ["review must be an object"]
    problems = [f"review has unknown field {key!r}" for key in sorted(set(review) - REVIEW_KEYS)]
    problems += [f"review needs {key}" for key in ("status", "reviewers", "approver") if key not in review]
    if problems:
        return problems
    status, reviewers, approver = review["status"], review["reviewers"], review["approver"]
    if status not in REVIEW_STATUSES:
        return [f"review.status must be one of {', '.join(REVIEW_STATUSES)}"]
    problems += _list_of("review.reviewers", reviewers, CODE)
    if approver is not None and not (isinstance(approver, str) and CODE.match(approver)):
        problems.append("review.approver must be a reviewer code such as E01, or null")
    if problems:
        return problems
    if status == "UNREVIEWED" and (reviewers or approver):
        problems.append("an UNREVIEWED record has no reviewers or approver")
    if status != "UNREVIEWED" and not reviewers:
        problems.append(f"a {status} record needs at least one reviewer")
    if approver and status not in ("HUMAN_APPROVED", "REJECTED"):
        problems.append(f"a {status} record has no approver yet")
    if status == "HUMAN_APPROVED":
        if not approver:
            problems.append("HUMAN_APPROVED needs a lead editor as approver")
        elif approver in reviewers:
            problems.append("the approver must not also be a reviewer (two different people)")
    if status == "REJECTED" and record.get("split") != "excluded":
        problems.append("a REJECTED record must have split 'excluded'")
    return problems


def check_record(record: Any) -> list[str]:
    """Every way one record breaks the format; an empty list means it follows it."""
    if not isinstance(record, dict):
        return ["a record must be a JSON object"]
    missing = sorted(REQUIRED - set(record))
    if missing:
        return [f"missing {', '.join(missing)}"]
    problems = [f"unknown field {key!r}" for key in sorted(set(record) - REQUIRED - OPTIONAL)]
    if record["szsf_version"] != SZSF_VERSION:
        problems.append(f"szsf_version must be {SZSF_VERSION!r}")
    for name, allowed in (("kind", KINDS), ("tier", TIERS), ("split", SPLITS), ("origin", ORIGINS)):
        if record[name] not in allowed:
            problems.append(f"{name} must be one of {', '.join(allowed)}")
    for name in ("english", "zomi", "zomi_standard"):
        problems += _text_problems(name, record[name])
    for name in ("id", "source"):
        if not isinstance(record[name], str) or not record[name] or re.search(r"\s", record[name]):
            problems.append(f"{name} must be text without spaces")
    if record["kind"] == "dictionary_sense" and isinstance(record["id"], str) and not SENSE_ID.match(record["id"]):
        problems.append("a dictionary_sense id looks like ZD-000123 or ZS-000123")
    if not (isinstance(record["standard_version"], str) and VERSION.match(record["standard_version"])):
        problems.append("standard_version must look like 1.0.0")

    rules = record.get("zomi_standard_rules", [])
    problems += _list_of("zomi_standard_rules", rules, RULE_ID)
    if "zomi_standard_flags" in record:
        problems += _list_of("zomi_standard_flags", record["zomi_standard_flags"])
    if "quality_flags" in record:
        problems += _list_of("quality_flags", record["quality_flags"])
    if isinstance(record["zomi"], str) and isinstance(record["zomi_standard"], str):
        if record["zomi_standard"] != record["zomi"] and not rules:
            problems.append("zomi_standard differs from zomi, so zomi_standard_rules must name the rules that changed it")
    score = record.get("quality_score")
    if "quality_score" in record and (isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 1):
        problems.append("quality_score must be a number from 0 to 1")
    for name in ("model", "reference"):
        if name in record and record[name] is not None and not isinstance(record[name], str):
            problems.append(f"{name} must be text or null")

    problems += _review_problems(record)
    if record["tier"] == "gold" and record["origin"] == "machine_generated":
        if not isinstance(record["review"], dict) or record["review"].get("status") != "HUMAN_APPROVED":
            problems.append("a gold record that came from a machine must be HUMAN_APPROVED")
    return problems


def read_records(path: Path) -> Iterable[tuple[int, Any]]:
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield number, json.loads(line)
            except json.JSONDecodeError as error:
                yield number, ValueError(f"not JSON ({error.msg})")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rights(path: Path) -> dict[str, dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8")).get("sources", {})


def validate(path: Path, rights: dict[str, dict] | None = None, purpose: str | None = None,
             manifest: dict | None = None) -> list[str]:
    """Problems with a whole file, each with its line number; empty when the file follows SZSF."""
    problems: list[str] = []
    ids: dict[str, int] = {}
    records = 0
    for number, record in read_records(path):
        records += 1
        if isinstance(record, ValueError):
            problems.append(f"line {number}: {record}")
            continue
        found = check_record(record)
        problems += [f"line {number}: {problem}" for problem in found]
        if found and "id" not in record:
            continue
        record_id = record.get("id")
        if isinstance(record_id, str):
            if record_id in ids:
                problems.append(f"line {number}: id {record_id!r} repeats line {ids[record_id]}")
            ids.setdefault(record_id, number)
        if rights is not None and isinstance(record.get("source"), str):
            entry = rights.get(record["source"])
            if entry is None:
                problems.append(f"line {number}: source {record['source']!r} is not in the rights file")
            elif purpose and record.get("split") != "excluded" and entry.get(PURPOSES[purpose]) != "cleared":
                problems.append(f"line {number}: source {record['source']!r} is not cleared for {purpose} "
                                f"({PURPOSES[purpose]}: {entry.get(PURPOSES[purpose], 'not recorded')})")
    if not records:
        problems.append("the file has no records")
    if manifest is not None:
        if manifest.get("sha256") != sha256_file(path):
            problems.append("the file does not match its manifest's SHA-256")
        if manifest.get("records") != records:
            problems.append(f"the manifest counts {manifest.get('records')} records, the file has {records}")
    return problems


def build_manifest(path: Path, rights: dict[str, dict] | None = None, created_at: str | None = None) -> dict:
    """The manifest of a file that already passed validate()."""
    counts: dict[str, collections.Counter[str]] = {
        name: collections.Counter() for name in ("kind", "tier", "split", "origin", "source", "review_status")
    }
    versions: set[str] = set()
    records = 0
    for _, record in read_records(path):
        records += 1
        for name in ("kind", "tier", "split", "origin", "source"):
            counts[name][record[name]] += 1
        counts["review_status"][record["review"]["status"]] += 1
        versions.add(record["standard_version"])
    rights = rights or {}
    sources = sorted(counts["source"])
    return {
        "format": "SZSF",
        "szsf_version": SZSF_VERSION,
        "file": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "records": records,
        "created_at": created_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "standard_versions": sorted(versions),
        "counts": {name: dict(sorted(counter.items())) for name, counter in counts.items()},
        "rights_snapshot": {
            source: {key: rights.get(source, {}).get(key, "not recorded")
                     for key in ("train", "display", "redistribute", "commercial")}
            for source in sources
        },
        "note": "The rights snapshot copies data/rights.json when the manifest was made. It does not clear any source.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("validate", help="check a file against the format")
    check.add_argument("file", type=Path)
    check.add_argument("--rights", type=Path, default=DEFAULT_RIGHTS, help="rights file (default: data/rights.json)")
    check.add_argument("--no-rights", action="store_true", help="skip the check that every source is in the rights file")
    check.add_argument("--purpose", choices=sorted(PURPOSES), help="also require each source to be cleared for this use")
    check.add_argument("--manifest", type=Path, help="also check the file against its manifest")
    write = commands.add_parser("manifest", help="write the manifest of a valid file")
    write.add_argument("file", type=Path)
    write.add_argument("--out", type=Path, required=True)
    write.add_argument("--rights", type=Path, default=DEFAULT_RIGHTS)
    args = parser.parse_args(argv)

    rights = None if getattr(args, "no_rights", False) else load_rights(args.rights)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8")) if getattr(args, "manifest", None) else None
    problems = validate(args.file, rights, getattr(args, "purpose", None), manifest)
    if problems:
        shown = problems[:50]
        print(f"{args.file.name} does not follow the Siamsil Zomi Standard Format ({len(problems)} problems):",
              file=sys.stderr)
        print("\n".join(f"  {problem}" for problem in shown), file=sys.stderr)
        if len(problems) > len(shown):
            print(f"  … and {len(problems) - len(shown)} more", file=sys.stderr)
        return 1
    if args.command == "manifest":
        args.out.write_text(json.dumps(build_manifest(args.file, rights), indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(f"{args.file.name} follows the Siamsil Zomi Standard Format {SZSF_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
