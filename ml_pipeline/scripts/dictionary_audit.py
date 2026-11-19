#!/usr/bin/env python3
"""Find headword problems in the reference dictionaries for the owner to decide (docs/DICTIONARY_AUDIT.md).

  python3 ml_pipeline/scripts/dictionary_audit.py audit \\
      --db data/processed/reference/reference_dictionaries.sqlite \\
      --decisions ../siamsil-data/reviews/dictionary-headword-decisions.jsonl \\
      --out-dir ../siamsil-data/reviews/dictionary-audit-1
  python3 ml_pipeline/scripts/dictionary_audit.py record \\
      --sheet ../siamsil-data/reviews/dictionary-audit-1/headword-review.csv \\
      --findings ../siamsil-data/reviews/dictionary-audit-1/findings.jsonl \\
      --decisions ../siamsil-data/reviews/dictionary-headword-decisions.jsonl \\
      --roster ../siamsil-data/reviews/roster.csv --owner O01

What `audit` looks for, in this order:

  duplicate_headword  the same English headword and part of speech entered more than once in one source
  zomi_variant        two spellings in one entry that the adopted Standard Form makes the same word
  inflected_form      an English headword that is a regular inflection (-s, -es, -ies, -ed, -ing) of another
                      headword in the same source: "books" beside "book". A candidate only: "building" can be a
                      headword in its own right, so the owner decides
  missing_zomi        a sense with no Zomi
  missing_pos         an entry with no part of speech
  not_standard_form   Zomi that the adopted rules would spell differently, with the standard form beside it

The Zomi checks use only the owner's adopted rules (data/zomi_standard_form/standard.json); this tool knows no Zomi of
its own and suggests no new words. The English checks use regular English inflection only.

Nothing in the dictionary changes. `record` saves the owner's decisions (accept, reject, defer) to an append-only
file, each marked `approval: owner_sole`; only the roster's owner may record them. Accepted findings are applied by
a later step with a preview and rollback. A finding decided before (other than defer) is not offered again while its
content is unchanged. The dictionaries are `needs_review` in data/rights.json: keep every output in the private data
repository.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corpus_reviews  # type: ignore  # noqa: E402
import zolai_standard  # type: ignore  # noqa: E402

CATEGORIES = ("duplicate_headword", "zomi_variant", "inflected_form", "missing_zomi", "missing_pos",
              "not_standard_form")
DECISIONS = ("accept", "reject", "defer")
SHEET_COLUMNS = ["finding_id", "category", "source", "headword", "detail", "proposal", "decision", "notes"]
WORD = re.compile(r"^[a-z]+$")


def finding(category: str, source: str, headword: str, key: str, detail: str, proposal: str,
            entries: list[str], senses: list[str] | None = None) -> dict:
    """One finding. Its id is stable across runs; its digest changes when what it describes changes."""
    ident = "F-" + hashlib.sha1(f"{category}|{source}|{key}".encode("utf-8")).hexdigest()[:12]
    digest = hashlib.sha1(json.dumps([detail, proposal, sorted(entries), sorted(senses or [])],
                                     ensure_ascii=False).encode("utf-8")).hexdigest()
    return {"finding_id": ident, "category": category, "source": source, "headword": headword, "detail": detail,
            "proposal": proposal, "entries": sorted(entries), "senses": sorted(senses or []), "digest": digest}


def base_forms(word: str) -> list[str]:
    """Regular English bases a word could be inflected from, most likely first. Candidates, not a lemmatizer."""
    out: list[str] = []
    if len(word) < 4:
        return out
    if word.endswith("ies"):
        out.append(word[:-3] + "y")
    if word.endswith("es") and word[:-2].endswith(("s", "x", "z", "ch", "sh")):
        out.append(word[:-2])
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        out.append(word[:-1])
    if word.endswith("ied"):
        out.append(word[:-3] + "y")
    if word.endswith("ed"):
        stem = word[:-2]
        out += [stem, stem + "e"]
        if len(stem) > 2 and stem[-1] == stem[-2]:
            out.append(stem[:-1])
    if word.endswith("ing"):
        stem = word[:-3]
        out += [stem, stem + "e"]
        if len(stem) > 2 and stem[-1] == stem[-2]:
            out.append(stem[:-1])
    seen: set[str] = set()
    return [b for b in out if len(b) >= 3 and b != word and not (b in seen or seen.add(b))]


def split_zomi(text: str | None) -> list[str]:
    """The alternatives in a sense's Zomi: ';' separates equivalents in the reference dictionaries."""
    return [part.strip() for part in (text or "").split(";") if part.strip()]


