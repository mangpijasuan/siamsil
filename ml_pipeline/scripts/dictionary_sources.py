"""Read dictionary sources into one record shape for the editorial dictionary (docs/DICTIONARY.md).

Each reader returns SourceRecords: one per sense, with the source's text exactly as
written (only surrounding whitespace is trimmed and wrapped lines joined) and the
original row kept in `raw`. Nothing is translated, corrected, or merged here.

Formats (data/dictionary_sources.json):
  master_workbook    50K English-Zomi-Burmese native-review workbook (01_All_Records, 04_Open_Issue_Index)
  learners_json      Essential 3000 learner's dictionary JSON
  standard_workbook  Zomi Standard Dictionary workbook (Master Data sheet)
  ordbog_pdf         Zomi Ordbog, dansk-[engelsk]-zomi PDF (needs poppler's pdftotext)
  tongdot_tsv        TongDot dictionary lines: headword, headword as shown, "(pos) definition"
"""

from __future__ import annotations

import re
import subprocess
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

POS = {
    "n": "n.", "noun": "n.",
    "v": "v.", "verb": "v.", "transitive verb": "v.", "intransitive verb": "v.",
    "modal v": "modal v.", "modal verb": "modal v.",
    "phrasal v": "phrasal v.", "phrasal verb": "phrasal v.",
    "adj": "adj.", "adjective": "adj.",
    "adv": "adv.", "adverb": "adv.",
    "prep": "prep.", "preposition": "prep.",
    "pron": "pron.", "pronoun": "pron.",
    "conj": "conj.", "conjunction": "conj.",
    "interj": "interj.", "interjection": "interj.", "exclamation": "interj.",
    "num": "num.", "numeral": "num.", "number": "num.",
    "det": "det.", "determiner": "det.", "article": "det.",
    "prop n": "prop. n.", "proper noun": "prop. n.",
    "phr": "phr.", "phrase": "phr.",
}


@dataclass
class Issue:
    source_issue_id: str
    category: str | None
    code: str | None
    description: str | None
    priority: str | None
    required_reviewer: str | None
    raw: dict[str, Any]


@dataclass
class SourceRecord:
    record_id: str
    headword: str
    part_of_speech: str | None
    sense_id: str | None = None
    sense_number: int | None = None
    definition_en: str | None = None
    explanation_ctd: str | None = None
    usage_tier: str | None = None
    domain: str | None = None
    equivalents: list[tuple[str, str, str]] = field(default_factory=list)  # (language, kind, text)
    examples: list[tuple[str, str | None, str | None]] = field(default_factory=list)  # (kind, english, ctd)
    issues: list[Issue] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceRead:
    records: list[SourceRecord]
    skipped: dict[str, int]
    unlinked_issues: list[Issue] = field(default_factory=list)


def clean(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(value))).strip()
    return text or None


def normalize_pos(value: Any) -> str | None:
    """A standard abbreviation, or None when the label is missing or not recognised."""
    text = clean(value)
    if not text:
        return None
    key = re.sub(r"[.]", "", text.lower()).strip()
    key = re.sub(r"\s+", " ", key)
    if key in POS:
        return POS[key]
    first = re.split(r"[;,/]", key)[0].strip()
    return POS.get(first)


