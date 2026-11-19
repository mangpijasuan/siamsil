#!/usr/bin/env python3
"""Apply the owner's accepted decisions to the dictionary: plan, preview, apply, roll back (docs/CHANGESETS.md).

The originals are never edited. The reference dictionaries database is rebuilt from siamsil-data at any time;
`build` makes an applied copy of it from the originals plus every changeset the owner applied and has not rolled
back, oldest first. Undoing a change is recording that its changeset is rolled back and building again.

  plan      gather accepted decisions (dictionary_audit.py and proposals.py) into a changeset file
  preview   every change before and after, conflicts, and a random sample to spot-check; apply needs it
  apply     the owner records that a previewed changeset is applied (append-only ledger, owner_sole)
  rollback  the owner records that an applied changeset is undone
  build     the applied copy: originals + active changesets, each change checked against what it expects to find
  status    progress across corpus review, dictionary findings, proposals and changesets

What a change may touch. Deterministic changes (the owner's adopted Standard Form, merging duplicate entries,
marking inflected forms) and text the owner wrote ("edit") change the dictionary itself. A model's suggestion that
the owner accepted as it stands is stored beside the dictionary, in `sense_annotations`, never in the dictionary's
own text, so the training export (which reads entries, senses and examples) cannot take in model-written text.
Every applied change is listed in `applied_changes`, with its changeset, decision, origin and before and after.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import shutil
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corpus_reviews  # type: ignore  # noqa: E402
import zolai_standard  # type: ignore  # noqa: E402

OPS = ("merge_entries", "standardize_zomi", "mark_inflected", "add_zomi_headword", "set_definition", "annotate_sense")
EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS applied_changes (
    changeset_id TEXT NOT NULL, position INTEGER NOT NULL, op TEXT NOT NULL, decision TEXT NOT NULL,
    origin TEXT NOT NULL, provider_derived INTEGER NOT NULL, target TEXT NOT NULL, before TEXT, after TEXT
);
CREATE TABLE IF NOT EXISTS inflected_forms (entry_id TEXT NOT NULL, base_headword TEXT NOT NULL, changeset_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS zomi_headwords (
    zomi TEXT NOT NULL, meaning_en TEXT, variant_of TEXT, evidence TEXT NOT NULL, origin TEXT NOT NULL,
    provider_derived INTEGER NOT NULL, changeset_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sense_annotations (
    sense_id TEXT NOT NULL, kind TEXT NOT NULL, value TEXT NOT NULL, origin TEXT NOT NULL,
    provider_derived INTEGER NOT NULL, changeset_id TEXT NOT NULL
);
"""


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_jsonl(path: Path | None) -> list[dict]:
    if path is None or not Path(path).exists():
        return []
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def latest(records: list[dict], key: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for record in records:
        out[record[key]] = record
    return out


# --- plan ------------------------------------------------------------------------------------------------------

def plan(findings: list[dict], headword_decisions: list[dict], proposals: list[dict], proposal_decisions: list[dict],
         already_applied: set[str] = frozenset()) -> dict:
    """A changeset from accepted decisions not yet in an applied changeset. Decisions that need a value the owner
    has not given (a missing part of speech, missing Zomi) are listed under needs_input, not guessed."""
    by_finding = {f["finding_id"]: f for f in findings}
    by_proposal = {p["proposal_id"]: p for p in proposals}
    ops: list[dict] = []
    needs_input: list[dict] = []
    for ident, decision in sorted(latest(headword_decisions, "finding_id").items()):
        ref = f"headword:{ident}:{decision['recorded_at']}"
        if decision["decision"] != "accept" or ref in already_applied:
            continue
        item = by_finding.get(ident)
        if item is None or item["digest"] != decision["digest"]:
            needs_input.append({"decision": ref, "reason": "the finding is not in the findings given, or has changed"})
            continue
        base = {"decision": ref, "origin": "deterministic", "provider_derived": False}
        category = item["category"]
        if category == "duplicate_headword":
            ops.append({**base, "op": "merge_entries", "keep": item["entries"][0], "remove": item["entries"][1:]})
        elif category in ("zomi_variant", "not_standard_form"):
            for sense in item["senses"]:
                ops.append({**base, "op": "standardize_zomi", "sense": sense})
        elif category == "inflected_form":
            # The finding lists the form's entries and the base word's together: name the form by its headword.
            base_word = item["detail"].split("'")[3]
            ops.append({**base, "op": "mark_inflected", "source": item["source"], "headword": item["headword"],
                        "base_headword": base_word})
        else:
            needs_input.append({"decision": ref, "reason": f"{category} needs the value you want; "
                                                          "fix it in the dictionary review sheet"})
    for ident, decision in sorted(latest(proposal_decisions, "proposal_id").items()):
        ref = f"proposal:{ident}:{decision['recorded_at']}"
        if decision["decision"] not in ("accept", "edit") or ref in already_applied:
            continue
        p = by_proposal.get(ident)
        if p is None:
            needs_input.append({"decision": ref, "reason": "the proposal is not in the proposals given"})
            continue
        owner_text = decision.get("edited_text", "") if decision["decision"] == "edit" else ""
        base = {"decision": ref, "origin": p["origin"], "provider_derived": p["origin"] == "provider_assisted"}
        target = p.get("target") or {}
        if p["kind"] in ("headword_candidate", "alternative_form"):
            ops.append({**base, "op": "add_zomi_headword", "zomi": p["payload"].get("zomi", ""),
                        "meaning_en": owner_text, "variant_of": p["payload"].get("standard_form", ""),
                        "evidence": p.get("evidence", [])})
        elif target.get("type") != "sense" or not target.get("id"):
            needs_input.append({"decision": ref, "reason": f"{p['kind']} has no sense to attach to"})
        elif p["kind"] in ("definition", "english_equivalent") and (owner_text or p["origin"] == "deterministic"):
            # The owner's own words (or a rule's output) may become the dictionary's text.
            text = owner_text or p["payload"].get("english", "")
            ops.append({**base, "op": "set_definition", "sense": target["id"], "text": text})
        else:
            # A model's suggestion accepted as it stands: kept beside the dictionary, not in it.
            value = owner_text or "; ".join(f"{k}: {v}" for k, v in p["payload"].items())
            ops.append({**base, "op": "annotate_sense", "sense": target["id"], "kind": p["kind"], "value": value})
    body = json.dumps(ops, sort_keys=True, ensure_ascii=False)
    return {"format": "siamsil-changeset", "version": 1,
            "changeset_id": "C-" + hashlib.sha1(body.encode("utf-8")).hexdigest()[:12], "created_at": now_utc(),
            "ops": ops, "needs_input": needs_input}


# --- applying one change to a database -------------------------------------------------------------------------

def _dedupe_alternatives(text: str) -> str:
    seen, parts = set(), []
    for part in (p.strip() for p in text.split(";")):
        key = zolai_standard.norm(part)
        if part and key not in seen:
            seen.add(key)
            parts.append(part)
    return "; ".join(parts)


def apply_op(con: sqlite3.Connection, op: dict, standard: zolai_standard.Standard, changeset_id: str,
             position: int, dry_run: bool = False) -> tuple[str, str, str, str]:
    """Apply one change. Returns (status, target, before, after); status is applied, unchanged or conflict.
    A change applies only where the database still holds what the change expects."""
    kind = op["op"]
    if kind == "merge_entries":
        found = {row[0] for row in con.execute(
            f"SELECT id FROM entries WHERE id IN ({','.join('?' * (1 + len(op['remove'])))})", [op["keep"], *op["remove"]])}
        target = op["keep"]
        if op["keep"] not in found:
            return "conflict", target, "", "the entry to keep is gone"
        remove = [e for e in op["remove"] if e in found]
        if not remove:
            return "unchanged", target, "", ""
        before, after = ", ".join([op["keep"], *remove]), op["keep"]
        if not dry_run:
            marks = ",".join("?" * len(remove))
            con.execute(f"UPDATE senses SET entry_id = ? WHERE entry_id IN ({marks})", [op["keep"], *remove])
            con.execute(f"DELETE FROM entries WHERE id IN ({marks})", remove)
        return "applied", target, before, after
    if kind == "standardize_zomi":
        row = con.execute("SELECT zomi FROM senses WHERE id = ?", (op["sense"],)).fetchone()
        if row is None:
            return "conflict", op["sense"], "", "the sense is gone"
        before = row[0] or ""
        after = _dedupe_alternatives(zolai_standard.standardize(before, standard).text)
        if after == before:
            return "unchanged", op["sense"], before, after
        if not dry_run:
            con.execute("UPDATE senses SET zomi = ? WHERE id = ?", (after, op["sense"]))
        return "applied", op["sense"], before, after
    if kind == "mark_inflected":
        present = [row[0] for row in con.execute(
            "SELECT id FROM entries WHERE source_id = ? AND normalized_headword = ? ORDER BY id",
            (op["source"], op["headword"]))]
        if not present:
            return "conflict", op["headword"], "", "the headword is gone"
        if not dry_run:
            con.executemany("INSERT INTO inflected_forms VALUES (?, ?, ?)",
                            [(e, op["base_headword"], changeset_id) for e in present])
        return "applied", ",".join(present), "", f"inflected form of '{op['base_headword']}'"
    if kind == "add_zomi_headword":
        if not op["zomi"]:
            return "conflict", "", "", "no Zomi form"
        exists = con.execute("SELECT 1 FROM zomi_headwords WHERE zomi = ?", (op["zomi"],)).fetchone()
        if exists:
            return "unchanged", op["zomi"], "", ""
        if not dry_run:
            con.execute("INSERT INTO zomi_headwords VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (op["zomi"], op.get("meaning_en") or None, op.get("variant_of") or None,
                         json.dumps(op.get("evidence", []), ensure_ascii=False), op["origin"],
                         int(op["provider_derived"]), changeset_id))
        return "applied", op["zomi"], "", op.get("meaning_en") or "(meaning to add)"
    if kind == "set_definition":
        row = con.execute("SELECT definition_en FROM senses WHERE id = ?", (op["sense"],)).fetchone()
        if row is None:
            return "conflict", op["sense"], "", "the sense is gone"
        if (row[0] or "") == op["text"]:
            return "unchanged", op["sense"], row[0] or "", op["text"]
        if not dry_run:
            con.execute("UPDATE senses SET definition_en = ? WHERE id = ?", (op["text"], op["sense"]))
        return "applied", op["sense"], row[0] or "", op["text"]
    if kind == "annotate_sense":
        if con.execute("SELECT 1 FROM senses WHERE id = ?", (op["sense"],)).fetchone() is None:
            return "conflict", op["sense"], "", "the sense is gone"
        if not dry_run:
            con.execute("INSERT INTO sense_annotations VALUES (?, ?, ?, ?, ?, ?)",
                        (op["sense"], op["kind"], op["value"], op["origin"], int(op["provider_derived"]), changeset_id))
        return "applied", op["sense"], "", f"{op['kind']}: {op['value']}"
    raise ValueError(f"unknown change {kind!r}")


