#!/usr/bin/env python3
"""Move Siamsil's Excel work sheets in and out of the pipeline formats.

Human evaluation set (docs/EVALUATION_SET.md), English -> Zomi or Zomi -> English:
  testset-sheet SOURCES.csv --out SHEET.xlsx
      Make the translator's "Translate" sheet from a sources list (columns id,
      domain, and english or zomi; the column sets the direction), with instructions.
  testset-import SHEET.xlsx --translator T01 --origin TEXT --out DRAFT.jsonl
      Read the translator's "Translate" sheet. Translated rows become draft
      items (review_outcome "pending"); blank rows are counted and skipped.
  review-sheet DRAFT.jsonl --out REVIEW.xlsx
      Make the second reader's sheet: accept each translation or correct it.
  review-merge DRAFT.jsonl REVIEW.xlsx --reviewer R01 --out SET.jsonl
      Combine both into the evaluation set and validate it. Rows the reviewer
      has not decided stay out of the set and are listed.

Corpus spot-check (docs/GENERATOR_REVIEW.md):
  ratings-sheet review.csv --out SHEET.xlsx
      Make a reviewer's "Rate" sheet from review.csv, with 0-2 dropdowns.
  ratings-import SHEET.xlsx --out review.csv
      Read the "Rate" sheet into review.csv for `review_sample.py summarize` and `record`.

Contributor IDs (T01, R01) map to names in a private roster, never in these files.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from eval_set import DOMAINS, validate_items
from review_sample import REVIEW_COLUMNS

# direction -> (source language, target language), as the sheets name them.
LANGUAGES = {"en-zomi": ("English", "Zomi"), "zomi-en": ("Zomi", "English")}
DECISIONS = ("Accept", "Correct")


def sheet_direction(rows: list[dict[str, str]]) -> str:
    """A Translate or Review sheet's direction, from its translation column."""
    columns = set(rows[0]) if rows else set()
    for direction, (_, target) in LANGUAGES.items():
        if f"{target} translation" in columns:
            return direction
    sys.exit("the sheet has neither a 'Zomi translation' nor an 'English translation' column")


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return " ".join(str(value).split())


def append_text(sheet, values: list) -> None:
    """Append a row whose text is never run as a formula. openpyxl stores a string
    starting with '=' as a formula, which Excel would evaluate when the sheet is
    opened; sentence text and machine-made Zomi must stay plain text."""
    sheet.append(values)
    for cell in sheet[sheet.max_row]:
        if isinstance(cell.value, str) and cell.value.startswith("="):
            cell.data_type = "s"


