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
from unittest.mock import patch

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
from corpus_reviews import (  # type: ignore  # noqa: E402
    HUMAN_APPROVED,
    NEEDS_CORRECTION,
    READY_FOR_APPROVAL,
    REJECTED,
)
from export_datasets import corpus_records  # type: ignore  # noqa: E402
from language_engine import LanguageEngine  # type: ignore  # noqa: E402
from review_sample import (  # type: ignore  # noqa: E402
    approval_sheet,
    approve,
    export,
    main as review_main,
    record,
)

# Zomi-side strings are placeholders, never real language data.
ROSTER = {"R01": "reviewer", "R02": "reviewer", "E01": "lead_editor", "E02": "lead_editor"}


def rating(pair_hash: str, meaning: int, fluency: int, reviewer: str = "R01") -> dict:
    return {
        "kind": "review",
        "pair_hash": pair_hash,
        "meaning": meaning,
        "fluency": fluency,
        "reviewer": reviewer,
        "reviewed_on": "2026-10-25",
        "batch": "test",
        "notes": "",
        "correction": "",
    }


def approval(pair_hash: str, decision: str = "approve", approver: str = "E01") -> dict:
    return {
        "kind": "approval",
        "pair_hash": pair_hash,
        "decision": decision,
        "approver": approver,
        "approved_on": "2026-10-26",
        "batch": "approval-1",
        "notes": "",
    }


HASH_A, HASH_B = "a" * 40, "b" * 40


class DecisionTests(unittest.TestCase):
    def status(self, records: list[dict], min_reviewers: int = 1) -> str:
        return corpus_reviews.decide(records, min_reviewers)[HASH_A].status

    def test_an_acceptable_review_alone_is_never_approved(self) -> None:
        self.assertEqual(self.status([rating(HASH_A, 2, 1)]), READY_FOR_APPROVAL)

    def test_a_separate_lead_editor_approval_makes_it_human_approved(self) -> None:
        decision = corpus_reviews.decide([rating(HASH_A, 2, 1), approval(HASH_A)])[HASH_A]
        self.assertEqual(decision, corpus_reviews.Decision(HUMAN_APPROVED, ("R01",), "E01"))

    def test_the_lead_editor_can_reject(self) -> None:
        self.assertEqual(self.status([rating(HASH_A, 2, 2), approval(HASH_A, "reject")]), REJECTED)

    def test_a_reviewer_cannot_approve_their_own_review(self) -> None:
        self.assertEqual(self.status([rating(HASH_A, 2, 2, "R01"), approval(HASH_A, approver="R01")]), READY_FOR_APPROVAL)

    def test_an_approval_older_than_the_latest_review_does_not_count(self) -> None:
        records = [rating(HASH_A, 2, 2), approval(HASH_A), rating(HASH_A, 2, 1, "R02")]
        self.assertEqual(self.status(records), READY_FOR_APPROVAL)

    def test_partly_right_or_unreadable_needs_correction(self) -> None:
        decisions = corpus_reviews.decide([rating(HASH_A, 1, 2), rating(HASH_B, 2, 0)])
        self.assertEqual((decisions[HASH_A].status, decisions[HASH_B].status), (NEEDS_CORRECTION, NEEDS_CORRECTION))

    def test_approval_cannot_rescue_a_pair_a_reviewer_rejected(self) -> None:
        records = [rating(HASH_A, 2, 2, "R01"), rating(HASH_A, 0, 1, "R02"), approval(HASH_A)]
        self.assertEqual(self.status(records), REJECTED)

    def test_a_reviewers_latest_rating_replaces_their_earlier_one(self) -> None:
        self.assertEqual(self.status([rating(HASH_A, 0, 0), rating(HASH_A, 2, 1)]), READY_FOR_APPROVAL)

    def test_minimum_reviewers(self) -> None:
        one = [rating(HASH_A, 2, 2, "R01")]
        self.assertEqual(self.status(one, min_reviewers=2), NEEDS_CORRECTION)
        self.assertEqual(self.status(one + [rating(HASH_A, 2, 1, "R02")], min_reviewers=2), READY_FOR_APPROVAL)

    def test_malformed_saved_records_stop_loading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reviews.jsonl"
            for bad, message in (
                (rating(HASH_A, 2, 2, reviewer="Ann Smith"), "roster code"),
                (rating(HASH_A, 3, 2), "0, 1, or 2"),
                (approval(HASH_A, decision="maybe"), "approve or reject"),
                ({**rating(HASH_A, 2, 2), "kind": "vote"}, "unknown kind"),
            ):
                path.write_text(json.dumps(bad) + "\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    corpus_reviews.load(path)
            path.write_text("{not json\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not JSON"):
                corpus_reviews.load(path)

    def test_roster_needs_codes_and_known_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "roster.csv"
            path.write_text("code,role,name\nR01,reviewer,\nE01,lead_editor,\n", encoding="utf-8")
            self.assertEqual(corpus_reviews.load_roster(path), {"R01": "reviewer", "E01": "lead_editor"})
            path.write_text("code,role\nR01,owner\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "role"):
                corpus_reviews.load_roster(path)


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
            ingest_parallel(con, corpus, "2026-10-25T00:00:00+00:00")
        apply_corpus_checks(con, [])
        con.close()

    def hash_of(self, n: int) -> str:
        return pair_key(f"English sentence number {n}.", f"ZOMI_PLACEHOLDER_{n}")

    def read(self, path: Path) -> list[dict]:
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))


