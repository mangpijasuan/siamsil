from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))

from build_language_db import (  # type: ignore  # noqa: E402
    EVAL_HOLDOUT_SPLIT,
    apply_corpus_checks,
    connect,
    create_schema,
    ingest_parallel,
    length_log_ratio,
    name_tokens,
    number_mismatch,
    percentile,
    template_key,
)

# Zomi-side strings are placeholders, never real language data.

NAME_CONTEXT = [f"Yesterday {name} called me." for name in ("Tom", "Mary") for _ in range(5)]


class NameAndTemplateTests(unittest.TestCase):
    def test_names_are_learned_from_mid_sentence_capitalization(self) -> None:
        names = name_tokens(NAME_CONTEXT + ["I think The Hobbit is long.", "I read the book."])
        self.assertEqual(names, {"tom", "mary"})

    def test_words_mostly_lowercase_mid_sentence_are_not_names(self) -> None:
        sentences = ["We saw Apple there."] * 5 + ["We ate an apple there."] * 5
        self.assertEqual(name_tokens(sentences), set())

    def test_template_variants_share_a_key(self) -> None:
        names = {"tom", "mary"}
        self.assertEqual(template_key("Tom is 30.", names), template_key("Mary is 25!", names))
        self.assertEqual(template_key("Tom's dog barked.", names), template_key("Mary's dog barked.", names))
        self.assertNotEqual(template_key("Tom is 30.", names), template_key("Tom was 30.", names))


class AlignmentCheckTests(unittest.TestCase):
    def test_number_mismatch(self) -> None:
        self.assertFalse(number_mismatch("Room 12 at 3", "ZOMI 3 ZOMI 12"))
        self.assertTrue(number_mismatch("Room 12", "ZOMI 21"))
        self.assertTrue(number_mismatch("I have 3 cats.", "ZOMI_PLACEHOLDER"))

    def test_length_ratio_ignores_short_text(self) -> None:
        self.assertIsNone(length_log_ratio("Hi.", "ZOMI_PLACEHOLDER_LONGER_THAN_TWENTY"))
        self.assertAlmostEqual(length_log_ratio("a" * 20, "b" * 20), 0.0)

    def test_percentile_bounds(self) -> None:
        values = [float(v) for v in range(101)]
        self.assertEqual(percentile(values, 0.0), 0.0)
        self.assertEqual(percentile(values, 0.5), 50.0)
        self.assertEqual(percentile(values, 1.0), 100.0)


class CorpusPassTests(unittest.TestCase):
    def build(self, pairs: list[tuple[str, str]], eval_items: list[dict] | None = None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        corpus = Path(tmp.name) / "corpus.csv"
        with corpus.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["index", "en", "zomi", "model", "worker"])
            for index, (en, zomi) in enumerate(pairs):
                writer.writerow([index, en, zomi, "test-model", "test-worker"])
        con = connect(Path(tmp.name) / "language.sqlite")
        self.addCleanup(con.close)
        create_schema(con)
        with redirect_stdout(StringIO()):
            ingest_parallel(con, corpus, "2026-10-04T00:00:00+00:00")
        return con, apply_corpus_checks(con, eval_items, batch=3)

    def rows(self, con) -> dict[str, tuple[str, list[str], str]]:
        return {
            en: (split, json.loads(flags), template)
            for en, split, flags, template in con.execute(
                "SELECT normalized_source_text, dataset_split, quality_flags, template_hash FROM parallel_sentences"
            )
        }

    def test_template_variants_land_in_one_split(self) -> None:
        pairs = [(s, f"ZOMI_PLACEHOLDER_CONTEXT_{i}") for i, s in enumerate(NAME_CONTEXT)]
        pairs += [("Tom is happy.", "ZOMI_PLACEHOLDER_A"), ("Mary is happy.", "ZOMI_PLACEHOLDER_B")]
        con, checks = self.build(pairs)
        rows = self.rows(con)
        self.assertEqual(rows["Tom is happy."][0], rows["Mary is happy."][0])
        self.assertEqual(rows["Tom is happy."][2], rows["Mary is happy."][2])
        self.assertEqual(checks["names_learned"], 2)
        self.assertEqual(sum(checks["splits"].values()), len(pairs))

    def test_reused_target_and_number_mismatch_are_flagged(self) -> None:
        pairs = [
            ("The river is wide.", "ZOMI_PLACEHOLDER_SAME"),
            ("My brother cooks rice.", "ZOMI_PLACEHOLDER_SAME"),
            ("Open the window, please.", "ZOMI_PLACEHOLDER_SAME"),
            ("I bought 4 eggs.", "ZOMI_PLACEHOLDER_EGGS"),
        ]
        con, checks = self.build(pairs)
        rows = self.rows(con)
        self.assertIn("target_reused", rows["The river is wide."][1])
        self.assertIn("number_mismatch", rows["I bought 4 eggs."][1])
        self.assertNotIn("target_reused", rows["I bought 4 eggs."][1])
        self.assertEqual(checks["flags"]["target_reused"], 3)
        score = con.execute(
            "SELECT quality_score FROM parallel_sentences WHERE normalized_source_text = 'I bought 4 eggs.'"
        ).fetchone()[0]
        self.assertLess(score, 1.0)

    def test_pairs_matching_evaluation_items_are_held_out(self) -> None:
        pairs = [
            ("Where is the clinic?", "ZOMI_PLACEHOLDER_1"),
            ("Unrelated sentence.", "ZOMI_PLACEHOLDER_EVAL_REF"),
            ("Something else entirely.", "ZOMI_PLACEHOLDER_3"),
        ]
        eval_items = [
            {"direction": "en-zomi", "source_text": "where is the CLINIC", "references": ["ZOMI_PLACEHOLDER_X"]},
            {"direction": "zomi-en", "source_text": "ZOMI_PLACEHOLDER_EVAL_REF", "references": ["Other."]},
        ]
        con, checks = self.build(pairs, eval_items)
        rows = self.rows(con)
        self.assertEqual(rows["Where is the clinic?"][0], EVAL_HOLDOUT_SPLIT)
        self.assertEqual(rows["Unrelated sentence."][0], EVAL_HOLDOUT_SPLIT)
        self.assertNotEqual(rows["Something else entirely."][0], EVAL_HOLDOUT_SPLIT)
        self.assertEqual(checks["splits"][EVAL_HOLDOUT_SPLIT], 2)


if __name__ == "__main__":
    unittest.main()