def run_changeset(con: sqlite3.Connection, changeset: dict, standard: zolai_standard.Standard,
                  dry_run: bool = False) -> list[dict]:
    con.executescript(EXTRA_SCHEMA)
    results = []
    for position, op in enumerate(changeset["ops"]):
        status, target, before, after = apply_op(con, op, standard, changeset["changeset_id"], position, dry_run)
        results.append({"position": position, "op": op["op"], "decision": op["decision"], "status": status,
                        "target": target, "before": before, "after": after, "origin": op["origin"],
                        "provider_derived": op["provider_derived"]})
        if status == "applied" and not dry_run:
            con.execute("INSERT INTO applied_changes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (changeset["changeset_id"], position, op["op"], op["decision"], op["origin"],
                         int(op["provider_derived"]), target, before, after))
    return results


# --- ledger ----------------------------------------------------------------------------------------------------

def active_changesets(ledger: list[dict]) -> list[str]:
    """Changeset ids applied and not rolled back, in the order they were first applied."""
    order: list[str] = []
    state: dict[str, str] = {}
    for entry in ledger:
        if entry["kind"] == "applied" and entry["changeset_id"] not in order:
            order.append(entry["changeset_id"])
        state[entry["changeset_id"]] = entry["kind"]
    return [c for c in order if state.get(c) == "applied"]