def audit(con: sqlite3.Connection, standard: zolai_standard.Standard, sources: set[str] | None = None) -> list[dict]:
    entries = con.execute(
        "SELECT id, source_id, headword, normalized_headword, part_of_speech FROM entries ORDER BY source_id, "
        "normalized_headword, source_index").fetchall()
    senses: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for sense_id, entry_id, zomi in con.execute("SELECT id, entry_id, zomi FROM senses ORDER BY entry_id, sense_number"):
        senses[entry_id].append((sense_id, zomi or ""))
    found: list[dict] = []
    by_key: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
    headwords: dict[str, dict[str, list[tuple[str, str]]]] = defaultdict(lambda: defaultdict(list))
    for entry_id, source, headword, normalized, pos in entries:
        if sources and source not in sources:
            continue
        pos_key = (pos or "").strip().lower().rstrip(".")
        by_key[(source, normalized, pos_key)].append((entry_id, headword))
        headwords[source][normalized].append((entry_id, pos or ""))
        if not (pos or "").strip():
            found.append(finding("missing_pos", source, headword, entry_id, "no part of speech",
                                 "add the part of speech", [entry_id]))
        entry_senses = senses.get(entry_id, [])
        for sense_id, zomi in entry_senses:
            if not zomi.strip():
                found.append(finding("missing_zomi", source, headword, sense_id, "this sense has no Zomi",
                                     "add the Zomi, or remove the sense", [entry_id], [sense_id]))
        # Spelling variants and standard form, across every Zomi alternative of the entry.
        spellings: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for sense_id, zomi in entry_senses:
            for part in split_zomi(zomi):
                result = zolai_standard.standardize(part, standard)
                spellings[zolai_standard.norm(result.text)][zolai_standard.norm(part)].add(sense_id)
                if result.rules:
                    found.append(finding(
                        "not_standard_form", source, headword, f"{sense_id}|{zolai_standard.norm(part)}",
                        f"'{part}' is not in the adopted standard form ({', '.join(result.rules)})",
                        f"standard form: '{result.text}'", [entry_id], [sense_id]))
        for standard_form, forms in spellings.items():
            if len(forms) > 1:
                written = sorted(forms)
                ids = sorted({s for group in forms.values() for s in group})
                found.append(finding(
                    "zomi_variant", source, headword, f"{entry_id}|{standard_form}",
                    "the same word spelled " + " and ".join(f"'{w}'" for w in written),
                    f"keep one spelling: '{standard_form}' (the adopted standard form)", [entry_id], ids))
    for (source, normalized, pos_key), group in by_key.items():
        if len(group) > 1:
            ids = [entry_id for entry_id, _ in group]
            found.append(finding(
                "duplicate_headword", source, group[0][1], f"{normalized}|{pos_key}",
                f"'{group[0][1]}' ({pos_key or 'no part of speech'}) is entered {len(group)} times",
                "merge into one headword, keeping every sense", ids))
    for source, words in headwords.items():
        for normalized, group in words.items():
            if not WORD.match(normalized):
                continue
            base = next((b for b in base_forms(normalized) if b in words), None)
            if base is None:
                continue
            pos = ", ".join(sorted({p for _, p in group if p})) or "no part of speech"
            base_pos = ", ".join(sorted({p for _, p in words[base] if p})) or "no part of speech"
            found.append(finding(
                "inflected_form", source, normalized, f"{normalized}|{base}",
                f"'{normalized}' ({pos}) looks like an inflected form of '{base}' ({base_pos})",
                f"list '{normalized}' under '{base}' as an inflected form, or keep it as its own headword",
                [e for e, _ in group] + [e for e, _ in words[base]]))
    order = {name: n for n, name in enumerate(CATEGORIES)}
    found.sort(key=lambda f: (order[f["category"]], f["source"], f["headword"].lower(), f["finding_id"]))
    return found


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def settled(decisions: list[dict]) -> set[tuple[str, str]]:
    """(finding id, digest) of findings the owner accepted or rejected; deferred ones come back."""
    latest: dict[tuple[str, str], str] = {}
    for record in decisions:
        latest[(record["finding_id"], record["digest"])] = record["decision"]
    return {key for key, decision in latest.items() if decision != "defer"}


