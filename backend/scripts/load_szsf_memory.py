"""Load an SZSF master file into PostgreSQL as an internal translation-memory table.

Internal use only. Every row keeps its tier, origin, review status and
provider_derived flag, so nothing machine-generated can be mistaken for
reviewed Zomi. This script does not expose anything over HTTP; see
docs/DATA_RIGHTS.md before any external use of these rows.

    python backend/scripts/load_szsf_memory.py --file szsf-master-v1.1.0.jsonl.gz \
        --dsn postgresql://user:pass@localhost/siamsil_local [--limit 20000]
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import sys

import psycopg

DDL = """
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE TABLE IF NOT EXISTS szsf_entries (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    english TEXT NOT NULL,
    zomi TEXT NOT NULL,
    zomi_standard TEXT NOT NULL,
    standard_version TEXT,
    tier TEXT NOT NULL,
    split TEXT,
    quality_score DOUBLE PRECISION,
    source TEXT,
    origin TEXT,
    review_status TEXT NOT NULL DEFAULT 'UNREVIEWED',
    provider_derived BOOLEAN NOT NULL DEFAULT FALSE
);
"""
INDEXES = """
CREATE INDEX IF NOT EXISTS idx_szsf_en_trgm ON szsf_entries USING gin (english gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_szsf_zo_trgm ON szsf_entries USING gin (zomi_standard gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_szsf_en_lower ON szsf_entries (lower(english));
"""
COLS = ("id", "kind", "english", "zomi", "zomi_standard", "standard_version", "tier",
        "split", "quality_score", "source", "origin", "review_status", "provider_derived")


def rows(path: str, limit: int | None):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        for n, line in enumerate(fh):
            if limit is not None and n >= limit:
                return
            r = json.loads(line)
            review = r.get("review")
            status = review.get("status") if isinstance(review, dict) else review
            yield (r["id"], r["kind"], r["english"], r["zomi"], r["zomi_standard"],
                   r.get("standard_version"), r["tier"], r.get("split"),
                   r.get("quality_score"), r.get("source"), r.get("origin"),
                   status or "UNREVIEWED", bool(r.get("provider_derived")))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--replace", action="store_true", help="truncate the table first")
    a = ap.parse_args()
    with psycopg.connect(a.dsn) as conn:
        conn.execute(DDL)
        if a.replace:
            conn.execute("TRUNCATE szsf_entries")
        total = 0
        with conn.cursor() as cur, cur.copy(
            f"COPY szsf_entries ({', '.join(COLS)}) FROM STDIN"
        ) as cp:
            for row in rows(a.file, a.limit):
                cp.write_row(row)
                total += 1
        conn.execute(INDEXES)
        conn.execute("ANALYZE szsf_entries")
    print(f"loaded {total} rows", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
