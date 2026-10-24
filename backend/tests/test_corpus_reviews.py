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
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "services"))

import corpus_reviews  # type: ignore  # noqa: E402
from build_language_db import (  # type: ignore  # noqa: E402
    apply_corpus_checks,
    apply_reviews,
    connect,
    create_schema,
    ingest_parallel,
    pair_key,
)
from export_datasets import corpus_records  # type: ignore  # noqa: E402
from language_engine import LanguageEngine  # type: ignore  # noqa: E402
from review_sample import export, main as review_main, record  # type: ignore  # noqa: E402

# Zomi-side strings are placeholders, never real language data.


def rating(pair_hash: str, meaning: int, fluency: int, reviewer: str = "R01") -> dict:
    return {
        "pair_hash": pair_hash,
        "meaning": meaning,
        "fluency": fluency,
        "reviewer": reviewer,
        "reviewed_on": "2026-10-24",
        "batch": "test",
        "notes": "",
    }


HASH_A, HASH_B, HASH_C = "a" * 40, "b" * 40, "c" * 40


class DecisionTests(unittest.TestCase):
    def test_acceptable_rating_is_accepted(self) -> None:
        self.assertEqual(corpus_reviews.decide([rating(HASH_A, 2, 1)])[HASH_A].status, "accepted")

    def test_partly_right_meaning_or_unreadable_zomi_stays_undecided(self) -> None:
        decisions = corpus_reviews.decide([rating(HASH_A, 1, 2), rating(HASH_B, 2, 0)])
        self.assertEqual(decisions[HASH_A].status, "partial")
        self.assertEqual(decisions[HASH_B].status, "partial")

    def test_any_wrong_meaning_rejects_even_if_another_reviewer_accepted(self) -> None:
        decisions = corpus_reviews.decide([rating(HASH_A, 2, 2, "R01"), rating(HASH_A, 0, 1, "R02")])
        self.assertEqual(decisions[HASH_A].status, "rejected")

    def test_a_reviewers_latest_rating_replaces_their_earlier_one(self) -> None:
        decisions = corpus_reviews.decide([rating(HASH_A, 0, 0), rating(HASH_A, 2, 1)])
        self.assertEqual(decisions[HASH_A], corpus_reviews.Decision("accepted", 1))

    def test_minimum_reviewers(self) -> None:
        one = [rating(HASH_A, 2, 2, "R01")]
        two = one + [rating(HASH_A, 2, 1, "R02")]
        self.assertEqual(corpus_reviews.decide(one, min_reviewers=2)[HASH_A].status, "partial")
        self.assertEqual(corpus_reviews.decide(two, min_reviewers=2)[HASH_A].status, "accepted")

    def test_malformed_saved_records_stop_loading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reviews.jsonl"
            path.write_text(json.dumps(rating(HASH_A, 2, 2, reviewer="Ann Smith")) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "roster code"):
                corpus_reviews.load(path)
            path.write_text(json.dumps(rating(HASH_A, 3, 2)) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "0, 1, or 2"):
                corpus_reviews.load(path)
            path.write_text("{not json\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not JSON"):
                corpus_reviews.load(path)


class CorpusFixture(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        corpus = self.dir / "corpus.csv"
        with corpus.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["index", "en", "zomi", "model", "worker"])
            for n in range(6):
                writer.writerow([n, f"English sentence number {n}.", f"ZOMI_PLACEHOLDER_{n}", "model-a", "w"])
        self.database = self.dir / "language.sqlite"
        con = connect(self.database)
        create_schema(con)
        with redirect_stdout(StringIO()):
            ingest_parallel(con, corpus, "2026-10-24T00:00:00+00:00")
        apply_corpus_checks(con, [])
        con.close()

    def hash_of(self, n: int) -> str:
        return pair_key(f"English sentence number {n}.", f"ZOMI_PLACEHOLDER_{n}")

    def read(self, path: Path) -> list[dict]:
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))