def _private(path: Path):
    return open(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8", newline="")


def write_outputs(out_dir: Path, findings: list[dict]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(out_dir, 0o700)
    with _private(out_dir / "findings.jsonl") as handle:
        for item in findings:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    with _private(out_dir / "headword-review.csv") as handle:
        writer = csv.DictWriter(handle, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        for item in findings:
            writer.writerow({**{k: item[k] for k in SHEET_COLUMNS if k in item}, "decision": "", "notes": ""})
    counts = Counter(item["category"] for item in findings)
    with _private(out_dir / "summary.json") as handle:
        json.dump({"findings": len(findings), "by_category": {c: counts.get(c, 0) for c in CATEGORIES},
                   "note": "findings only: nothing in the dictionary was changed"}, handle, indent=2)
        handle.write("\n")


def record(rows: list[dict], findings: list[dict], *, owner: str, roster: dict[str, str], decided_on: str,
           recorded_at: str) -> tuple[list[dict], list[str]]:
    """Decision records for the rows the owner filled in. Returns (records, errors); any error saves nothing."""
    if roster.get(owner) != corpus_reviews.OWNER:
        return [], [f"{owner} is not the owner in the roster; only the owner decides dictionary findings"]
    by_id = {item["finding_id"]: item for item in findings}
    records, errors = [], []
    for number, row in enumerate(rows, start=2):
        decision = (row.get("decision") or "").strip().lower()
        if not decision:
            continue
        ident = (row.get("finding_id") or "").strip()
        item = by_id.get(ident)
        if decision not in DECISIONS:
            errors.append(f"row {number}: decision must be {', '.join(DECISIONS)}, not {decision!r}")
        elif item is None:
            errors.append(f"row {number}: {ident or '<blank>'} is not in this audit's findings")
        elif (row.get("proposal") or "") != item["proposal"] or (row.get("detail") or "") != item["detail"]:
            errors.append(f"row {number}: the detail or proposal was edited; write changes in notes")
        else:
            records.append({"kind": "headword_decision", "finding_id": ident, "category": item["category"],
                            "source": item["source"], "headword": item["headword"], "decision": decision,
                            "proposal": item["proposal"], "digest": item["digest"], "decided_by": owner,
                            "decided_on": decided_on, "recorded_at": recorded_at,
                            "approval": corpus_reviews.OWNER_SOLE, "notes": (row.get("notes") or "").strip()})
    return records, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("audit", help="find problems and write a decision sheet")
    run.add_argument("--db", type=Path, required=True, help="reference_dictionaries.sqlite")
    run.add_argument("--out-dir", type=Path, required=True)
    run.add_argument("--decisions", type=Path, help="earlier decisions: settled findings are not offered again")
    run.add_argument("--source", action="append", help="only this source id (repeatable)")
    run.add_argument("--standard", type=Path, default=zolai_standard.DEFAULT_STANDARD)
    rec = commands.add_parser("record", help="save the owner's decisions from a filled-in sheet")
    rec.add_argument("--sheet", type=Path, required=True)
    rec.add_argument("--findings", type=Path, required=True)
    rec.add_argument("--decisions", type=Path, required=True)
    rec.add_argument("--roster", type=Path, required=True)
    rec.add_argument("--owner", required=True)
    rec.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args(argv)

    if args.command == "audit":
        for path in (args.db, args.out_dir):
            if "data/raw" in path.resolve().as_posix():
                sys.exit("data/raw is never read or written by this tool")
        con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
        try:
            found = audit(con, zolai_standard.load(args.standard), set(args.source or []) or None)
        finally:
            con.close()
        done = settled(load_jsonl(args.decisions)) if args.decisions else set()
        offered = [f for f in found if (f["finding_id"], f["digest"]) not in done]
        write_outputs(args.out_dir, offered)
        counts = Counter(f["category"] for f in offered)
        for category in CATEGORIES:
            print(f"{category}: {counts.get(category, 0):,}")
        print(f"{len(offered):,} findings to decide ({len(found) - len(offered):,} already decided). Nothing in the "
              "dictionary was changed. Keep these files in the private data repository.")
        return 0

    roster = corpus_reviews.load_roster(args.roster)
    with args.sheet.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    records, errors = record(rows, load_jsonl(args.findings), owner=args.owner, roster=roster,
                             decided_on=args.date, recorded_at=now)
    for error in errors:
        print(f"error: {error}")
    if errors:
        print("nothing saved; fix the rows above and run again")
        return 1
    corpus_reviews.append(args.decisions, records)
    counts = Counter(r["decision"] for r in records)
    print(f"saved {len(records)} decisions by {args.owner} ({', '.join(f'{k} {counts.get(k, 0)}' for k in DECISIONS)}) "
          f"to {args.decisions}; nothing in the dictionary was changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