def match_key(headword: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", headword).casefold()).strip()


def split_alternatives(text: str | None) -> list[str]:
    return [part.strip() for part in (text or "").split(";") if part.strip()]


def _sheet_rows(path: Path, sheet: str, header_row: int) -> Iterable[dict[str, Any]]:
    import openpyxl

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = workbook[sheet].iter_rows(min_row=header_row, values_only=True)
        header = [str(h).strip() if h is not None else "" for h in next(rows)]
        for row in rows:
            if any(cell is not None and str(cell).strip() for cell in row):
                yield {name: cell for name, cell in zip(header, row) if name}
    finally:
        workbook.close()


# Columns of 01_All_Records that hold the source text and its existing QC; review columns are empty templates.
MASTER_KEEP = (
    "Entry ID", "Headword", "Part of speech", "Sense number", "Simple English definition",
    "Current Standard Zomi", "Current Burmese (reference only)", "Usage tier code", "Standard Zomi review status",
    "Review priority", "Current-text safety warning", "Domain", "Usage tier", "Tier reason", "Editorial status",
    "Burmese review status", "English review status", "Confidence", "Policy history", "Merge history",
    "Aliases (reference only)", "Last updated version", "Last changed stage", "Publication entry number",
)


def read_master_workbook(path: Path) -> SourceRead:
    records: dict[str, SourceRecord] = {}
    skipped: dict[str, int] = {}
    for row in _sheet_rows(path, "01_All_Records", 2):
        sense_id, headword = clean(row.get("Entry ID")), clean(row.get("Headword"))
        if not sense_id or not headword:
            skipped["no_id_or_headword"] = skipped.get("no_id_or_headword", 0) + 1
            continue
        equivalents = [("ctd", "equivalent", t) for t in split_alternatives(clean(row.get("Current Standard Zomi")))]
        burmese = clean(row.get("Current Burmese (reference only)"))
        if burmese:
            equivalents.append(("my", "equivalent", burmese))
        number = clean(row.get("Sense number"))
        records[sense_id] = SourceRecord(
            record_id=sense_id,
            sense_id=sense_id,
            headword=headword,
            part_of_speech=normalize_pos(row.get("Part of speech")),
            sense_number=int(number) if number and number.isdigit() else None,
            definition_en=clean(row.get("Simple English definition")),
            usage_tier=clean(row.get("Usage tier code")),
            domain=clean(row.get("Domain")),
            equivalents=equivalents,
            raw={k: row.get(k) for k in MASTER_KEEP if k in row},
        )
    unlinked: list[Issue] = []
    for row in _sheet_rows(path, "04_Open_Issue_Index", 2):
        issue_id = clean(row.get("Item ID"))
        if not issue_id:
            continue
        issue = Issue(
            source_issue_id=issue_id,
            category=clean(row.get("Issue category")),
            code=clean(row.get("Issue code")),
            description=clean(row.get("Description")),
            priority=clean(row.get("Priority")),
            required_reviewer=clean(row.get("Required reviewer")),
            raw={k: v for k, v in row.items() if not (isinstance(v, str) and v.startswith("="))},
        )
        target = records.get(clean(row.get("Record ID")) or "")
        (target.issues if target else unlinked).append(issue)
    return SourceRead(list(records.values()), skipped, unlinked)


def read_learners_json(path: Path) -> SourceRead:
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    records, skipped = [], {}
    for entry in data["entries"]:
        headword = clean(entry.get("headword"))
        if not headword:
            skipped["no_headword"] = skipped.get("no_headword", 0) + 1
            continue
        for sense in entry.get("senses") or []:
            examples = [("phrase", clean(p.get("english")), clean(p.get("zomi"))) for p in sense.get("common_phrases") or []]
            examples += [("example", clean(e.get("english")), clean(e.get("zomi"))) for e in sense.get("examples") or []]
            records.append(SourceRecord(
                record_id=f"{int(entry['id']):06d}:{sense['number']}",
                headword=headword,
                part_of_speech=normalize_pos(entry.get("part_of_speech")),
                sense_number=sense.get("number"),
                definition_en=clean(sense.get("definition_en")),
                explanation_ctd=clean(sense.get("explanation_zomi")),
                equivalents=[("ctd", "equivalent", t) for t in split_alternatives(clean(sense.get("zomi_equivalents")))],
                examples=[x for x in examples if x[1] or x[2]],
                raw={"entry_id": entry["id"], "headword": entry.get("headword"), "ipa": entry.get("ipa"),
                     "part_of_speech": entry.get("part_of_speech"), "sense": sense},
            ))
    return SourceRead(records, skipped)


def read_standard_workbook(path: Path) -> SourceRead:
    records, skipped = [], {}
    for row in _sheet_rows(path, "Master Data", 1):
        record_id, headword = clean(row.get("ID")), clean(row.get("Headword"))
        if not record_id or not headword:
            skipped["no_id_or_headword"] = skipped.get("no_id_or_headword", 0) + 1
            continue
        issues = []
        if clean(row.get("Flagged")) == "Yes":
            issues.append(Issue(
                source_issue_id=f"{record_id}:flagged",
                category="Flagged in source: headword not in English dictionary",
                code="FLAGGED",
                description=clean(row.get("Suggested Correction")),
                priority=None,
                required_reviewer=None,
                raw={"Flagged": row.get("Flagged"), "Suggested Correction": row.get("Suggested Correction")},
            ))
        records.append(SourceRecord(
            record_id=record_id,
            headword=headword,
            part_of_speech=normalize_pos(row.get("POS (full)")) or normalize_pos(row.get("POS")),
            explanation_ctd=clean(row.get("Definition (Zomi)")),
            issues=issues,
            raw={k: v for k, v in row.items()},
        ))
    return SourceRead(records, skipped)


ORDBOG_ENTRY = re.compile(
    r"^(?P<danish>[^\[]*?)\s*\[(?P<english>[^\]]*)\](?:\s*\((?P<pos>[^)]*)\))?:\s*(?P<ctd>.*)$"
)
# A Danish label that wrapped: the line ends at the English, and the next line starts "(v.): ...".
ORDBOG_HEAD_ONLY = re.compile(r"^[^\[]*\[[^\]]*\]$")


def parse_ordbog_pages(pages: list[str]) -> SourceRead:
    """Entries look like `afsky [abhor] (v.): ih, mudah, ...`; following lines continue the Zomi.

    Wrapped layouts are handled: a Danish label split across lines before the English,
    the English and part of speech on separate lines, and entries without a part of speech.
    """
    records, skipped = [], {}
    current: dict[str, Any] | None = None
    entries: list[dict[str, Any]] = []
    carry, carry_page = "", 0  # a wrapped label can continue on the next page
    positions: dict[int, int] = {}
    for page_number, page in enumerate(pages, 1):
        for line in page.split("\n"):
            line = line.strip()
            if not line or re.fullmatch(r"\d+", line):
                continue
            if ORDBOG_HEAD_ONLY.match(line):
                if carry and current is not None:
                    current["lines"].append(carry)
                carry, carry_page = line, page_number
                continue
            entry_page = page_number
            if carry:
                line, entry_page, carry = f"{carry} {line}", carry_page, ""
            match = ORDBOG_ENTRY.match(line)
            if match:
                fields = match.groupdict()
                if not fields["danish"].strip() and current is not None and len(current["lines"]) > 1:
                    # The Danish label was on the previous line, which was read as Zomi text.
                    fields["danish"] = current["lines"].pop()
                positions[entry_page] = positions.get(entry_page, 0) + 1
                current = {**fields, "lines": [fields["ctd"]], "page": entry_page, "position": positions[entry_page]}
                entries.append(current)
            elif current is not None:
                current["lines"].append(line)
    if carry and current is not None:
        current["lines"].append(carry)
    # The book repeats an English headword and its Zomi under each Danish synonym; keep one
    # sense per identical (English, part of speech, Zomi) with every Danish label and page.
    grouped: dict[tuple, list[dict[str, Any]]] = {}
    for entry in entries:
        english = clean(entry["english"])
        if not english or english.strip("-") == "":
            skipped["no_english_headword"] = skipped.get("no_english_headword", 0) + 1
            continue
        gloss = clean(" ".join(entry["lines"]))
        grouped.setdefault((match_key(english), normalize_pos(entry["pos"]), gloss), []).append(
            {**entry, "english": english, "gloss": gloss}
        )
    skipped["repeated_under_another_danish_label"] = sum(len(v) - 1 for v in grouped.values())
    for occurrences in grouped.values():
        entry = occurrences[0]
        english, gloss = entry["english"], entry["gloss"]
        record_id = f"p{entry['page']:03d}-{entry['position']:03d}"
        issues = []
        if gloss and re.search(r"\[[^\]]+\]\s*(\([^)]*\))?:", gloss):
            issues.append(Issue(
                source_issue_id=f"{record_id}:merged-entry",
                category="Extraction check: another entry may be joined to this one",
                code="MERGED_ENTRY",
                description="The Zomi text contains a bracketed English headword; check the source page and split it.",
                priority="High",
                required_reviewer="Editor",
                raw={"page": entry["page"]},
            ))
        records.append(SourceRecord(
            record_id=record_id,
            headword=english,
            part_of_speech=normalize_pos(entry["pos"]),
            equivalents=[("ctd", "gloss", gloss)] if gloss else [],
            issues=issues,
            raw={
                "english": english,
                "part_of_speech": clean(entry["pos"]),
                "zomi": gloss,
                "occurrences": [{"danish": clean(o["danish"]), "page": o["page"]} for o in occurrences],
            },
        ))
    return SourceRead(records, {k: v for k, v in skipped.items() if v})


def read_ordbog_pdf(path: Path) -> SourceRead:
    try:
        text = subprocess.run(["pdftotext", "-raw", str(path), "-"], check=True, capture_output=True, text=True).stdout
    except FileNotFoundError as error:
        raise RuntimeError("pdftotext is required for ordbog_pdf sources (brew install poppler)") from error
    return parse_ordbog_pages(text.split("\f"))


TONGDOT_POS = {"a": "adj.", "vt": "v.", "vi": "v.", "v.t": "v.", "v.i": "v.", "abbr": None, "abbrev": None}
MYANMAR = re.compile("[\u1000-\u109f]")
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")


def _tongdot_pos(label: str | None) -> str | None:
    key = re.sub(r"[()\s]+", " ", label or "").strip().rstrip(".").lower()
    if key in TONGDOT_POS:
        return TONGDOT_POS[key]
    return normalize_pos(key)


def read_tongdot_tsv(path: Path) -> SourceRead:
    """One sense per line. TongDot mixes Tedim, other Chin languages and Burmese without labels.

    A definition in Myanmar script becomes a Burmese (`my`) gloss. Any other definition becomes a
    `ctd` gloss with an open VARIETY_CHECK issue: a reviewer confirms it is Tedim (or rejects it)
    before it can be approved. Definitions are kept whole; nothing is split, corrected or guessed.
    """
    records: list[SourceRecord] = []
    skipped: dict[str, int] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        parts = line.split("\t")
        if len(parts) != 3:
            if line.strip():
                skipped["not_three_columns"] = skipped.get("not_three_columns", 0) + 1
            continue
        headword, shown, definition = (clean(part) for part in parts)
        if not headword or not definition:
            skipped["no_headword_or_definition"] = skipped.get("no_headword_or_definition", 0) + 1
            continue
        match = re.match(r"^\(+([^()]*)\)*\.?\)?\s*:?\s*", definition)
        label = match.group(1) if match else None
        text = clean(definition[match.end():] if match else definition)
        if not text:
            skipped["no_definition_text"] = skipped.get("no_definition_text", 0) + 1
            continue
        record_id = f"L{number:06d}"
        issues: list[Issue] = []
        if MYANMAR.search(text):
            equivalents = [("my", "gloss", text)]
            if LATIN_WORD.search(MYANMAR.sub(" ", text)):
                issues.append(Issue(f"{record_id}:mixed", "Burmese definition with Latin-script text", "MIXED_SCRIPT",
                                    "Separate any English or Chin words from the Burmese.", None, None, {}))
        else:
            equivalents = [("ctd", "gloss", text)]
            issues.append(Issue(f"{record_id}:variety", "Language not labelled in source", "VARIETY_CHECK",
                                "TongDot mixes Chin languages: confirm this gloss is Tedim Zomi before approving.",
                                None, None, {}))
        records.append(SourceRecord(
            record_id=record_id,
            headword=headword,
            part_of_speech=_tongdot_pos(label),
            equivalents=equivalents,
            issues=issues,
            raw={"line": number, "headword": parts[0], "shown": parts[1], "definition": parts[2], "pos_label": label},
        ))
    return SourceRead(records, skipped)


READERS = {
    "master_workbook": read_master_workbook,
    "learners_json": read_learners_json,
    "standard_workbook": read_standard_workbook,
    "ordbog_pdf": read_ordbog_pdf,
    "tongdot_tsv": read_tongdot_tsv,
}
