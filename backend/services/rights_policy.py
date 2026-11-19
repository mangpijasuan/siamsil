#!/usr/bin/env python3
"""Per-source, per-use rights decisions, three clearance paths, verified subsets (docs/RIGHTS_POLICY.md).

`data/rights.json` keeps its four states (cleared, needs_review, blocked, not_permitted) and its four legacy
columns (display, train, redistribute, commercial). This module adds a purpose-specific layer:

    use                   legacy column   risk
    display               display         low
    retrieval             -               medium    internal retrieval / RAG context
    local_embeddings      -               medium    embeddings from a model Siamsil runs itself
    external_llm          -               high      text sent to a third-party provider
    commercial_inference  commercial      high      paid API or product output
    train                 train           high
    redistribute          redistribute    high

A `cleared` decision names one of three clearance paths; the evidence each needs is proportionate to the risk:

    owner_original   Path A  data the project owner created. Owner decision + documented provenance + the
                             automated checks below. A second reviewer is optional.
    open_license     Path B  third-party data under a verified open license, public-domain dedication or a
                             written grant whose recorded scope covers the use. Evidence-based; a second reviewer
                             is optional.
    restricted       Path C  provider-derived, disputed, flagged, combined or otherwise uncertain data, and any
                             clearance resting on a verbal report. Needs an independent verifier.

A source or decision that shows any Path C trait is escalated automatically: an A or B decision on it does not
authorize anything until it is re-decided on Path C. Rights clearance is legal only; it never changes a record's
linguistic review status or training tier, and review fields are not accepted in a rights decision.

Default deny: an unknown source, use or subset, an uncleared status, a clearance that fails validation, or a
subset whose membership no longer matches what was cleared, is not allowed. No clearance is made by this code
except through `decide`, which records a decision a person gives it.

Usage:
  python3 ml_pipeline/scripts/rights_policy.py validate
  python3 ml_pipeline/scripts/rights_policy.py check SOURCE USE [--subset ID]
  python3 ml_pipeline/scripts/rights_policy.py report [SOURCE]
  python3 ml_pipeline/scripts/rights_policy.py attest SOURCE no_third_party_content --by O01
  python3 ml_pipeline/scripts/rights_policy.py decide SOURCE USE --path PATH --by CODE --evidence TEXT ...
"""
from __future__ import annotations

import argparse
import copy
import datetime as _dt
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from collections.abc import Callable, Iterable

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
USES = tuple(USE_RISK)
LEGACY_COLUMN = {"display": "display", "train": "train", "redistribute": "redistribute",
                 "commercial_inference": "commercial"}

PATHS = ("owner_original", "open_license", "restricted")
PATH_LABEL = {"owner_original": "A (owner-original)", "open_license": "B (open license / written grant)",
              "restricted": "C (restricted / uncertain)"}
EVIDENCE_TYPES = ("owner_authorship", "open_license", "public_domain", "cc0_declaration", "written_permission",
                  "publisher_permission", "owner_report")
PATH_EVIDENCE = {
    "owner_original": ("owner_authorship",),
    "open_license": ("open_license", "public_domain", "cc0_declaration", "written_permission"),
    "restricted": EVIDENCE_TYPES,
}
# Evidence about someone else's grant: it supports clearance only once the grantor's own rights are checked.
SUPPORTING_EVIDENCE = ("publisher_permission", "open_license", "cc0_declaration", "written_permission")

