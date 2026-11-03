"""Generate Bible spelling review candidates. Bible usage is evidence, never an automatic correction.

Only display-cleared Zomi Bible versions are scanned. Export verse references and
variant IDs, not verse text. Output must stay in the private data workspace.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HEADERS = ["version", "book_id", "chapter", "verse", "check_id", "observed",
           "alternatives", "reason", "status", "reviewer_1", "reviewer_2", "decision"]


def matching_patterns(checks_path: Path):
    checks = json.loads(checks_path.read_text(encoding="utf-8"))["checks"]
    result = []
    for check in checks:
        if check.get("special"):
            continue
        for variants in check.get("variants", []):
            if len(variants) < 2:
                continue
            for variant in variants:
                pieces = [r"[ 	]+" if c == " " else re.escape(c) for c in variant]
                expression = r"(?<![A-Za-z'-])" + "".join(pieces) + r"(?![A-Za-z'-])"
                result.append((check["id"], variant, variants, re.compile(expression, re.I)))
    return result


def scan(db: Path, checks_path: Path, limit: int):
    patterns = matching_patterns(checks_path)
    rows = []
    con = sqlite3.connect(f"file:{db.resolve()}?mode=ro", uri=True)
    try:
        versions = con.execute(
            "SELECT id FROM versions WHERE display_status = ? AND language_iso IN ('ctd', 'zom')",
            ("cleared",),
        ).fetchall()
        for (version,) in versions:
            verses = con.execute(
                "SELECT book_id, chapter, verse, text FROM verses WHERE version_id = ?",
                (version,),
            )
            for book, chapter, verse, text in verses:
                for check_id, variant, alternatives, pattern in patterns:
                    if pattern.search(text):
                        rows.append({
                            "version": version, "book_id": book, "chapter": chapter,
                            "verse": verse, "check_id": check_id, "observed": variant,
                            "alternatives": " | ".join(alternatives),
                            "reason": "Bible spelling variant; verify meaning and style guide",
                            "status": "needs_human_review", "reviewer_1": "",
                            "reviewer_2": "", "decision": "",
                        })
                        if len(rows) >= limit:
                            return rows
        return rows
    finally:
        con.close()


def write_csv(rows, destination: Path):
    resolved = destination.resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise ValueError("Review exports must be outside the public repository")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--checks", type=Path, default=ROOT / "data/zolai_standard/rule_checks.json")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    if not 1 <= args.limit <= 5000:
        parser.error("--limit must be 1..5000")
    rows = scan(args.db, args.checks, args.limit)
    write_csv(rows, args.out)
    print(f"{len(rows)} reference-only Bible cases sent to human review; no changes approved")


if __name__ == "__main__":
    main()