def ledger_entry(kind: str, changeset: dict, sha256: str, owner: str, roster: dict[str, str]) -> dict:
    if roster.get(owner) != corpus_reviews.OWNER:
        raise PermissionError(f"{owner} is not the owner in the roster; only the owner applies or rolls back changes")
    return {"kind": kind, "changeset_id": changeset["changeset_id"], "changeset_sha256": sha256,
            "changes": len(changeset["ops"]), "decided_by": owner, "recorded_at": now_utc(),
            "approval": corpus_reviews.OWNER_SOLE}


def build(base_db: Path, out_db: Path, ledger: list[dict], changesets_dir: Path,
          standard: zolai_standard.Standard) -> Counter:
    """The applied copy: the base database plus every active changeset, oldest first."""
    if out_db.resolve() == base_db.resolve():
        raise ValueError("the applied copy must not overwrite the base database")
    tmp = out_db.with_suffix(".building")
    shutil.copyfile(base_db, tmp)
    counts: Counter = Counter()
    con = sqlite3.connect(tmp)
    try:
        con.executescript(EXTRA_SCHEMA)
        for changeset_id in active_changesets(ledger):
            path = changesets_dir / f"{changeset_id}.json"
            changeset = json.loads(path.read_text(encoding="utf-8"))
            for result in run_changeset(con, changeset, standard):
                counts[result["status"]] += 1
            counts["changesets"] += 1
        con.commit()
    finally:
        con.close()
    os.replace(tmp, out_db)
    return counts