# Licenses Path B can rely on, the uses each permits and whether it requires attribution. A license not listed
# here (NoDerivatives, custom terms, "see website") is uncertain and goes through Path C.
_ALL = frozenset(USES)
_NON_COMMERCIAL = _ALL - {"commercial_inference"}
KNOWN_LICENSES: dict[str, dict[str, Any]] = {
    "public-domain": {"uses": _ALL, "attribution": False},
    "CC0-1.0": {"uses": _ALL, "attribution": False},
    "CC-BY-2.0-FR": {"uses": _ALL, "attribution": True},
    "CC-BY-3.0": {"uses": _ALL, "attribution": True},
    "CC-BY-4.0": {"uses": _ALL, "attribution": True},
    "CC-BY-SA-4.0": {"uses": _ALL, "attribution": True, "obligations": "share-alike on redistribution"},
    "CC-BY-NC-4.0": {"uses": _NON_COMMERCIAL - {"redistribute"}, "attribution": True},
    "MIT": {"uses": _ALL, "attribution": True},
}
# Path A provenance must carry these owner attestations before any use can be cleared on it.
OWNER_ATTESTATIONS = ("sole_author", "no_third_party_content")
# Linguistic review is a separate process (docs/RIGHTS_POLICY.md): these never belong in a rights decision.
QUALITY_FIELDS = ("review_status", "reviewed_by", "quality", "quality_tier", "tier", "approved_text")

