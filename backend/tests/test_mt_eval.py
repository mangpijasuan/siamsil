from __future__ import annotations

import csv
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))

from build_language_db import apply_corpus_checks, connect, create_schema, ingest_parallel  # type: ignore  # noqa: E402
from mt_eval import gate, main, retrieval_translate, score_systems  # type: ignore  # noqa: E402

# Zomi-side strings are placeholders, never real language data. Scores are only
# checked for ordering and identity, not for any claim about translation quality.


def item(n: int, domain: str, source: str, reference: str, direction: str = "en-zomi") -> dict:
    return {
        "id": f"{direction}-{n:04d}",
        "direction": direction,
        "domain": domain,
        "source_text": source,
        "references": [reference],
        "source_origin": "test",
        "translator": "T01",
        "reviewer": "R01",
        "adjudicator": None,
        "review_outcome": "accepted",
        "notes": "",
    }


ITEMS = [
    item(1, "health", "Where is the clinic?", "placeholder words for the clinic question"),
    item(2, "health", "I need a doctor.", "placeholder words asking for a doctor"),
    item(3, "news", "The road is closed.", "placeholder words about the closed road"),
    item(4, "news", "It rained all night.", "placeholder words about rain at night"),
]
PERFECT = {i["id"]: i["references"][0] for i in ITEMS}
PARTIAL = {i["id"]: " ".join(i["references"][0].split()[:3]) for i in ITEMS}


class ScoringTests(unittest.TestCase):
    def test_perfect_output_scores_100_and_empty_scores_0(self) -> None:
        results = score_systems(ITEMS, {"perfect": PERFECT, "empty": {}}, resamples=200, seed=1)
        self.assertEqual(results["systems"]["perfect"]["metrics"]["chrf++"]["score"], 100.0)
        self.assertEqual(results["systems"]["perfect"]["metrics"]["bleu"]["score"], 100.0)
        self.assertEqual(results["systems"]["empty"]["metrics"]["chrf++"]["score"], 0.0)
        self.assertEqual(results["systems"]["empty"]["missing"], len(ITEMS))

    def test_domains_and_intervals_are_reported(self) -> None:
        results = score_systems(ITEMS, {"partial": PARTIAL}, resamples=200, seed=1)
        entry = results["systems"]["partial"]
        self.assertEqual(set(entry["by_domain"]), {"health", "news"})
        self.assertEqual(entry["by_domain"]["health"]["items"], 2)
        low, high = entry["metrics"]["chrf++"]["ci95"]
        self.assertLessEqual(low, entry["metrics"]["chrf++"]["score"])
        self.assertGreaterEqual(high, entry["metrics"]["chrf++"]["score"])

    def test_multiple_references_are_padded(self) -> None:
        items = [dict(ITEMS[0], references=["alpha beta", "gamma delta"]), ITEMS[1]]
        results = score_systems(items, {"s": {items[0]["id"]: "gamma delta"}}, resamples=50, seed=1)
        self.assertGreater(results["systems"]["s"]["metrics"]["chrf++"]["score"], 0.0)

    def test_scoring_is_deterministic(self) -> None:
        first = score_systems(ITEMS, {"a": PARTIAL, "b": PERFECT}, resamples=200, seed=7)
        second = score_systems(ITEMS, {"a": PARTIAL, "b": PERFECT}, resamples=200, seed=7)
        self.assertEqual(first, second)


