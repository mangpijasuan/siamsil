#!/usr/bin/env python3
"""Cluster corpus pairs and order them for the owner's review, highest impact first (docs/REVIEW_QUEUES.md).

Reads SZSF rows (the filtered set from filter_szsf_corpus.py, or a master file) and writes a review queue that
`review_sample.py export-queue` reads unchanged, with each cluster's pairs next to each other in the sheet.

  python3 ml_pipeline/scripts/review_clusters.py \\
      --input ../siamsil-data/szsf/filtered-v1.1.0/szsf-filtered.jsonl \\
      --reviews ../siamsil-data/reviews/corpus-reviews.jsonl \\
      --near-scope ../siamsil-data/szsf/filtered-v1.1.0/review-queue.jsonl \\
      --out-dir ../siamsil-data/reviews/clusters-v1

Two kinds of cluster, both computed on this machine with no model or outside service:

  template  English that is the same once case, spacing, punctuation and numbers are set aside
            (build_language_db.template_key, the key that already keeps such sentences in one split).
            "I am 30 years old." and "I am 45 years old." are one template.
  near      English sentences that share most of their words and word pairs (MinHash, then an exact Jaccard
            check >= --near-threshold, default 0.7: about one word changed in a sentence of ten words or more),
            among the rows of --near-scope only, because this is the slow part. Grouped for context: their
            English differs, so their Zomi is expected to differ and does not count as inconsistent.

Each cluster gets a priority and the parts it is made of (all reported, so the order can be checked):

  frequency     log2(1 + pairs in the cluster)              one decision pattern covers many pairs
  inconsistency (distinct Zomi - 1) / (pairs - 1)           one English template translated several ways
                                                            (template clusters only; 0 for near clusters)
  uncertainty   mean over pairs of (1 - quality_score) + 0.5 per soft flag + 1 for an older or unknown model
  priority      2 * frequency + 3 * inconsistency + uncertainty

Queue order: the first --per-cluster pairs of each cluster (default 10: the representative, then the most
uncertain), cluster by cluster in priority order; then the single rows, most uncertain first; then the rest of
every cluster. Pairs that already have a review
decision (--reviews) are left out, and so are rows in held-out splits (validation, test) unless --include-held-out.

This only orders work. It changes no text, decides nothing, approves nothing and marks nothing as reviewed: the
owner still decides every pair (docs/GOVERNANCE.md). Outputs hold corpus ids and fingerprints, not sentence text,
except `clusters.jsonl`, which shows each cluster's English representative; the corpus is `blocked` in
data/rights.json, so keep every output in the private data repository.

Outputs, in --out-dir (private permissions):
  cluster-queue.jsonl   {"id", "english_sha256", "cluster", "rank"} in review order, for export-queue --ids
  clusters.jsonl        one line per cluster: id, kind, size, members, representative, zomi_variants, scores
  summary.json          counts and the parameters used
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_language_db import pair_key, template_key  # type: ignore  # noqa: E402
from filter_szsf_corpus import OLD_MODELS, SOFT_FLAGS, english_sha256, read_rows  # type: ignore  # noqa: E402

HELD_OUT = {"validation", "test", "excluded"}
WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
DIGITS = re.compile(r"\d+")
PERMUTATIONS = 32
BANDS = 16  # 16 bands of 2: a pair at Jaccard 0.6 shares a band with probability > 0.99; candidates are verified
MERSENNE = (1 << 61) - 1


class Row:
    """One queued pair, kept small: a full run holds about 1.8 million of these (Python 3.9 has no slots dataclass)."""

    __slots__ = ("id", "_sha", "zomi_key", "uncertainty")

    def __init__(self, id: str, sha: str, zomi_key: bytes, uncertainty: float) -> None:
        self.id, self._sha, self.zomi_key, self.uncertainty = id, bytes.fromhex(sha), zomi_key, uncertainty

    @property
    def sha(self) -> str:
        return self._sha.hex()


@dataclass
class Cluster:
    kind: str
    members: list[Row]
    representative: str = ""
    scores: dict[str, float] = field(default_factory=dict)


def uncertainty(row: dict) -> float:
    score = row.get("quality_score")
    value = 1 - float(score) if isinstance(score, (int, float)) and not isinstance(score, bool) else 1.0
    value += 0.5 * len(set(row.get("quality_flags") or []) & SOFT_FLAGS)
    if row.get("model") in OLD_MODELS:
        value += 1.0
    return round(value, 4)


def zomi_key(text: str) -> bytes:
    """The Zomi with case, spacing, punctuation and numbers set aside, to count distinct translations."""
    words = [DIGITS.sub("#", w.lower()) for w in WORD.findall(text or "")]
    return hashlib.blake2b(" ".join(words).encode("utf-8"), digest_size=8).digest()


def shingles(english: str) -> set[str]:
    """Words and word pairs. Pairs keep word order; words keep a one-word change from costing too much: in an
    n-word sentence one substituted word leaves an overlap of about (n - 2) / (n + 1)."""
    words = [DIGITS.sub("#", w.lower()) for w in WORD.findall(english or "")]
    return set(words) | {f"{a} {b}" for a, b in zip(words, words[1:])}


def _hash64(text: str) -> int:
    return int.from_bytes(hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest(), "big")


def _coefficients(seed: int = 20261119) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    return [(rng.randrange(1, MERSENNE), rng.randrange(0, MERSENNE)) for _ in range(PERMUTATIONS)]


COEFFICIENTS = _coefficients()


def minhash(items: set[str]) -> tuple[int, ...]:
    hashed = [_hash64(item) for item in items] or [0]
    return tuple(min((a * h + b) % MERSENNE for h in hashed) for a, b in COEFFICIENTS)


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a or b else 1.0


def decided_pairs(path: Path | None) -> set[str]:
    """Pair hashes that already have a review record (any decision): the owner has seen them."""
    if path is None or not path.exists():
        return set()
    import corpus_reviews  # type: ignore

    return {record["pair_hash"] for record in corpus_reviews.load(path)}


def read_scope(path: Path | None) -> set[str] | None:
    if path is None:
        return None
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            ids.add(str(json.loads(line)["id"]) if line.startswith("{") else line)
    return {i if i.startswith("corpus-") else f"corpus-{i}" for i in ids}


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        self.parent.setdefault(item, item)
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def near_clusters(candidates: dict[str, tuple[str, Row]], threshold: float) -> list[list[str]]:
    """Groups of ids whose English shares at least `threshold` of its word 2-grams (verified, not estimated)."""
    sets = {row_id: shingles(english) for row_id, (english, _) in candidates.items()}
    buckets: dict[tuple[int, tuple[int, ...]], list[str]] = defaultdict(list)
    width = PERMUTATIONS // BANDS
    for row_id, items in sets.items():
        if len(items) < 5:
            continue  # two or three words: too short to call a near duplicate
        signature = minhash(items)
        for band in range(BANDS):
            buckets[(band, signature[band * width:(band + 1) * width])].append(row_id)
    groups = _UnionFind()
    for members in buckets.values():
        if len(members) < 2 or len(members) > 500:
            continue  # a huge bucket is a generic phrase pattern, not a near-duplicate group
        first = members[0]
        for other in members[1:]:
            if jaccard(sets[first], sets[other]) >= threshold:
                groups.union(first, other)
    found: dict[str, list[str]] = defaultdict(list)
    for row_id in groups.parent:
        found[groups.find(row_id)].append(row_id)
    return [sorted(ids, key=_id_order) for ids in found.values() if len(ids) > 1]


def _id_order(row_id: str) -> tuple[int, str]:
    tail = row_id.removeprefix("corpus-")
    return (int(tail), "") if tail.isdigit() else (1 << 62, row_id)


def score_cluster(cluster: Cluster) -> None:
    size = len(cluster.members)
    variants = len({m.zomi_key for m in cluster.members})
    frequency = math.log2(1 + size)
    inconsistency = (variants - 1) / (size - 1) if size > 1 and cluster.kind == "template" else 0.0
    mean_uncertainty = sum(m.uncertainty for m in cluster.members) / size
    cluster.scores = {
        "frequency": round(frequency, 4),
        "inconsistency": round(inconsistency, 4),
        "uncertainty": round(mean_uncertainty, 4),
        "zomi_variants": variants,
        "priority": round(2 * frequency + 3 * inconsistency + mean_uncertainty, 4),
    }


def build(rows: Iterable[dict], *, decided: set[str] = frozenset(), include_held_out: bool = False,
          near_scope: set[str] | None = None, near_threshold: float = 0.7, min_size: int = 2
          ) -> tuple[list[Cluster], list[Row], Counter]:
    """Clusters (template, then near) and the remaining single rows, all scored. Each row is in at most one."""
    stats: Counter = Counter()
    by_template: dict[bytes, list[Row]] = defaultdict(list)
    english_of: dict[str, str] = {}
    for record in rows:
        stats["read"] += 1
        if record.get("split") in HELD_OUT and not include_held_out:
            stats["skipped_held_out"] += 1
            continue
        english, zomi = (record.get("english") or "").strip(), (record.get("zomi") or "").strip()
        if not english or not zomi:
            stats["skipped_empty"] += 1
            continue
        if pair_key(english, zomi) in decided:
            stats["skipped_already_reviewed"] += 1
            continue
        row = Row(str(record["id"]), english_sha256(record), zomi_key(record.get("zomi_standard") or zomi),
                  uncertainty(record))
        by_template[bytes.fromhex(template_key(english, set()))].append(row)
        if near_scope is not None and row.id in near_scope:
            english_of[row.id] = english
        stats["queued_rows"] += 1

    clusters: list[Cluster] = []
    singles: dict[str, Row] = {}
    for members in by_template.values():
        if len(members) >= min_size:
            clusters.append(Cluster("template", sorted(members, key=lambda m: _id_order(m.id))))
        else:
            for member in members:
                singles[member.id] = member

    if near_scope is not None:
        candidates = {i: (english_of[i], singles[i]) for i in english_of if i in singles}
        for ids in near_clusters(candidates, near_threshold):
            clusters.append(Cluster("near", [singles.pop(i) for i in ids]))

    for cluster in clusters:
        score_cluster(cluster)
        cluster.representative = max(cluster.members, key=lambda m: (m.uncertainty, -_id_order(m.id)[0])).id
        stats[f"clusters_{cluster.kind}"] += 1
        stats[f"rows_in_{cluster.kind}_clusters"] += len(cluster.members)
    clusters.sort(key=lambda c: (-c.scores["priority"], _id_order(c.members[0].id)))
    rest = sorted(singles.values(), key=lambda r: (-r.uncertainty, _id_order(r.id)))
    stats["single_rows"] = len(rest)
    return clusters, rest, stats


def queue_lines(clusters: list[Cluster], singles: list[Row], per_cluster: int = 10) -> Iterable[dict]:
    """Review order, in three parts:

    1. each cluster in priority order: its representative, then its most uncertain members, up to `per_cluster`
       (a template can hold tens of thousands of pairs; its first few show the pattern);
    2. the single rows, most uncertain first;
    3. the rest of every cluster, in the same cluster order.
    """
    rank = 0
    later: list[tuple[str, Row]] = []
    for number, cluster in enumerate(clusters, start=1):
        label = f"{cluster.kind}-{number:06d}"
        ordered = sorted(cluster.members, key=lambda m: (m.id != cluster.representative, -m.uncertainty,
                                                         _id_order(m.id)))
        for member in ordered[:per_cluster]:
            rank += 1
            yield {"id": member.id, "english_sha256": member.sha, "cluster": label, "rank": rank}
        later.extend((label, member) for member in ordered[per_cluster:])
    for row in singles:
        rank += 1
        yield {"id": row.id, "english_sha256": row.sha, "cluster": None, "rank": rank}
    for label, member in later:
        rank += 1
        yield {"id": member.id, "english_sha256": member.sha, "cluster": label, "rank": rank}


def _private_writer(path: Path):
    return open(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8")


def write_outputs(out_dir: Path, clusters: list[Cluster], singles: list[Row], stats: Counter,
                  representatives: dict[str, str], parameters: dict, per_cluster: int = 10) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(out_dir, 0o700)
    with _private_writer(out_dir / "cluster-queue.jsonl") as handle:
        for line in queue_lines(clusters, singles, per_cluster):
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    with _private_writer(out_dir / "clusters.jsonl") as handle:
        for number, cluster in enumerate(clusters, start=1):
            handle.write(json.dumps({
                "cluster": f"{cluster.kind}-{number:06d}", "kind": cluster.kind, "size": len(cluster.members),
                "representative": cluster.representative,
                "representative_english": representatives.get(cluster.representative, ""),
                "members": [m.id for m in cluster.members], **cluster.scores,
            }, ensure_ascii=False) + "\n")
    with _private_writer(out_dir / "summary.json") as handle:
        json.dump({"counts": dict(sorted(stats.items())), "parameters": parameters,
                   "note": "ordering only: nothing was reviewed, approved or changed"}, handle, indent=2)
        handle.write("\n")


def run(input_path: Path, out_dir: Path, *, reviews: Path | None = None, near_scope: Path | None = None,
        near_threshold: float = 0.7, include_held_out: bool = False, min_size: int = 2,
        per_cluster: int = 10) -> Counter:
    if "data/raw" in input_path.resolve().as_posix() or "data/raw" in out_dir.resolve().as_posix():
        raise ValueError("data/raw is never read or written by this tool")
    clusters, singles, stats = build(read_rows(input_path), decided=decided_pairs(reviews),
                                     include_held_out=include_held_out, near_scope=read_scope(near_scope),
                                     near_threshold=near_threshold, min_size=min_size)
    wanted = {c.representative for c in clusters}
    representatives = {str(r["id"]): r.get("english", "") for r in read_rows(input_path) if str(r["id"]) in wanted}
    write_outputs(out_dir, clusters, singles, stats, representatives, {
        "input": str(input_path), "reviews": str(reviews) if reviews else None,
        "near_scope": str(near_scope) if near_scope else None, "near_threshold": near_threshold,
        "include_held_out": include_held_out, "min_size": min_size, "per_cluster": per_cluster,
        "priority": "2*log2(1+size) + 3*(distinct_zomi-1)/(size-1) + mean uncertainty",
    }, per_cluster)
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, required=True, help="SZSF rows: szsf-filtered.jsonl or a master .gz")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, help="corpus-reviews.jsonl: pairs already reviewed are left out")
    parser.add_argument("--near-scope", type=Path, help="queue file (ids) to look for near duplicates in")
    parser.add_argument("--near-threshold", type=float, default=0.7)
    parser.add_argument("--min-size", type=int, default=2, help="smallest template cluster (default 2)")
    parser.add_argument("--include-held-out", action="store_true", help="also queue validation and test rows")
    parser.add_argument("--per-cluster", type=int, default=10, help="pairs per cluster in the first pass (default 10)")
    args = parser.parse_args(argv)
    if not 0 < args.near_threshold <= 1:
        parser.error("--near-threshold must be in (0, 1]")
    if args.per_cluster < 1:
        parser.error("--per-cluster must be at least 1")
    stats = run(args.input, args.out_dir, reviews=args.reviews, near_scope=args.near_scope,
                near_threshold=args.near_threshold, include_held_out=args.include_held_out, min_size=args.min_size,
                per_cluster=args.per_cluster)
    for key, value in sorted(stats.items()):
        print(f"{key}: {value:,}")
    print("Ordering only: nothing was reviewed or approved. The corpus is blocked in data/rights.json; "
          "keep these files in the private data repository.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
