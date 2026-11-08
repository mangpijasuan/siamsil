#!/usr/bin/env python3
"""Swap English personal names for Zomi names in training pairs (docs/ZOMI_NAMES.md).

  sheet   list the names found in a pairs file, for the project owner to mark as a person and a gender
  apply   write a copy of a pairs file with the marked names swapped, in English and Zomi alike

  python3 ml_pipeline/scripts/localize_names.py sheet --pairs ../siamsil-data/parallel --out names-sheet.xlsx
  python3 ml_pipeline/scripts/localize_names.py apply --pairs pairs.jsonl --people names-sheet.xlsx --out pairs.names.jsonl

The Zomi names come only from data/zomi_names.json, the project owner's list. Which English words are people, and
their gender, come only from the sheet the owner marks. Nothing is guessed: an unmarked name, a name marked "either",
a name after a title (Mr, Mrs, Dr, Uncle, ...), and a pair whose Zomi side does not use the English name as many times as
the English side does are all left exactly as they were. A swapped pair keeps its originals beside the new text.
"""

from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Iterable, Iterator

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NAMES = ROOT / "data" / "zomi_names.json"

STAGES = ("child", "young_adult", "married", "older")
GENDERS = ("female", "male")
TITLES = ("Mr", "Mrs", "Miss", "Ms", "Dr", "Professor", "Prof", "Uncle", "Aunt", "Grandpa", "Grandma",
          "Grandfather", "Grandmother", "Sir", "Madam", "Father", "Mother", "Brother", "Sister")
SHEET_COLUMNS = ["Name", "Pairs", "Alone with he", "Alone with she", "Pronoun hint", "Person?", "Gender", "Notes"]
HINT_MIN_SENTENCES = 20
HINT_MIN_SHARE = 0.8
csv.field_size_limit(8_000_000)


# The owner's Zomi names ------------------------------------------------------------------------------------------

class Names:
    def __init__(self, data: dict, source: str = "zomi_names.json") -> None:
        self.default_stage = data.get("default_stage")
        if self.default_stage not in STAGES:
            raise ValueError(f"{source}: default_stage must be one of {', '.join(STAGES)}")
        for key in ("decided_by", "decided_on"):
            if not data.get(key):
                raise ValueError(f"{source}: {key} is required (who decided this, and when)")
        self.version = data.get("version", "0.0.0")
        self.confirmed = bool(data.get("confirmed_by"))
        self.pools: dict[str, dict[str, list[str]]] = {}
        for stage, by_gender in data.get("pools", {}).items():
            if stage not in STAGES:
                raise ValueError(f"{source}: unknown stage {stage!r}")
            self.pools[stage] = {}
            for gender, names in by_gender.items():
                if gender not in GENDERS:
                    raise ValueError(f"{source}: unknown gender {gender!r} in {stage}")
                if not isinstance(names, list) or not all(isinstance(n, str) and n.strip() and n == n.strip() for n in names):
                    raise ValueError(f"{source}: {stage}/{gender} must be a list of names with no outer spaces")
                if len(set(names)) != len(names):
                    raise ValueError(f"{source}: {stage}/{gender} lists a name twice")
                self.pools[stage][gender] = list(names)

    def pool(self, gender: str, stage: str | None = None) -> list[str]:
        return self.pools.get(stage or self.default_stage, {}).get(gender, [])


def load_names(path: Path = DEFAULT_NAMES) -> Names:
    return Names(json.loads(path.read_text(encoding="utf-8")), path.name)


# Reading pairs and the owner's marks ------------------------------------------------------------------------------

def read_pairs(path: Path) -> Iterator[dict]:
    """Records with `id`, `english` and `zomi` from a .jsonl, .csv or .csv.gz file, or a folder of .csv.gz parts."""
    if path.is_dir():
        for part in sorted(path.glob("*.csv.gz")):
            yield from read_pairs(part)
        return
    if path.suffix == ".jsonl":
        with path.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, start=1):
                if line.strip():
                    record = json.loads(line)
                    record.setdefault("id", f"line-{number}")
                    yield record
        return
    opener = gzip.open(path, "rt", encoding="utf-8", newline="") if path.suffix == ".gz" else path.open(encoding="utf-8", newline="")
    with opener as handle:
        for row in csv.DictReader(handle):
            yield {"id": f"corpus-{row['index']}", "english": row["en"], "zomi": row["zomi"]}


def load_people(path: Path) -> dict[str, str]:
    """Name -> "female" or "male" for the rows the owner marked Person? yes with a gender."""
    if path.suffix == ".xlsx":
        import openpyxl

        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
        rows = list(book["Names"].iter_rows(values_only=True))
        book.close()
    else:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
    header = [str(cell or "").strip() for cell in rows[0]]
    for needed in ("Name", "Person?", "Gender"):
        if needed not in header:
            raise ValueError(f"{path.name} has no '{needed}' column")
    at = {name: header.index(name) for name in ("Name", "Person?", "Gender")}
    people: dict[str, str] = {}
    for row in rows[1:]:
        cells = [str(cell or "").strip() for cell in row]
        if len(cells) <= max(at.values()):
            continue
        if cells[at["Person?"]].lower() == "yes" and cells[at["Gender"]].lower() in GENDERS:
            people[cells[at["Name"]]] = cells[at["Gender"]].lower()
    return people


