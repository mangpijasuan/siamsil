#!/usr/bin/env python3
"""
Import scanned PDF dictionary books into the Siamsil dictionary (offline, no API key).

Uses Tesseract OCR (free, runs locally) to extract text from each page,
then parses the text into structured dictionary entries.

Usage:
    python import_pdf_dictionary.py path/to/dict.pdf
    python import_pdf_dictionary.py path/to/dict.pdf --out processed_data/dictionary.json
    python import_pdf_dictionary.py path/to/dict.pdf --pages 5-200
    python import_pdf_dictionary.py path/to/dict.pdf --dry-run

Requirements:
    pip install pdf2image pillow pytesseract
    brew install tesseract poppler          # macOS
    # Ubuntu/Debian: apt install tesseract-ocr poppler-utils
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from pdf2image import convert_from_path
except ImportError:
    sys.exit("pdf2image not installed.\n  Run: pip install pdf2image pillow\n  and: brew install poppler")

try:
    import pytesseract
except ImportError:
    sys.exit("pytesseract not installed.\n  Run: pip install pytesseract\n  and: brew install tesseract")

# ── Paths ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR  = Path(__file__).parent
PIPELINE_DIR = SCRIPT_DIR.parent
DEFAULT_OUT  = PIPELINE_DIR / "processed_data" / "dictionary.json"
BACKEND_DATA = PIPELINE_DIR.parent / "backend" / "data" / "dictionary.json"

# ── Part-of-speech abbreviations to recognise ─────────────────────────────────

POS_PATTERNS = re.compile(
    r"\b(n\.|v\.|vt\.|vi\.|adj\.|adv\.|prep\.|conj\.|pron\.|interj\.|abbr\.)\b"
)

# ── Parse one page of OCR text into entries ───────────────────────────────────

def parse_page(text: str, source: str) -> list[dict]:
    """
    Heuristic parser for English–Zomi dictionary pages.

    Assumes the layout has one entry per line (or a few lines) like:
        headword  /phonetic/  pos  definition  Zomi: zomi_word
    or columns separated by whitespace / tab.

    We try several patterns and fall back to splitting on common separators.
    """
    entries: list[dict] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or len(line) < 3:
            continue

        entry: dict = {
            "english": "",
            "zomi": "",
            "phonetic": "",
            "part_of_speech": "",
            "definition": "",
            "domain": "",
            "verified": False,
            "source": source,
        }

        # ── Extract phonetic between / / or ( ) ──────────────────────────────
        phonetic_match = re.search(r"[/\(]([^/\)]{2,30})[/\)]", line)
        if phonetic_match:
            entry["phonetic"] = phonetic_match.group(1).strip()
            line = line[:phonetic_match.start()] + line[phonetic_match.end():]

        # ── Extract part of speech ────────────────────────────────────────────
        pos_match = POS_PATTERNS.search(line)
        if pos_match:
            entry["part_of_speech"] = pos_match.group(1)
            line = line[:pos_match.start()] + line[pos_match.end():]

        # ── Try to split English headword from Zomi translation ───────────────
        # Pattern 1: separated by tab
        if "\t" in line:
            parts = [p.strip() for p in line.split("\t", 1)]
            entry["english"] = parts[0]
            entry["zomi"]    = parts[1] if len(parts) > 1 else ""

        # Pattern 2: explicit "Zomi:" or "Z:" label
        elif re.search(r"\bZomi\s*:", line, re.IGNORECASE):
            m = re.split(r"\bZomi\s*:", line, maxsplit=1, flags=re.IGNORECASE)
            entry["english"] = m[0].strip()
            entry["zomi"]    = m[1].strip()

        # Pattern 3: long dash or em-dash separator  word — translation
        elif "—" in line or " - " in line:
            sep = "—" if "—" in line else " - "
            parts = [p.strip() for p in line.split(sep, 1)]
            entry["english"] = parts[0]
            entry["zomi"]    = parts[1] if len(parts) > 1 else ""

        # Pattern 4: two or more spaces acting as column separator
        elif re.search(r"  +", line):
            parts = re.split(r"  +", line.strip(), maxsplit=1)
            entry["english"] = parts[0].strip()
            entry["zomi"]    = parts[1].strip() if len(parts) > 1 else ""

        # Pattern 5: treat entire line as English headword (single-column books)
        else:
            entry["english"] = line.strip()

        # ── Clean up headword ─────────────────────────────────────────────────
        entry["english"] = entry["english"].strip(" .,;:-")

        # Skip lines that look like page numbers, headers, or noise
        if (
            not entry["english"]
            or len(entry["english"]) > 80
            or entry["english"].isdigit()
            or re.match(r"^(page|chapter|section|\d+)$", entry["english"], re.IGNORECASE)
        ):
            continue

        entries.append(entry)

    return entries


# ── Load / merge / save ───────────────────────────────────────────────────────

def load_existing(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def merge_entries(existing: list[dict], new_entries: list[dict]) -> tuple[list[dict], int]:
    seen: set[tuple[str, str]] = set()
    merged = list(existing)

    for e in existing:
        key = ((e.get("english") or "").lower().strip(), (e.get("zomi") or "").lower().strip())
        seen.add(key)

    next_id = max((e.get("id", 0) for e in merged), default=0) + 1
    added = 0

    for e in new_entries:
        key = ((e.get("english") or "").lower().strip(), (e.get("zomi") or "").lower().strip())
        if key in seen or not e.get("english"):
            continue
        seen.add(key)
        merged.append({**e, "id": next_id})
        next_id += 1
        added += 1

    return merged, added


def save(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Saved → {path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Offline PDF dictionary importer (Tesseract OCR).")
    parser.add_argument("pdf", help="Path to the scanned dictionary PDF")
    parser.add_argument("--out",   default=str(DEFAULT_OUT), help="Output dictionary.json path")
    parser.add_argument("--pages", help="Page range, e.g. '5-200' or '10'")
    parser.add_argument("--dpi",   type=int, default=300, help="Render DPI (default 300; higher = better OCR)")
    parser.add_argument("--lang",  default="eng", help="Tesseract language code(s), e.g. 'eng' or 'eng+mya' (default: eng)")
    parser.add_argument("--dry-run", action="store_true", help="Print first 20 entries without saving")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        sys.exit(f"PDF not found: {pdf_path}")

    source_label = f"scanned-pdf:{pdf_path.stem}"

    # ── Parse page range ──────────────────────────────────────────────────────
    first_page = last_page = None
    if args.pages:
        parts = args.pages.split("-")
        first_page = int(parts[0])
        last_page  = int(parts[1]) if len(parts) == 2 else first_page

    print(f"\nConverting PDF → images (DPI={args.dpi}) …")
    images = convert_from_path(
        str(pdf_path),
        dpi=args.dpi,
        first_page=first_page,
        last_page=last_page,
        fmt="jpeg",
    )
    total = len(images)
    print(f"  {total} page(s) to process\n")

    all_new: list[dict] = []

    for i, img in enumerate(images):
        page_num = (first_page or 1) + i
        print(f"  Page {page_num}/{total + (first_page or 1) - 1} … ", end="", flush=True)

        text = pytesseract.image_to_string(img, lang=args.lang)
        entries = parse_page(text, source_label)
        all_new.extend(entries)
        print(f"{len(entries)} entries")

    print(f"\nTotal extracted: {len(all_new)} entries")

    if args.dry_run:
        print("\nFirst 20 entries (dry-run, not saving):")
        print(json.dumps(all_new[:20], ensure_ascii=False, indent=2))
        return

    out_path = Path(args.out)
    existing = load_existing(out_path)
    merged, added = merge_entries(existing, all_new)
    print(f"Added {added} new entries ({len(merged)} total).\n")
    save(out_path, merged)

    if BACKEND_DATA.parent.exists():
        save(BACKEND_DATA, merged)

    print("\nDone. Restart the backend to reload the dictionary.")


if __name__ == "__main__":
    main()
