#!/usr/bin/env python3
"""Check and describe a file in the Siamsil Zomi Standard Format (SZSF): docs/SZSF.md.

SZSF is the authoritative data schema and file standard for Siamsil's trained and reviewed Zomi data: one JSON
object per line, each carrying the original text, its standard form, where it came from, who reviewed it and
what it may be used for.

  validate   check every record, and optionally the rights and the manifest
  manifest   write the manifest of a valid file: counts, SHA-256, and a snapshot of each source's rights

  python3 ml_pipeline/scripts/szsf.py validate szsf-master-v1.0.0.jsonl --purpose training --roster roster.csv
  python3 ml_pipeline/scripts/szsf.py manifest szsf-master-v1.0.0.jsonl --out szsf-master-v1.0.0.manifest.json

A passing check says the file follows the format. It does not say the Zomi is correct, and it does not clear any
source: rights stay in data/rights.json and human approval stays with the reviewers.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RIGHTS = ROOT / "data" / "rights.json"
DEFAULT_STANDARD = ROOT / "data" / "zomi_standard_form" / "standard.json"

SZSF_VERSION = "1.0"
KINDS = ("translation_pair", "dictionary_sense")
TIERS = ("gold", "silver", "bronze")
SPLITS = ("train", "validation", "test", "excluded")
ORIGINS = ("human_written", "machine_generated", "unknown")
# The SOP-07 status names (ml_pipeline/scripts/corpus_reviews.py), plus the state before any review.
REVIEW_STATUSES = ("UNREVIEWED", "NEEDS_CORRECTION", "READY_FOR_APPROVAL", "HUMAN_APPROVED", "REJECTED")
PURPOSES = {"training": "train", "display": "display"}

CODE = re.compile(r"^[A-Z]{1,3}[0-9]{2,4}$")  # the same roster-code form as corpus_reviews.py
MASTER_NAME = re.compile(r"^szsf-master-v\d+\.\d+\.\d+\.jsonl$")
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
RULE_ID = re.compile(r"^ZS-\d{3}$")
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
SENSE_ID = re.compile(r"^(ZD|ZS)-\d{6,}$")
# What UTF-8 text looks like after an export read it as Mac Roman: ’ -> ‚Äô, é -> √©. Never valid text.
DAMAGE = re.compile("‚Ä[ôúùòìî¶]|√[©±°®ß≠¢†§™´¨ÆØ∞≤≥¥µ∂∑∏π∫ªºΩæø¿¡¬ƒ≈∆«»…]")

REQUIRED = {
    "szsf_version", "id", "kind", "english", "zomi", "zomi_standard", "standard_version", "source",
    "origin", "tier", "split", "review",
}
OPTIONAL = {
    "zomi_standard_rules", "zomi_standard_flags", "model", "provider_derived", "english_source", "quality_score",
    "quality_flags", "reference",
    # Lineage a published record needs (docs/ARCHITECTURE.md): checked for form here, required by the release builder.
    "license_status", "verified_at", "prompt_version", "release_version",
}
REVIEW_KEYS = {"status", "reviewers", "approver", "batch"}


LINE_BREAKS = ("Cc", "Zl", "Zp")  # control characters and the Unicode line and paragraph separators


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _metadata_problems(record: dict[str, Any]) -> list[str]:
    """Every text value outside the three main fields is held to the same character rules."""
    problems = []
    for key, value in record.items():
        if key in ("english", "zomi", "zomi_standard"):
            continue
        for text in _strings(value):
            if any(unicodedata.category(char) in LINE_BREAKS for char in text):
                problems.append(f"{key} has a control or line-break character")
            if unicodedata.normalize("NFC", text) != text:
                problems.append(f"{key} is not Unicode NFC")
            if DAMAGE.search(text):
                problems.append(f"{key} has damaged characters (UTF-8 read as Mac Roman)")
    return sorted(set(problems))


def _text_problems(name: str, value: Any) -> list[str]:
    if not isinstance(value, str):
        return [f"{name} must be text"]
    problems = []
    if not value.strip():
        problems.append(f"{name} is empty")
    elif value != value.strip():
        problems.append(f"{name} has spaces at its start or end")
    if any(unicodedata.category(char) in LINE_BREAKS for char in value):
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
    if approver and approver in reviewers:
        problems.append("the approver must not also be a reviewer (two different people)")
    if status == "HUMAN_APPROVED" and not approver:
        problems.append("HUMAN_APPROVED needs a lead editor as approver")
    if status == "REJECTED" and record.get("split") != "excluded":
        problems.append("a REJECTED record must have split 'excluded'")
    return problems


def _standard_problems(record: dict[str, Any], rules: Any, standard: dict[str, Any] | None) -> list[str]:
    """Cited rules must be in the adopted rule set the record says it used."""
    if standard is None or not isinstance(rules, list) or not rules:
        return []
    problems = [f"zomi_standard_rules cites {rule_id}, which is not an adopted rule" for rule_id in rules
                if rule_id not in standard["rules"]]
    if record.get("standard_version") != standard["version"]:
        problems.append(f"standard_version {record.get('standard_version')!r} is not the adopted rule set "
                        f"({standard['version']!r}); check against that version's standard.json")
    return problems


def check_record(record: Any, standard: dict[str, Any] | None = None) -> list[str]:
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
    for name in ("id", "source", "english_source"):
        if name in record and (not isinstance(record[name], str) or not record[name] or re.search(r"\s", record[name])):
            problems.append(f"{name} must be text without spaces")
    problems += _metadata_problems(record)
    for name in ("license_status", "prompt_version", "release_version"):
        if name in record and not (isinstance(record[name], str) and record[name].strip()):
            problems.append(f"{name} must be text")
    if "verified_at" in record and not (isinstance(record["verified_at"], str) and STAMP.match(record["verified_at"])):
        problems.append("verified_at must be a UTC time like 2026-11-08T12:00:00Z")
    if record["kind"] == "dictionary_sense" and isinstance(record["id"], str) and not SENSE_ID.match(record["id"]):
        problems.append("a dictionary_sense id looks like ZD-000123 or ZS-000123")
    if not (isinstance(record["standard_version"], str) and VERSION.match(record["standard_version"])):
        problems.append("standard_version must look like 1.0.0")

    rules = record.get("zomi_standard_rules", [])
    problems += _list_of("zomi_standard_rules", rules, RULE_ID)
    problems += _standard_problems(record, rules, standard)
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
    if record["origin"] == "machine_generated":
        # Provenance of the machine that wrote the Zomi; "unknown" is the explicit way to say it was not recorded.
        if not (isinstance(record.get("model"), str) and record["model"].strip()):
            problems.append("a machine_generated record needs model (the machine that wrote the Zomi, or 'unknown')")
        if not isinstance(record.get("provider_derived"), bool):
            problems.append("a machine_generated record needs provider_derived true or false "
                            "(true when the Zomi or its labels come from an outside provider's output)")
    elif "provider_derived" in record and not isinstance(record["provider_derived"], bool):
        problems.append("provider_derived must be true or false")

    problems += _review_problems(record)
    if record["tier"] == "gold" and record["origin"] == "machine_generated":
        if not isinstance(record["review"], dict) or record["review"].get("status") != "HUMAN_APPROVED":
            problems.append("a gold record that came from a machine must be HUMAN_APPROVED")
    return problems


def read_records(path: Path) -> Iterable[tuple[int, Any]]:
    with path.open("rb") as handle:
        for number, raw in enumerate(handle, start=1):
            try:
                line = raw.decode("utf-8")
            except UnicodeDecodeError as error:
                yield number, ValueError(f"not valid UTF-8 ({error.reason})")
                continue
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


def load_standard(path: Path = DEFAULT_STANDARD) -> dict[str, Any]:
    """The adopted rule set: its version and the IDs of its rules."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"version": data.get("version"), "rules": {rule.get("id") for rule in data.get("rules", [])}}