def read_sheet(path: Path, sheet: str) -> list[dict[str, str]]:
    """Rows of a sheet as dicts keyed by its header row."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    if sheet not in wb.sheetnames:
        sys.exit(f"{path} has no sheet named '{sheet}' (found: {', '.join(wb.sheetnames)})")
    rows = list(wb[sheet].iter_rows(values_only=True))
    wb.close()
    if not rows:
        return []
    header = [_cell(h) for h in rows[0]]
    return [dict(zip(header, (_cell(v) for v in row))) for row in rows[1:] if any(v is not None for v in row)]


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def cmd_testset_sheet(args: argparse.Namespace) -> int:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    from eval_set import read_sources

    items, errors = read_sources(args.sources)
    if errors:
        for error in errors[:20]:
            print(f"error: {error}")
        sys.exit(f"{args.sources} is not a valid sources list")
    direction = items[0]["direction"] if items else "en-zomi"
    source, target = LANGUAGES[direction]
    wb = Workbook()
    intro = wb.active
    intro.title = "Instructions"
    intro.column_dimensions["A"].width = 110
    if direction == "en-zomi":
        guidance = (
            "For every row, write the Zomi you would naturally use, in the agreed spelling standard.",
            "• Translate the meaning, not word by word. Keep names, numbers and dates as in the English.",
            "• Do not use Google Translate, ChatGPT, Gemini or any other machine translation, and do not copy from the Bible.",
            "• If a sentence is unclear or does not fit Zomi life, write why in Notes and leave the translation blank.",
        )
    else:
        guidance = (
            "For every row, write the English a fluent speaker would naturally use for what the Zomi says.",
            "• Translate the meaning, not word by word. Keep names, numbers and dates as in the Zomi.",
            "• For a saying or simile, give its meaning in plain English; you may add the literal sense in Notes.",
            "• Do not use Google Translate, ChatGPT, Gemini or any other machine translation, and do not copy from the Bible.",
            "• If the Zomi is unclear or looks misspelled, write why in Notes and leave the translation blank.",
        )
    for line in (
        f"Siamsil test set: translate {source} into {target}",
        "",
        *guidance,
        f"• Do not change the ID, Topic or {source} columns.",
        "Keep this file private. Test sentences must never be used for training or shared publicly.",
    ):
        intro.append([line])
    intro["A1"].font = Font(bold=True, size=14, color="1B2A4A")

    sheet = wb.create_sheet("Translate")
    header = ["ID", "Topic", source, f"{target} translation", "Notes"]
    widths = [14, 14, 60, 60, 35]
    sheet.append(header)
    for index, width in enumerate(widths, 1):
        cell = sheet.cell(1, index)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1B2A4A")
        sheet.column_dimensions[cell.column_letter].width = width
    sheet.freeze_panes = "A2"
    for item in items:
        append_text(sheet, [item["id"], item["domain"], item["source_text"], "", ""])
        for col in (3, 4, 5):
            sheet.cell(sheet.max_row, col).alignment = Alignment(wrap_text=True, vertical="top")
        for col in (4, 5):
            sheet.cell(sheet.max_row, col).fill = PatternFill("solid", fgColor="F8F6F0")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(args.out)
    print(f"wrote translation sheet for {len(items)} sentences to {args.out}")
    return 0


def cmd_testset_import(args: argparse.Namespace) -> int:
    rows = read_sheet(args.sheet, "Translate")
    direction = sheet_direction(rows) if rows else "en-zomi"
    source, target = LANGUAGES[direction]
    items, blank, bad_topic = [], 0, []
    for row in rows:
        translation = row.get(f"{target} translation", "")
        if not translation:
            blank += 1
            continue
        topic = row.get("Topic", "")
        if topic not in DOMAINS:
            bad_topic.append(row.get("ID", "?"))
        items.append({
            "id": row["ID"],
            "direction": direction,
            "domain": topic,
            "source_text": row[source],
            "references": [translation],
            "source_origin": args.origin,
            "translator": args.translator,
            "reviewer": "",
            "adjudicator": None,
            "review_outcome": "pending",
            "notes": row.get("Notes", ""),
        })
    if bad_topic:
        sys.exit(f"unknown topic in rows: {', '.join(bad_topic[:10])}; topics must be one of {', '.join(DOMAINS)}")
    write_jsonl(args.out, items)
    print(f"{len(items)} translated, {blank} not yet translated; wrote draft {args.out}")
    return 0


def cmd_review_sheet(args: argparse.Namespace) -> int:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    items = read_jsonl(args.draft)
    direction = items[0]["direction"] if items else "en-zomi"
    source, target = LANGUAGES[direction]
    wb = Workbook()
    intro = wb.active
    intro.title = "Instructions"
    intro.column_dimensions["A"].width = 110
    for line in (
        f"Siamsil test set: check each {target} translation",
        "",
        f"For every row, read the {source} and the {target} translation.",
        f"• Decision = Accept if the {target} is correct, natural, and says the same as the {source}.",
        f"• Decision = Correct if anything should change; write your full corrected {target} in 'Corrected {target}'.",
        "• Do not use Google Translate, ChatGPT, Gemini, or other machine translation.",
        "• Leave Decision blank if you are unsure; that row stays out of the test set for now.",
        "Keep this file private. Test sentences must never be used for training or shared publicly.",
    ):
        intro.append([line])
    intro["A1"].font = Font(bold=True, size=14, color="1B2A4A")

    sheet = wb.create_sheet("Review")
    header = ["ID", "Topic", source, f"{target} translation", "Decision", f"Corrected {target}", "Notes"]
    widths = [14, 14, 55, 55, 12, 55, 35]
    sheet.append(header)
    for index, width in enumerate(widths, 1):
        cell = sheet.cell(1, index)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1B2A4A")
        sheet.column_dimensions[cell.column_letter].width = width
    sheet.freeze_panes = "A2"
    for item in items:
        append_text(sheet, [item["id"], item["domain"], item["source_text"], item["references"][0], None, "", ""])
        for col in (3, 4, 6, 7):
            sheet.cell(sheet.max_row, col).alignment = Alignment(wrap_text=True, vertical="top")
        for col in (5, 6):
            sheet.cell(sheet.max_row, col).fill = PatternFill("solid", fgColor="F8F6F0")
    choice = DataValidation(type="list", formula1='"' + ",".join(DECISIONS) + '"', allow_blank=True)
    sheet.add_data_validation(choice)
    if items:
        choice.add(f"E2:E{sheet.max_row}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(args.out)
    print(f"wrote review sheet for {len(items)} items to {args.out}")
    return 0


def cmd_review_merge(args: argparse.Namespace) -> int:
    drafts = {item["id"]: item for item in read_jsonl(args.draft)}
    decisions = {row["ID"]: row for row in read_sheet(args.review, "Review") if row.get("ID")}
    items, undecided, problems = [], [], []
    for item_id, item in drafts.items():
        row = decisions.get(item_id, {})
        decision = row.get("Decision", "")
        if not decision:
            undecided.append(item_id)
            continue
        merged = {**item, "reviewer": args.reviewer}
        if decision == "Accept":
            merged["review_outcome"] = "accepted"
        elif decision == "Correct":
            target = LANGUAGES.get(item.get("direction"), LANGUAGES["en-zomi"])[1]
            corrected = row.get(f"Corrected {target}", "")
            if not corrected:
                problems.append(f"{item_id}: 'Correct' needs the corrected {target}")
                continue
            merged["review_outcome"] = "corrected"
            merged["references"] = [corrected]
        else:
            problems.append(f"{item_id}: decision must be Accept or Correct, not '{decision}'")
            continue
        if row.get("Notes"):
            merged["notes"] = "; ".join(filter(None, [item.get("notes", ""), f"reviewer: {row['Notes']}"]))
        items.append(merged)
    if problems:
        for problem in problems[:20]:
            print(f"error: {problem}")
        sys.exit(f"{len(problems)} rows need fixing in {args.review}")
    numbered = [{**item, "_line": i} for i, item in enumerate(items, 1)]
    errors, warnings = validate_items(numbered)
    if errors:
        for error in errors[:20]:
            print(f"error: {error}")
        sys.exit("the merged set is not valid; nothing written")
    write_jsonl(args.out, items)
    accepted = sum(1 for item in items if item["review_outcome"] == "accepted")
    print(f"{len(items)} items ({accepted} accepted, {len(items) - accepted} corrected); "
          f"{len(undecided)} undecided left out; wrote {args.out}")
    for warning in warnings:
        print(f"warning: {warning}")
    return 0


RATE_HEADER = ["ID", "English", "Zomi (machine-made)", "Meaning (0-2)", "Fluency (0-2)", "Correction (optional)", "Notes"]


def cmd_ratings_sheet(args: argparse.Namespace) -> int:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    with args.review.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    wb = Workbook()
    intro = wb.active
    intro.title = "Instructions"
    intro.column_dimensions["A"].width = 110
    for line in (
        "Siamsil corpus review: rate machine-made Zomi",
        "",
        "Each row has an English sentence and a Zomi sentence made by a machine. Rate the Zomi; do not edit it.",
        "Meaning: does the Zomi say what the English says?  0 wrong or missing · 1 partly right · 2 fully right",
        "Fluency: is it Zomi a speaker would write?  0 not readable as Zomi · 1 understandable, with errors · 2 natural",
        "Correction (optional): if you know the right Zomi, write it here. It is kept for the lead editor and never",
        "replaces the original automatically.",
        "Leave a row blank if you are unsure. Do not use Google Translate, ChatGPT, Gemini or other machine translation.",
        "Keep this file private.",
    ):
        intro.append([line])
    intro["A1"].font = Font(bold=True, size=14, color="1B2A4A")

    sheet = wb.create_sheet("Rate")
    widths = [10, 50, 50, 14, 14, 45, 30]
    sheet.append(RATE_HEADER)
    for index, width in enumerate(widths, 1):
        cell = sheet.cell(1, index)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1B2A4A")
        sheet.column_dimensions[cell.column_letter].width = width
    sheet.freeze_panes = "A2"
    for row in rows:
        append_text(sheet, [row["sample_id"], row["english"], row["zomi"], None, None, "", ""])
        for col in (2, 3, 6, 7):
            sheet.cell(sheet.max_row, col).alignment = Alignment(wrap_text=True, vertical="top")
        for col in (4, 5, 6, 7):
            sheet.cell(sheet.max_row, col).fill = PatternFill("solid", fgColor="F8F6F0")
    score = DataValidation(type="list", formula1='"0,1,2"', allow_blank=True)
    sheet.add_data_validation(score)
    if rows:
        score.add(f"D2:E{sheet.max_row}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(args.out)
    print(f"wrote rating sheet for {len(rows)} pairs to {args.out}")
    return 0


def cmd_ratings_import(args: argparse.Namespace) -> int:
    rows = read_sheet(args.sheet, "Rate")
    out_rows, rated = [], 0
    for row in rows:
        meaning, fluency = row.get("Meaning (0-2)", ""), row.get("Fluency (0-2)", "")
        rated += bool(meaning or fluency)
        out_rows.append({
            "sample_id": row.get("ID", ""),
            "english": row.get("English", ""),
            "zomi": row.get("Zomi (machine-made)", ""),
            "meaning": meaning,
            "fluency": fluency,
            "correction": row.get("Correction (optional)", ""),
            "notes": row.get("Notes", ""),
        })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"{rated} of {len(out_rows)} rows rated; wrote {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("testset-sheet")
    p.add_argument("sources", type=Path, help="CSV with columns id, domain, and english or zomi")
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=cmd_testset_sheet)

    p = commands.add_parser("testset-import")
    p.add_argument("sheet", type=Path)
    p.add_argument("--translator", required=True, help="contributor ID, e.g. T01")
    p.add_argument("--origin", required=True, help="where the source sentences came from")
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=cmd_testset_import)

    p = commands.add_parser("review-sheet")
    p.add_argument("draft", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=cmd_review_sheet)

    p = commands.add_parser("review-merge")
    p.add_argument("draft", type=Path)
    p.add_argument("review", type=Path)
    p.add_argument("--reviewer", required=True, help="contributor ID, e.g. R01")
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=cmd_review_merge)

    p = commands.add_parser("ratings-sheet")
    p.add_argument("review", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=cmd_ratings_sheet)

    p = commands.add_parser("ratings-import")
    p.add_argument("sheet", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=cmd_ratings_import)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