class ApplyReviewTests(CorpusFixture):
    def test_rebuild_marks_accepted_verified_and_drops_rejected(self) -> None:
        decisions = corpus_reviews.decide(
            [rating(self.hash_of(0), 2, 2), rating(self.hash_of(1), 0, 1), rating(self.hash_of(2), 1, 1),
             rating("f" * 40, 2, 2)]
        )
        con = sqlite3.connect(self.database)
        counts = apply_reviews(con, decisions)
        self.assertEqual(counts, {"accepted": 1, "rejected": 1, "partial": 1, "not_in_corpus": 1})
        rows = {
            pair_hash: (verified, json.loads(flags), score)
            for pair_hash, verified, flags, score in con.execute(
                "SELECT pair_hash, verified, quality_flags, quality_score FROM parallel_sentences"
            )
        }
        self.assertEqual(rows[self.hash_of(0)][0], 1)
        self.assertEqual(rows[self.hash_of(1)], (0, ["reviewer_rejected"], 0))
        self.assertEqual(rows[self.hash_of(2)][0], 0)

        exported = {record["english"]: record for record in corpus_records(con, silver=set(), min_score=0.5)}
        con.close()
        self.assertEqual(exported["English sentence number 0."]["tier"], "silver")
        self.assertTrue(exported["English sentence number 0."]["human_reviewed"])
        self.assertNotIn("English sentence number 1.", exported)
        self.assertEqual(exported["English sentence number 2."]["tier"], "bronze")

    def test_app_labels_accepted_pairs_and_never_shows_rejected_ones(self) -> None:
        con = sqlite3.connect(self.database)
        apply_reviews(con, corpus_reviews.decide([rating(self.hash_of(0), 2, 1), rating(self.hash_of(1), 0, 2)]))
        con.close()
        engine = LanguageEngine(self.database)
        for direction in (None, "en-zom"):
            accepted = engine.search_parallel("English sentence number 0.", direction=direction)
            self.assertEqual(accepted[0]["label"], "Machine-translated example, accepted by Zomi reviewers")
            self.assertTrue(accepted[0]["verified"])
            shown = [hit["english"] for hit in engine.search_parallel("English sentence number 1.", direction=direction)]
            self.assertNotIn("English sentence number 1.", shown)
        self.assertEqual(engine.search_parallel("ZOMI_PLACEHOLDER_1", direction="zom-en"), [])

    def test_reviewers_outrank_a_low_automatic_score(self) -> None:
        con = sqlite3.connect(self.database)
        con.execute("UPDATE parallel_sentences SET quality_score = 0.2 WHERE pair_hash = ?", (self.hash_of(3),))
        apply_reviews(con, corpus_reviews.decide([rating(self.hash_of(3), 2, 1)]))
        verified, score = con.execute(
            "SELECT verified, quality_score FROM parallel_sentences WHERE pair_hash = ?", (self.hash_of(3),)
        ).fetchone()
        exported = [r["english"] for r in corpus_records(con, silver=set(), min_score=0.5)]
        con.close()
        self.assertEqual((verified, score), (1, 1.0))
        self.assertIn("English sentence number 3.", exported)

    def test_applying_twice_changes_nothing(self) -> None:
        decisions = corpus_reviews.decide([rating(self.hash_of(1), 0, 0)])
        con = sqlite3.connect(self.database)
        apply_reviews(con, decisions)
        apply_reviews(con, decisions)
        flags = con.execute(
            "SELECT quality_flags FROM parallel_sentences WHERE pair_hash = ?", (self.hash_of(1),)
        ).fetchone()[0]
        con.close()
        self.assertEqual(json.loads(flags), ["reviewer_rejected"])