def validate(path: Path, rights: dict[str, dict] | None = None, purpose: str | None = None,
             manifest: dict | None = None, standard: dict[str, Any] | None = None,
             roster: dict[str, str] | None = None, allow_provider_derived: bool = False) -> list[str]:
    """Problems with a whole file, each with its line number; empty when the file follows SZSF."""
    if purpose and rights is None:
        return ["a purpose can only be checked against the rights file: do not skip it"]
    problems: list[str] = []
    if not MASTER_NAME.match(path.name):
        problems.append(f"the file name must look like szsf-master-v1.0.0.jsonl, not {path.name!r}")
    ids: dict[str, int] = {}
    records = 0
    record_problems = 0
    for number, record in read_records(path):
        records += 1
        if isinstance(record, ValueError):
            problems.append(f"line {number}: {record}")
            record_problems += 1
            continue
        found = check_record(record, standard)
        problems += [f"line {number}: {problem}" for problem in found]
        record_problems += len(found)
        if not isinstance(record, dict):
            continue
        record_id = record.get("id")
        if isinstance(record_id, str):
            if record_id in ids:
                problems.append(f"line {number}: id {record_id!r} repeats line {ids[record_id]}")
            ids.setdefault(record_id, number)
        if roster is not None and isinstance(record.get("review"), dict):
            review = record["review"]
            if isinstance(review.get("reviewers"), list):
                problems += [f"line {number}: {code} is not a reviewer in the roster" for code in review["reviewers"]
                             if isinstance(code, str) and roster.get(code) != "reviewer"]
            if isinstance(review.get("approver"), str) and roster.get(review["approver"]) != "lead_editor":
                problems.append(f"line {number}: {review['approver']} is not a lead editor in the roster")
        if rights is not None:
            for field in ("source", "english_source"):
                if not isinstance(record.get(field), str):
                    continue
                entry = rights.get(record[field])
                if entry is None:
                    problems.append(f"line {number}: {field} {record[field]!r} is not in the rights file")
                elif purpose and record.get("split") != "excluded" and entry.get(PURPOSES[purpose]) != "cleared":
                    problems.append(f"line {number}: {field} {record[field]!r} is not cleared for {purpose} "
                                    f"({PURPOSES[purpose]}: {entry.get(PURPOSES[purpose], 'not recorded')})")
        if (purpose == "training" and record.get("provider_derived") is True and record.get("split") != "excluded"
                and not allow_provider_derived):
            problems.append(f"line {number}: provider-derived records are left out of training by default "
                            "(docs/QUALITY_OPERATOR_ARCHITECTURE.md); exclude it or record the permission")
    if not records:
        problems.append("the file has no records")
    if manifest is not None:
        if manifest.get("sha256") != sha256_file(path):
            problems.append("the file does not match its manifest's SHA-256")
        if manifest.get("records") != records:
            problems.append(f"the manifest counts {manifest.get('records')} records, the file has {records}")
        if not problems and not record_problems:
            expected = build_manifest(path, rights, manifest.get("created_at"))
            for key, value in expected.items():
                if key in ("created_at", "note") or (key == "rights_snapshot" and rights is None):
                    continue
                if manifest.get(key) != value:
                    problems.append(f"the manifest's {key} does not match the file")
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
    check.add_argument("--no-rights", action="store_true",
                       help="skip the check that every source is in the rights file (not allowed with --purpose)")
    check.add_argument("--purpose", choices=sorted(PURPOSES), help="also require each source to be cleared for this use")
    check.add_argument("--allow-provider-derived", action="store_true",
                       help="with --purpose training, keep provider-derived records (only when the provider's terms allow it)")
    check.add_argument("--roster", type=Path, help="the private reviewer roster (CSV: code, role); checks every reviewer and approver")
    check.add_argument("--standard", type=Path, default=DEFAULT_STANDARD, help="the adopted rule set (default: data/zomi_standard_form/standard.json)")
    check.add_argument("--manifest", type=Path, help="also check the file against its manifest")
    write = commands.add_parser("manifest", help="write the manifest of a valid file")
    write.add_argument("file", type=Path)
    write.add_argument("--out", type=Path, required=True)
    write.add_argument("--rights", type=Path, default=DEFAULT_RIGHTS)
    args = parser.parse_args(argv)

    if getattr(args, "no_rights", False) and getattr(args, "purpose", None):
        parser.error("--no-rights cannot be combined with --purpose: a purpose is checked against the rights file")
    rights = None if getattr(args, "no_rights", False) else load_rights(args.rights)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8")) if getattr(args, "manifest", None) else None
    standard = load_standard(args.standard) if args.command == "validate" else load_standard()
    roster = None
    if getattr(args, "roster", None):
        from corpus_reviews import load_roster  # type: ignore

        roster = load_roster(args.roster)
    if args.command == "manifest" and args.out.name != args.file.name.removesuffix(".jsonl") + ".manifest.json":
        parser.error(f"the manifest must be named {args.file.name.removesuffix('.jsonl')}.manifest.json")
    problems = validate(args.file, rights, getattr(args, "purpose", None), manifest, standard, roster,
                        getattr(args, "allow_provider_derived", False))
    if problems:
        shown = problems[:50]
        print(f"{args.file.name} does not follow the Siamsil Zomi Standard Format ({len(problems)} problems):",
              file=sys.stderr)
        print("\n".join(f"  {problem}" for problem in shown), file=sys.stderr)
        if len(problems) > len(shown):
            print(f"  … and {len(problems) - len(shown)} more", file=sys.stderr)
        return 1
    if args.command == "manifest":
        text = json.dumps(build_manifest(args.file, rights), indent=2, ensure_ascii=False) + "\n"
        args.out.parent.mkdir(parents=True, exist_ok=True)
        handle_fd, temp_name = tempfile.mkstemp(prefix=args.out.name + ".", suffix=".part", dir=args.out.parent)
        try:
            with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(temp_name, args.out)  # the old manifest stays whole until the new one is complete
        except BaseException:
            Path(temp_name).unlink(missing_ok=True)
            raise
        print(f"Wrote {args.out}")
    else:
        print(f"{args.file.name} follows the Siamsil Zomi Standard Format {SZSF_VERSION}")
        if roster is None:
            print("Note: no --roster given, so reviewer and approver codes were checked for form only.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
