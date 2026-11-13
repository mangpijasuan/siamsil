#!/usr/bin/env python3
"""Apply the adopted Siamsil Zomi Standard Form: step 5 of docs/ZOMI_STANDARD_FORM.md.

The standard is data/zomi_standard_form/standard.json. It holds only rules Zomi reviewers
adopted (two reviewer codes each); AI suggestions and evidence live elsewhere
(rule_checks.json, the review workbook) and are never read here.

  validate   check standard.json: IDs, two reviewers, no variant in two rules, no chains
  apply      add a standard form beside a text field in a JSONL file; the original is kept
  variants   list each standard spelling with its variants (for dictionary search)
  preview    what proposed rules (data/zomi_standard_form/proposed_rules.json) would change in the
             corpus, with examples. Proposals are never applied: only two reviewers adopt a rule.

  python3 ml_pipeline/scripts/zolai_standard.py validate
  python3 ml_pipeline/scripts/zolai_standard.py apply --input pairs.jsonl --field zomi --out pairs.standard.jsonl
  python3 ml_pipeline/scripts/zolai_standard.py variants
  python3 ml_pipeline/scripts/zolai_standard.py preview --db data/processed/language/siamsil_language.sqlite

A rule's mode is "replace" (the standard form uses the standard spelling) or "flag"
(the text is unchanged and the match is listed, for spellings whose meaning depends on
context). With no adopted rules, the standard form equals the original.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STANDARD = ROOT / "data" / "zomi_standard_form" / "standard.json"
DEFAULT_CHECKS = ROOT / "data" / "zomi_standard_form" / "rule_checks.json"
DEFAULT_PROPOSALS = ROOT / "data" / "zomi_standard_form" / "proposed_rules.json"
PROPOSAL_ID = re.compile(r"^P-\d{3}$")

RULE_ID = re.compile(r"^ZS-\d{3}$")
REVIEWER = re.compile(r"^[A-Z]\d{2}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
MODES = ("replace", "flag")
APOSTROPHES = "'’‘ʼ"
APOSTROPHE_CLASS = "[" + APOSTROPHES + "]"


class StandardError(ValueError):
    """standard.json breaks a rule of the review process."""


def norm(text: str) -> str:
    """Key for comparing spellings: lower case, one apostrophe form, single spaces."""
    text = text.translate(str.maketrans({c: "'" for c in APOSTROPHES}))
    return " ".join(text.lower().split())


@dataclass(frozen=True)
class Rule:
    id: str
    standard: str
    variants: tuple[str, ...]
    mode: str
    check: str | None
    approved_by: tuple[str, ...]
    approved_on: str
    reason: str


@dataclass
class Standard:
    version: str
    rules: list[Rule]
    _by_variant: dict[str, Rule] = field(default_factory=dict, repr=False)
    _pattern: re.Pattern[str] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        for rule in self.rules:
            for variant in rule.variants:
                self._by_variant[norm(variant)] = rule
        if self._by_variant:
            # Longest first, so a phrase wins over a word inside it.
            forms = sorted(self._by_variant, key=len, reverse=True)
            body = "|".join(_variant_regex(form) for form in forms)
            self._pattern = re.compile(
                rf"(?<![^\W\d_])(?<![{APOSTROPHES}\-])(?:{body})(?![^\W\d_])(?![{APOSTROPHES}\-])",
                re.IGNORECASE,
            )


def _variant_regex(form: str) -> str:
    parts = []
    for char in form:
        if char == "'":
            parts.append(APOSTROPHE_CLASS)
        elif char == " ":
            parts.append(r"[ \t]+")
        else:
            parts.append(re.escape(char))
    return "".join(parts)


def load_check_ids(path: Path = DEFAULT_CHECKS) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {check["id"] for check in data["checks"]}


def parse(data: dict, check_ids: set[str] | None = None) -> Standard:
    """Build a Standard from standard.json's content, or raise StandardError listing every problem."""
    problems: list[str] = []
    version = data.get("version")
    if not isinstance(version, str) or not VERSION.match(version):
        problems.append("version must look like 1.0.0")
    raw_rules = data.get("rules")
    if not isinstance(raw_rules, list):
        raise StandardError("rules must be a list")

    rules: list[Rule] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_rules):
        where = f"rule {raw.get('id', index) if isinstance(raw, dict) else index}"
        if not isinstance(raw, dict):
            problems.append(f"{where}: must be an object")
            continue
        rule_id = raw.get("id")
        if not isinstance(rule_id, str) or not RULE_ID.match(rule_id):
            problems.append(f"{where}: id must look like ZS-001")
        elif rule_id in seen_ids:
            problems.append(f"{where}: id used twice")
        else:
            seen_ids.add(rule_id)
        standard = raw.get("standard")
        if not isinstance(standard, str) or not standard.strip():
            problems.append(f"{where}: standard spelling is missing")
            standard = ""
        variants = raw.get("variants")
        if not isinstance(variants, list) or not variants or not all(isinstance(v, str) and v.strip() for v in variants):
            problems.append(f"{where}: variants must be a non-empty list of spellings")
            variants = []
        if standard and any(norm(v) == norm(standard) for v in variants):
            problems.append(f"{where}: a variant is the standard spelling itself")
        mode = raw.get("mode", "replace")
        if mode not in MODES:
            problems.append(f"{where}: mode must be one of {', '.join(MODES)}")
        approved_by = raw.get("approved_by")
        if (not isinstance(approved_by, list) or not all(isinstance(c, str) and REVIEWER.match(c) for c in approved_by)
                or len(set(approved_by)) < 2):
            problems.append(f"{where}: needs two different reviewer codes (like R01, E01) in approved_by")
            approved_by = []
        approved_on = raw.get("approved_on")
        if not isinstance(approved_on, str) or not DATE.match(approved_on):
            problems.append(f"{where}: approved_on must be a date (YYYY-MM-DD)")
        reason = raw.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            problems.append(f"{where}: reason is missing")
        check = raw.get("check")
        if check is not None and check_ids is not None and check not in check_ids:
            problems.append(f"{where}: check '{check}' is not in rule_checks.json")
        rules.append(Rule(
            id=str(rule_id), standard=standard, variants=tuple(variants), mode=str(mode), check=check,
            approved_by=tuple(approved_by), approved_on=str(approved_on), reason=str(reason),
        ))

    owner: dict[str, str] = {}
    standards = {norm(rule.standard): rule.id for rule in rules if rule.standard}
    for rule in rules:
        for variant in rule.variants:
            key = norm(variant)
            if key in owner and owner[key] != rule.id:
                problems.append(f"rule {rule.id}: variant '{variant}' is also in {owner[key]}")
            owner[key] = rule.id
            if key in standards and standards[key] != rule.id:
                problems.append(f"rule {rule.id}: variant '{variant}' is the standard spelling of {standards[key]}")

    if problems:
        raise StandardError("; ".join(problems))
    return Standard(version=str(version), rules=rules)