class ApplyReviewTests(CorpusFixture):
    def test_rebuild_verifies_only_human_approved_pairs_and_drops_rejected(self) -> None:
        records = [
            rating(self.hash_of(0), 2, 2), approval(self.hash_of(0)),  # approved
            rating(self.hash_of(1), 0, 1),                              # rejected
            rating(self.hash_of(2), 1, 1),                              # needs correction
            rating(self.hash_of(4), 2, 2),                              # ready, not approved
            rating("f" * 40, 2, 2),                                     # no longer in corpus
        ]
        con = sqlite3.connect(self.database)
        counts = apply_reviews(con, corpus_reviews.decide(records))
        self.assertEqual(
            counts,
            {HUMAN_APPROVED: 1, READY_FOR_APPROVAL: 1, NEEDS_CORRECTION: 1, REJECTED: 1, "not_in_corpus": 1},
        )
        rows = {
            pair_hash: (verified, json.loads(flags), score)
            for pair_hash, verified, flags, score in con.execute(
                "SELECT pair_hash, verified, quality_flags, quality_score FROM parallel_sentences"
            )
        }
        self.assertEqual(rows[self.hash_of(0)][0], 1)
        self.assertEqual(rows[self.hash_of(1)], (0, ["reviewer_rejected"], 0))
        self.assertEqual(rows[self.hash_of(2)][0], 0)
        self.assertEqual(rows[self.hash_of(4)][0], 0)

        exported = {record["english"]: record for record in corpus_records(con, silver=set(), min_score=0.5)}
        con.close()
        self.assertEqual(exported["English sentence number 0."]["tier"], "silver")
        self.assertTrue(exported["English sentence number 0."]["human_reviewed"])
        self.assertNotIn("English sentence number 1.", exported)
        self.assertEqual(exported["English sentence number 4."]["tier"], "bronze")

    def test_app_labels_approved_pairs_and_never_shows_rejected_ones(self) -> None:
        con = sqlite3.connect(self.database)
        apply_reviews(con, corpus_reviews.decide(
            [rating(self.hash_of(0), 2, 1), approval(self.hash_of(0)), rating(self.hash_of(1), 0, 2)]
        ))
        con.close()
        engine = LanguageEngine(self.database)
        for direction in (None, "en-zom"):
            approved = engine.search_parallel("English sentence number 0.", direction=direction)
            self.assertEqual(approved[0]["label"], "Machine-translated example, approved by Zomi reviewers")
            self.assertTrue(approved[0]["verified"])
            shown = [hit["english"] for hit in engine.search_parallel("English sentence number 1.", direction=direction)]
            self.assertNotIn("English sentence number 1.", shown)
        self.assertEqual(engine.search_parallel("ZOMI_PLACEHOLDER_1", direction="zom-en"), [])

    def test_people_outrank_a_low_automatic_score(self) -> None:
        con = sqlite3.connect(self.database)
        con.execute("UPDATE parallel_sentences SET quality_score = 0.2 WHERE pair_hash = ?", (self.hash_of(3),))
        apply_reviews(con, corpus_reviews.decide([rating(self.hash_of(3), 2, 1), approval(self.hash_of(3))]))
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

    def test_build_refuses_a_reviews_path_that_does_not_exist(self) -> None:
        import build_language_db  # type: ignore

        argv = ["build_language_db.py", "--raw", str(self.dir), "--reviews", str(self.dir / "typo.jsonl")]
        with patch.object(sys, "argv", argv), self.assertRaisesRegex(SystemExit, "Reviews file not found"):
            build_language_db.main()


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

    def save(self, rows: list[dict], **kwargs) -> tuple[list[dict], list[str], int]:
        options = {"reviewer": "R01", "reviewed_on": "d", "batch": "b", "existing": [], "roster": ROSTER}
        return record(rows, self.key, **{**options, **kwargs})

    def test_key_file_carries_the_stable_pair_hash(self) -> None:
        for review_row, key_row in zip(self.review, self.key):
            self.assertEqual(key_row["pair_hash"], pair_key(review_row["english"], review_row["zomi"]))

    def test_rated_rows_become_records_with_corrections_and_timestamps(self) -> None:
        rows = self.rate([("2", "2"), ("1", "1"), ("", "")])
        rows[1]["correction"], rows[1]["notes"] = "CORRECTED_PLACEHOLDER", "word order"
        records, errors, unchanged = self.save(rows, recorded_at="2026-10-25T10:00:00Z")
        self.assertEqual((errors, unchanged), ([], 0))
        self.assertEqual([(r["meaning"], r["fluency"]) for r in records], [(2, 2), (1, 1)])
        self.assertEqual(records[1]["correction"], "CORRECTED_PLACEHOLDER")
        self.assertEqual({r["kind"] for r in records}, {"review"})
        self.assertEqual(records[0]["recorded_at"], "2026-10-25T10:00:00Z")
        self.assertTrue(all("english" not in r and "zomi" not in r for r in records))

    def test_only_roster_reviewers_can_be_recorded(self) -> None:
        for code in ("R09", "E01", "Mangpi"):
            _, errors, _ = self.save(self.rate([("2", "2")]), reviewer=code)
            self.assertIn("not listed as a reviewer", errors[0])

    def test_saving_the_same_sheet_again_adds_nothing(self) -> None:
        rows = self.rate([("2", "2")])
        first, _, _ = self.save(rows)
        again, errors, unchanged = self.save(rows, existing=first)
        self.assertEqual((again, errors, unchanged), ([], [], 1))

    def test_same_scores_in_a_later_batch_are_a_new_review(self) -> None:
        rows = self.rate([("2", "2")])
        first, _, _ = self.save(rows, reviewed_on="2026-10-25", batch="b1")
        later, errors, unchanged = self.save(rows, reviewed_on="2026-11-02", batch="b2", existing=first)
        self.assertEqual((len(later), errors, unchanged), (1, [], 0))
        self.assertEqual(later[0]["reviewed_on"], "2026-11-02")

    def test_edited_sentence_text_is_refused(self) -> None:
        # Punctuation- and case-only edits leave pair_hash unchanged, so they are checked exactly too.
        for edit in (lambda text: text + " edited", lambda text: text.rstrip("."), str.upper):
            rows = self.rate([("2", "2")])
            rows[0]["english"] = edit(rows[0]["english"])
            records, errors, _ = self.save(rows)
            self.assertEqual(records, [])
            self.assertIn("differs from the exported pair", errors[0])

    def test_bad_scores_are_refused(self) -> None:
        _, errors, _ = self.save(self.rate([("3", "1")]))
        self.assertIn("0, 1, or 2", errors[0])

    def test_old_key_without_pair_hash_uses_the_database(self) -> None:
        old_key = [{k: v for k, v in row.items() if k not in ("pair_hash", "text_sha256")} for row in self.key]
        rows = self.rate([("2", "1")])
        options = {"reviewer": "R01", "reviewed_on": "d", "batch": "b", "existing": [], "roster": ROSTER}
        _, errors, _ = record(rows, old_key, **options)
        self.assertIn("--database", errors[0])
        con = sqlite3.connect(self.database)
        records, errors, _ = record(rows, old_key, **options, con=con)
        rows[0]["english"] = rows[0]["english"].rstrip(".")
        _, edited_errors, _ = record(rows, old_key, **options, con=con)
        con.close()
        self.assertEqual(errors, [])
        self.assertEqual(records[0]["pair_hash"], self.key[0]["pair_hash"])
        self.assertIn("differs from the exported pair", edited_errors[0])


