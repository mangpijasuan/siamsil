#!/usr/bin/env python3
"""Summarize completed human decisions without pooling diagnostic oversamples."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from gold_test_workflow import read_jsonl

DECISIONS = {"approve", "edit", "reject", "uncertain"}


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    fraction = successes / total
    denominator = 1 + z * z / total
    center = (fraction + z * z / (2 * total)) / denominator
    spread = z * math.sqrt(fraction * (1 - fraction) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, center - spread), min(1.0, center + spread)


def summarize(packet_dir: Path, decisions_path: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(output)
    manifest = json.loads((packet_dir / "manifest.json").read_text(encoding="utf-8"))
    packets = {
        "uniform_random": read_jsonl(packet_dir / "random.jsonl"),
        "flagged_diagnostic": read_jsonl(packet_dir / "flagged.jsonl"),
    }
    for label, filename in (("random", "random.jsonl"), ("flagged", "flagged.jsonl")):
        digest = hashlib.sha256((packet_dir / filename).read_bytes()).hexdigest()
        if digest != manifest[label]["sha256"]:
            raise ValueError(f"Packet changed after sampling: {filename}")
    originals = {row["sentence_id"]: row for rows in packets.values() for row in rows}
    decisions: dict[int, dict] = {}
    for decision in read_jsonl(decisions_path):
        sentence_id = decision.get("sentence_id")
        if sentence_id not in originals or sentence_id in decisions:
            raise ValueError(f"Unknown or duplicate sentence ID: {sentence_id}")
        label = decision.get("decision")
        if label not in DECISIONS or not str(decision.get("reviewer_id", "")).strip():
            raise ValueError(f"Missing reviewer or invalid decision for {sentence_id}")
        if label == "edit" and not str(decision.get("corrected_zomi", "")).strip():
            raise ValueError(f"Edited row {sentence_id} needs corrected_zomi")
        if not isinstance(decision.get("error_tags", []), list):
            raise ValueError(f"error_tags must be a list for {sentence_id}")
        decisions[sentence_id] = decision
    if set(decisions) != set(originals):
        raise ValueError(f"Missing human decisions for {len(set(originals) - set(decisions))} sampled rows")
    if any(row["decision"] == "uncertain" for row in decisions.values()):
        raise ValueError("Resolve uncertain random and diagnostic decisions with an adjudicator first")

    result: dict = {
        "population": manifest["population"],
        "population_count": manifest["population_count"],
        "random_sample": {},
        "flagged_diagnostic": {},
        "interpretation": "Random-sample rates describe reviewer decisions on the training split, not verified model accuracy or legal approval. Flagged rows are excluded from prevalence estimates.",
    }
    random_rows = packets["uniform_random"]
    random_counts = Counter(decisions[row["sentence_id"]]["decision"] for row in random_rows)
    approved = random_counts["approve"]
    low, high = wilson_interval(approved, len(random_rows))
    by_model: dict[str, Counter] = defaultdict(Counter)
    for row in random_rows:
        by_model[row["model"] or "unknown"][decisions[row["sentence_id"]]["decision"]] += 1
    result["random_sample"] = {
        "n": len(random_rows), "decisions": dict(random_counts),
        "approve_without_edit_rate": approved / len(random_rows),
        "approve_without_edit_wilson_95": [low, high],
        "by_model": {model: {"n": sum(counts.values()), "decisions": dict(counts)} for model, counts in by_model.items()},
    }
    flagged_rows = packets["flagged_diagnostic"]
    result["flagged_diagnostic"] = {
        "n": len(flagged_rows),
        "decisions": dict(Counter(decisions[row["sentence_id"]]["decision"] for row in flagged_rows)),
    }
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-dir", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.packet_dir, args.decisions, args.output)
    print(f"Summarized {result['random_sample']['n']} random human reviews")
    print("Diagnostic flagged rows were not pooled into the prevalence estimate")


if __name__ == "__main__":
    main()