# The swap ---------------------------------------------------------------------------------------------------------

def _digest(key: str) -> int:
    return int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big")


class Localizer:
    def __init__(self, names: Names, people: dict[str, str], seed: str = "szsf-names-1", share: float = 1.0) -> None:
        self.names, self.people, self.seed, self.share = names, people, seed, share
        ordered = sorted(people, key=len, reverse=True)
        self.pattern = re.compile(r"(?<!\w)(" + "|".join(re.escape(n) for n in ordered) + r")(?!\w)") if ordered else None
        title = "|".join(TITLES)
        self.title_pattern = re.compile(rf"(?<!\w)(?:{title})\.?\s+(" + "|".join(re.escape(n) for n in ordered) + r")(?!\w)") if ordered else None
        self.with_name = 0
        self.skipped: collections.Counter[str] = collections.Counter()
        self.swapped: collections.Counter[str] = collections.Counter()

    def _choose(self, record_id: str, name: str, gender: str, taken: set[str]) -> str | None:
        pool = self.names.pool(gender)
        start = _digest(f"{self.seed}:{record_id}:{name}") % len(pool) if pool else 0
        for step in range(len(pool)):
            candidate = pool[(start + step) % len(pool)]
            if candidate not in taken:
                return candidate
        return None

    def localize(self, record: dict) -> dict | None:
        """The pair with its names swapped, or None when it is left as it was (the reason is counted)."""
        if self.pattern is None:
            return None
        english, zomi = record["english"], record["zomi"]
        in_english = self.pattern.findall(english)
        if not in_english:
            return None
        found = list(dict.fromkeys(in_english))
        self.with_name += 1
        record_id = str(record["id"])
        if self.share < 1 and _digest(f"share:{self.seed}:{record_id}") / 2**64 >= self.share:
            self.skipped["not chosen (share)"] += 1
            return None
        if self.title_pattern and self.title_pattern.search(english):
            self.skipped["name after a title"] += 1
            return None
        if collections.Counter(in_english) != collections.Counter(self.pattern.findall(zomi)):
            self.skipped["Zomi side does not use the names as often"] += 1
            return None
        chosen: dict[str, str] = {}
        taken: set[str] = set()
        for name in found:
            picked = self._choose(record_id, name, self.people[name], taken)
            if picked is None:
                self.skipped["name pool too small for this pair"] += 1
                return None
            chosen[name] = picked
            taken.add(picked)
        swap = lambda text: self.pattern.sub(lambda m: chosen[m.group(1)], text)  # noqa: E731
        out = dict(record)
        out.update({"english": swap(english), "zomi": swap(zomi), "english_original": english, "zomi_original": zomi,
                    "names_localized": chosen, "names_version": self.names.version})
        self.swapped.update(chosen.keys())
        return out


def apply(pairs: Iterable[dict], localizer: Localizer, out: Path, limit: int | None = None) -> tuple[int, int]:
    """Write every pair to `out`, swapped where possible. Returns (pairs written, pairs swapped)."""
    written = swapped = 0
    with out.open("w", encoding="utf-8") as handle:
        for record in pairs:
            changed = localizer.localize(record)
            handle.write(json.dumps(changed or record, ensure_ascii=False) + "\n")
            written += 1
            swapped += changed is not None
            if limit and written >= limit:
                break
    return written, swapped


# The owner's sheet ------------------------------------------------------------------------------------------------

def candidate_names(pairs: Iterable[dict], min_pairs: int = 100) -> list[dict]:
    """The capitalized words the build treats as names, with counts and a pronoun hint from sentences with one name."""
    from build_language_db import WORD_RE, name_tokens  # type: ignore

    records = [record["english"] for record in pairs]
    learned = name_tokens(records)
    pairs_with: collections.Counter[str] = collections.Counter()
    he: collections.Counter[str] = collections.Counter()
    she: collections.Counter[str] = collections.Counter()
    forms: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    for english in records:
        tokens = [t for t in WORD_RE.findall(english) if t[:1].isupper() and t.isalpha() and t.lower() in learned]
        names = {t.lower() for t in tokens}
        for token in tokens:
            forms[token.lower()][token] += 1
        for name in names:
            pairs_with[name] += 1
        if len(names) == 1:
            words = {t.lower() for t in WORD_RE.findall(english)}
            (only,) = names
            he[only] += bool(words & {"he", "him", "his", "himself"})
            she[only] += bool(words & {"she", "her", "hers", "herself"})
    rows = []
    for name, count in pairs_with.most_common():
        if count < min_pairs:
            break
        hint, total = "", he[name] + she[name]
        if total >= HINT_MIN_SENTENCES:
            hint = "he" if he[name] >= HINT_MIN_SHARE * total else "she" if she[name] >= HINT_MIN_SHARE * total else "unclear"
        rows.append({"name": forms[name].most_common(1)[0][0], "pairs": count, "he": he[name], "she": she[name], "hint": hint})
    return rows


