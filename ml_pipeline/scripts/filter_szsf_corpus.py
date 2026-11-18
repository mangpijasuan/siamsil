#!/usr/bin/env python3
"""Filter an SZSF master file into a filtered set, a quarantine, a review queue and a re-audit sample.

This only sorts rows. It never changes a record's text, tier, review status or split, and it never deletes
the input. "Filtered" does not mean reviewed: every kept row is still unreviewed machine Zomi.

  python3 ml_pipeline/scripts/filter_szsf_corpus.py \
      --input ../siamsil-data/szsf/szsf-master-v1.1.0.jsonl.gz --out-dir ../siamsil-data/szsf/filtered-v1.1.0

Outputs, all in --out-dir:
  szsf-filtered.jsonl        kept rows, unchanged, with a manifest (szsf-filtered.manifest.json)
  quarantine.jsonl           rows left out, each as {"id", "reasons", "record"}
  review-queue.jsonl         kept rows that carry a soft flag, as {"id", "reasons"}
  reaudit-sample.jsonl       a ranked sample of kept rows from older or unknown models, {"id", "model", "priority"}
  summary.json               counts per reason

Rows are quarantined for a HARD reason: an empty side, English copied as Zomi, or a quality flag that means the
pair is probably wrong (html_or_script, number_mismatch, possible_language_mismatch, identical, suspicious_repeat).
SOFT flags (length_ratio_outlier, extremely_short, extremely_long, target_reused) keep the row and add it to the
review queue, because a short or differently sized sentence is often correct.

Duplicates: within a split, an exact (english, zomi_standard) pair is kept once, the one with the highest
quality_score. A train pair identical to a validation or test pair is dropped, so held-out text never leaks.

The corpus is `blocked` in data/rights.json (docs/DATA_RIGHTS.md): keep every output in the private data
repository, never in the public one. Outputs under data/raw are refused.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import heapq
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent))
import szsf  # type: ignore  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
HARD_FLAGS = {"html_or_script", "number_mismatch", "possible_language_mismatch", "identical", "suspicious_repeat"}
SOFT_FLAGS = {"length_ratio_outlier", "extremely_short", "extremely_long", "target_reused"}
OLD_MODELS = {"gemini-pro", "unknown", "", None}
HELD_OUT = {"validation", "test"}
DEFAULT_SAMPLE = 5000


def digest(*parts: str) -> bytes:
    return hashlib.blake2b("\x1f".join(parts).encode("utf-8"), digest_size=12).digest()


def open_text(path: Path):
    return gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open("r", encoding="utf-8")


def read_rows(path: Path) -> Iterator[dict]:
    with open_text(path) as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def texts(row: dict) -> tuple[str, str]:
    return (row.get("english") or "").strip(), (row.get("zomi_standard") or "").strip()


def hard_reasons(row: dict) -> list[str]:
    english, zomi = texts(row)
    reasons = []
    if not english:
        reasons.append("empty_english")
    if not zomi:
        reasons.append("empty_zomi")
    if english and zomi and english.lower() == zomi.lower():
        reasons.append("english_copied_as_zomi")
    reasons += sorted(set(row.get("quality_flags") or []) & HARD_FLAGS)
    return reasons


def soft_reasons(row: dict) -> list[str]:
    return sorted(set(row.get("quality_flags") or []) & SOFT_FLAGS)


def score(row: dict) -> float:
    value = row.get("quality_score")
    return float(value) if isinstance(value, (int, float)) else 0.0


def plan(path: Path) -> tuple[dict[tuple[str, bytes], tuple[float, str]], set[bytes], Counter]:
    """Pass 1: the best row per (split, pair) among rows that are not quarantined, and the held-out pairs."""
    best: dict[tuple[str, bytes], tuple[float, str]] = {}
    held_out: set[bytes] = set()
    stats: Counter = Counter()
    for row in read_rows(path):
        stats["read"] += 1
        if hard_reasons(row):
            continue
        split = row.get("split", "")
        key = (split, digest(*texts(row)))
        current = best.get(key)
        if current is None or score(row) > current[0]:
            best[key] = (score(row), row["id"])
        if split in HELD_OUT:
            held_out.add(key[1])
    return best, held_out, stats


class AtomicOut:
    """Write to a temporary file and move it into place only when it is complete."""

    def __init__(self, path: Path):
        self.path = path
        fd, self.temp = tempfile.mkstemp(prefix=path.name + ".", suffix=".part", dir=path.parent)
        self.handle = os.fdopen(fd, "w", encoding="utf-8")

    def write(self, obj: dict) -> None:
        self.handle.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def commit(self) -> None:
        self.handle.close()
        os.replace(self.temp, self.path)

    def abort(self) -> None:
        self.handle.close()
        if os.path.exists(self.temp):
            os.remove(self.temp)


def run(input_path: Path, out_dir: Path, sample_size: int = DEFAULT_SAMPLE, rights: dict | None = None) -> dict:
    raw = (ROOT / "data" / "raw").resolve()
    if raw in out_dir.resolve().parents or out_dir.resolve() == raw:
        raise SystemExit("refusing to write under data/raw")
    out_dir.mkdir(parents=True, exist_ok=True)

    best, held_out, stats = plan(input_path)
    seen: set[tuple[str, bytes]] = set()
    sample: list[tuple[tuple[int, float], str, str]] = []  # a heap of the sample_size best candidates

    outs = {name: AtomicOut(out_dir / name) for name in
            ("szsf-filtered.jsonl", "quarantine.jsonl", "review-queue.jsonl", "reaudit-sample.jsonl")}
    try:
        for row in read_rows(input_path):
            reasons = hard_reasons(row)
            split = row.get("split", "")
            pair = digest(*texts(row))
            key = (split, pair)
            if not reasons:
                if split == "train" and pair in held_out:
                    reasons = ["duplicate_of_held_out_pair"]
                elif best.get(key, (0, row["id"]))[1] != row["id"] or key in seen:
                    reasons = ["duplicate_pair"]
            if reasons:
                outs["quarantine.jsonl"].write({"id": row["id"], "reasons": reasons, "record": row})
                for reason in reasons:
                    stats[f"quarantined:{reason}"] += 1
                stats["quarantined"] += 1
                continue
            seen.add(key)
            soft = soft_reasons(row)
            outs["szsf-filtered.jsonl"].write(row)
            stats["kept"] += 1
            if soft:
                outs["review-queue.jsonl"].write({"id": row["id"], "reasons": soft})
                stats["review_queue"] += 1
                for reason in soft:
                    stats[f"soft:{reason}"] += 1
            if row.get("model") in OLD_MODELS and sample_size > 0:
                # Most in need of review first: more soft flags, then lower quality score.
                item = ((len(soft), -score(row)), row["id"], str(row.get("model")))
                if len(sample) < sample_size:
                    heapq.heappush(sample, item)
                elif item > sample[0]:
                    heapq.heapreplace(sample, item)
        for priority, row_id, model in sorted(sample, reverse=True):
            outs["reaudit-sample.jsonl"].write({"id": row_id, "model": model, "priority": list(priority)})
        stats["reaudit_sample"] = len(sample)
        for out in outs.values():
            out.commit()
    except BaseException:
        for out in outs.values():
            out.abort()
        raise

    filtered = out_dir / "szsf-filtered.jsonl"
    manifest = szsf.build_manifest(filtered, rights)
    manifest["note"] = (manifest["note"] + " Filtered from "
                        f"{input_path.name}: rows were sorted, never edited. Filtered does not mean reviewed.")
    summary = dict(sorted(stats.items()))
    (out_dir / "szsf-filtered.manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, required=True, help="SZSF master (.jsonl or .jsonl.gz)")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--sample", type=int, default=DEFAULT_SAMPLE, help="size of the re-audit sample (default 5000)")
    parser.add_argument("--rights", type=Path, default=szsf.DEFAULT_RIGHTS)
    args = parser.parse_args(argv)
    summary = run(args.input, args.out_dir, args.sample, szsf.load_rights(args.rights))
    for key, value in summary.items():
        print(f"{key}: {value:,}")
    print("Note: the corpus is blocked in data/rights.json. Keep these files in the private data repository.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
