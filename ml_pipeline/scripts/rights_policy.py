#!/usr/bin/env python3
"""Per-source, per-use rights decisions, with verified subsets (docs/RIGHTS_POLICY.md).

`data/rights.json` keeps its four states (cleared, needs_review, blocked, not_permitted) and its four
legacy columns (display, train, redistribute, commercial). This module adds a purpose-specific layer:

    use                   legacy column   risk
    display               display         low
    retrieval             -               medium    internal retrieval / RAG context
    local_embeddings      -               medium    embeddings from a model Siamsil runs itself
    external_llm          -               high      text sent to a third-party provider
    commercial_inference  commercial      high      paid API or product output
    train                 train           high
    redistribute          redistribute    high

A source may carry `uses` (explicit per-use decisions), `subsets` (independently verified parts that can be
used before the whole source is cleared) and `components` (parts whose clearances a combined record needs).

Default deny: an unknown source, use or subset, an uncleared status, a clearance that fails validation, or a
subset whose membership no longer matches what was cleared, is not allowed. Nothing here changes production
behavior by itself; callers must opt in, and no clearance is made by this code.

Usage:
  python3 ml_pipeline/scripts/rights_policy.py validate [--rights data/rights.json]
  python3 ml_pipeline/scripts/rights_policy.py check SOURCE USE [--subset ID]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RIGHTS = ROOT / "data" / "rights.json"

STATES = ("cleared", "needs_review", "blocked", "not_permitted")
USE_RISK = {
    "display": "low",
    "retrieval": "medium",
    "local_embeddings": "medium",
    "external_llm": "high",
    "commercial_inference": "high",
    "train": "high",
    "redistribute": "high",
}
LEGACY_COLUMN = {"display": "display", "train": "train", "redistribute": "redistribute",
                 "commercial_inference": "commercial"}
EVIDENCE_TYPES = ("owner_report", "written_permission", "publisher_permission", "open_license", "cc0_declaration")
# Evidence about the publisher's own rights; it supports clearance only once the underlying rights are checked.
SUPPORTING_EVIDENCE = ("publisher_permission", "open_license", "cc0_declaration")
PERSON_CODE = re.compile(r"^[A-Z]{1,3}\d{2}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class Decision:
    allowed: bool
    status: str
    reason: str
    basis: str  # "source", "legacy", "subset" or "none"


def membership_digest(ids: Iterable[str]) -> str:
    """SHA-256 of the sorted record ids. A subset is cleared for exactly the members it was verified on."""
    return hashlib.sha256("\n".join(sorted(str(i) for i in ids)).encode("utf-8")).hexdigest()


def load_rights(path: Path = DEFAULT_RIGHTS) -> dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8"))["sources"]


def entry_errors(entry: Any, source: dict, use: str) -> list[str]:
    """Why a per-use entry is not a valid decision. Only `cleared` carries extra obligations."""
    if not isinstance(entry, dict):
        return ["the decision must be an object with a status"]
    status = entry.get("status")
    if status not in STATES:
        return [f"status must be one of {', '.join(STATES)}"]
    if status != "cleared":
        return []
    errors = []
    if not str(entry.get("evidence", "")).strip():
        errors.append("a clearance must record its evidence")
    if entry.get("evidence_type") not in EVIDENCE_TYPES:
        errors.append(f"evidence_type must be one of {', '.join(EVIDENCE_TYPES)}")
    if not DATE.match(str(entry.get("decided_on", ""))):
        errors.append("decided_on must be a YYYY-MM-DD date")
    decided_by = entry.get("decided_by")
    if not PERSON_CODE.match(str(decided_by)):
        errors.append("decided_by must be a roster code such as O01, not a name")
    verified = entry.get("verified_by")
    if not isinstance(verified, list) or not verified or not all(PERSON_CODE.match(str(v)) for v in verified):
        errors.append("a clearance needs independent verification: verified_by is a list of roster codes")
    elif decided_by in verified:
        errors.append("the person who decided cannot be the one who verified")
    if entry.get("evidence_type") in SUPPORTING_EVIDENCE and entry.get("underlying_rights_checked") is not True:
        errors.append("a CC0 declaration, open license or publisher permission clears only after "
                      "underlying_rights_checked is true (it does not cover other people's rights)")
    if source.get("attribution_required") and not str(entry.get("attribution", "")).strip():
        errors.append("this source requires attribution: record the attribution text owed")
    if source.get("provider_derived"):
        terms = entry.get("provider_terms")
        if not isinstance(terms, dict) or not all(str(terms.get(k, "")).strip()
                                                  for k in ("product", "terms_reference", "reviewed_on")):
            errors.append("provider-derived text: record the provider terms reviewed "
                          "(product, terms_reference, reviewed_on)")
    return errors


def source_status(source: dict, use: str) -> tuple[str, str]:
    """(status, basis) from the explicit per-use decision, else the legacy column, else needs_review."""
    explicit = (source.get("uses") or {}).get(use)
    if explicit is not None:
        return str(explicit.get("status", "needs_review")) if isinstance(explicit, dict) else "needs_review", "source"
    column = LEGACY_COLUMN.get(use)
    if column and column in source:
        return str(source[column]), "legacy"
    return "needs_review", "none"


def _components_cleared(sources: dict, source: dict, use: str) -> str | None:
    for name in source.get("components") or []:
        component = sources.get(name)
        if component is None or not _source_allows(sources, component, use)[0]:
            return name
    return None


def _source_allows(sources: dict, source: dict, use: str) -> tuple[bool, str, str]:
    status, basis = source_status(source, use)
    if status != "cleared":
        return False, status, f"{use} is {status} for this source"
    if basis == "source":
        errors = entry_errors(source["uses"][use], source, use)
        if errors:
            return False, "needs_review", f"clearance for {use} is not valid: {errors[0]}"
    held = _components_cleared(sources, source, use)
    if held:
        return False, "needs_review", f"{use} is not cleared for component {held}"
    return True, "cleared", ""


def _subset_allows(sources: dict, source_id: str, source: dict, subset_id: str, use: str,
                   members: Iterable[str] | None) -> tuple[bool, str, str]:
    subset = (source.get("subsets") or {}).get(subset_id)
    if not isinstance(subset, dict):
        return False, "needs_review", f"unknown subset {subset_id}"
    entry = (subset.get("uses") or {}).get(use)
    status = str(entry.get("status")) if isinstance(entry, dict) else "needs_review"
    if status != "cleared":
        return False, status, f"{use} is {status} for subset {subset_id}"
    errors = entry_errors(entry, source, use)
    if errors:
        return False, "needs_review", f"clearance for {use} on subset {subset_id} is not valid: {errors[0]}"
    if source_status(source, use)[0] == "not_permitted":
        return False, "not_permitted", f"the rights holder refused {use}; a subset cannot override that"
    for name in source.get("components") or []:
        component = sources.get(name, {})
        held = ((subset.get("component_clearances") or {}).get(name) or {}).get(use)
        if entry_errors(held, component, use) or (held or {}).get("status") != "cleared":
            return False, "needs_review", f"subset {subset_id} has no valid {use} clearance for component {name}"
    if members is None:
        return False, "needs_review", f"membership of subset {subset_id} was not supplied"
    if membership_digest(members) != subset.get("members_sha256"):
        return False, "needs_review", f"subset {subset_id} no longer matches the members that were cleared"
    return True, "cleared", ""


def authorize(sources: dict, source_id: str, use: str, subset: str | None = None,
              members: Iterable[str] | None = None) -> Decision:
    """May this source (or a verified subset of it) be used for this purpose? Default deny."""
    if use not in USE_RISK:
        return Decision(False, "needs_review", f"unknown use {use}", "none")
    source = sources.get(source_id)
    if not isinstance(source, dict):
        return Decision(False, "needs_review", f"unknown source {source_id}", "none")
    allowed, status, reason = _source_allows(sources, source, use)
    if allowed:
        return Decision(True, "cleared", "", source_status(source, use)[1])
    if subset is not None:
        sub_allowed, sub_status, sub_reason = _subset_allows(sources, source_id, source, subset, use, members)
        if sub_allowed:
            return Decision(True, "cleared", "", "subset")
        return Decision(False, sub_status, sub_reason, "subset")
    return Decision(False, status, reason, source_status(source, use)[1])


def select_usable(records: Iterable[dict], sources: dict, use: str, *,
                  members: dict[str, Iterable[str]] | None = None,
                  source_of: Callable[[dict], str] = lambda r: r["source"],
                  subset_of: Callable[[dict], str | None] = lambda r: r.get("subset"),
                  id_of: Callable[[dict], str] = lambda r: r["id"]) -> tuple[list[dict], Counter]:
    """Records usable for `use`, and a count of the reasons the rest were excluded.

    A record tagged with a subset counts as a member only if its id is in the supplied membership; a record
    that merely claims a subset is excluded.
    """
    member_sets = {name: set(map(str, ids)) for name, ids in (members or {}).items()}
    usable: list[dict] = []
    excluded: Counter = Counter()
    cache: dict[tuple[str, str | None], Decision] = {}
    for record in records:
        source_id, subset_id = source_of(record), subset_of(record)
        claimed = subset_id if subset_id in member_sets and str(id_of(record)) in member_sets[subset_id] else None
        if subset_id and claimed is None:
            subset_id = None  # not a verified member: judged as the source alone
        key = (source_id, claimed)
        if key not in cache:
            cache[key] = authorize(sources, source_id, use, claimed, member_sets.get(claimed) if claimed else None)
        decision = cache[key]
        if decision.allowed:
            usable.append(record)
        else:
            excluded[f"{source_id}: {decision.reason}"] += 1
    return usable, excluded


def validate_rights(sources: dict) -> list[str]:
    """Structural problems in the register. Empty means the register is consistent."""
    problems: list[str] = []
    for name, source in sorted(sources.items()):
        if not isinstance(source, dict):
            problems.append(f"{name}: not an object")
            continue
        for column in ("display", "train", "redistribute", "commercial"):
            if column in source and source[column] not in STATES:
                problems.append(f"{name}.{column}: {source[column]!r} is not one of {', '.join(STATES)}")
        for use, entry in (source.get("uses") or {}).items():
            if use not in USE_RISK:
                problems.append(f"{name}.uses.{use}: unknown use")
                continue
            for message in entry_errors(entry, source, use):
                problems.append(f"{name}.uses.{use}: {message}")
            column = LEGACY_COLUMN.get(use)
            if (isinstance(entry, dict) and entry.get("status") == "cleared" and column
                    and column in source and source[column] != "cleared"):
                problems.append(f"{name}.uses.{use}: cleared, but legacy column {column} is {source[column]}; "
                                "change both in the same decision")
            if (isinstance(entry, dict) and entry.get("status") == "cleared"
                    and _components_cleared(sources, source, use)):
                problems.append(f"{name}.uses.{use}: cleared before its components are")
        for component in source.get("components") or []:
            if component not in sources:
                problems.append(f"{name}.components: unknown source {component}")
        for subset_id, subset in (source.get("subsets") or {}).items():
            where = f"{name}.subsets.{subset_id}"
            if not re.fullmatch(r"[0-9a-f]{64}", str((subset or {}).get("members_sha256", ""))):
                problems.append(f"{where}: members_sha256 must be the SHA-256 of the cleared members")
            for use, entry in ((subset or {}).get("uses") or {}).items():
                if use not in USE_RISK:
                    problems.append(f"{where}.uses.{use}: unknown use")
                    continue
                for message in entry_errors(entry, source, use):
                    problems.append(f"{where}.uses.{use}: {message}")
                if isinstance(entry, dict) and entry.get("status") == "cleared":
                    if source_status(source, use)[0] == "not_permitted":
                        problems.append(f"{where}.uses.{use}: the source is not_permitted for this use")
                    for component in source.get("components") or []:
                        held = ((subset.get("component_clearances") or {}).get(component) or {}).get(use)
                        if entry_errors(held, sources.get(component, {}), use) or (held or {}).get("status") != "cleared":
                            problems.append(f"{where}.uses.{use}: no valid clearance for component {component}")
        dates = [str(item.get("date", "")) for item in source.get("history") or []]
        if dates != sorted(dates) or not all(DATE.match(d) for d in dates):
            problems.append(f"{name}.history: entries must be dated YYYY-MM-DD and in order (append, never rewrite)")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "check"):
        command = sub.add_parser(name)
        command.add_argument("--rights", type=Path, default=DEFAULT_RIGHTS)
    check = sub.choices["check"]
    check.add_argument("source")
    check.add_argument("use", choices=sorted(USE_RISK))
    check.add_argument("--subset")
    args = parser.parse_args()
    sources = load_rights(args.rights)
    if args.command == "validate":
        problems = validate_rights(sources)
        for problem in problems:
            print(problem)
        print(f"{len(sources)} sources, {len(problems)} problems")
        sys.exit(1 if problems else 0)
    decision = authorize(sources, args.source, args.use, args.subset)  # a subset needs its members: see docs
    print(f"{'ALLOWED' if decision.allowed else 'DENIED'}: {args.source} / {args.use} ({decision.status}) {decision.reason}")
    sys.exit(0 if decision.allowed else 1)


if __name__ == "__main__":
    main()
