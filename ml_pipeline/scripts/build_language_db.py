#!/usr/bin/env python3
"""Build the Siamsil language database from immutable raw files.

Reads:
  data/raw/dictionary/Zomi_Standard_Dictionary_AI_Cleaned.xlsx
  data/raw/parallel/zomi_english_sentences.csv

Optionally reads human evaluation sets (--eval) so matching pairs are held out.

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
import math
import re
import sqlite3
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_VERSION = "1.1.0"
DATASET_VERSION = "v2"

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW = ROOT / "data" / "raw"
DEFAULT_OUT_DB = ROOT / "data" / "processed" / "language" / "siamsil_language.sqlite"
DEFAULT_REPORT = ROOT / "data" / "processed" / "language" / "quality_report.json"
DEFAULT_MANIFEST = ROOT / "data" / "processed" / "language" / "manifest.json"
DEFAULT_VERSIONS = ROOT / "data" / "versions"
EVAL_TRANSLATION = ROOT / "data" / "evaluation" / "translation" / "sample.jsonl"
EVAL_DICTIONARY = ROOT / "data" / "evaluation" / "dictionary" / "sample.jsonl"

HTML_RE = re.compile(r"<(script|style|iframe|object|embed|link|meta)\b|</?[a-z][^>]{0,80}>", re.I)
REPEAT_RE = re.compile(r"(.)\1{8,}")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
NON_WORD_RE = re.compile(r"[^\w\s'-]+", re.UNICODE)
WS_RE = re.compile(r"\s+")
WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
DIGITS_RE = re.compile(r"\d+")

RATIO_MIN_CHARS = 20
RATIO_OUTLIER_FRACTION = 0.005  # flag this share of pairs at each end of the length-ratio range
TARGET_REUSE_MIN_FAMILIES = 3
EVAL_HOLDOUT_SPLIT = "eval_holdout"

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
    return split_for_key(hashlib.sha1(normalize_word(english).encode("utf-8")).hexdigest())


def split_for_key(digest: str) -> str:
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


def name_tokens(english_sentences, min_count: int = 5, min_share: float = 0.9) -> set[str]:
    """Learn proper names from the English side itself.

    A word counts as a name when, away from the start of a sentence, it is
    capitalized at least min_count times and in at least min_share of its uses.
    Returns lowercase forms.
    """
    capitalized: Counter[str] = Counter()
    lowercase: Counter[str] = Counter()
    for sentence in english_sentences:
        for token in WORD_RE.findall(sentence)[1:]:
            if len(token) < 2 or not token.isalpha():
                continue
            if token[0].isupper():
                capitalized[token.lower()] += 1
            elif token.islower():
                lowercase[token] += 1
    return {
        word
        for word, count in capitalized.items()
        if count >= min_count and count >= min_share * (count + lowercase[word])
    }


def template_key(english: str, names: set[str]) -> str:
    """Hash of the English with names and numbers masked.

    "Tom is 30." and "Mary is 25." share a key, so template variants land in
    the same split instead of leaking across train and test.
    """
    tokens = []
    for token in WORD_RE.findall(normalize_text(english)):
        lower = token.lower()
        if lower in names:
            tokens.append("<name>")
        elif DIGITS_RE.fullmatch(token):
            tokens.append("<num>")
        else:
            tokens.append(lower)
    return hashlib.sha1(" ".join(tokens).encode("utf-8")).hexdigest()


def number_mismatch(source: str, target: str) -> bool:
    return sorted(DIGITS_RE.findall(source)) != sorted(DIGITS_RE.findall(target))


def length_log_ratio(source: str, target: str) -> float | None:
    """log(target chars / source chars), or None when either side is too short to judge."""
    if len(source) < RATIO_MIN_CHARS or len(target) < RATIO_MIN_CHARS:
        return None
    return math.log(len(target) / len(source))


def percentile(sorted_values: list[float], fraction: float) -> float:
    index = min(len(sorted_values) - 1, max(0, round(fraction * (len(sorted_values) - 1))))
    return sorted_values[index]


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
        "target_reused": 0.4,
        "number_mismatch": 0.3,
        "length_ratio_outlier": 0.25,
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
            template_hash TEXT,
            version TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX idx_parallel_split ON parallel_sentences(dataset_split);
        CREATE INDEX idx_parallel_hash ON parallel_sentences(pair_hash);
        CREATE INDEX idx_parallel_family ON parallel_sentences(family_hash);
        CREATE INDEX idx_parallel_template ON parallel_sentences(template_hash);
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


def apply_corpus_checks(con: sqlite3.Connection, eval_items: list[dict] | None = None, batch: int = 10_000) -> dict:
    """Second pass over ingested pairs: checks that need the whole corpus.

    - masks learned names and numbers to group template variants, and assigns
      the split by template family
    - flags numbers that differ between sides, length-ratio outliers relative
      to this corpus, and Zomi text reused for unrelated English sentences
    - moves pairs matching a human evaluation item to the eval_holdout split
    """
    from eval_set import item_texts

    def column(sql: str):
        return (row[0] for row in con.execute(sql))

    names = name_tokens(column("SELECT normalized_source_text FROM parallel_sentences"))

    ratios = sorted(
        ratio
        for ratio in (
            length_log_ratio(en, zom)
            for en, zom in con.execute(
                "SELECT normalized_source_text, normalized_target_text FROM parallel_sentences"
            )
        )
        if ratio is not None
    )
    bounds = (
        (percentile(ratios, RATIO_OUTLIER_FRACTION), percentile(ratios, 1 - RATIO_OUTLIER_FRACTION))
        if ratios
        else None
    )

    reused_targets = set(
        column(
            f"""
            SELECT normalized_target_text FROM parallel_sentences
            GROUP BY normalized_target_text
            HAVING COUNT(DISTINCT family_hash) >= {TARGET_REUSE_MIN_FAMILIES}
            """
        )
    )

    eval_english: set[str] = set()
    eval_zomi: set[str] = set()
    for item in eval_items or []:
        english, zomi = item_texts(item)
        eval_english.update(template_key(text, names) for text in english if normalize_word(text))
        eval_zomi.update(key for key in (normalize_word(text) for text in zomi) if key)

    splits: Counter[str] = Counter()
    flag_counts: Counter[str] = Counter()
    flagged = 0
    last_id = 0
    while True:
        rows = con.execute(
            """
            SELECT id, normalized_source_text, normalized_target_text, quality_flags
            FROM parallel_sentences WHERE id > ? ORDER BY id LIMIT ?
            """,
            (last_id, batch),
        ).fetchall()
        if not rows:
            break
        updates = []
        for row_id, en, zom, flags_json in rows:
            flags = json.loads(flags_json or "[]")
            extra = []
            if zom in reused_targets:
                extra.append("target_reused")
            if number_mismatch(en, zom):
                extra.append("number_mismatch")
            ratio = length_log_ratio(en, zom)
            if bounds and ratio is not None and not bounds[0] <= ratio <= bounds[1]:
                extra.append("length_ratio_outlier")
            flags += [flag for flag in extra if flag not in flags]

            key = template_key(en, names)
            if key in eval_english or normalize_word(zom) in eval_zomi:
                split = EVAL_HOLDOUT_SPLIT
            else:
                split = split_for_key(key)

            splits[split] += 1
            flag_counts.update(flags)
            flagged += bool(flags)
            updates.append((json.dumps(flags, ensure_ascii=False), quality_score(flags), key, split, row_id))
        con.executemany(
            """
            UPDATE parallel_sentences
            SET quality_flags = ?, quality_score = ?, template_hash = ?, dataset_split = ?
            WHERE id = ?
            """,
            updates,
        )
        con.commit()
        last_id = rows[-1][0]

    total = sum(splits.values())
    return {
        "splits": dict(splits),
        "flags": dict(flag_counts),
        "clean": total - flagged,
        "flagged": flagged,
        "template_families": con.execute(
            "SELECT COUNT(DISTINCT template_hash) FROM parallel_sentences"
        ).fetchone()[0],
        "largest_template_family": con.execute(
            "SELECT COALESCE(MAX(n), 0) FROM (SELECT COUNT(*) AS n FROM parallel_sentences GROUP BY template_hash)"
        ).fetchone()[0],
        "names_learned": len(names),
        "length_log_ratio_bounds": [round(b, 4) for b in bounds] if bounds else None,
        "eval_items_checked": len(eval_items or []),
    }


def file_fingerprint(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    try:
        shown = str(path.resolve().relative_to(ROOT))
    except ValueError:
        shown = path.name
    return {"path": shown, "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def release_manifest(
    database: Path,
    source_files: dict[str, Path],
    eval_files: list[Path],
    counts: dict,
    created_at: str,
) -> dict:
    """Describe a language release precisely enough to verify or reproduce it.

    Evaluation sets are recorded by hash only; their content stays hidden.
    """
    return {
        "name": "siamsil-language",
        "version": DATASET_VERSION,
        "created_at": created_at,
        "script_version": SCRIPT_VERSION,
        "database": file_fingerprint(database),
        "counts": counts,
        "source_files": {key: file_fingerprint(path) for key, path in source_files.items()},
        "evaluation_sets": [
            {"file": path.name, "sha256": file_fingerprint(path)["sha256"]} for path in eval_files
        ],
    }


def write_release_manifest(manifest: dict, current: Path, versions_dir: Path) -> Path:
    """Write the current manifest and an immutable copy named by version and database hash."""
    text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    current.parent.mkdir(parents=True, exist_ok=True)
    current.write_text(text, encoding="utf-8")
    versions_dir.mkdir(parents=True, exist_ok=True)
    versioned = versions_dir / f"siamsil-language-{manifest['version']}-{manifest['database']['sha256'][:12]}.json"
    versioned.write_text(text, encoding="utf-8")
    return versioned


def load_eval_items(paths: list[Path]) -> list[dict]:
    from eval_set import load_items

    items: list[dict] = []
    for path in paths:
        if not path.exists():
            sys.exit(f"Evaluation set not found: {path}")
        loaded, errors = load_items(path)
        if errors:
            sys.exit(f"Evaluation set {path} is not valid JSONL: {errors[0]}")
        items.extend(loaded)
    return items


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
    parser.add_argument(
        "--eval",
        type=Path,
        action="append",
        default=[],
        help="Human evaluation set (JSONL); matching corpus pairs go to the eval_holdout split. Repeatable.",
    )
    args = parser.parse_args()

    eval_items = load_eval_items(args.eval)

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

    print("Running whole-corpus checks (template families, alignment, evaluation holdout)…")
    checks = apply_corpus_checks(con, eval_items)
    print(f"  template families: {checks['template_families']:,}")
    print(f"  evaluation holdout pairs: {checks['splits'].get(EVAL_HOLDOUT_SPLIT, 0):,}")

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
            "clean": checks["clean"],
            "needs_review": checks["flagged"],
            "verified": 0,
            "splits": checks["splits"],
            "split_key": "template family (English with learned names and numbers masked)",
            "template_families": checks["template_families"],
            "largest_template_family": checks["largest_template_family"],
            "names_learned": checks["names_learned"],
            "length_log_ratio_bounds": checks["length_log_ratio_bounds"],
            "evaluation_items_checked": checks["eval_items_checked"],
            "quality_flags": checks["flags"],
            "models": parallel_stats["models"],
            "note": "Zomi side is machine-translated and unverified. Do not treat as gold data.",
        },
    }

    DEFAULT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Exporting evaluation samples…")
    export_evaluation_samples(con)
    con.commit()
    try:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except sqlite3.OperationalError:
        pass
    con.close()

    print("Hashing inputs and database for the release manifest…")
    manifest = release_manifest(
        database=args.out,
        source_files={"dictionary_master": dictionary_xlsx, "parallel_csv": parallel_csv},
        eval_files=args.eval,
        counts={"dictionary_entries": dict_total, "parallel_sentences": parallel_total},
        created_at=created_at,
    )
    version_file = write_release_manifest(manifest, DEFAULT_MANIFEST, DEFAULT_VERSIONS)

    print(f"Wrote {args.out}")
    print(f"Wrote {version_file}")
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
