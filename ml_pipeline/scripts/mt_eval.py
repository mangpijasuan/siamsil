#!/usr/bin/env python3
"""Translation evaluation harness: run systems on a human evaluation set, score, and gate.

Commands:
  translate --system retrieval --eval FILE --db DB --out HYP.jsonl
      Run a system over an evaluation set. Output lines: {"id", "hypothesis", "system"}.
  score --eval FILE --hyp HYP.jsonl [--hyp ...] --out RESULTS.json
      chrF++ and BLEU per system and per domain, 95% bootstrap intervals, and paired
      comparisons between every pair of systems.
  gate --results R1.json [--results R2.json] --candidate NAME --baseline NAME [--baseline ...]
      Pass only if the candidate beats every baseline on chrF++ in every results file
      with paired-bootstrap p < 0.05. Human evaluation is still required after this gate.

Only the human evaluation sets in docs/EVALUATION_SET.md are valid inputs. The parallel
corpus test split is machine-generated and must not be used to claim quality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
from sacrebleu.metrics import BLEU, CHRF

from build_language_db import EVAL_HOLDOUT_SPLIT, ROOT
from eval_set import load_items, validate_items

sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "services"))
from language_engine import fts_match  # noqa: E402

PRIMARY = "chrf++"
SIGNIFICANCE = 0.05


def metrics() -> dict:
    return {"chrf++": CHRF(word_order=2), "bleu": BLEU()}


# --- systems -----------------------------------------------------------------


def retrieval_translate(con: sqlite3.Connection, text: str, direction: str) -> str:
    """Baseline: the best-scoring corpus pair whose source side matches, as the app does today.

    Pairs held out for evaluation are excluded, otherwise the baseline could return
    the evaluation item's own pair.
    """
    source_col, target_col = (
        ("normalized_source_text", "normalized_target_text")
        if direction == "en-zomi"
        else ("normalized_target_text", "normalized_source_text")
    )
    row = con.execute(
        f"""
        SELECT {target_col} FROM parallel_sentences
        WHERE lower({source_col}) = lower(?) AND dataset_split != ?
        ORDER BY quality_score DESC, id LIMIT 1
        """,
        (text.strip(), EVAL_HOLDOUT_SPLIT),
    ).fetchone()
    if row:
        return row[0]
    match = fts_match(text)
    if not match:
        return ""
    fts_column = "normalized_source_text" if direction == "en-zomi" else "normalized_target_text"
    row = con.execute(
        f"""
        SELECT p.{target_col}
        FROM parallel_fts JOIN parallel_sentences p ON p.id = parallel_fts.rowid
        WHERE parallel_fts MATCH ? AND p.quality_score >= 0.5 AND p.dataset_split != ?
        ORDER BY bm25(parallel_fts), p.quality_score DESC, p.id LIMIT 1
        """,
        (f"{fts_column}: ({match})", EVAL_HOLDOUT_SPLIT),
    ).fetchone()
    return row[0] if row else ""


SYSTEMS = {"retrieval": retrieval_translate}


def run_system(name: str, con: sqlite3.Connection, items: list[dict]) -> list[dict]:
    translate = SYSTEMS[name]
    return [
        {"id": item["id"], "hypothesis": translate(con, item["source_text"], item["direction"]), "system": name}
        for item in items
    ]


# --- scoring -----------------------------------------------------------------


def references_matrix(items: list[dict]) -> list[list[str]]:
    """sacrebleu wants equal-length reference streams; pad with each item's first reference."""
    width = max(len(item["references"]) for item in items)
    padded = [item["references"] + [item["references"][0]] * (width - len(item["references"])) for item in items]
    return [list(stream) for stream in zip(*padded)]


def sentence_stats(metric, hypotheses: list[str], references: list[list[str]]) -> np.ndarray:
    # sacrebleu's per-sentence sufficient statistics; summing rows reproduces the corpus score.
    return np.array(metric._extract_corpus_statistics(hypotheses, references), dtype=np.int64)


def corpus_score(metric, stats: np.ndarray) -> float:
    return float(metric._compute_score_from_stats(stats.sum(axis=0).tolist()).score)


def score_systems(items: list[dict], hypotheses: dict[str, dict[str, str]], resamples: int, seed: int) -> dict:
    """hypotheses maps system -> {item id -> hypothesis}. Missing items score as empty output."""
    references = references_matrix(items)
    rng = np.random.default_rng(seed)
    samples = rng.integers(0, len(items), size=(resamples, len(items)))
    domains = sorted({item["domain"] for item in items})

    results: dict = {"systems": {}, "comparisons": []}
    primary_boot: dict[str, np.ndarray] = {}
    for system, by_id in hypotheses.items():
        outputs = [by_id.get(item["id"], "") for item in items]
        entry: dict = {
            "items": len(items),
            "missing": sum(1 for item in items if item["id"] not in by_id),
            "empty": sum(1 for text in outputs if not text.strip()),
            "metrics": {},
            "by_domain": {},
        }
        for name, metric in metrics().items():
            stats = sentence_stats(metric, outputs, references)
            boot = np.array([corpus_score(metric, stats[idx]) for idx in samples])
            entry["metrics"][name] = {
                "score": round(corpus_score(metric, stats), 2),
                "ci95": [round(float(np.percentile(boot, 2.5)), 2), round(float(np.percentile(boot, 97.5)), 2)],
            }
            if name == PRIMARY:
                primary_boot[system] = boot
                for domain in domains:
                    rows = [i for i, item in enumerate(items) if item["domain"] == domain]
                    entry["by_domain"][domain] = {"items": len(rows), name: round(corpus_score(metric, stats[rows]), 2)}
        results["systems"][system] = entry

    for a, b in combinations(sorted(hypotheses), 2):
        delta = results["systems"][a]["metrics"][PRIMARY]["score"] - results["systems"][b]["metrics"][PRIMARY]["score"]
        better, worse = (a, b) if delta >= 0 else (b, a)
        # Share of resamples where the apparent winner does not win: a one-sided paired p-value.
        p_value = float(np.mean(primary_boot[better] <= primary_boot[worse]))
        results["comparisons"].append(
            {"better": better, "worse": worse, "metric": PRIMARY, "delta": round(abs(delta), 2), "p_value": round(p_value, 4)}
        )
    return results