PERSON_CODE = re.compile(r"^[A-Z]{1,3}\d{2}$")
OWNER_CODE = re.compile(r"^O\d{2}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Decision:
    allowed: bool
    status: str
    reason: str
    basis: str  # "source", "legacy", "subset" or "none"
    path: str | None = None


def membership_digest(ids: Iterable[str]) -> str:
    """SHA-256 of the sorted record ids. A subset is cleared for exactly the members it was verified on."""
    return hashlib.sha256("\n".join(sorted(str(i) for i in ids)).encode("utf-8")).hexdigest()


def load_register(path: Path = DEFAULT_RIGHTS) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_rights(path: Path = DEFAULT_RIGHTS) -> dict[str, dict]:
    return load_register(path)["sources"]


# --- which path a source and a decision require --------------------------------------------------------------

def escalation_reasons(source: dict, entry: dict | None = None) -> list[str]:
    """Path C traits. Any one means a clearance needs an independent verifier."""
    reasons = []
    if source.get("provider_derived"):
        reasons.append("the text is provider-derived (machine output under a provider's terms)")
    if source.get("disputed"):
        reasons.append("the rights are disputed")
    if source.get("components"):
        reasons.append("it combines components with separate rights")
    for flag in source.get("risk_flags") or []:
        reasons.append(f"risk flag on the source: {flag}")
    if entry:
        if entry.get("evidence_type") in ("owner_report", "publisher_permission"):
            reasons.append(f"the evidence is a {entry['evidence_type'].replace('_', ' ')}, which needs confirming")
        for flag in entry.get("risk_flags") or []:
            reasons.append(f"risk flag on the decision: {flag}")
        if entry.get("escalate"):
            reasons.append(f"escalated: {entry['escalate']}")
    return reasons


def eligible_paths(source: dict, entry: dict | None = None) -> tuple[str, ...]:
    """The paths a clearance on this source may use. Path C is always available, never required to be avoided."""
    if escalation_reasons(source, entry):
        return ("restricted",)
    if source.get("origin") == "owner_original":
        return ("owner_original", "restricted")
    return ("open_license", "restricted")


def _owner_provenance_errors(source: dict, entry: dict) -> list[str]:
    """Automated checks for Path A. They run every time the register is validated or consulted."""
    errors = []
    provenance = source.get("provenance")
    if source.get("origin") != "owner_original" or not isinstance(provenance, dict):
        return ["Path A needs the source marked origin: owner_original with a provenance record"]
    missing = [a for a in OWNER_ATTESTATIONS if a not in (provenance.get("attestations") or [])]
    if missing:
        errors.append(f"Path A needs the owner's attestation(s): {', '.join(missing)}")
    if not DATE.match(str(provenance.get("attested_on", ""))):
        errors.append("provenance.attested_on must be a YYYY-MM-DD date")
    elif str(entry.get("decided_on", "")) < str(provenance["attested_on"]):
        errors.append("the decision predates the provenance it relies on")
    if "ai_assistance" not in provenance:
        errors.append("provenance.ai_assistance must say whether AI tools drafted any text ('none' or what)")
    if not SHA256.match(str(provenance.get("sha256", ""))):
        errors.append("provenance.sha256 must pin the exact file the attestation covers")
    if not OWNER_CODE.match(str(entry.get("decided_by", ""))):
        errors.append("a Path A decision is the owner's: decided_by must be an owner roster code (O01, ...)")
    return errors


def _open_license_errors(source: dict, entry: dict, use: str) -> list[str]:
    errors = []
    if entry.get("evidence_type") == "written_permission":
        grant = entry.get("grant")
        if not isinstance(grant, dict) or not all(str(grant.get(k, "")).strip()
                                                  for k in ("grantor", "date", "wording", "kept_at")):
            errors.append("a written grant must record grant.grantor, grant.date, grant.wording and grant.kept_at")
        elif use not in (grant.get("scope") or []):
            errors.append(f"the written grant's recorded scope does not include {use}")
        return errors
    license_id = entry.get("license")
    terms = KNOWN_LICENSES.get(str(license_id))
    if terms is None:
        return [f"license {license_id!r} is not one Path B can rely on ({', '.join(KNOWN_LICENSES)}); "
                "decide it on Path C"]
    if use not in terms["uses"]:
        errors.append(f"{license_id} does not permit {use}")
    if terms["attribution"] and not str(entry.get("attribution", "")).strip():
        errors.append(f"{license_id} requires attribution: record the attribution text owed")
    if terms.get("obligations") and not str(entry.get("obligations", "")).strip():
        errors.append(f"{license_id} carries obligations ({terms['obligations']}): record how they are met")
    return errors


def entry_errors(entry: Any, source: dict, use: str) -> list[str]:
    """Why a per-use entry is not a valid decision. Only `cleared` carries extra obligations."""
    if not isinstance(entry, dict):
        return ["the decision must be an object with a status"]
    status = entry.get("status")
    if status not in STATES:
        return [f"status must be one of {', '.join(STATES)}"]
    quality = [k for k in QUALITY_FIELDS if k in entry]
    if quality:
        return [f"linguistic review fields ({', '.join(quality)}) do not belong in a rights decision"]
    if status != "cleared":
        return []
    errors = []
    path = entry.get("path")
    if path not in PATHS:
        return [f"a clearance must name its path: one of {', '.join(PATHS)}"]
    if not str(entry.get("evidence", "")).strip():
        errors.append("a clearance must record its evidence")
    if entry.get("evidence_type") not in PATH_EVIDENCE[path]:
        errors.append(f"evidence_type for path {path} must be one of {', '.join(PATH_EVIDENCE[path])}")
    if not DATE.match(str(entry.get("decided_on", ""))):
        errors.append("decided_on must be a YYYY-MM-DD date")
    decided_by = entry.get("decided_by")
    if not PERSON_CODE.match(str(decided_by)):
        errors.append("decided_by must be a roster code such as O01, not a name")
    verified = entry.get("verified_by")
    if verified is not None and (not isinstance(verified, list)
                                 or not all(PERSON_CODE.match(str(v)) for v in verified)):
        errors.append("verified_by, when given, is a list of roster codes")
        verified = None
    if path not in eligible_paths(source, entry):
        reasons = "; ".join(escalation_reasons(source, entry)) or "the source is not marked owner_original"
        errors.append(f"path {path} is not available here ({reasons}); decide it on Path C")
    if path == "restricted":
        independent = [v for v in (verified or []) if v != decided_by]
        if not independent:
            errors.append("Path C needs an independent verifier: verified_by must name someone other than "
                          "decided_by")
        if entry.get("evidence_type") in SUPPORTING_EVIDENCE and entry.get("underlying_rights_checked") is not True:
            errors.append("a CC0 declaration, open license, publisher permission or written grant clears only "
                          "after underlying_rights_checked is true")
    elif path == "owner_original":
        errors.extend(_owner_provenance_errors(source, entry))
    elif path == "open_license":
        if entry.get("underlying_rights_checked") is not True:
            errors.append("Path B needs underlying_rights_checked: true (the licensor or grantor holds the rights "
                          "it grants; a re-upload's license does not)")
        errors.extend(_open_license_errors(source, entry, use))
    if source.get("attribution_required") and not str(entry.get("attribution", "")).strip():
        errors.append("this source requires attribution: record the attribution text owed")
    if source.get("provider_derived"):
        terms = entry.get("provider_terms")
        if not isinstance(terms, dict) or not all(str(terms.get(k, "")).strip()
                                                  for k in ("product", "terms_reference", "reviewed_on")):
            errors.append("provider-derived text: record the provider terms reviewed "
                          "(product, terms_reference, reviewed_on)")
    return errors


# --- authorization -------------------------------------------------------------------------------------------

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


def _subset_allows(sources: dict, source: dict, subset_id: str, use: str,
                   members: Iterable[str] | None) -> tuple[bool, str, str]:
    subset = (source.get("subsets") or {}).get(subset_id)
    if not isinstance(subset, dict):
        return False, "needs_review", f"unknown subset {subset_id}"
    entry = (subset.get("uses") or {}).get(use)
    status = str(entry.get("status")) if isinstance(entry, dict) else "needs_review"
    if status != "cleared":
        return False, status, f"{use} is {status} for subset {subset_id}"
    subset_source = _subset_view(source, subset)
    errors = entry_errors(entry, subset_source, use)
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


def _subset_view(source: dict, subset: dict) -> dict:
    """The source as a subset sees it: a subset may carry its own provenance (for example owner-written rows of a
    larger file), but it inherits every Path C trait of its source."""
    view = {k: v for k, v in source.items() if k not in ("uses", "subsets")}
    for key in ("origin", "provenance"):
        if key in subset:
            view[key] = subset[key]
    view["risk_flags"] = list(source.get("risk_flags") or []) + list(subset.get("risk_flags") or [])
    return view


def authorize(sources: dict, source_id: str, use: str, subset: str | None = None,
              members: Iterable[str] | None = None) -> Decision:
    """May this source (or a verified subset of it) be used for this purpose? Default deny."""
    if use not in USE_RISK:
        return Decision(False, "needs_review", f"unknown use {use}", "none")
    source = sources.get(source_id)
    if not isinstance(source, dict):
        return Decision(False, "needs_review", f"unknown source {source_id}", "none")
    allowed, status, reason = _source_allows(sources, source, use)
    basis = source_status(source, use)[1]
    if allowed:
        entry = (source.get("uses") or {}).get(use) if basis == "source" else None
        return Decision(True, "cleared", "", basis, (entry or {}).get("path"))
    if subset is not None:
        sub_allowed, sub_status, sub_reason = _subset_allows(sources, source, subset, use, members)
        if sub_allowed:
            path = (((source.get("subsets") or {}).get(subset) or {}).get("uses") or {}).get(use, {}).get("path")
            return Decision(True, "cleared", "", "subset", path)
        return Decision(False, sub_status, sub_reason, "subset")
    return Decision(False, status, reason, basis)


def read_members(path: Path) -> list[str]:
    """One record id per line; blank lines and # comments are ignored."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def usable_ids(sources: dict, source_id: str, use: str, base_dir: Path = ROOT / "data") -> frozenset[str] | None:
    """For code that reads a source record by record. None: the whole source may be used. Otherwise the ids of
    the records in subsets cleared for `use` whose membership file (`members_file`, relative to the register's
    folder) still matches its digest; possibly empty."""
    if authorize(sources, source_id, use).allowed:
        return None
    ids: set[str] = set()
    for subset_id, subset in ((sources.get(source_id) or {}).get("subsets") or {}).items():
        members_file = (subset or {}).get("members_file")
        if not members_file or not (Path(base_dir) / members_file).is_file():
            continue
        members = read_members(Path(base_dir) / members_file)
        if authorize(sources, source_id, use, subset_id, members).allowed:
            ids.update(members)
    return frozenset(ids)


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
        key = (source_id, claimed)
        if key not in cache:
            cache[key] = authorize(sources, source_id, use, claimed, member_sets.get(claimed) if claimed else None)
        decision = cache[key]
        if decision.allowed:
            usable.append(record)
        else:
            excluded[f"{source_id}: {decision.reason}"] += 1
    return usable, excluded


def legacy_statuses(sources: dict, use: str) -> dict[str, str]:
    """{source: status} for one use, as the policy decides it: "cleared" only when authorize() allows it. Lets
    code written against the legacy columns (export_datasets.py, import_usx_bibles.py) enforce the policy
    without changing shape."""
    out = {}
    for name, source in sources.items():
        if not isinstance(source, dict):
            continue
        decision = authorize(sources, name, use)
        out[name] = "cleared" if decision.allowed else (
            decision.status if decision.status != "cleared" else "needs_review")
    return out


# --- validation ----------------------------------------------------------------------------------------------

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
        if source.get("origin") not in (None, "owner_original", "third_party"):
            problems.append(f"{name}.origin: must be owner_original or third_party")
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
            if not SHA256.match(str((subset or {}).get("members_sha256", ""))):
                problems.append(f"{where}: members_sha256 must be the SHA-256 of the cleared members")
            view = _subset_view(source, subset or {})
            for use, entry in ((subset or {}).get("uses") or {}).items():
                if use not in USE_RISK:
                    problems.append(f"{where}.uses.{use}: unknown use")
                    continue
                for message in entry_errors(entry, view, use):
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


# --- eligibility report --------------------------------------------------------------------------------------

@dataclass
class Eligibility:
    source: str
    use: str
    status: str
    allowed: bool
    path: str | None
    needs: list[str] = field(default_factory=list)


def next_steps(source: dict, use: str) -> list[str]:
    """What is still missing before `use` can be cleared on this source, on the lightest path available."""
    status, _ = source_status(source, use)
    if status == "not_permitted":
        return ["the rights holder refused or no permission exists; only a new grant can change this"]
    paths = eligible_paths(source)
    path = paths[0]
    steps: list[str] = []
    if path == "restricted":
        steps += [f"Path C because {r}" for r in escalation_reasons(source)] or ["Path C"]
        steps.append("evidence, then an independent verifier (verified_by other than decided_by)")
        if source.get("provider_derived"):
            steps.append("the provider terms in force when the text was generated, and whether they allow " + use)
        return steps
    if path == "owner_original":
        provenance = source.get("provenance") or {}
        missing = [a for a in OWNER_ATTESTATIONS if a not in (provenance.get("attestations") or [])]
        if missing:
            steps.append("owner attestation(s): " + ", ".join(missing))
        if not SHA256.match(str(provenance.get("sha256", ""))):
            steps.append("provenance.sha256 of the file the attestation covers")
        steps.append(f"the owner's decision for {use} (`decide ... --path owner_original`)")
        return steps
    license_id = source.get("license")
    if license_id in KNOWN_LICENSES:
        if use not in KNOWN_LICENSES[license_id]["uses"]:
            return [f"{license_id} does not permit {use}"]
        steps.append(f"a decision for {use} citing the {license_id} evidence (`decide ... --path open_license`)")
    elif isinstance(source.get("grant"), dict):
        scope = source["grant"].get("scope") or []
        if use not in scope:
            steps.append(f"the recorded grant covers {', '.join(scope) or 'nothing'}; ask the grantor about {use}")
        else:
            steps.append(f"a decision for {use} citing the written grant (`decide ... --path open_license`)")
    else:
        steps.append("verify the license or get a written grant (grantor, date, wording, scope, where kept); "
                     "until then Path C")
    if source.get("attribution_required") or (KNOWN_LICENSES.get(str(license_id)) or {}).get("attribution"):
        steps.append("the attribution text owed")
    return steps


def eligibility(sources: dict, only: str | None = None) -> list[Eligibility]:
    rows = []
    for name in sorted(sources):
        if only and name != only:
            continue
        source = sources[name]
        if not isinstance(source, dict):
            continue
        for use in USES:
            decision = authorize(sources, name, use)
            rows.append(Eligibility(name, use, decision.status, decision.allowed,
                                    decision.path or (eligible_paths(source)[0] if not decision.allowed else None),
                                    [] if decision.allowed else next_steps(source, use)))
    return rows


# --- recording a decision ------------------------------------------------------------------------------------

def record_decision(register: dict, source_id: str, use: str, entry: dict, *, today: str | None = None) -> dict:
    """A new register with this decision recorded: the per-use entry replaced, the legacy column changed with it,
    and a dated history line appended. The earlier entry is kept in history. Raises ValueError if the result does
    not validate, so an incomplete decision is never written."""
    new = copy.deepcopy(register)
    sources = new["sources"]
    if source_id not in sources:
        raise ValueError(f"unknown source {source_id}")
    if use not in USE_RISK:
        raise ValueError(f"unknown use {use}")
    source = sources[source_id]
    previous = (source.get("uses") or {}).get(use)
    source.setdefault("uses", {})[use] = entry
    column = LEGACY_COLUMN.get(use)
    if column and entry.get("status") == "cleared":
        source[column] = "cleared"
    elif column and column in source and entry.get("status") != "cleared":
        source[column] = entry.get("status")
    date = today or entry.get("decided_on") or _dt.date.today().isoformat()
    history = source.setdefault("history", [])
    if history and str(history[-1].get("date", "")) > date:
        date = str(history[-1]["date"])
    note = (f"{use}: {entry.get('status')} on path {entry.get('path')} by {entry.get('decided_by')}"
            if entry.get("status") == "cleared" else f"{use}: {entry.get('status')}")
    history.append({"date": date, "status": entry.get("status"), "use": use, "note": note,
                    "previous": previous if previous is not None else source_status(register["sources"][source_id],
                                                                                    use)[0]})
    problems = [p for p in validate_rights(sources) if p.startswith(f"{source_id}.")]
    if problems:
        raise ValueError("the decision does not validate:\n  " + "\n  ".join(problems))
    return new


def record_attestation(register: dict, source_id: str, attestation: str, by: str, on: str) -> dict:
    """A new register with an owner attestation added to a Path A source's provenance, and a history line."""
    if attestation not in OWNER_ATTESTATIONS:
        raise ValueError(f"attestation must be one of {', '.join(OWNER_ATTESTATIONS)}")
    if not OWNER_CODE.match(by):
        raise ValueError("an attestation is the owner's: --by must be an owner roster code (O01, ...)")
    if not DATE.match(on):
        raise ValueError("--on must be a YYYY-MM-DD date")
    new = copy.deepcopy(register)
    source = new["sources"].get(source_id)
    if not isinstance(source, dict) or source.get("origin") != "owner_original":
        raise ValueError(f"{source_id} is not marked origin: owner_original")
    provenance = source.setdefault("provenance", {})
    attestations = provenance.setdefault("attestations", [])
    if attestation not in attestations:
        attestations.append(attestation)
    pending = [a for a in provenance.get("attestations_pending") or [] if a != attestation]
    if pending:
        provenance["attestations_pending"] = pending
    else:
        provenance.pop("attestations_pending", None)
    provenance["attested_on"] = max(on, str(provenance.get("attested_on", "")))
    history = source.setdefault("history", [])
    date = max(on, str(history[-1].get("date", ""))) if history else on
    history.append({"date": date, "status": "unchanged", "note": f"owner attestation {attestation} recorded by {by}"})
    return new


# --- command line --------------------------------------------------------------------------------------------

def _print_report(rows: list[Eligibility]) -> None:
    current = None
    for row in rows:
        if row.source != current:
            current = row.source
            print(f"\n{row.source}")
        mark = "ALLOWED" if row.allowed else row.status
        path = f" [{PATH_LABEL.get(row.path, row.path)}]" if row.path else ""
        print(f"  {row.use:<21} {mark:<13}{path}")
        for step in row.needs:
            print(f"      - {step}")
    allowed = sum(r.allowed for r in rows)
    print(f"\n{allowed} of {len(rows)} source-uses allowed")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "check", "report", "decide", "attest"):
        command = sub.add_parser(name)
        command.add_argument("--rights", type=Path, default=DEFAULT_RIGHTS)
    check = sub.choices["check"]
    check.add_argument("source")
    check.add_argument("use", choices=USES)
    check.add_argument("--subset")
    check.add_argument("--members", type=Path, help="file of subset member ids, one per line")
    report = sub.choices["report"]
    report.add_argument("source", nargs="?")
    decide = sub.choices["decide"]
    decide.add_argument("source")
    decide.add_argument("use", choices=USES)
    decide.add_argument("--path", choices=PATHS, required=True)
    decide.add_argument("--by", required=True, help="roster code of the person deciding (owner: O01, ...)")
    decide.add_argument("--evidence", required=True, help="what the evidence is and where it is kept")
    decide.add_argument("--evidence-type", choices=EVIDENCE_TYPES)
    decide.add_argument("--verified-by", nargs="*", default=None)
    decide.add_argument("--license")
    decide.add_argument("--attribution")
    decide.add_argument("--underlying-rights-checked", action="store_true")
    decide.add_argument("--on", help="decision date, YYYY-MM-DD (default today)")
    decide.add_argument("--dry-run", action="store_true")
    attest = sub.choices["attest"]
    attest.add_argument("source")
    attest.add_argument("attestation", choices=OWNER_ATTESTATIONS)
    attest.add_argument("--by", required=True, help="owner roster code (O01, ...)")
    attest.add_argument("--on", default=_dt.date.today().isoformat())
    args = parser.parse_args(argv)

    register = load_register(args.rights)
    sources = register["sources"]
    if args.command == "validate":
        problems = validate_rights(sources)
        for problem in problems:
            print(problem)
        print(f"{len(sources)} sources, {len(problems)} problems")
        sys.exit(1 if problems else 0)
    if args.command == "report":
        _print_report(eligibility(sources, args.source))
        return
    if args.command == "check":
        members = read_members(args.members) if args.members else None
        decision = authorize(sources, args.source, args.use, args.subset, members)
        path = f" path {decision.path}" if decision.path else ""
        print(f"{'ALLOWED' if decision.allowed else 'DENIED'}: {args.source} / {args.use} "
              f"({decision.status}{path}) {decision.reason}")
        sys.exit(0 if decision.allowed else 1)

    if args.command == "attest":
        try:
            new = record_attestation(register, args.source, args.attestation, args.by, args.on)
        except ValueError as error:
            sys.exit(str(error))
        Path(args.rights).write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"recorded: {args.source} attestation {args.attestation} by {args.by}")
        return

    default_type = {"owner_original": "owner_authorship", "open_license": "open_license"}.get(args.path)
    entry: dict[str, Any] = {
        "status": "cleared", "path": args.path, "evidence": args.evidence,
        "evidence_type": args.evidence_type or default_type,
        "decided_on": args.on or _dt.date.today().isoformat(), "decided_by": args.by,
    }
    if args.verified_by:
        entry["verified_by"] = args.verified_by
    if args.license:
        entry["license"] = args.license
    if args.attribution:
        entry["attribution"] = args.attribution
    if args.underlying_rights_checked:
        entry["underlying_rights_checked"] = True
    try:
        new = record_decision(register, args.source, args.use, entry)
    except ValueError as error:
        sys.exit(str(error))
    if args.dry_run:
        print(json.dumps(new["sources"][args.source], indent=2, ensure_ascii=False))
        return
    Path(args.rights).write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"recorded: {args.source} / {args.use} cleared on path {args.path} by {args.by}. "
          "Record it in docs/DATA_RIGHTS.md in the same change.")


if __name__ == "__main__":
    main()
