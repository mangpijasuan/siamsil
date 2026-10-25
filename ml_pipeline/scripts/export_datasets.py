#!/usr/bin/env python3
"""Export train / validation / test files for model training, by tier.

Reads a built language database and, optionally, the Bible and daily-use
workbook and the Bible versions database (import_usx_bibles.py). Writes JSONL
files plus a manifest under data/datasets/.

Tiers:
  gold    human-made or human-reviewed: Bible ("Original ZSF Text" only, and each
          Zomi Bible version paired verse by verse with each English version) and
          teacher-reviewed daily-use phrases
  silver  corpus pairs accepted by human reviewers (build_language_db.py --reviews),
          and corpus pairs with no quality flags from generators whose spot-check
          acceptable share (lower 95% bound) meets --silver-min-acceptable
  bronze  remaining corpus pairs with quality score >= --min-score

Rights gate: only sources whose training status in data/rights.json is
"cleared" are exported. --allow-uncleared also admits "needs_review" sources
for internal experiments and records that in the manifest; "blocked" sources
are never exported. A Bible version pair needs both versions admitted. Pairs
matching a human evaluation item (--eval) are never exported.

Bible splits are by whole book, the same for every version and the workbook, so
a verse never sits in training in one translation and in test in another.
Merged verse ranges (such as 17-18) are not paired.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from build_language_db import (
    EVAL_HOLDOUT_SPLIT,
    ROOT,
    eval_match_keys,
    file_fingerprint,
    load_eval_items,
    normalize_word,
    split_for_key,
    template_key,
)
from import_usx_bibles import BOOKS

BIBLE_TEST_BOOKS = frozenset({"RUT", "MRK", "1JN"})
BIBLE_VALIDATION_BOOKS = frozenset({"JOL", "JON", "PHP", "TIT"})
BOOK_CODES = {index + 1: code for index, (code, _, _) in enumerate(BOOKS)}
BOOK_CODES_BY_NAME = {name.lower(): code for code, name, _ in BOOKS}
BOOK_CODES_BY_NAME.update({"psalm": "PSA", "song of songs": "SNG", "canticles": "SNG", "revelations": "REV"})

SPLITS = ("train", "validation", "test")
DEFAULT_DB = ROOT / "data" / "processed" / "language" / "siamsil_language.sqlite"
DEFAULT_RIGHTS = ROOT / "data" / "rights.json"
DEFAULT_OUT = ROOT / "data" / "datasets"


def load_rights(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {name: entry["train"] for name, entry in data["sources"].items()}


def admitted_sources(rights: dict[str, str], allow_uncleared: bool) -> set[str]:
    allowed = {"cleared", "needs_review"} if allow_uncleared else {"cleared"}
    return {name for name, status in rights.items() if status in allowed}


def silver_models(summary: dict | None, min_acceptable: float) -> set[str]:
    """Generators whose acceptable-share lower 95% bound meets the threshold."""
    if not summary:
        return set()
    return {
        model
        for model, stats in summary.items()
        if stats.get("acceptable_95ci") and stats["acceptable_95ci"][0] >= min_acceptable
    }


def corpus_records(con: sqlite3.Connection, silver: set[str], min_score: float):
    rows = con.execute(
        """
        SELECT id, normalized_source_text, normalized_target_text, model,
               quality_flags, quality_score, dataset_split, verified
        FROM parallel_sentences
        WHERE dataset_split != ? AND quality_score >= ?
        ORDER BY id
        """,
        (EVAL_HOLDOUT_SPLIT, min_score),
    )
    for row_id, english, zomi, model, flags_json, score, split, verified in rows:
        flags = json.loads(flags_json or "[]")
        # A pair human reviewers accepted is silver whatever its generator scored; rejected
        # pairs never reach this loop (their quality score is 0).
        yield {
            "id": f"corpus-{row_id}",
            "english": english,
            "zomi": zomi,
            "source": "parallel_corpus",
            "tier": "silver" if verified or (not flags and model in silver) else "bronze",
            "human_reviewed": bool(verified),
            "split": split,
            "model": model,
            "quality_score": score,
            "quality_flags": flags,
        }


def bible_split(book_code: str) -> str:
    if book_code in BIBLE_TEST_BOOKS:
        return "test"
    if book_code in BIBLE_VALIDATION_BOOKS:
        return "validation"
    return "train"


def workbook_book_code(verse: dict) -> str | None:
    """The workbook's book ids are not reliable; match the English book name first."""
    name = verse.get("book_english") or (verse.get("reference") or "").rsplit(" ", 1)[0]
    if name:
        return BOOK_CODES_BY_NAME.get(name.strip().lower())
    return BOOK_CODES.get(verse.get("book_id"))