def gate(results_list: list[dict], candidate: str, baselines: list[str]) -> tuple[bool, list[str]]:
    if candidate in baselines:
        return False, [f"FAIL: {candidate} cannot be its own baseline"]
    lines = []
    passed = True
    for results in results_list:
        label = f"{results.get('eval_file', '?')} ({results.get('direction', '?')})"
        for baseline in baselines:
            if candidate not in results["systems"] or baseline not in results["systems"]:
                passed = False
                lines.append(f"FAIL {label}: missing scores for {candidate} or {baseline}")
                continue
            comparison = next(
                (c for c in results["comparisons"] if {c["better"], c["worse"]} == {candidate, baseline}), None
            )
            if comparison is None:
                passed = False
                lines.append(f"FAIL {label}: no comparison between {candidate} and {baseline}")
                continue
            wins = comparison["better"] == candidate and comparison["delta"] > 0
            significant = comparison["p_value"] < SIGNIFICANCE
            ok = wins and significant
            passed &= ok
            verdict = "PASS" if ok else "FAIL"
            sign = "+" if comparison["better"] == candidate else "-"
            lines.append(
                f"{verdict} {label}: {candidate} vs {baseline} {PRIMARY} "
                f"{sign}{comparison['delta']} (p={comparison['p_value']})"
            )
    return passed, lines


# --- commands ----------------------------------------------------------------


def load_valid_set(path: Path) -> list[dict]:
    if not path.exists():
        sys.exit(f"Evaluation set not found: {path}")
    items, parse_errors = load_items(path)
    errors, _ = validate_items(items)
    if parse_errors or errors or not items:
        for error in (parse_errors + errors)[:10]:
            print(f"error: {error}")
        sys.exit(f"{path} is not a valid evaluation set; run eval_set.py validate")
    return items


def read_hypotheses(path: Path) -> tuple[str, dict[str, str]]:
    by_id: dict[str, str] = {}
    system = path.stem
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                by_id[row["id"]] = row.get("hypothesis") or ""
                system = row.get("system") or system
    return system, by_id


def cmd_translate(args: argparse.Namespace) -> int:
    items = load_valid_set(args.eval)
    if not args.db.exists():
        sys.exit(f"Language database not found: {args.db}")
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        rows = run_system(args.system, con, items)
    finally:
        con.close()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} hypotheses to {args.out}")
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    items = load_valid_set(args.eval)
    hypotheses: dict[str, dict[str, str]] = {}
    for path in args.hyp:
        system, by_id = read_hypotheses(path)
        if system in hypotheses:
            sys.exit(f"Two hypothesis files name the same system: {system}")
        unknown = set(by_id) - {item["id"] for item in items}
        if unknown:
            sys.exit(f"{path} has ids not in the evaluation set, e.g. {sorted(unknown)[0]}")
        hypotheses[system] = by_id

    results = {
        "eval_file": args.eval.name,
        "eval_sha256": hashlib.sha256(args.eval.read_bytes()).hexdigest(),
        "direction": items[0]["direction"],
        "primary_metric": PRIMARY,
        "bootstrap_resamples": args.resamples,
        **score_systems(items, hypotheses, args.resamples, args.seed),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    for system, entry in sorted(results["systems"].items()):
        chrf, bleu = entry["metrics"]["chrf++"], entry["metrics"]["bleu"]
        print(
            f"{system:24} chrF++ {chrf['score']:6.2f} [{chrf['ci95'][0]:.2f}-{chrf['ci95'][1]:.2f}]"
            f"  BLEU {bleu['score']:6.2f}  empty {entry['empty']}/{entry['items']}"
        )
    print(f"wrote {args.out}")
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    results_list = [json.loads(path.read_text(encoding="utf-8")) for path in args.results]
    passed, lines = gate(results_list, args.candidate, args.baseline)
    for line in lines:
        print(line)
    print("automatic gate PASSED; human evaluation still required" if passed else "automatic gate FAILED")
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    translate = commands.add_parser("translate")
    translate.add_argument("--system", choices=sorted(SYSTEMS), required=True)
    translate.add_argument("--eval", type=Path, required=True)
    translate.add_argument("--db", type=Path, default=ROOT / "data" / "processed" / "language" / "siamsil_language.sqlite")
    translate.add_argument("--out", type=Path, required=True)
    translate.set_defaults(run=cmd_translate)

    score = commands.add_parser("score")
    score.add_argument("--eval", type=Path, required=True)
    score.add_argument("--hyp", type=Path, action="append", required=True)
    score.add_argument("--out", type=Path, required=True)
    score.add_argument("--resamples", type=int, default=1000)
    score.add_argument("--seed", type=int, default=12345)
    score.set_defaults(run=cmd_score)

    gate_parser = commands.add_parser("gate")
    gate_parser.add_argument("--results", type=Path, action="append", required=True)
    gate_parser.add_argument("--candidate", required=True)
    gate_parser.add_argument("--baseline", action="append", required=True)
    gate_parser.set_defaults(run=cmd_gate)

    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