def write_sheet(rows: list[dict], out: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    book = Workbook()
    intro = book.active
    intro.title = "Instructions"
    intro.column_dimensions["A"].width = 110
    for line in (
        "Siamsil names: which words are people?",
        "",
        "These are the capitalized words the English side uses most. Some are people, some are places, languages or days.",
        "For every row you can judge, fill in the yellow cells:",
        "• Person?  yes, or no (a place, a language, a day, a word).",
        "• Gender   female or male. Use 'either' if the name could be a girl's or a boy's: it will not be swapped.",
        "Leave a row blank if you are unsure. Only rows marked Person? yes with female or male are swapped.",
        "'Pronoun hint' counts sentences with only this name: he/him/his, or she/her. It is a hint, often wrong. You decide.",
        "Do not edit the Name, Pairs or hint columns. Names only: this sheet holds no Zomi text.",
    ):
        intro.append([line])
    intro["A1"].font = Font(bold=True, size=14)
    sheet = book.create_sheet("Names")
    sheet.append(SHEET_COLUMNS)
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1B2A4A")
    for width, letter in zip((16, 10, 14, 14, 14, 10, 10, 30), "ABCDEFGH"):
        sheet.column_dimensions[letter].width = width
    for row in rows:
        sheet.append([row["name"], row["pairs"], row["he"], row["she"], row["hint"], None, None, ""])
        for letter in "FGH":
            sheet[f"{letter}{sheet.max_row}"].fill = PatternFill("solid", fgColor="FFF4C2")
    sheet.freeze_panes = "B2"
    last = max(sheet.max_row, 2)
    for letter, options in (("F", "yes,no"), ("G", "female,male,either")):
        check = DataValidation(type="list", formula1=f'"{options}"', allow_blank=True)
        sheet.add_data_validation(check)
        check.add(f"{letter}2:{letter}{last}")
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top")
    out.parent.mkdir(parents=True, exist_ok=True)
    book.save(out)


# Command line -----------------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    sheet = commands.add_parser("sheet", help="list candidate names for the owner to mark")
    sheet.add_argument("--pairs", type=Path, required=True, help=".jsonl, .csv, .csv.gz, or a folder of .csv.gz parts")
    sheet.add_argument("--out", type=Path, required=True)
    sheet.add_argument("--min-pairs", type=int, default=100)
    run = commands.add_parser("apply", help="swap the marked names")
    run.add_argument("--pairs", type=Path, required=True)
    run.add_argument("--people", type=Path, required=True, help="the marked sheet (.xlsx or .csv)")
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--names", type=Path, default=DEFAULT_NAMES)
    run.add_argument("--share", type=float, default=1.0, help="share of eligible pairs to swap, chosen by hash (0-1)")
    run.add_argument("--seed", default="szsf-names-1")
    run.add_argument("--limit", type=int, help="stop after this many pairs (for a sample)")
    run.add_argument("--min-pool", type=int, default=10,
                     help="names needed per gender before a run is allowed (default 10; lower it only for a sample)")
    args = parser.parse_args(argv)

    if args.command == "sheet":
        rows = candidate_names(read_pairs(args.pairs), args.min_pairs)
        write_sheet(rows, args.out)
        print(f"Wrote {len(rows)} candidate names to {args.out}")
        return 0

    if args.out.resolve() == args.pairs.resolve():
        print("The output must be a new file: the pairs file is never changed in place.", file=sys.stderr)
        return 2
    if not 0 < args.share <= 1:
        print("--share must be above 0 and at most 1.", file=sys.stderr)
        return 2
    names, people = load_names(args.names), load_people(args.people)
    short = {g: len(names.pool(g)) for g in sorted(set(people.values())) if len(names.pool(g)) < args.min_pool}
    if short:
        print(f"Not enough Zomi names for the '{names.default_stage}' stage: "
              + ", ".join(f"{count} {gender}" for gender, count in short.items())
              + f" (a run needs {args.min_pool} per gender). With few names, one name would stand for every "
              "person in the data. Add names to data/zomi_names.json, or lower --min-pool for a small sample.",
              file=sys.stderr)
        return 2
    localizer = Localizer(names, people, args.seed, args.share)
    written, swapped = apply(read_pairs(args.pairs), localizer, args.out, args.limit)
    print(f"Wrote {written:,} pairs to {args.out}; swapped names in {swapped:,}.")
    print(f"  pairs with a marked name: {localizer.with_name:,}")
    for reason, count in sorted(localizer.skipped.items(), key=lambda item: -item[1]):
        print(f"  left as they were: {count:,} ({reason})")
    for name, count in localizer.swapped.most_common(10):
        print(f"  {name}: {count:,}")
    if not names.confirmed:
        print("Note: the names list is not yet confirmed by a second person.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