def gold_records(bible: list[dict], phrases: list[dict], skipped: Counter[str] | None = None):
    skipped = skipped if skipped is not None else Counter()
    for verse in bible:
        english, zomi = verse.get("english"), verse.get("zomi_original")
        if not english or not zomi:
            continue
        book_code = workbook_book_code(verse)
        if not book_code:
            skipped["bible_unknown_book"] += 1
            continue
        yield {
            "id": f"bible-{verse['book_id']}-{verse['chapter']}-{verse['verse']}",
            "english": english,
            "zomi": zomi,
            "source": "bible_original",
            "tier": "gold",
            "split": bible_split(book_code),
            "reference": verse.get("reference"),
        }
    for phrase in phrases:
        if not phrase.get("verified") or not phrase.get("english") or not phrase.get("zomi"):
            continue
        yield {
            "id": f"phrase-{phrase['id']}",
            "english": phrase["english"],
            "zomi": phrase["zomi"],
            "source": "daily_use_phrases",
            "tier": "gold",
            "split": split_for_key(template_key(phrase["english"], set())),
        }


def bible_version_records(path: Path, skipped: Counter[str]):
    """Each Zomi version paired with each English version, verse by verse."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        versions = con.execute(
            "SELECT id, language_iso, rights_source FROM versions WHERE language_iso IN ('zom', 'eng') ORDER BY sort_order"
        ).fetchall()
        zomi = [(vid, rights) for vid, iso, rights in versions if iso == "zom"]
        english = [(vid, rights) for vid, iso, rights in versions if iso == "eng"]
        for zomi_id, zomi_rights in zomi:
            for english_id, english_rights in english:
                skipped["bible_unpaired_verse"] += con.execute(
                    """
                    SELECT COUNT(*) FROM verses z WHERE z.version_id = ? AND NOT EXISTS (
                      SELECT 1 FROM verses e WHERE e.version_id = ? AND e.book_id = z.book_id
                        AND e.chapter = z.chapter AND e.verse = z.verse)
                    """,
                    (zomi_id, english_id),
                ).fetchone()[0]
                rows = con.execute(
                    """
                    SELECT z.book_id, b.name, z.chapter, z.verse, z.label, e.label, z.text, e.text
                    FROM verses z
                    JOIN verses e ON e.version_id = ? AND e.book_id = z.book_id
                      AND e.chapter = z.chapter AND e.verse = z.verse
                    JOIN books b ON b.book_id = z.book_id
                    WHERE z.version_id = ?
                    ORDER BY z.book_id, z.chapter, z.verse
                    """,
                    (english_id, zomi_id),
                )
                for book_id, book_name, chapter, verse, zomi_label, english_label, zomi_text, english_text in rows:
                    if "-" in zomi_label or "-" in english_label:
                        skipped["bible_verse_range"] += 1
                        continue
                    yield {
                        "id": f"bible-{zomi_id}-{english_id}-{book_id}-{chapter}-{verse}",
                        "english": english_text,
                        "zomi": zomi_text,
                        "source": zomi_rights,
                        "english_source": english_rights,
                        "tier": "gold",
                        "split": bible_split(BOOK_CODES[book_id]),
                        "reference": f"{book_name} {chapter}:{verse}",
                        "zomi_version": zomi_id,
                        "english_version": english_id,
                    }
    finally:
        con.close()


def load_workbook_sources(path: Path) -> tuple[list[dict], list[dict]]:
    from import_excel import import_bible, import_daily_use

    return import_bible(path), import_daily_use(path)


def export(
    con: sqlite3.Connection,
    out_dir: Path,
    *,
    rights: dict[str, str],
    allow_uncleared: bool,
    bible: list[dict],
    phrases: list[dict],
    eval_items: list[dict],
    summary: dict | None,
    min_acceptable: float,
    min_score: float,
    bible_versions: Path | None = None,
) -> dict:
    admitted = admitted_sources(rights, allow_uncleared)
    silver = silver_models(summary, min_acceptable)
    eval_english, eval_zomi = eval_match_keys(eval_items, set())

    counts: Counter[tuple[str, str, str]] = Counter()
    skipped: Counter[str] = Counter()
    out_dir.mkdir(parents=True, exist_ok=True)
    handles = {split: (out_dir / f"{split}.jsonl").open("w", encoding="utf-8") for split in SPLITS}
    try:
        streams = [gold_records(bible, phrases, skipped), corpus_records(con, silver, min_score)]
        if bible_versions:
            streams.append(bible_version_records(bible_versions, skipped))
        for stream in streams:
            for record in stream:
                if record["source"] not in admitted:
                    skipped[f"rights:{record['source']}"] += 1
                    continue
                if record.get("english_source", record["source"]) not in admitted:
                    skipped[f"rights:{record['english_source']}"] += 1
                    continue
                if (eval_english or eval_zomi) and (
                    template_key(record["english"], set()) in eval_english
                    or normalize_word(record["zomi"]) in eval_zomi
                ):
                    skipped["evaluation_match"] += 1
                    continue
                handles[record["split"]].write(json.dumps(record, ensure_ascii=False) + "\n")
                counts[(record["split"], record["tier"], record["source"])] += 1
    finally:
        for handle in handles.values():
            handle.close()

    by_split = {split: {"total": 0, "by_tier": Counter(), "by_source": Counter()} for split in SPLITS}
    for (split, tier, source), n in counts.items():
        by_split[split]["total"] += n
        by_split[split]["by_tier"][tier] += n
        by_split[split]["by_source"][source] += n
    for entry in by_split.values():
        entry["by_tier"] = dict(sorted(entry["by_tier"].items()))
        entry["by_source"] = dict(sorted(entry["by_source"].items()))
    return {
        "splits": by_split,
        "skipped": dict(skipped),
        "sources": {
            name: {"train_rights": status, "exported": name in admitted} for name, status in sorted(rights.items())
        },
        "uncleared_sources_included": sorted(n for n in admitted if rights[n] != "cleared"),
        "silver_models": sorted(silver),
        "parameters": {"min_score": min_score, "silver_min_acceptable": min_acceptable},
        "bible_split_books": {"test": sorted(BIBLE_TEST_BOOKS), "validation": sorted(BIBLE_VALIDATION_BOOKS)},
        "files": {split: file_fingerprint(out_dir / f"{split}.jsonl") for split in SPLITS},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--workbook", type=Path, help="Bible and daily-use workbook (Zomi_Bible_Final_v14.xlsx)")
    parser.add_argument("--eval", type=Path, action="append", default=[], help="Human evaluation set; repeatable")
    parser.add_argument("--bible-versions", type=Path, help="bible_versions.sqlite from import_usx_bibles.py")
    parser.add_argument("--generator-summary", type=Path, help="summary.json from review_sample.py summarize")
    parser.add_argument("--silver-min-acceptable", type=float, default=0.8)
    parser.add_argument("--min-score", type=float, default=0.5)
    parser.add_argument("--rights", type=Path, default=DEFAULT_RIGHTS)
    parser.add_argument("--allow-uncleared", action="store_true", help="Also export needs_review sources (internal use)")
    parser.add_argument("--out", type=Path, help="Output directory (default: data/datasets/<release>-export)")
    args = parser.parse_args(argv)

    if not args.db.exists():
        sys.exit(f"Language database not found: {args.db}")
    if args.bible_versions and not args.bible_versions.exists():
        sys.exit(f"Bible versions database not found: {args.bible_versions}")
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        version = con.execute("SELECT version FROM dataset_versions ORDER BY id DESC LIMIT 1").fetchone()[0]
        bible, phrases = load_workbook_sources(args.workbook) if args.workbook else ([], [])
        summary = json.loads(args.generator_summary.read_text(encoding="utf-8")) if args.generator_summary else None
        out_dir = args.out or DEFAULT_OUT / f"siamsil-{version}-export"
        result = export(
            con,
            out_dir,
            rights=load_rights(args.rights),
            allow_uncleared=args.allow_uncleared,
            bible=bible,
            phrases=phrases,
            eval_items=load_eval_items(args.eval),
            summary=summary,
            min_acceptable=args.silver_min_acceptable,
            min_score=args.min_score,
            bible_versions=args.bible_versions,
        )
    finally:
        con.close()

    inputs = {"database": file_fingerprint(args.db), "rights": file_fingerprint(args.rights)}
    if args.workbook:
        inputs["workbook"] = file_fingerprint(args.workbook)
    if args.bible_versions:
        inputs["bible_versions"] = file_fingerprint(args.bible_versions)
    if args.generator_summary:
        inputs["generator_summary"] = file_fingerprint(args.generator_summary)
    inputs["evaluation_sets"] = [{"file": p.name, "sha256": file_fingerprint(p)["sha256"]} for p in args.eval]
    manifest = {"language_release": version, "inputs": inputs, **result}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for split in SPLITS:
        print(f"{split:>10}: {result['splits'][split]['total']:,}  {result['splits'][split]['by_tier']}")
    for name, info in result["sources"].items():
        if not info["exported"]:
            print(f"not exported: {name} (training rights: {info['train_rights']})")
    if result["uncleared_sources_included"]:
        print(f"WARNING: uncleared sources included: {', '.join(result['uncleared_sources_included'])}")
    print(f"wrote {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