class GateTests(unittest.TestCase):
    def results(self, candidate: dict[str, str], baseline: dict[str, str]) -> dict:
        items = ITEMS * 10
        items = [dict(i, id=f"{i['id']}-{n}") for n, i in enumerate(items)]
        expand = lambda hyps: {f"{i['id']}-{n}": hyps.get(i["id"], "") for n, i in enumerate(ITEMS * 10)}  # noqa: E731
        scored = score_systems(items, {"candidate": expand(candidate), "retrieval": expand(baseline)}, 500, 3)
        return {"eval_file": "en-zomi-v1.jsonl", "direction": "en-zomi", **scored}

    def test_clear_winner_passes(self) -> None:
        passed, lines = gate([self.results(PERFECT, PARTIAL)], "candidate", ["retrieval"])
        self.assertTrue(passed, lines)

    def test_loser_and_tie_fail(self) -> None:
        passed, _ = gate([self.results(PARTIAL, PERFECT)], "candidate", ["retrieval"])
        self.assertFalse(passed)
        passed, _ = gate([self.results(PARTIAL, PARTIAL)], "candidate", ["retrieval"])
        self.assertFalse(passed)

    def test_every_results_file_must_pass(self) -> None:
        passed, lines = gate(
            [self.results(PERFECT, PARTIAL), self.results(PARTIAL, PERFECT)], "candidate", ["retrieval"]
        )
        self.assertFalse(passed)
        self.assertEqual(sum(line.startswith("PASS") for line in lines), 1)

    def test_missing_system_fails(self) -> None:
        passed, _ = gate([self.results(PERFECT, PARTIAL)], "candidate", ["hosted-llm"])
        self.assertFalse(passed)

    def test_candidate_cannot_be_its_own_baseline(self) -> None:
        passed, lines = gate([self.results(PERFECT, PARTIAL)], "candidate", ["candidate"])
        self.assertFalse(passed)
        self.assertIn("own baseline", lines[0])


class RetrievalBaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        corpus = Path(tmp.name) / "corpus.csv"
        with corpus.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["index", "en", "zomi", "model", "worker"])
            writer.writerow([0, "The road is closed.", "ZOMI_PLACEHOLDER_ROAD", "m", "w"])
            writer.writerow([1, "Where is the clinic?", "ZOMI_PLACEHOLDER_CLINIC", "m", "w"])
            writer.writerow([2, "The market opens early.", "ZOMI_PLACEHOLDER_MARKET", "m", "w"])
        path = Path(tmp.name) / "language.sqlite"
        con = connect(path)
        create_schema(con)
        with redirect_stdout(StringIO()):
            ingest_parallel(con, corpus, "t")
        apply_corpus_checks(con, [ITEMS[0]])  # "Where is the clinic?" is held out
        con.close()
        self.con = sqlite3.connect(path)
        self.addCleanup(self.con.close)
        self.dir = Path(tmp.name)
        self.db = path

    def test_exact_and_reverse_matches(self) -> None:
        self.assertEqual(retrieval_translate(self.con, "the road is closed.", "en-zomi"), "ZOMI_PLACEHOLDER_ROAD")
        self.assertEqual(retrieval_translate(self.con, "ZOMI_PLACEHOLDER_ROAD", "zomi-en"), "The road is closed.")

    def test_full_text_fallback(self) -> None:
        self.assertEqual(retrieval_translate(self.con, "market opens", "en-zomi"), "ZOMI_PLACEHOLDER_MARKET")
        self.assertEqual(retrieval_translate(self.con, "nothing like this", "en-zomi"), "")

    def test_held_out_pairs_are_never_returned(self) -> None:
        self.assertEqual(retrieval_translate(self.con, "Where is the clinic?", "en-zomi"), "")

    def test_commands_end_to_end(self) -> None:
        eval_path = self.dir / "en-zomi-v1.jsonl"
        eval_path.write_text("".join(json.dumps(i) + "\n" for i in ITEMS), encoding="utf-8")
        hyp = self.dir / "retrieval.jsonl"
        results = self.dir / "results.json"
        with redirect_stdout(StringIO()):
            self.assertEqual(main(["translate", "--system", "retrieval", "--eval", str(eval_path),
                                   "--db", str(self.db), "--out", str(hyp)]), 0)
            self.assertEqual(main(["score", "--eval", str(eval_path), "--hyp", str(hyp),
                                   "--out", str(results), "--resamples", "50"]), 0)
            self.assertEqual(main(["gate", "--results", str(results), "--candidate", "retrieval",
                                   "--baseline", "retrieval"]), 1)
        data = json.loads(results.read_text(encoding="utf-8"))
        self.assertEqual(data["direction"], "en-zomi")
        self.assertEqual(data["systems"]["retrieval"]["items"], len(ITEMS))


if __name__ == "__main__":
    unittest.main()