# --- status ----------------------------------------------------------------------------------------------------

def status(*, corpus_reviews_path: Path | None = None, corpus_revisions_path: Path | None = None,
           findings_path: Path | None = None, headword_decisions_path: Path | None = None,
           proposals_path: Path | None = None, proposal_decisions_path: Path | None = None,
           ledger_path: Path | None = None) -> dict:
    """One summary of where the review work stands. Every number is counted from the files given."""
    report: dict = {}
    if corpus_reviews_path and Path(corpus_reviews_path).exists():
        import corpus_revisions  # type: ignore

        decisions = corpus_reviews.decide(corpus_reviews.load(Path(corpus_reviews_path)))
        revisions = corpus_revisions.load(Path(corpus_revisions_path)) if corpus_revisions_path else []
        report["corpus_pairs_reviewed"] = dict(sorted(Counter(
            corpus_revisions.linguistic_statuses(decisions, revisions).values()).items()))
    if findings_path:
        findings = load_jsonl(findings_path)
        decided = latest(load_jsonl(headword_decisions_path), "finding_id")
        report["dictionary_findings"] = {
            "total": len(findings),
            **dict(sorted(Counter(decided[f["finding_id"]]["decision"] if f["finding_id"] in decided else "open"
                                  for f in findings).items()))}
    if proposals_path:
        proposals = load_jsonl(proposals_path)
        decided = latest(load_jsonl(proposal_decisions_path), "proposal_id")
        report["proposals"] = {
            "total": len(proposals),
            **dict(sorted(Counter(decided[p["proposal_id"]]["decision"] if p["proposal_id"] in decided else "open"
                                  for p in proposals).items()))}
    if ledger_path:
        ledger = load_jsonl(ledger_path)
        active = active_changesets(ledger)
        report["changesets"] = {"applied": len(active),
                                "rolled_back": len({e["changeset_id"] for e in ledger} - set(active)),
                                "changes_in_applied": sum(e["changes"] for e in ledger if e["kind"] == "applied"
                                                          and e["changeset_id"] in active)}
    return report


# --- command line ----------------------------------------------------------------------------------------------

