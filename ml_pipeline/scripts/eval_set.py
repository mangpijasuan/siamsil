#!/usr/bin/env python3
"""Validate, leakage-check, and fingerprint human evaluation sets.

The format and process are specified in docs/EVALUATION_SET.md.

Commands:
  validate FILE                 schema, unique IDs, independent review
  leakage FILE --corpus CSV     items whose text also appears in the parallel corpus
  manifest FILE                 write FILE's .manifest.json (counts and SHA-256)

Each command exits non-zero when the set must not be frozen.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from build_language_db import normalize_word

SCHEMA_VERSION = 1
DIRECTIONS = {"en-zomi", "zomi-en"}
DOMAINS = ("conversation", "education", "government", "health", "religion", "news", "informal")
OUTCOMES = {"accepted", "corrected", "adjudicated"}
REQUIRED_TEXT = ("id", "direction", "domain", "source_text", "source_origin", "translator", "reviewer")


def load_items(path: Path) -> tuple[list[dict], list[str]]:
    items: list[dict] = []
    errors: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_no}: invalid JSON ({exc.msg})")
                continue
            if not isinstance(item, dict):
                errors.append(f"line {line_no}: expected a JSON object")
                continue
            item["_line"] = line_no
            items.append(item)
    return items, errors


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def validate_items(items: list[dict]) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors block freezing; warnings are coverage gaps."""
    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    directions: Counter[str] = Counter()
    domains: Counter[str] = Counter()

    for item in items:
        where = f"line {item['_line']}"
        for field in REQUIRED_TEXT:
            if not _text(item.get(field)):
                errors.append(f"{where}: '{field}' must be a non-empty string")

        item_id = _text(item.get("id"))
        if item_id:
            if item_id in seen_ids:
                errors.append(f"{where}: duplicate id '{item_id}'")
            seen_ids.add(item_id)

        direction = item.get("direction")
        if direction not in DIRECTIONS:
            errors.append(f"{where}: direction must be one of {sorted(DIRECTIONS)}")
        else:
            directions[direction] += 1

        domain = item.get("domain")
        if domain not in DOMAINS:
            errors.append(f"{where}: domain must be one of {list(DOMAINS)}")
        else:
            domains[domain] += 1

        references = item.get("references")
        if not isinstance(references, list) or not references or not all(_text(r) for r in references):
            errors.append(f"{where}: 'references' must be a non-empty list of non-empty strings")

        outcome = item.get("review_outcome")
        if outcome not in OUTCOMES:
            errors.append(f"{where}: review_outcome must be one of {sorted(OUTCOMES)}")

        translator = _text(item.get("translator"))
        reviewer = _text(item.get("reviewer"))
        adjudicator = _text(item.get("adjudicator"))
        if translator and translator == reviewer:
            errors.append(f"{where}: reviewer must differ from translator")
        if outcome == "adjudicated" and not adjudicator:
            errors.append(f"{where}: adjudicated items need an adjudicator")
        if adjudicator and adjudicator in {translator, reviewer}:
            errors.append(f"{where}: adjudicator must differ from translator and reviewer")

    if len(directions) > 1:
        errors.append(f"a set holds one direction; found {dict(directions)}")

    missing = [d for d in DOMAINS if domains[d] == 0]
    if items and missing:
        warnings.append(f"no items for domains: {', '.join(missing)}")

    return errors, warnings


def item_texts(item: dict) -> tuple[list[str], list[str]]:
    """Return (english_texts, zomi_texts) for an item."""
    source = [_text(item.get("source_text"))]
    references = [_text(r) for r in item.get("references") or [] if isinstance(r, str)]
    if item.get("direction") == "zomi-en":
        return references, source
    return source, references


def find_leaks(items: list[dict], corpus_rows) -> dict[str, set[str]]:
    """Map item id -> corpus sides ('en', 'zomi') where its normalized text appears.

    corpus_rows yields (english, zomi) pairs, e.g. from the parallel CSV.
    """
    english_index: dict[str, set[str]] = {}
    zomi_index: dict[str, set[str]] = {}
    for item in items:
        item_id = _text(item.get("id")) or f"line {item['_line']}"
        english, zomi = item_texts(item)
        for text in english:
            key = normalize_word(text)
            if key:
                english_index.setdefault(key, set()).add(item_id)
        for text in zomi:
            key = normalize_word(text)
            if key:
                zomi_index.setdefault(key, set()).add(item_id)

    leaks: dict[str, set[str]] = {}
    for english, zomi in corpus_rows:
        for item_id in english_index.get(normalize_word(english), ()):
            leaks.setdefault(item_id, set()).add("en")
        for item_id in zomi_index.get(normalize_word(zomi), ()):
            leaks.setdefault(item_id, set()).add("zomi")
    return leaks


def read_corpus(path: Path):
    csv.field_size_limit(min(sys.maxsize, 8_000_000))
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            yield row.get("en") or "", row.get("zomi") or ""


def build_manifest(path: Path, items: list[dict]) -> dict:
    directions = sorted({item.get("direction") for item in items if item.get("direction") in DIRECTIONS})
    return {
        "schema_version": SCHEMA_VERSION,
        "file": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "direction": directions[0] if len(directions) == 1 else None,
        "items": len(items),
        "by_domain": {d: sum(1 for i in items if i.get("domain") == d) for d in DOMAINS},
        "by_outcome": dict(sorted(Counter(i.get("review_outcome") for i in items).items(), key=str)),
    }


def _load_or_exit(path: Path) -> list[dict]:
    if not path.exists():
        sys.exit(f"Evaluation file not found: {path}")
    items, parse_errors = load_items(path)
    if parse_errors:
        for error in parse_errors:
            print(f"error: {error}")
        sys.exit(1)
    return items


def cmd_validate(args: argparse.Namespace) -> int:
    items = _load_or_exit(args.file)
    errors, warnings = validate_items(items)
    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    print(f"{len(items)} items, {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors or not items else 0


def cmd_leakage(args: argparse.Namespace) -> int:
    items = _load_or_exit(args.file)
    if not args.corpus.exists():
        sys.exit(f"Parallel corpus not found: {args.corpus}")
    leaks = find_leaks(items, read_corpus(args.corpus))
    for item_id in sorted(leaks):
        print(f"leak: {item_id} matches corpus {'+'.join(sorted(leaks[item_id]))}")
    print(f"{len(leaks)} of {len(items)} items overlap the corpus")
    return 1 if leaks else 0


def cmd_manifest(args: argparse.Namespace) -> int:
    items = _load_or_exit(args.file)
    errors, _ = validate_items(items)
    if errors or not items:
        print("error: set does not validate; run 'validate' first")
        return 1
    manifest = build_manifest(args.file, items)
    out = args.file.with_suffix(".manifest.json")
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate")
    validate.add_argument("file", type=Path)
    validate.set_defaults(run=cmd_validate)

    leakage = commands.add_parser("leakage")
    leakage.add_argument("file", type=Path)
    leakage.add_argument("--corpus", type=Path, required=True)
    leakage.set_defaults(run=cmd_leakage)

    manifest = commands.add_parser("manifest")
    manifest.add_argument("file", type=Path)
    manifest.set_defaults(run=cmd_manifest)

    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
