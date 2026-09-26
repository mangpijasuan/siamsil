#!/usr/bin/env python3
"""Build the Siamsil language database from immutable raw files.

Reads:
  data/raw/dictionary/Zomi_Standard_Dictionary_AI_Cleaned.xlsx
  data/raw/parallel/zomi_english_sentences.csv

Writes (never touches raw files):
  data/processed/language/siamsil_language.sqlite
  data/processed/language/quality_report.json
  data/processed/language/manifest.json
  data/evaluation/translation/sample.jsonl
  data/evaluation/dictionary/sample.jsonl
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_VERSION = "1.0.0"
DATASET_VERSION = "v1"

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW = ROOT / "data" / "raw"
DEFAULT_OUT_DB = ROOT / "data" / "processed" / "language" / "siamsil_language.sqlite"
DEFAULT_REPORT = ROOT / "data" / "processed" / "language" / "quality_report.json"
DEFAULT_MANIFEST = ROOT / "data" / "processed" / "language" / "manifest.json"
EVAL_TRANSLATION = ROOT / "data" / "evaluation" / "translation" / "sample.jsonl"
EVAL_DICTIONARY = ROOT / "data" / "evaluation" / "dictionary" / "sample.jsonl"

HTML_RE = re.compile(r"<(script|style|iframe|object|embed|link|meta)\b|</?[a-z][^>]{0,80}>", re.I)
REPEAT_RE = re.compile(r"(.)\1{8,}")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
NON_WORD_RE = re.compile(r"[^\w\s'-]+", re.UNICODE)
WS_RE = re.compile(r"\s+")

ENGLISH_FUNCTION_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "to", "of", "and", "in",
    "that", "it", "for", "on", "with", "as", "this", "by", "from", "or", "at",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFC", str(value))
    text = text.replace("\ufeff", "")
    text = WS_RE.sub(" ", text).strip()
    return text


def normalize_word(value: str | None) -> str:
    text = normalize_text(value).lower()
    text = NON_WORD_RE.sub(" ", text)
    return WS_RE.sub(" ", text).strip()


def pair_key(english: str, zomi: str) -> str:
    return hashlib.sha1(f"{normalize_word(english)}\t{normalize_word(zomi)}".encode("utf-8")).hexdigest()


def english_family_key(english: str) -> str:
    return hashlib.sha1(normalize_word(english).encode("utf-8")).hexdigest()


def dataset_split_for(english: str) -> str:
    """Hash split on normalized English to reduce sentence-family leakage."""
    digest = hashlib.sha1(normalize_word(english).encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    if bucket < 90:
        return "train"
    if bucket < 95:
        return "validation"
    return "test"


def quality_flags(source: str, target: str) -> list[str]:
    flags: list[str] = []
    if not source or not target:
        flags.append("empty")
        return flags
    if source == target:
        flags.append("identical")
    if CONTROL_RE.search(source) or CONTROL_RE.search(target):
        flags.append("invalid_unicode")
    if HTML_RE.search(source) or HTML_RE.search(target):
        flags.append("html_or_script")
    if REPEAT_RE.search(source) or REPEAT_RE.search(target):
        flags.append("suspicious_repeat")
    src_words = source.split()
    tgt_words = target.split()
    if len(src_words) <= 1 and len(tgt_words) <= 1:
        flags.append("extremely_short")
    if len(source) > 600 or len(target) > 600 or len(src_words) > 80 or len(tgt_words) > 80:
        flags.append("extremely_long")
    tgt_tokens = [t.lower() for t in NON_WORD_RE.sub(" ", target).split() if t]
    if tgt_tokens:
        function_ratio = sum(1 for t in tgt_tokens if t in ENGLISH_FUNCTION_WORDS) / len(tgt_tokens)
        if function_ratio >= 0.45 and target.isascii():
            flags.append("possible_language_mismatch")
    return flags


def quality_score(flags: list[str]) -> float:
    penalties = {
        "empty": 1.0,
        "identical": 0.7,
        "invalid_unicode": 0.6,
        "html_or_script": 0.6,
        "suspicious_repeat": 0.5,
        "possible_language_mismatch": 0.35,
        "extremely_long": 0.2,
        "extremely_short": 0.15,
    }
    score = 1.0
    for flag in flags:
        score -= penalties.get(flag, 0.1)
    return round(max(0.0, score), 3)


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=OFF")
    con.execute("PRAGMA temp_store=MEMORY")
    con.execute("PRAGMA cache_size=-200000")
    return con


def create_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE dataset_versions (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            script_version TEXT NOT NULL,
            source_files TEXT NOT NULL
        );

        CREATE TABLE dictionary_entries (
            id INTEGER PRIMARY KEY,
            source_word TEXT NOT NULL,
            normalized_word TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'en',
            dialect TEXT,
            part_of_speech TEXT,
            part_of_speech_full TEXT,
            definition TEXT,
            pronunciation TEXT,
            usage_notes TEXT,
            source TEXT,
            source_reference TEXT,
            confidence REAL,
            verification_status TEXT NOT NULL,
            flagged INTEGER NOT NULL DEFAULT 0,
            suggested_correction TEXT,
            letter TEXT,
            version TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX idx_dict_normalized ON dictionary_entries(normalized_word);
        CREATE INDEX idx_dict_letter ON dictionary_entries(letter);
        CREATE INDEX idx_dict_status ON dictionary_entries(verification_status);

        CREATE VIRTUAL TABLE dictionary_fts USING fts5(
            source_word,
            definition,
            part_of_speech,
            tokenize = 'unicode61 remove_diacritics 2'
        );

        CREATE TABLE parallel_sentences (
            id INTEGER PRIMARY KEY,
            raw_source_text TEXT NOT NULL,
            raw_target_text TEXT NOT NULL,
            normalized_source_text TEXT NOT NULL,
            normalized_target_text TEXT NOT NULL,
            source_language TEXT NOT NULL DEFAULT 'en',
            target_language TEXT NOT NULL DEFAULT 'zom',
            source TEXT,
            source_reference TEXT,
            model TEXT,
            quality_flags TEXT,
            quality_score REAL,
            verified INTEGER NOT NULL DEFAULT 0,
            dataset_split TEXT NOT NULL,
            pair_hash TEXT NOT NULL,
            family_hash TEXT NOT NULL,
            version TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX idx_parallel_split ON parallel_sentences(dataset_split);
        CREATE INDEX idx_parallel_hash ON parallel_sentences(pair_hash);
        CREATE INDEX idx_parallel_family ON parallel_sentences(family_hash);
        CREATE INDEX idx_parallel_score ON parallel_sentences(quality_score);

        CREATE VIRTUAL TABLE parallel_fts USING fts5(
            normalized_source_text,
            normalized_target_text,
            tokenize = 'unicode61 remove_diacritics 2'
        );
        """
    )