def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as handle:
        handle.write(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--findings", type=Path, action="append", default=[])
    p.add_argument("--headword-decisions", type=Path)
    p.add_argument("--proposals", type=Path, action="append", default=[])
    p.add_argument("--proposal-decisions", type=Path)
    p.add_argument("--changesets-dir", type=Path, required=True)
    p.add_argument("--ledger", type=Path, required=True)
    v = sub.add_parser("preview")
    v.add_argument("--changeset", type=Path, required=True)
    v.add_argument("--base-db", type=Path, required=True)
    v.add_argument("--sample", type=int, default=20)
    v.add_argument("--seed", type=int, default=20261119)
    for name in ("apply", "rollback"):
        a = sub.add_parser(name)
        a.add_argument("--changeset", type=Path, required=True)
        a.add_argument("--ledger", type=Path, required=True)
        a.add_argument("--roster", type=Path, required=True)
        a.add_argument("--owner", required=True)
    b = sub.add_parser("build")
    b.add_argument("--base-db", type=Path, required=True)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--ledger", type=Path, required=True)
    b.add_argument("--changesets-dir", type=Path, required=True)
    s = sub.add_parser("status")
    for flag in ("corpus-reviews", "corpus-revisions", "findings", "headword-decisions", "proposals",
                 "proposal-decisions", "ledger"):
        s.add_argument(f"--{flag}", type=Path)
    s.add_argument("--out", type=Path, help="also write the summary as JSON")
    args = parser.parse_args(argv)

    for path in [getattr(args, n, None) for n in ("out", "changesets_dir", "ledger", "changeset")]:
        if path is not None and "data/raw" in Path(path).resolve().as_posix():
            sys.exit("data/raw is never written by this tool")
    standard = zolai_standard.load()

    if args.command == "plan":
        applied_refs: set[str] = set()
        for changeset_id in active_changesets(load_jsonl(args.ledger)):
            done = json.loads((args.changesets_dir / f"{changeset_id}.json").read_text(encoding="utf-8"))
            applied_refs |= {op["decision"] for op in done["ops"]}
        changeset = plan([f for path in args.findings for f in load_jsonl(path)], load_jsonl(args.headword_decisions),
                         [x for path in args.proposals for x in load_jsonl(path)], load_jsonl(args.proposal_decisions),
                         applied_refs)
        if not changeset["ops"]:
            print(f"nothing to apply ({len(changeset['needs_input'])} decisions need your input)")
            return 0
        path = args.changesets_dir / f"{changeset['changeset_id']}.json"
        _write_private(path, json.dumps(changeset, indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {path}: {len(changeset['ops'])} changes, {len(changeset['needs_input'])} need your input. "
              "Nothing is applied: preview it next.")
        return 0

    if args.command == "preview":
        changeset = json.loads(args.changeset.read_text(encoding="utf-8"))
        tmp = args.changeset.with_suffix(".preview.sqlite")
        shutil.copyfile(args.base_db, tmp)
        con = sqlite3.connect(tmp)
        try:
            results = run_changeset(con, changeset, standard, dry_run=False)  # on a throwaway copy
        finally:
            con.close()
            tmp.unlink()
        counts = Counter(r["status"] for r in results)
        rng = random.Random(args.seed)
        applied = [r for r in results if r["status"] == "applied"]
        sample = rng.sample(applied, min(args.sample, len(applied)))
        csv_path = args.changeset.with_suffix(".preview.csv")
        sampled = {r["position"] for r in sample}
        with open(os.open(csv_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8",
                  newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["position", "op", "status", "target", "before", "after",
                                                        "origin", "provider_derived", "decision", "in_sample"])
            writer.writeheader()
            for r in results:
                writer.writerow({**{k: r[k] for k in writer.fieldnames if k in r},
                                 "in_sample": "yes" if r["position"] in sampled else ""})
        receipt = {"changeset_id": changeset["changeset_id"], "changeset_sha256": file_sha256(args.changeset),
                   "previewed_at": now_utc(), "counts": dict(counts), "sample_seed": args.seed,
                   "sample_positions": sorted(sampled)}
        _write_private(args.changeset.with_suffix(".preview.json"), json.dumps(receipt, indent=2) + "\n")
        print(f"{changeset['changeset_id']}: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
        for r in sample:
            print(f"  [{r['op']}] {r['target']}: {r['before']!r} -> {r['after']!r}")
        print(f"all changes, before and after: {csv_path}. Spot-check the sample; if it is right, apply.")
        return 0

    if args.command in ("apply", "rollback"):
        changeset = json.loads(args.changeset.read_text(encoding="utf-8"))
        sha = file_sha256(args.changeset)
        ledger = load_jsonl(args.ledger)
        active = active_changesets(ledger)
        if args.command == "apply":
            receipt_path = args.changeset.with_suffix(".preview.json")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {}
            if receipt.get("changeset_sha256") != sha:
                sys.exit("preview this changeset first (or again: it changed since the preview)")
            if changeset["changeset_id"] in active:
                sys.exit(f"{changeset['changeset_id']} is already applied")
            kind = "applied"
        else:
            if changeset["changeset_id"] not in active:
                sys.exit(f"{changeset['changeset_id']} is not applied, so there is nothing to roll back")
            kind = "rolled_back"
        try:
            entry = ledger_entry(kind, changeset, sha, args.owner, corpus_reviews.load_roster(args.roster))
        except PermissionError as error:
            sys.exit(str(error))
        corpus_reviews.append(args.ledger, [entry])
        print(f"{changeset['changeset_id']} {kind.replace('_', ' ')} by {args.owner}. Run build to make the applied "
              "copy; the originals are unchanged.")
        return 0

    if args.command == "build":
        counts = build(args.base_db, args.out, load_jsonl(args.ledger), args.changesets_dir, standard)
        print(f"built {args.out}: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
        if counts.get("conflict"):
            print("some changes found the dictionary changed since they were planned and were skipped; "
                  "see applied_changes and plan again")
        return 0

    report = status(corpus_reviews_path=args.corpus_reviews, corpus_revisions_path=args.corpus_revisions,
                    findings_path=args.findings, headword_decisions_path=args.headword_decisions,
                    proposals_path=args.proposals, proposal_decisions_path=args.proposal_decisions,
                    ledger_path=args.ledger)
    for section, values in report.items():
        print(section.replace("_", " "))
        for key, value in values.items():
            print(f"  {key:<22} {value:>8,}")
    if args.out:
        _write_private(args.out, json.dumps(report, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