class RecordTests(CorpusFixture):
    def setUp(self) -> None:
        super().setUp()
        review_path, key_path, _ = export(self.database, self.dir / "batch-1", per_model=3, seed="s")
        self.review_path, self.key_path = review_path, key_path
        self.review, self.key = self.read(review_path), self.read(key_path)

    def rate(self, scores: list[tuple[str, str]]) -> list[dict]:
        rows = [dict(row) for row in self.review]
        for row, (meaning, fluency) in zip(rows, scores):
            row["meaning"], row["fluency"] = meaning, fluency
        return rows

    def test_key_file_carries_the_stable_pair_hash(self) -> None:
        for review_row, key_row in zip(self.review, self.key):
            self.assertEqual(key_row["pair_hash"], pair_key(review_row["english"], review_row["zomi"]))

    def test_rated_rows_become_records_and_blank_rows_are_skipped(self) -> None:
        records, errors, unchanged = record(
            self.rate([("2", "2"), ("0", "1"), ("", "")]), self.key,
            reviewer="R01", reviewed_on="2026-10-24", batch="batch-1", existing=[],
        )
        self.assertEqual(errors, [])
        self.assertEqual(unchanged, 0)
        self.assertEqual([(r["meaning"], r["fluency"]) for r in records], [(2, 2), (0, 1)])
        self.assertEqual(records[0]["pair_hash"], self.key[0]["pair_hash"])
        self.assertTrue(all("english" not in r and "zomi" not in r for r in records))

    def test_saving_the_same_sheet_again_adds_nothing(self) -> None:
        rows = self.rate([("2", "2")])
        first, _, _ = record(rows, self.key, reviewer="R01", reviewed_on="d", batch="b", existing=[])
        again, errors, unchanged = record(rows, self.key, reviewer="R01", reviewed_on="d", batch="b", existing=first)
        self.assertEqual((again, errors, unchanged), ([], [], 1))

    def test_edited_sentence_text_is_refused(self) -> None:
        rows = self.rate([("2", "2")])
        rows[0]["zomi"] = rows[0]["zomi"] + " edited"
        records, errors, _ = record(rows, self.key, reviewer="R01", reviewed_on="d", batch="b", existing=[])
        self.assertEqual(records, [])
        self.assertIn("differs from the exported pair", errors[0])

    def test_bad_scores_and_names_instead_of_codes_are_refused(self) -> None:
        _, errors, _ = record(self.rate([("3", "1")]), self.key, reviewer="R01", reviewed_on="d", batch="b", existing=[])
        self.assertIn("0, 1, or 2", errors[0])
        _, errors, _ = record(self.rate([("2", "2")]), self.key, reviewer="Mangpi", reviewed_on="d", batch="b", existing=[])
        self.assertIn("roster code", errors[0])

    def test_old_key_without_pair_hash_uses_the_database(self) -> None:
        old_key = [{k: v for k, v in row.items() if k != "pair_hash"} for row in self.key]
        rows = self.rate([("2", "1")])
        _, errors, _ = record(rows, old_key, reviewer="R01", reviewed_on="d", batch="b", existing=[])
        self.assertIn("--database", errors[0])
        con = sqlite3.connect(self.database)
        records, errors, _ = record(rows, old_key, reviewer="R01", reviewed_on="d", batch="b", existing=[], con=con)
        con.close()
        self.assertEqual(errors, [])
        self.assertEqual(records[0]["pair_hash"], self.key[0]["pair_hash"])

    def test_record_command_saves_nothing_when_any_row_is_wrong(self) -> None:
        reviews = self.dir / "reviews" / "corpus-reviews.jsonl"
        rows = self.rate([("2", "2"), ("9", "9")])
        with self.review_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        args = [str(self.review_path), str(self.key_path), "--reviewer", "R01", "--reviews", str(reviews)]
        with redirect_stdout(StringIO()):
            self.assertEqual(review_main(["record", *args]), 1)
        self.assertFalse(reviews.exists())

        rows[1]["meaning"], rows[1]["fluency"] = "2", "1"
        with self.review_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        with redirect_stdout(StringIO()):
            self.assertEqual(review_main(["record", *args, "--date", "2026-10-24"]), 0)
        saved = corpus_reviews.load(reviews)
        self.assertEqual(len(saved), 2)
        self.assertEqual({r["batch"] for r in saved}, {"batch-1"})


if __name__ == "__main__":
    unittest.main()
