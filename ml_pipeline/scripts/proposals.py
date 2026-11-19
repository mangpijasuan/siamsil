#!/usr/bin/env python3
"""Suggestions for the owner to decide: attested words, spelling variants and AI candidates (docs/PROPOSALS.md).

A proposal is never a decision. Every proposal has status `ai_suggested` (docs/GOVERNANCE.md) until the owner
accepts, edits, rejects or defers it, and accepting one records the owner's decision, not a change to any data:
a later step applies accepted proposals with a preview and rollback.

  mine-words  Zomi word forms that occur in texts cleared for it but nowhere in the dictionary, with counts and
              references. No model and no invention: each word is quoted from a source text. A form that the
              owner's adopted Standard Form turns into a word the dictionary has is a spelling variant of it.
  generate    Ask a model for suggestions about given items (a sense, a headword, a candidate), through a command
              you name that reads a prompt on stdin and prints JSON. Its output is untrusted: it is checked, capped
              and always recorded as `ai_candidate`, never as attested.
  sheet       A decision sheet (CSV) for a proposals file.
  record      Save the owner's decisions (accept, edit, reject, defer), owner only, append-only.

What each kind of proposal claims (`evidence_class`):

  attested          the form occurs in a named source text; references are given
  spelling_variant  a spelling the adopted Standard Form maps to a form the dictionary has
  derived_form      built from an attested form by a rule the owner adopted (none are adopted yet)
  proposed_term     a new term the owner or a speaker put forward
  ai_candidate      a model's suggestion: unverified, whatever the model says about it

Where it comes from (`origin`): `deterministic` (a rule in this repository), `local_model` (a model on your own
computer) or `provider_assisted` (an outside service). Rights are checked per source in data/rights.json before
any text is read: mining needs `train` (a word list is derived data), a local model needs `retrieval`, an outside
provider needs `external_llm`. Provider-assisted proposals keep that origin after the owner accepts them, so
training exports can leave them out (docs/QUALITY_OPERATOR_ARCHITECTURE.md, Lane B).

  python3 ml_pipeline/scripts/proposals.py mine-words --bible-db data/processed/bible/bible_versions.sqlite \\
      --reference-db data/processed/reference/reference_dictionaries.sqlite \\
      --out ../siamsil-data/reviews/proposals/attested-words-1.jsonl
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shlex
import sqlite3
import subprocess
import sys
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corpus_reviews  # type: ignore  # noqa: E402
import rights_policy  # type: ignore  # noqa: E402
import zolai_standard  # type: ignore  # noqa: E402

TOOL_VERSION = "1.0.0"
STATUS = "ai_suggested"
KINDS = ("headword_candidate", "alternative_form", "definition", "part_of_speech", "example", "relation",
         "synonym", "antonym", "morphology", "english_equivalent", "correction")
EVIDENCE_CLASSES = ("attested", "spelling_variant", "derived_form", "proposed_term", "ai_candidate")
ORIGINS = ("deterministic", "local_model", "provider_assisted")
USE_FOR_ORIGIN = {"deterministic": "train", "local_model": "retrieval", "provider_assisted": "external_llm"}
DECISIONS = ("accept", "edit", "reject", "defer")
SHEET_COLUMNS = ["proposal_id", "kind", "evidence_class", "origin", "target", "proposal", "evidence", "explanation",
                 "decision", "edited_text", "notes"]
MAX_TEXT = 500
ZOMI_LANGUAGES = ("ctd", "zom")
TOKEN = re.compile(r"[^\W\d_]+(?:['’ʼ-][^\W\d_]+)*", re.UNICODE)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def proposal_id(kind: str, target: dict, payload: dict) -> str:
    key = json.dumps([kind, target, payload], sort_keys=True, ensure_ascii=False)
    return "P-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def make(kind: str, target: dict, payload: dict, evidence_class: str, origin: str, generator: dict,
         inputs: list[str], evidence: list[dict] | None = None, explanation: str = "",
         confidence: float | None = None) -> dict:
    record = {"proposal_id": proposal_id(kind, target, payload), "kind": kind, "target": target, "payload": payload,
              "evidence_class": evidence_class, "evidence": evidence or [], "origin": origin, "generator": generator,
              "inputs": sorted(set(inputs)), "explanation": explanation, "status": STATUS, "created_at": now_utc()}
    if confidence is not None:
        record["confidence_self_reported"] = confidence
    return record


def validate(record: dict) -> list[str]:
    """Why a proposal record is not acceptable. Empty means it is."""
    errors = []
    if record.get("status") != STATUS:
        errors.append(f"status must be {STATUS}: a proposal is never a decision")
    for field, allowed in (("kind", KINDS), ("evidence_class", EVIDENCE_CLASSES), ("origin", ORIGINS)):
        if record.get(field) not in allowed:
            errors.append(f"{field} must be one of {', '.join(allowed)}")
    generator = record.get("generator") or {}
    if not generator.get("name") or not generator.get("version"):
        errors.append("generator needs a name and a version")
    origin = record.get("origin")
    if origin in ("local_model", "provider_assisted"):
        if record.get("evidence_class") != "ai_candidate":
            errors.append("a model's suggestion is an ai_candidate, whatever it claims")
        if not generator.get("prompt_sha256") or not generator.get("run_id"):
            errors.append("a model's suggestion records the prompt's sha256 and the run id")
    if origin == "provider_assisted":
        terms = generator.get("provider_terms") or {}
        if not all(str(terms.get(k, "")).strip() for k in ("product", "terms_reference", "reviewed_on")):
            errors.append("a provider-assisted suggestion records the provider terms reviewed")
    if record.get("evidence_class") in ("attested", "spelling_variant"):
        refs = record.get("evidence") or []
        if not refs or not all(isinstance(r, dict) and r.get("source") and r.get("ref") for r in refs):
            errors.append("an attested form or spelling variant names its source and references")
    if not record.get("inputs"):
        errors.append("inputs must name the data sources read")
    return errors


def check_rights(sources: dict, inputs: Iterable[str], origin: str) -> list[str]:
    """Sources that may not be read for this origin. Default deny (rights_policy.authorize)."""
    use = USE_FOR_ORIGIN[origin]
    return [f"{source}: {rights_policy.authorize(sources, source, use).reason or use + ' not cleared'}"
            for source in sorted(set(inputs)) if not rights_policy.authorize(sources, source, use).allowed]


def tokens(text: str) -> list[str]:
    return TOKEN.findall(text or "")


# --- mine-words ------------------------------------------------------------------------------------------------

def dictionary_forms(reference: sqlite3.Connection, standard: zolai_standard.Standard) -> set[str]:
    """Every Zomi word form in the dictionary's senses and examples, and each whole equivalent (a standard form can
    be two words: ZS-001 spells 'uhi' as 'uh hi'), as written and in standard form."""
    forms: set[str] = set()
    for (text,) in reference.execute("SELECT zomi FROM senses UNION ALL SELECT zomi FROM examples"):
        for piece in [*(part.strip() for part in (text or "").split(";")), *tokens(text or "")]:
            if piece:
                forms.add(zolai_standard.norm(piece))
                forms.add(zolai_standard.norm(zolai_standard.standardize(piece, standard).text))
    return forms


def mine_words(bible: sqlite3.Connection, reference: sqlite3.Connection, sources: dict,
               standard: zolai_standard.Standard, *, min_count: int = 3, max_refs: int = 3,
               run_id: str | None = None) -> tuple[list[dict], dict]:
    """Attested word forms missing from the dictionary, most frequent first, and what was read or skipped."""
    versions = bible.execute("SELECT id, rights_source, language_iso FROM versions ORDER BY sort_order").fetchall()
    readable, skipped = [], {}
    for version_id, rights_source, language in versions:
        if language not in ZOMI_LANGUAGES:
            continue
        decision = rights_policy.authorize(sources, rights_source or "", "train")
        if decision.allowed:
            readable.append((version_id, rights_source))
        else:
            skipped[version_id] = decision.reason or "train not cleared"
    known = dictionary_forms(reference, standard)
    counts: Counter = Counter()
    capitalized: Counter = Counter()
    refs: dict[str, list[dict]] = defaultdict(list)
    seen_in: dict[str, set[str]] = defaultdict(set)
    for version_id, rights_source in readable:
        rows = bible.execute("SELECT book_id, chapter, verse, text FROM verses WHERE version_id = ? "
                             "ORDER BY book_id, chapter, verse", (version_id,))
        for book, chapter, verse, text in rows:
            words = tokens(text)
            for position, word in enumerate(words):
                form = zolai_standard.norm(word)
                if len(form) < 2 or form in known:
                    continue
                counts[form] += 1
                seen_in[form].add(rights_source)
                if position > 0 and word[:1].isupper():
                    capitalized[form] += 1
                if len(refs[form]) < max_refs:
                    refs[form].append({"source": rights_source, "ref": f"{version_id}:{book}:{chapter}:{verse}"})
    generator = {"name": "mine-words", "version": TOOL_VERSION, "run_id": run_id or uuid.uuid4().hex[:12],
                 "standard_version": standard.version}
    found = []
    for form, count in counts.most_common():
        if count < min_count:
            break
        standard_form = zolai_standard.norm(zolai_standard.standardize(form, standard).text)
        payload: dict[str, Any] = {"zomi": form, "occurrences": count}
        if capitalized[form] >= max(1, round(count * 0.8)):
            payload["mostly_capitalized"] = True  # inside sentences: probably a name
        inputs = sorted(seen_in[form])
        if standard_form != form and standard_form in known:
            payload["standard_form"] = standard_form
            found.append(make("alternative_form", {"type": "new"}, payload, "spelling_variant", "deterministic",
                              generator, inputs, refs[form],
                              f"'{form}' occurs {count} times; the adopted Standard Form spells it "
                              f"'{standard_form}', which the dictionary has"))
        else:
            found.append(make("headword_candidate", {"type": "new"}, payload, "attested", "deterministic",
                              generator, inputs, refs[form],
                              f"'{form}' occurs {count} times in the texts read and is not in the dictionary"))
    report = {"versions_read": [v for v, _ in readable], "versions_skipped": skipped,
              "dictionary_forms": len(known), "candidates": len(found), "min_count": min_count}
    return found, report


# --- generate (a model you run) --------------------------------------------------------------------------------

def _clean(value: Any) -> str:
    text = " ".join(str(value).split()) if value is not None else ""
    return text[:MAX_TEXT]


def parse_model_output(raw: str) -> tuple[list[dict], int]:
    """Suggestions from a model's stdout (a JSON list, a JSON object with "suggestions", or JSON lines).
    Returns (suggestions, number dropped). Anything malformed is dropped, never repaired by guessing."""
    raw = raw.strip()
    items: list[Any] = []
    try:
        parsed = json.loads(raw)
        items = parsed.get("suggestions", []) if isinstance(parsed, dict) else parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        for line in raw.splitlines():
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                items.append(None)
    kept, dropped = [], 0
    for item in items:
        if not isinstance(item, dict) or item.get("kind") not in KINDS or not isinstance(item.get("payload"), dict):
            dropped += 1
            continue
        payload = {str(k)[:40]: _clean(v) for k, v in list(item["payload"].items())[:8] if _clean(v)}
        if not payload:
            dropped += 1
            continue
        confidence = item.get("confidence")
        confidence = float(confidence) if isinstance(confidence, (int, float)) and 0 <= confidence <= 1 else None
        kept.append({"kind": item["kind"], "payload": payload, "explanation": _clean(item.get("explanation")),
                     "confidence": confidence})
    return kept, dropped


def generate(items: list[dict], *, prompt_template: str, command: list[str], model_name: str, model_version: str,
             origin: str, sources: dict, provider_terms: dict | None = None, timeout: int = 120,
             run_id: str | None = None) -> tuple[list[dict], dict]:
    """Run the model on each item. Refuses before running anything if an item's source is not cleared."""
    if origin not in ("local_model", "provider_assisted"):
        raise ValueError("origin must be local_model or provider_assisted")
    if origin == "provider_assisted" and not provider_terms:
        raise ValueError("an outside provider needs --provider-terms (product, terms_reference, reviewed_on)")
    refused = check_rights(sources, [str(item.get("source", "")) for item in items], origin)
    if refused:
        raise PermissionError("not cleared for " + USE_FOR_ORIGIN[origin] + ": " + "; ".join(refused))
    if "{item}" not in prompt_template:
        raise ValueError("the prompt template must contain {item} where the item goes")
    generator = {"name": model_name, "version": model_version, "run_id": run_id or uuid.uuid4().hex[:12],
                 "prompt_sha256": hashlib.sha256(prompt_template.encode("utf-8")).hexdigest(),
                 "command": command[0] if command else ""}
    if provider_terms:
        generator["provider_terms"] = provider_terms
    found, report = [], Counter()
    for item in items:
        prompt = prompt_template.replace("{item}", json.dumps(item, ensure_ascii=False))
        try:
            done = subprocess.run(command, input=prompt, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            report["timed_out"] += 1
            continue
        if done.returncode != 0:
            report["model_errors"] += 1
            continue
        suggestions, dropped = parse_model_output(done.stdout)
        report["dropped_malformed"] += dropped
        target = {"type": str(item.get("type", "item")), "id": str(item.get("id", ""))}
        for suggestion in suggestions:
            found.append(make(suggestion["kind"], target, suggestion["payload"], "ai_candidate", origin, generator,
                              [str(item.get("source", ""))], explanation=suggestion["explanation"],
                              confidence=suggestion["confidence"]))
        report["items"] += 1
    report["suggestions"] = len(found)
    return found, dict(report)


# --- sheet and record ------------------------------------------------------------------------------------------

def _summary(payload: dict) -> str:
    return "; ".join(f"{k}: {v}" for k, v in payload.items())


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_sheet(path: Path, proposals: list[dict]) -> None:
    with open(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        for p in proposals:
            writer.writerow({"proposal_id": p["proposal_id"], "kind": p["kind"], "evidence_class": p["evidence_class"],
                             "origin": p["origin"], "target": f"{p['target'].get('type')}:{p['target'].get('id', '')}",
                             "proposal": _summary(p["payload"]),
                             "evidence": ", ".join(r["ref"] for r in p.get("evidence", [])),
                             "explanation": p.get("explanation", ""), "decision": "", "edited_text": "", "notes": ""})


def record(rows: list[dict], proposals: list[dict], *, owner: str, roster: dict[str, str], decided_on: str,
           recorded_at: str) -> tuple[list[dict], list[str]]:
    """The owner's decisions on filled-in rows. Any error saves nothing. Provenance goes with each decision."""
    if roster.get(owner) != corpus_reviews.OWNER:
        return [], [f"{owner} is not the owner in the roster; only the owner decides proposals"]
    by_id = {p["proposal_id"]: p for p in proposals}
    out, errors = [], []
    for number, row in enumerate(rows, start=2):
        decision = (row.get("decision") or "").strip().lower()
        if not decision:
            continue
        ident = (row.get("proposal_id") or "").strip()
        p = by_id.get(ident)
        edited = (row.get("edited_text") or "").strip()
        if decision not in DECISIONS:
            errors.append(f"row {number}: decision must be {', '.join(DECISIONS)}, not {decision!r}")
        elif p is None:
            errors.append(f"row {number}: {ident or '<blank>'} is not in this proposals file")
        elif (row.get("proposal") or "") != _summary(p["payload"]):
            errors.append(f"row {number}: the proposal was edited; put your version in edited_text with 'edit'")
        elif decision == "edit" and not edited:
            errors.append(f"row {number}: 'edit' needs your text in edited_text")
        else:
            out.append({"kind": "proposal_decision", "proposal_id": ident, "proposal_kind": p["kind"],
                        "decision": decision, "edited_text": edited if decision == "edit" else "",
                        "evidence_class": p["evidence_class"], "origin": p["origin"], "generator": p["generator"],
                        "provider_derived": p["origin"] == "provider_assisted", "decided_by": owner,
                        "decided_on": decided_on, "recorded_at": recorded_at, "approval": corpus_reviews.OWNER_SOLE,
                        "notes": (row.get("notes") or "").strip()})
    return out, errors


# --- command line ----------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    mine = sub.add_parser("mine-words", help="attested word forms missing from the dictionary")
    mine.add_argument("--bible-db", type=Path, required=True)
    mine.add_argument("--reference-db", type=Path, required=True)
    mine.add_argument("--out", type=Path, required=True)
    mine.add_argument("--min-count", type=int, default=3)
    gen = sub.add_parser("generate", help="suggestions from a model you run")
    gen.add_argument("--items", type=Path, required=True, help="JSON lines: {id, type, source, ...the item's fields}")
    gen.add_argument("--prompt", type=Path, required=True, help="prompt template with {item}")
    gen.add_argument("--command", required=True, help="the model command; reads the prompt on stdin, prints JSON")
    gen.add_argument("--model-name", required=True)
    gen.add_argument("--model-version", required=True)
    gen.add_argument("--origin", choices=("local_model", "provider_assisted"), default="local_model")
    gen.add_argument("--provider-terms", type=Path, help="JSON: product, terms_reference, reviewed_on")
    gen.add_argument("--out", type=Path, required=True)
    gen.add_argument("--limit", type=int, default=50, help="most items to send in one run (default 50)")
    sheet = sub.add_parser("sheet", help="a decision sheet for a proposals file")
    sheet.add_argument("--proposals", type=Path, required=True)
    sheet.add_argument("--out", type=Path, required=True)
    sheet.add_argument("--decisions", type=Path, help="leave out proposals already accepted, edited or rejected")
    rec = sub.add_parser("record", help="save the owner's decisions")
    rec.add_argument("--sheet", type=Path, required=True)
    rec.add_argument("--proposals", type=Path, required=True)
    rec.add_argument("--decisions", type=Path, required=True)
    rec.add_argument("--roster", type=Path, required=True)
    rec.add_argument("--owner", required=True)
    rec.add_argument("--date", default=date.today().isoformat())
    for command in (mine, gen):
        command.add_argument("--rights", type=Path, default=rights_policy.DEFAULT_RIGHTS)
    args = parser.parse_args(argv)

    for path in (getattr(args, "out", None), getattr(args, "decisions", None)):
        if path is not None and "data/raw" in Path(path).resolve().as_posix():
            sys.exit("data/raw is never written by this tool")

    if args.command == "mine-words":
        sources = rights_policy.load_rights(args.rights)
        bible = sqlite3.connect(f"file:{args.bible_db}?mode=ro", uri=True)
        reference = sqlite3.connect(f"file:{args.reference_db}?mode=ro", uri=True)
        try:
            found, report = mine_words(bible, reference, sources, zolai_standard.load(), min_count=args.min_count)
        finally:
            bible.close()
            reference.close()
        write_jsonl(args.out, found)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"wrote {len(found):,} proposals (status ai_suggested) to {args.out}; nothing was changed")
        return 0

    if args.command == "generate":
        items = load_jsonl(args.items)[: max(0, args.limit)]
        terms = json.loads(args.provider_terms.read_text(encoding="utf-8")) if args.provider_terms else None
        try:
            found, report = generate(items, prompt_template=args.prompt.read_text(encoding="utf-8"),
                                     command=shlex.split(args.command), model_name=args.model_name,
                                     model_version=args.model_version, origin=args.origin,
                                     sources=rights_policy.load_rights(args.rights), provider_terms=terms)
        except (PermissionError, ValueError) as error:
            sys.exit(f"nothing was sent: {error}")
        write_jsonl(args.out, found)
        print(json.dumps(report, indent=2))
        print(f"wrote {len(found):,} suggestions (ai_candidate, status ai_suggested) to {args.out}")
        return 0

    if args.command == "sheet":
        proposals = load_jsonl(args.proposals)
        done = {d["proposal_id"] for d in load_jsonl(args.decisions) if d["decision"] != "defer"} if args.decisions else set()
        offered = [p for p in proposals if p["proposal_id"] not in done]
        write_sheet(args.out, offered)
        print(f"wrote {len(offered):,} proposals to {args.out} ({len(proposals) - len(offered):,} already decided)")
        return 0

    roster = corpus_reviews.load_roster(args.roster)
    with args.sheet.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    out, errors = record(rows, load_jsonl(args.proposals), owner=args.owner, roster=roster, decided_on=args.date,
                         recorded_at=now_utc())
    for error in errors:
        print(f"error: {error}")
    if errors:
        print("nothing saved; fix the rows above and run again")
        return 1
    corpus_reviews.append(args.decisions, out)
    counts = Counter(r["decision"] for r in out)
    print(f"saved {len(out)} decisions ({', '.join(f'{k} {counts.get(k, 0)}' for k in DECISIONS)}) to {args.decisions};"
          " nothing in the dictionary was changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