class ApprovalTests(CorpusFixture):
    def ready_records(self) -> list[dict]:
        return [rating(self.hash_of(0), 2, 2, "R01"), rating(self.hash_of(1), 2, 1, "R01"), rating(self.hash_of(2), 1, 2)]

    def sheet(self, records: list[dict]) -> list[dict]:
        con = sqlite3.connect(self.database)
        rows = approval_sheet(records, con)
        con.close()
        return rows

    def decide_rows(self, rows: list[dict], decisions: list[str]) -> list[dict]:
        return [{**row, "decision": decision} for row, decision in zip(rows, decisions)]

    def run_approve(self, rows: list[dict], records: list[dict], approver: str = "E01") -> tuple[list[dict], list[str]]:
        return approve(rows, approver=approver, roster=ROSTER, existing=records, approved_on="d", batch="a1")

    def test_sheet_lists_only_pairs_ready_for_approval_with_their_reviews(self) -> None:
        rows = self.sheet(self.ready_records())
        self.assertEqual(sorted(row["english"] for row in rows), ["English sentence number 0.", "English sentence number 1."])
        self.assertTrue(all("R01 meaning 2" in row["reviews"] for row in rows))

    def test_approve_and_reject_are_saved_and_change_the_status(self) -> None:
        records = self.ready_records()
        rows = self.decide_rows(self.sheet(records), ["approve", "reject"])
        saved, errors = self.run_approve(rows, records)
        self.assertEqual(errors, [])
        statuses = {pair: d.status for pair, d in corpus_reviews.decide(records + saved).items()}
        self.assertEqual(sorted(statuses[r["pair_hash"]] for r in rows), sorted([HUMAN_APPROVED, REJECTED]))
        self.assertEqual({r["kind"] for r in saved}, {"approval"})

    def test_blank_decisions_wait(self) -> None:
        records = self.ready_records()
        saved, errors = self.run_approve(self.decide_rows(self.sheet(records), ["", ""]), records)
        self.assertEqual((saved, errors), ([], []))

    def test_only_a_roster_lead_editor_who_did_not_review_can_approve(self) -> None:
        records = self.ready_records()
        rows = self.decide_rows(self.sheet(records), ["approve"])
        for code in ("R02", "E09"):
            _, errors = self.run_approve(rows, records, approver=code)
            self.assertIn("not listed as a lead_editor", errors[0])
        dual_role = {**ROSTER, "R01": "lead_editor"}
        _, errors = approve(rows, approver="R01", roster=dual_role, existing=records, approved_on="d", batch="a1")
        self.assertIn("reviewed this pair", errors[0])

    def test_edited_text_unknown_decisions_and_stale_sheets_are_refused(self) -> None:
        records = self.ready_records()
        rows = self.sheet(records)
        edited = [{**rows[0], "decision": "approve", "zomi": rows[0]["zomi"] + "."}]
        self.assertIn("differs from the sheet", self.run_approve(edited, records)[1][0])
        self.assertIn("approve or reject", self.run_approve(self.decide_rows(rows, ["yes"]), records)[1][0])
        newer = records + [rating(rows[0]["pair_hash"], 0, 0, "R02")]
        self.assertIn("not ready for approval", self.run_approve(self.decide_rows(rows, ["approve"]), newer)[1][0])

    def test_full_offline_workflow_through_the_command_line(self) -> None:
        reviews, roster = self.dir / "reviews.jsonl", self.dir / "roster.csv"
        roster.write_text("code,role\nR01,reviewer\nE01,lead_editor\n", encoding="utf-8")
        review_path, key_path, _ = export(self.database, self.dir / "batch-1", per_model=2, seed="s")
        rows = self.read(review_path)
        for row in rows:
            row["meaning"], row["fluency"] = "2", "2"
        with review_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        common = ["--reviews", str(reviews), "--roster", str(roster)]
        sheet = self.dir / "approve.csv"
        with redirect_stdout(StringIO()):
            self.assertEqual(review_main(["record", str(review_path), str(key_path), "--reviewer", "R01", *common]), 0)
            self.assertEqual(review_main(["approval-sheet", "--database", str(self.database),
                                          "--reviews", str(reviews), "--out", str(sheet)]), 0)
            approval_rows = self.read(sheet)
            approval_rows[0]["decision"] = "approve"
            with sheet.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(approval_rows[0]))
                writer.writeheader()
                writer.writerows(approval_rows)
            self.assertEqual(review_main(["approve", str(sheet), "--approver", "E01", *common]), 0)
            self.assertEqual(review_main(["approve", str(sheet), "--approver", "R01", *common]), 1)
        statuses = sorted(d.status for d in corpus_reviews.decide(corpus_reviews.load(reviews)).values())
        self.assertEqual(statuses, [HUMAN_APPROVED, READY_FOR_APPROVAL])

    def test_reviewer_excel_sheet_round_trips_ratings_and_corrections(self) -> None:
        import openpyxl
        from worksheets import main as worksheets_main  # type: ignore

        review_path, _, _ = export(self.database, self.dir / "batch-3", per_model=2, seed="s")
        sheet, back = self.dir / "rate.xlsx", self.dir / "back.csv"
        with redirect_stdout(StringIO()):
            worksheets_main(["ratings-sheet", str(review_path), "--out", str(sheet)])
            book = openpyxl.load_workbook(sheet)
            book["Rate"]["D2"], book["Rate"]["E2"], book["Rate"]["F2"] = 2, 1, "CORRECTED_PLACEHOLDER"
            book.save(sheet)
            worksheets_main(["ratings-import", str(sheet), "--out", str(back)])
        rows = self.read(back)
        self.assertEqual((rows[0]["meaning"], rows[0]["fluency"], rows[0]["correction"]), ("2", "1", "CORRECTED_PLACEHOLDER"))
        self.assertEqual([r["english"] for r in rows], [r["english"] for r in self.read(review_path)])

    def test_record_needs_the_roster_file(self) -> None:
        review_path, key_path, _ = export(self.database, self.dir / "batch-2", per_model=1, seed="s")
        args = ["record", str(review_path), str(key_path), "--reviewer", "R01",
                "--reviews", str(self.dir / "r.jsonl"), "--roster", str(self.dir / "missing.csv")]
        with redirect_stdout(StringIO()), self.assertRaisesRegex(SystemExit, "Roster not found"):
            review_main(args)


if __name__ == "__main__":
    unittest.main()