def ingest_master_dictionary(con: sqlite3.Connection, path: Path, created_at: str) -> dict:
    try:
        import openpyxl
    except ImportError:
        sys.exit("openpyxl is required. Run: python3 -m pip install -r ml_pipeline/requirements.txt")

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    if "Master Data" not in wb.sheetnames:
        sys.exit(f"Expected sheet 'Master Data' in {path}")
    ws = wb["Master Data"]

    stats: Counter[str] = Counter()
    rows_out: list[tuple] = []
    fts_out: list[tuple] = []
    next_id = 1

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        stats["source_rows"] += 1
        source_id, letter, headword, pos, pos_full, definition, flagged, suggestion = (list(row) + [None] * 8)[:8]
        word = normalize_text(headword)
        if not word:
            stats["empty_headword"] += 1
            continue
        flagged_yes = str(flagged or "").strip().lower() in {"yes", "y", "true", "1"}
        definition_text = normalize_text(definition)
        status = "needs_review" if flagged_yes else "unreviewed"
        if flagged_yes:
            stats["flagged"] += 1
        if not definition_text:
            stats["empty_definition"] += 1
        rows_out.append(
            (
                next_id,
                word,
                normalize_word(word),
                "en",
                None,
                normalize_text(pos),
                normalize_text(pos_full),
                definition_text,
                None,
                None,
                "Zomi Standard Dictionary",
                f"master_id:{source_id}",
                0.4 if flagged_yes else 0.7,
                status,
                1 if flagged_yes else 0,
                normalize_text(suggestion),
                (str(letter).strip().upper()[:1] if letter else word[:1].upper()),
                DATASET_VERSION,
                created_at,
            )
        )
        fts_out.append((word, definition_text or "", normalize_text(pos) or ""))
        next_id += 1

    wb.close()
    con.executemany(
        """
        INSERT INTO dictionary_entries (
            id, source_word, normalized_word, language, dialect, part_of_speech,
            part_of_speech_full, definition, pronunciation, usage_notes, source,
            source_reference, confidence, verification_status, flagged,
            suggested_correction, letter, version, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        rows_out,
    )
    con.executemany(
        "INSERT INTO dictionary_fts (source_word, definition, part_of_speech) VALUES (?,?,?)",
        fts_out,
    )
    stats["ingested"] = len(rows_out)
    stats["next_id"] = next_id
    con.commit()
    return dict(stats)


def ingest_parallel(con: sqlite3.Connection, path: Path, created_at: str) -> dict:
    if not path.exists():
        sys.exit(f"Parallel corpus not found: {path}")

    csv.field_size_limit(min(sys.maxsize, 8_000_000))
    stats: Counter[str] = Counter()
    seen_hashes: set[str] = set()
    batch_rows: list[tuple] = []
    batch_fts: list[tuple] = []
    next_id = 1
    split_counts: Counter[str] = Counter()
    flag_counts: Counter[str] = Counter()
    model_counts: Counter[str] = Counter()

    insert_sql = """
        INSERT INTO parallel_sentences (
            id, raw_source_text, raw_target_text, normalized_source_text,
            normalized_target_text, source_language, target_language, source,
            source_reference, model, quality_flags, quality_score, verified,
            dataset_split, pair_hash, family_hash, version, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """

    def flush() -> None:
        if not batch_rows:
            return
        con.executemany(insert_sql, batch_rows)
        con.executemany(
            "INSERT INTO parallel_fts (normalized_source_text, normalized_target_text) VALUES (?,?)",
            batch_fts,
        )
        batch_rows.clear()
        batch_fts.clear()

    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        expected = {"en", "zomi"}
        if not reader.fieldnames or not expected.issubset(set(reader.fieldnames)):
            sys.exit(f"Unexpected CSV columns: {reader.fieldnames}")

        for row in reader:
            stats["source_rows"] += 1
            raw_en = str(row.get("en") or "")
            raw_zom = str(row.get("zomi") or "")
            en = normalize_text(raw_en)
            zom = normalize_text(raw_zom)
            if not en or not zom:
                stats["empty"] += 1
                continue
            digest = pair_key(en, zom)
            if digest in seen_hashes:
                stats["duplicates"] += 1
                continue
            seen_hashes.add(digest)

            flags = quality_flags(en, zom)
            score = quality_score(flags)
            for flag in flags:
                flag_counts[flag] += 1
            if flags:
                stats["flagged_rows"] += 1
            else:
                stats["clean_rows"] += 1

            split = dataset_split_for(en)
            split_counts[split] += 1
            model = normalize_text(row.get("model"))
            if model:
                model_counts[model] += 1
            worker = normalize_text(row.get("worker"))

            batch_rows.append(
                (
                    next_id,
                    raw_en,
                    raw_zom,
                    en,
                    zom,
                    "en",
                    "zom",
                    "OPUS/Tatoeba + Gemini machine translation",
                    worker,
                    model,
                    json.dumps(flags, ensure_ascii=False),
                    score,
                    0,
                    split,
                    digest,
                    english_family_key(en),
                    DATASET_VERSION,
                    created_at,
                )
            )
            batch_fts.append((en, zom))
            next_id += 1

            if len(batch_rows) >= 10_000:
                flush()
                con.commit()
                if stats["source_rows"] % 100_000 == 0:
                    print(f"  parallel rows scanned: {stats['source_rows']:,}", flush=True)

    flush()
    con.commit()
    stats["ingested"] = next_id - 1
    return {
        "counts": dict(stats),
        "splits": dict(split_counts),
        "flags": dict(flag_counts),
        "models": dict(model_counts),
    }


def export_evaluation_samples(con: sqlite3.Connection) -> None:
    EVAL_TRANSLATION.parent.mkdir(parents=True, exist_ok=True)
    EVAL_DICTIONARY.parent.mkdir(parents=True, exist_ok=True)

    translation_rows = con.execute(
        """
        SELECT id, normalized_source_text, normalized_target_text, dataset_split,
               quality_score, quality_flags, model, source_reference
        FROM parallel_sentences
        WHERE dataset_split = 'test' AND quality_score >= 0.8
        ORDER BY id
        LIMIT 400
        """
    ).fetchall()
    with EVAL_TRANSLATION.open("w", encoding="utf-8") as handle:
        for row in translation_rows:
            handle.write(
                json.dumps(
                    {
                        "id": row[0],
                        "english": row[1],
                        "zomi": row[2],
                        "split": row[3],
                        "quality_score": row[4],
                        "quality_flags": json.loads(row[5] or "[]"),
                        "model": row[6],
                        "source_reference": row[7],
                        "verified": False,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    dictionary_rows = con.execute(
        """
        SELECT id, source_word, part_of_speech, definition, verification_status, source, flagged
        FROM dictionary_entries
        WHERE definition IS NOT NULL AND definition != ''
        ORDER BY id
        LIMIT 200
        """
    ).fetchall()
    with EVAL_DICTIONARY.open("w", encoding="utf-8") as handle:
        for row in dictionary_rows:
            handle.write(
                json.dumps(
                    {
                        "id": row[0],
                        "headword": row[1],
                        "part_of_speech": row[2],
                        "definition": row[3],
                        "verification_status": row[4],
                        "source": row[5],
                        "flagged": bool(row[6]),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DB)
    parser.add_argument("--limit-parallel", type=int, default=0, help="Optional cap for tests")
    args = parser.parse_args()

    dictionary_xlsx = args.raw / "dictionary" / "Zomi_Standard_Dictionary_AI_Cleaned.xlsx"
    parallel_csv = args.raw / "parallel" / "zomi_english_sentences.csv"

    if not dictionary_xlsx.exists():
        sys.exit(f"Dictionary workbook not found: {dictionary_xlsx}")

    created_at = utc_now()
    print("Building Siamsil language database…")
    con = connect(args.out)
    create_schema(con)

    print("Ingesting dictionary master…")
    dict_stats = ingest_master_dictionary(con, dictionary_xlsx, created_at)
    print(f"  master entries: {dict_stats.get('ingested', 0):,}")

    print("Ingesting parallel corpus (this can take a few minutes)…")
    parallel_stats = ingest_parallel(con, parallel_csv, created_at)
    print(f"  unique pairs kept: {parallel_stats['counts'].get('ingested', 0):,}")

    source_files = {
        "dictionary_master": str(dictionary_xlsx.relative_to(ROOT)),
        "parallel_csv": str(parallel_csv.relative_to(ROOT)),
    }
    con.execute(
        """
        INSERT INTO dataset_versions (name, version, created_at, script_version, source_files)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("siamsil-language", DATASET_VERSION, created_at, SCRIPT_VERSION, json.dumps(source_files)),
    )

    dict_total = con.execute("SELECT COUNT(*) FROM dictionary_entries").fetchone()[0]
    parallel_total = con.execute("SELECT COUNT(*) FROM parallel_sentences").fetchone()[0]
    flagged_dict = con.execute("SELECT COUNT(*) FROM dictionary_entries WHERE flagged = 1").fetchone()[0]
    verified_dict = con.execute(
        "SELECT COUNT(*) FROM dictionary_entries WHERE verification_status = 'verified'"
    ).fetchone()[0]

    report = {
        "generated_at": created_at,
        "script_version": SCRIPT_VERSION,
        "dataset_version": DATASET_VERSION,
        "dictionary": {
            "source_rows": dict_stats.get("source_rows"),
            "ingested": dict_total,
            "flagged_for_review": flagged_dict,
            "verified": verified_dict,
            "empty_headword": dict_stats.get("empty_headword", 0),
            "empty_definition": dict_stats.get("empty_definition", 0),
            "note": "Zomi Standard Dictionary is the sole dictionary source.",
        },
        "parallel": {
            "source_rows": parallel_stats["counts"].get("source_rows"),
            "unique_pairs_kept": parallel_total,
            "duplicates_dropped": parallel_stats["counts"].get("duplicates", 0),
            "empty_dropped": parallel_stats["counts"].get("empty", 0),
            "clean": parallel_stats["counts"].get("clean_rows", 0),
            "needs_review": parallel_stats["counts"].get("flagged_rows", 0),
            "verified": 0,
            "splits": parallel_stats["splits"],
            "quality_flags": parallel_stats["flags"],
            "models": parallel_stats["models"],
            "note": "Zomi side is machine-translated and unverified. Do not treat as gold data.",
        },
    }

    DEFAULT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    DEFAULT_MANIFEST.write_text(
        json.dumps(
            {
                "name": "siamsil-language",
                "version": DATASET_VERSION,
                "created_at": created_at,
                "script_version": SCRIPT_VERSION,
                "database": str(args.out.relative_to(ROOT)),
                "counts": {
                    "dictionary_entries": dict_total,
                    "parallel_sentences": parallel_total,
                },
                "source_files": source_files,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("Exporting evaluation samples…")
    export_evaluation_samples(con)
    con.commit()
    try:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except sqlite3.OperationalError:
        pass
    con.close()

    print(f"Wrote {args.out}")
    print(f"Wrote {DEFAULT_REPORT}")
    print(
        "Dataset quality report\n"
        f"  Dictionary entries: {dict_total:,}\n"
        f"  Flagged dictionary rows: {flagged_dict:,}\n"
        f"  Parallel source rows: {report['parallel']['source_rows']:,}\n"
        f"  Unique pairs kept: {parallel_total:,}\n"
        f"  Duplicates dropped: {report['parallel']['duplicates_dropped']:,}\n"
        f"  Verified parallel pairs: 0\n"
    )


if __name__ == "__main__":
    main()