def load(path: Path = DEFAULT_STANDARD, checks: Path | None = DEFAULT_CHECKS) -> Standard:
    data = json.loads(path.read_text(encoding="utf-8"))
    return parse(data, load_check_ids(checks) if checks else None)


def _match_case(found: str, replacement: str) -> str:
    letters = [c for c in found if c.isalpha()]
    if len(letters) > 1 and all(c.isupper() for c in letters):
        return replacement.upper()
    if letters and found.lstrip()[0].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


@dataclass
class Result:
    text: str
    rules: list[str]
    flags: list[dict]


def standardize(text: str, standard: Standard) -> Result:
    """The standard form of text, the replace rules that changed it, and flag-rule matches."""
    if standard._pattern is None:
        return Result(text, [], [])
    applied: list[str] = []
    flags: list[dict] = []

    def swap(match: re.Match[str]) -> str:
        found = match.group(0)
        rule = standard._by_variant[norm(found)]
        if rule.mode == "flag":
            flags.append({"rule": rule.id, "text": found, "start": match.start()})
            return found
        if rule.id not in applied:
            applied.append(rule.id)
        return _match_case(found, rule.standard)

    return Result(standard._pattern.sub(swap, text), applied, flags)


def load_proposals(path: Path = DEFAULT_PROPOSALS, checks: Path | None = DEFAULT_CHECKS,
                   adopted: Standard | None = None) -> tuple[Standard, dict[str, dict]]:
    """Proposed rules (decisions waiting for a second reviewer) as a Standard to preview, and each one's record.

    A proposal is not a rule: it has fewer than two reviewers, so `parse` would refuse it, and nothing here is read by
    `apply` or by the SZSF converter. It gets a stand-in ID (ZS-9nn) only so the same checks run on it: no variant in two
    rules, none that is another rule's standard spelling, a known check. A proposal that already lists two reviewers
    belongs in standard.json, and a proposal that clashes with an adopted rule is refused.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("proposals")
    if not isinstance(raw, list):
        raise StandardError("proposals must be a list")
    problems: list[str] = []
    stand_in: list[dict] = []
    records: dict[str, dict] = {}
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            problems.append(f"proposal {index}: must be an object")
            continue
        name = str(item.get("id"))
        if not PROPOSAL_ID.match(name):
            problems.append(f"proposal {name}: id must look like P-001")
        if name in records:
            problems.append(f"proposal {name}: id used twice")
        if len(set(item.get("approved_by") or [])) >= 2:
            problems.append(f"proposal {name}: already has two reviewers; adopt it in standard.json instead")
        reviews = item.get("reviews") or []
        codes = {r.get("code") for r in reviews if isinstance(r, dict) and r.get("code")}
        if not all(isinstance(r, dict) and r.get("reviewer") and r.get("kind") and r.get("decided_on") for r in reviews):
            problems.append(f"proposal {name}: each review needs reviewer, kind and decided_on")
        if any(code and not REVIEWER.match(str(code)) for code in codes):
            problems.append(f"proposal {name}: a review code must look like R01 or E01")
        if len(codes) >= 2:
            problems.append(f"proposal {name}: two reviewers with codes have confirmed it; adopt it in standard.json instead")
        if not item.get("proposed_by") or not item.get("proposed_on"):
            problems.append(f"proposal {name}: needs proposed_by and proposed_on (who asked for it, and when)")
        records[name] = item
        stand_in.append({**{k: item.get(k) for k in ("standard", "variants", "mode", "check", "reason")},
                         "id": f"ZS-9{index:02d}", "approved_by": ["P01", "P02"], "approved_on": str(item.get("proposed_on"))})
    if problems:
        raise StandardError("; ".join(problems))
    preview = parse({"version": "0.0.0", "rules": stand_in}, load_check_ids(checks) if checks else None)
    if adopted is not None:
        taken = {norm(r.standard) for r in adopted.rules} | {norm(v) for r in adopted.rules for v in r.variants}
        clash = sorted({v for r in preview.rules for v in (r.standard, *r.variants) if norm(v) in taken})
        if clash:
            raise StandardError(f"proposal spellings that an adopted rule already uses: {', '.join(clash)}")
    by_stand_in = {f"ZS-9{index:02d}": str(item.get("id")) for index, item in enumerate(raw, start=1)}
    for rule in preview.rules:
        records[by_stand_in[rule.id]]["_stand_in"] = rule.id
    return preview, records


def preview_changes(rows: Iterable[tuple[str, str, str]], preview: Standard, records: dict[str, dict],
                    examples: int = 3) -> dict[str, dict]:
    """For each proposal: how many times its variants occur, in how many pairs, and a few before/after examples.

    `rows` are (id, english, zomi). Nothing is written: this is only to see what a proposal would do.
    """
    names = {record["_stand_in"]: name for name, record in records.items() if "_stand_in" in record}
    report = {name: {"occurrences": 0, "pairs": 0, "examples": [], "variants": {}} for name in names.values()}
    if preview._pattern is None:
        return report
    for row_id, english, zomi in rows:
        seen: set[str] = set()
        for match in preview._pattern.finditer(zomi):
            found = match.group(0)
            name = names[preview._by_variant[norm(found)].id]
            entry = report[name]
            entry["occurrences"] += 1
            entry["variants"][norm(found)] = entry["variants"].get(norm(found), 0) + 1
            seen.add(name)
        for name in seen:
            report[name]["pairs"] += 1
            if len(report[name]["examples"]) < examples:
                after = standardize(zomi, preview).text
                report[name]["examples"].append({"id": row_id, "english": english, "before": zomi, "after": after})
    return report


def variant_index(standard: Standard) -> dict[str, str]:
    """Every spelling (normalized) -> its standard spelling, including the standard itself."""
    index: dict[str, str] = {}
    for rule in standard.rules:
        index[norm(rule.standard)] = rule.standard
        for variant in rule.variants:
            index[norm(variant)] = rule.standard
    return index


def search_forms(word: str, standard: Standard) -> list[str]:
    """All spellings a search for word should match: its standard form first, then the variants."""
    key = norm(word)
    for rule in standard.rules:
        forms = [rule.standard, *rule.variants]
        if key in {norm(form) for form in forms}:
            return forms
    return [word]


def apply_records(records: Iterable[dict], field_name: str, standard: Standard) -> Iterable[dict]:
    """Copy each record and add <field>_standard, _standard_rules, _standard_flags, standard_version."""
    for record in records:
        out = dict(record)
        value = record.get(field_name)
        if isinstance(value, str):
            result = standardize(value, standard)
            out[f"{field_name}_standard"] = result.text
            out[f"{field_name}_standard_rules"] = result.rules
            out[f"{field_name}_standard_flags"] = result.flags
            out["standard_version"] = standard.version
        yield out


def _read_jsonl(path: Path) -> Iterable[dict]:
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as error:
                    raise SystemExit(f"{path}:{number}: not JSON ({error.msg})") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply the adopted Siamsil Zomi Standard Form.")
    parser.add_argument("--standard", type=Path, default=DEFAULT_STANDARD)
    parser.add_argument("--checks", type=Path, default=DEFAULT_CHECKS)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="check standard.json")
    apply = commands.add_parser("apply", help="add a standard form beside a text field")
    apply.add_argument("--input", type=Path, required=True)
    apply.add_argument("--field", required=True, help="the text field to standardize, e.g. zomi")
    apply.add_argument("--out", type=Path, help="output JSONL (default: standard output)")
    commands.add_parser("variants", help="list standard spellings and their variants")
    preview_parser = commands.add_parser("preview", help="what proposed rules would change in the corpus (nothing is applied)")
    preview_parser.add_argument("--proposals", type=Path, default=DEFAULT_PROPOSALS)
    preview_parser.add_argument("--db", type=Path, required=True, help="language database to read (read-only)")
    preview_parser.add_argument("--examples", type=int, default=3, help="before/after examples per proposal")
    args = parser.parse_args(argv)

    try:
        standard = load(args.standard, args.checks)
    except StandardError as error:
        print(f"{args.standard}: {error}", file=sys.stderr)
        return 1

    if args.command == "preview":
        import sqlite3

        try:
            preview, records = load_proposals(args.proposals, args.checks, standard)
        except (StandardError, OSError, ValueError) as error:
            print(f"{args.proposals}: {error}", file=sys.stderr)
            return 1
        con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
        try:
            rows = con.execute("SELECT id, normalized_source_text, normalized_target_text FROM parallel_sentences ORDER BY id")
            report = preview_changes(((f"corpus-{i}", e, z) for i, e, z in rows), preview, records, args.examples)
        finally:
            con.close()
        print("Proposed rules are NOT adopted and change nothing. Two reviewers must adopt a rule (docs/ZOMI_STANDARD_FORM.md).")
        for name, result in report.items():
            record = records[name]
            print(f"\n{name}: {', '.join(record['variants'])} -> {record['standard']} ({record.get('mode', 'replace')}), "
                  f"proposed by {record['proposed_by']} on {record['proposed_on']}")
            seen = ", ".join(f"{r['reviewer']} ({r['kind']}, {r['decided_on']})" for r in record.get("reviews", [])) or "none"
            print(f"  reviews: {seen}; adopted only when two different reviewers have confirmed")
            print(f"  {result['occurrences']:,} occurrences in {result['pairs']:,} pairs; by spelling: "
                  + ", ".join(f"{v} {c:,}" for v, c in sorted(result["variants"].items(), key=lambda x: -x[1])))
            for example in result["examples"]:
                print(f"  {example['id']}  {example['english']}\n    before: {example['before']}\n    after:  {example['after']}")
        return 0

    if args.command == "validate":
        print(f"Siamsil Zomi Standard Form {standard.version}: {len(standard.rules)} adopted rule(s), valid")
    elif args.command == "variants":
        for rule in standard.rules:
            print("\t".join([rule.id, rule.standard, ", ".join(rule.variants), rule.mode]))
    else:
        if args.out and args.out.resolve() == args.input.resolve():
            print("--out must differ from --input; originals are never overwritten", file=sys.stderr)
            return 1
        lines = (json.dumps(r, ensure_ascii=False) + "\n" for r in apply_records(_read_jsonl(args.input), args.field, standard))
        if args.out:
            with args.out.open("w", encoding="utf-8") as handle:
                handle.writelines(lines)
        else:
            sys.stdout.writelines(lines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
