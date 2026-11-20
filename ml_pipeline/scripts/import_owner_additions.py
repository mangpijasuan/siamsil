#!/usr/bin/env python3
"""Turn the owner's filled candidate-headwords workbook into a source file for the editorial dictionary.

Input: Siamsil_New_Headwords_To_Translate.xlsx after the owner filled it (sheets Words, Phrases, Forms you have,
Names). Only rows the owner marked to add, with the owner's own Zomi, are used.

Output: one JSON-lines file, written privately (owner-only permissions), that backend/scripts/import_dictionary_sources.py
reads as format "owner_additions_jsonl" once it is listed in data/dictionary_sources.json. Nothing is written when any
row has a problem; nothing here reviews, approves or clears anything. Every sense arrives unreviewed, and the owner
reviews it later in a separate sitting (docs/DICTIONARY.md, "Owner-only review").

  python3 ml_pipeline/scripts/import_owner_additions.py --workbook filled.xlsx --batch 2026-12-a \\
      --out-dir ../siamsil-data/dictionary/sources/owner-additions [--owner-code E01] [--dry-run]
      [--skip-existing earlier-batch.jsonl ...] [--register-config]

What it checks, per row: the decision is a recognised "add" choice; the Zomi is present, clean text and not a copy
of the English; "I change the meaning" has the new meaning; no headword and part of speech is added twice. It
reports (does not fix) Zomi that uses a spelling an adopted SZSF rule would change, rows added with a draft marked
"check source", and rows added with an AI-drafted English meaning.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import dictionary_sources as sources  # noqa: E402

SHEETS = {
    # sheet: (headword column, decision column)
    "Words": ("English word", "Decision"),
    "Phrases": ("English phrase", "Decision"),
    "Forms you have": ("English form", "Your decision"),
    "Names": ("Capitalised word", "Decision"),
}
COLUMNS = {
    "pos": ("Part of speech (AI draft)",),
    "draft": ("English meaning (AI draft)",),
    "note": ("AI note",),
    "own_meaning": ("Your meaning if you change it",),
    "zomi": ("Your Zomi", "Your Zomi spelling or word"),
}
ADD_DRAFT = ("add (draft is fine)", "add")
ADD_OWN = ("add (i change the meaning)",)
ADD_FORM = ("add as own entry",)
NOT_ADDED = ("skip", "later", "discuss", "covered by the base word", "")
POS_FIX = {"phr. v.": "phrasal v."}
CONTROL = re.compile(r"[\u0000-\u0008\u000b-\u001f\u007f  ]")
BATCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,40}$")


def clean(value) -> str:
    return re.sub(r"[ \t]+", " ", unicodedata.normalize("NFC", "" if value is None else str(value))).strip()


def meaning_source(note: str) -> str:
    low = note.lower()
    if low.startswith("wordnet"):
        return "wordnet"
    return "ai_draft"


def read_rows(path: Path) -> tuple[list[dict], list[str]]:
    """Every row of the four sheets as a dict with the fields this tool needs, and any structural problems."""
    import openpyxl

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows: list[dict] = []
    problems: list[str] = []
    try:
        for sheet, (headword_col, decision_col) in SHEETS.items():
            if sheet not in workbook.sheetnames:
                problems.append(f"sheet '{sheet}' is missing")
                continue
            data = list(workbook[sheet].iter_rows(values_only=True))
            if not data:
                continue
            header = [clean(h) for h in data[0]]

            def column(*names):
                for name in names:
                    if name in header:
                        return header.index(name)
                return None

            index = {"headword": column(headword_col), "decision": column(decision_col)}
            for key, names in COLUMNS.items():
                index[key] = column(*names)
            missing = [k for k in ("headword", "decision", "zomi") if index[k] is None]
            if missing:
                problems.append(f"sheet '{sheet}' lacks the columns for: {', '.join(missing)}")
                continue
            for number, values in enumerate(data[1:], start=2):
                def get(key):
                    i = index.get(key)
                    return clean(values[i]) if i is not None and i < len(values) else ""

                rows.append({"sheet": sheet, "row": number, "headword": get("headword"), "decision": get("decision"),
                             "pos": get("pos"), "draft": get("draft"), "note": get("note"),
                             "own_meaning": get("own_meaning"), "zomi": get("zomi")})
    finally:
        workbook.close()
    return rows, problems


def build(rows: list[dict], batch: str, owner_code: str | None, skip: set[tuple[str, str]],
          standard=None) -> tuple[list[dict], list[str], list[str], Counter]:
    """(records, errors, warnings, counts). Records are returned only for rows that are fully valid."""
    records: list[dict] = []
    errors: list[str] = []
    warnings: list[str] = []
    counts: Counter = Counter()
    seen: dict[tuple[str, str], str] = {}
    for row in rows:
        where = f"{row['sheet']} row {row['row']} ({row['headword']})"
        decision = row["decision"].lower()
        if not row["headword"]:
            if decision or row["zomi"]:
                errors.append(f"{where}: no headword")
            continue
        if decision in ADD_DRAFT or decision in ADD_OWN or (row["sheet"] == "Forms you have" and decision in ADD_FORM):
            own = decision in ADD_OWN
        elif decision in NOT_ADDED:
            counts[f"not added ({decision or 'no decision'})"] += 1
            if row["zomi"] and not decision:
                warnings.append(f"{where}: has Zomi but no decision, so it was not added")
            continue
        else:
            errors.append(f"{where}: decision '{row['decision']}' is not one I know")
            continue
        zomi = row["zomi"]
        if not zomi:
            errors.append(f"{where}: marked to add but 'Your Zomi' is empty")
            continue
        if CONTROL.search(zomi):
            errors.append(f"{where}: the Zomi has control or line-break characters")
            continue
        if sources.match_key(zomi) == sources.match_key(row["headword"]):
            errors.append(f"{where}: the Zomi is the same as the English headword")
            continue
        if own:
            definition, source = row["own_meaning"], "owner"
            if not definition:
                errors.append(f"{where}: 'I change the meaning' but 'Your meaning' is empty")
                continue
        else:
            definition = row["draft"]
            source = meaning_source(row["note"])
            if not definition:
                errors.append(f"{where}: no English meaning (add yours, or choose 'I change the meaning')")
                continue
            if row["note"].lower().startswith("check source"):
                warnings.append(f"{where}: added with a draft meaning marked 'check source'")
        pos = POS_FIX.get(row["pos"], row["pos"]) or None
        normalized = sources.normalize_pos(pos) if pos else None
        if pos and not normalized:
            warnings.append(f"{where}: part of speech '{pos}' not recognised; stored without one")
        key = (sources.match_key(row["headword"]), normalized or "")
        if key in skip:
            counts["already in an earlier batch"] += 1
            continue
        if key in seen:
            errors.append(f"{where}: {row['headword']} ({normalized or 'no pos'}) is also added at {seen[key]}")
            continue
        seen[key] = where
        if standard is not None:
            result = standard.apply(zomi) if hasattr(standard, "apply") else None
            if result is not None and result.rules:
                warnings.append(f"{where}: your Zomi uses a spelling that adopted rule(s) {', '.join(result.rules)} would change")
        record_id = "OA-" + hashlib.sha1("|".join(key).encode("utf-8")).hexdigest()[:10]
        record = {"id": record_id, "headword": row["headword"], "part_of_speech": normalized, "definition_en": definition,
                  "zomi": zomi, "meaning_source": source, "sheet": row["sheet"], "row": row["row"], "batch": batch}
        if owner_code:
            record["owner_code"] = owner_code
        if row.get("note") and source == "ai_draft":
            record["note"] = row["note"][:80]
        records.append(record)
        counts[f"added ({source} meaning)"] += 1
    return records, errors, warnings, counts


def dumps(records: list[dict]) -> str:
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records)


def write_private(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"{path} already exists; choose a new --batch name")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)


def existing_keys(files: list[Path]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for file in files:
        for line in file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                keys.add((sources.match_key(row["headword"]), row.get("part_of_speech") or ""))
    return keys


def config_entry(batch: str, file: Path, sha256: str, out_dir_in_repo: str | None) -> dict:
    return {
        "title": f"Owner additions, batch {batch}: English headwords translated by hand by the project owner",
        "role": "reference",
        "version": batch,
        "format": "owner_additions_jsonl",
        "root": "data_repo",
        "path": out_dir_in_repo or f"dictionary/sources/owner-additions/{file.name}",
        "sha256": sha256,
        "rights": "owner_additions",
    }


class _Standard:
    """Wraps the adopted SZSF rules so a row's Zomi can be checked without changing it."""

    def __init__(self) -> None:
        import zolai_standard

        self.module = zolai_standard
        self.rules = zolai_standard.load()

    def apply(self, text: str):
        return self.module.standardize(text, self.rules)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workbook", type=Path, required=True, help="the filled candidate-headwords workbook")
    parser.add_argument("--batch", required=True, help="a new name for this batch, e.g. 2026-12-a")
    parser.add_argument("--out-dir", type=Path, required=True, help="private folder for the output file")
    parser.add_argument("--owner-code", help="the owner's roster code, recorded on each row (not a name)")
    parser.add_argument("--skip-existing", type=Path, action="append", default=[],
                        help="an earlier batch file: its headwords are not added again")
    parser.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    parser.add_argument("--register-config", action="store_true",
                        help="also add the batch to data/dictionary_sources.json (otherwise the entry is only printed)")
    args = parser.parse_args(argv)
    if not BATCH.match(args.batch):
        print("The batch name may use letters, digits, '.', '_' and '-' only.", file=sys.stderr)
        return 2
    try:
        rows, problems = read_rows(args.workbook)
        skip = existing_keys(args.skip_existing)
    except (OSError, ValueError, KeyError) as error:
        print(f"Could not read the inputs: {error}", file=sys.stderr)
        return 2
    try:
        standard = _Standard()
    except Exception:  # the rule check is advice only
        standard = None
    records, errors, warnings, counts = build(rows, args.batch, args.owner_code, skip, standard)
    errors = problems + errors
    for name, number in sorted(counts.items()):
        print(f"{number:7,}  {name}")
    for line in warnings[:40]:
        print(f"warning: {line}")
    if len(warnings) > 40:
        print(f"... and {len(warnings) - 40} more warnings")
    if errors:
        print(f"\nNothing was written: {len(errors)} problem(s):", file=sys.stderr)
        for line in errors[:60]:
            print(f"  {line}", file=sys.stderr)
        if len(errors) > 60:
            print(f"  ... and {len(errors) - 60} more", file=sys.stderr)
        return 1
    if not records:
        print("No rows were marked to add; nothing to write.")
        return 0
    content = dumps(records)
    sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
    target = args.out_dir / f"owner-additions-{args.batch}.jsonl"
    if args.dry_run:
        print(f"\nDry run: would write {len(records):,} senses to {target} (sha256 {sha256})")
        return 0
    try:
        write_private(target, content)
    except FileExistsError as error:
        print(str(error), file=sys.stderr)
        return 1
    entry = config_entry(args.batch, target, sha256, None)
    print(f"\nWrote {len(records):,} senses to {target} (private, sha256 {sha256}).")
    print("No review or approval was recorded: review them later in a separate sitting.")
    source_id = f"owner_additions_{re.sub(r'[^a-z0-9]+', '_', args.batch.lower()).strip('_')}"
    if args.register_config:
        config_path = ROOT / "data" / "dictionary_sources.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if source_id in config["sources"]:
            print(f"{source_id} is already in {config_path}", file=sys.stderr)
            return 1
        config["sources"][source_id] = entry
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Added {source_id} to {config_path}.")
    else:
        print(f'\nAdd this to "sources" in data/dictionary_sources.json (or rerun with --register-config):\n'
              f'"{source_id}": {json.dumps(entry, indent=2, ensure_ascii=False)}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
