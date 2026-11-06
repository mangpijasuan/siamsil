#!/usr/bin/env python3
"""SOP-01 dictionary candidate miner: read-only language SQLite -> draft JSONL.

No translations, definitions, or approvals are invented. Generated records are
internal review candidates only, NEVER published or included in model training.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data/processed/language/siamsil_language.sqlite"
TOKEN = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")
STOP = frozenset(("the a an and or is are was were to of in on at for with by from this that "
                  "it he she we you they i not be been have has had do does did can could "
                  "will would should may might as but if then than so very there here what "
                  "when where why how who which their our your his her its my me us them").split())


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold().strip()


def eligible(token: str) -> bool:
    word = normalize(token)
    return 3 <= len(word) <= 32 and word.isalpha() and word not in STOP


def collect(db_path: Path, target: int = 10000, min_frequency: int = 3,
            max_rows: int | None = None) -> list[dict]:
    if target < 1 or min_frequency < 1 or (max_rows is not None and max_rows < 1):
        raise ValueError("target, min_frequency, and max_rows must be positive")
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    with sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True) as con:
        existing = {normalize(word) for (word,) in con.execute(
            "SELECT source_word FROM dictionary_entries")}
        counter: Counter[str] = Counter()
        evidence: dict[str, list[int]] = defaultdict(list)
        query = ("SELECT id, normalized_source_text FROM parallel_sentences "
                 "WHERE source_language = 'en' AND dataset_split != 'eval_holdout' "
                 "ORDER BY id")
        if max_rows is not None:
            query += " LIMIT ?"
        for row_id, text in con.execute(query, (max_rows,) if max_rows is not None else ()):
            # Ignore the first token to reduce sentence-initial capitalization noise.
            for token in TOKEN.findall(text)[1:]:
                word = normalize(token)
                if not eligible(word) or word in existing:
                    continue
                counter[word] += 1
                if len(evidence[word]) < 3 and row_id not in evidence[word]:
                    evidence[word].append(row_id)
    candidates = []
    for word, frequency in sorted(counter.items(), key=lambda x: (-x[1], x[0])):
        if frequency < min_frequency:
            continue
        candidates.append({
            "candidate_id": hashlib.sha256(("siamsil-dict-v1:en:" + word).encode()).hexdigest()[:24],
            "headword": word,
            "language": "en",
            "dialect": None,
            "proposed_zomi": None,
            "definition": None,
            "part_of_speech": None,
            "frequency": frequency,
            "source_key": "parallel_corpus",
            "evidence_sentence_ids": evidence[word],
            "origin": "automated_token_extraction",
            "review_status": "DRAFT",
            "rights_status": "needs_review",
            "human_verified": False,
        })
        if len(candidates) >= target:
            break
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--target", type=int, default=10000)
    parser.add_argument("--min-frequency", type=int, default=3)
    parser.add_argument("--max-rows", type=int)
    args = parser.parse_args()
    candidates = collect(args.db, args.target, args.min_frequency, args.max_rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as stream:
        for row in candidates:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"target": args.target, "generated": len(candidates),
                      "status": "DRAFT", "output": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
