"""Owner-only review (docs/GOVERNANCE.md): the project owner may review and approve alone; nobody else may.

Zomi-side strings are placeholders, never real language data.
"""
from __future__ import annotations

import csv
import sqlite3
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import corpus_reviews as cr  # type: ignore  # noqa: E402
import corpus_revisions  # type: ignore  # noqa: E402
import dictionary_reviews as dr  # type: ignore  # noqa: E402
import szsf  # type: ignore  # noqa: E402
from build_language_db import apply_reviews, apply_revisions  # type: ignore  # noqa: E402
from review_sample import approve, export, main as review_main, revise  # type: ignore  # noqa: E402
from test_corpus_reviews import CorpusFixture, approval, rating  # type: ignore  # noqa: E402

ROSTER = {"O01": "owner", "R01": "reviewer", "E01": "lead_editor"}
HASH = "c" * 40


def owner_approval(pair_hash: str, decision: str = "approve") -> dict:
    return {**approval(pair_hash, decision, "O01"), "approval": cr.OWNER_SOLE}


class DecideTests(unittest.TestCase):
    def test_the_owner_can_approve_their_own_review(self) -> None:
        decision = cr.decide([rating(HASH, 2, 2, "O01"), owner_approval(HASH)])[HASH]
        self.assertEqual(decision.status, cr.HUMAN_APPROVED)
        self.assertTrue(decision.owner_sole)
        self.assertEqual(decision.linguistic_status, "owner_approved")

    def test_an_unmarked_self_approval_still_does_not_count(self) -> None:
        decision = cr.decide([rating(HASH, 2, 2, "O01"), approval(HASH, approver="O01")])[HASH]
        self.assertEqual(decision.status, cr.READY_FOR_APPROVAL)
        self.assertEqual(decision.linguistic_status, "owner_reviewed")

    def test_an_approval_of_someone_elses_review_is_not_owner_sole(self) -> None:
        decision = cr.decide([rating(HASH, 2, 2, "R01"), approval(HASH, approver="O01")])[HASH]
        self.assertEqual(decision.status, cr.HUMAN_APPROVED)
        self.assertFalse(decision.owner_sole)

    def test_an_approval_older_than_a_new_review_lapses(self) -> None:
        records = [rating(HASH, 2, 2, "O01"), owner_approval(HASH), rating(HASH, 1, 1, "O01")]
        self.assertEqual(cr.decide(records)[HASH].linguistic_status, "needs_recheck")

    def test_roster_owner_acts_as_reviewer_and_lead_editor_and_only_they_approve_alone(self) -> None:
        records = [rating(HASH, 2, 2, "O01"), owner_approval(HASH)]
        self.assertEqual(cr.roster_problems(records, ROSTER), [])
        forged = [rating(HASH, 2, 2, "E01"), {**approval(HASH, approver="E01"), "approval": cr.OWNER_SOLE}]
        problems = cr.roster_problems(forged, {**ROSTER, "E01": "lead_editor"})
        self.assertTrue(any("not the owner" in p for p in problems))

    def test_approval_field_only_takes_owner_sole(self) -> None:
        self.assertTrue(cr.validate({**approval(HASH), "approval": "self"}))
        self.assertEqual(cr.validate(owner_approval(HASH)), [])

    def test_linguistic_statuses(self) -> None:
        self.assertEqual(cr.LINGUISTIC_STATUSES, ("unreviewed", "ai_suggested", "owner_reviewed",
                                                  "owner_approved", "rejected", "needs_recheck"))
        self.assertEqual(cr.linguistic_status(None), "unreviewed")
        self.assertEqual(cr.linguistic_status(cr.REJECTED), "rejected")
        # A record nobody reviewed has no decision at all: bulk machine processing never approves anything.
        self.assertEqual(cr.decide([]), {})


class RevisionRecordTests(unittest.TestCase):
    def revision(self, **changes) -> dict:
        record = {"kind": "revision", "pair_hash": HASH, "before": "ZOMI_A", "after": "ZOMI_B",
                  "proposed_by": ["O01"], "approver": "O01", "approved_on": "2026-11-19"}
        record.update(changes)
        return record

    def test_owner_edit_and_approve_must_be_marked(self) -> None:
        self.assertTrue(corpus_revisions.validate(self.revision()))
        self.assertEqual(corpus_revisions.validate(self.revision(approval=cr.OWNER_SOLE)), [])

    def test_owner_sole_is_only_for_the_owners_own_fix(self) -> None:
        self.assertTrue(corpus_revisions.validate(self.revision(proposed_by=["R01"], approval=cr.OWNER_SOLE)))

    def test_dictionary_revisions_follow_the_same_rule(self) -> None:
        record = {**self.revision(), "sense_id": "ZD-000001"}
        del record["pair_hash"]
        self.assertTrue(dr.validate(record))
        self.assertEqual(dr.validate({**record, "approval": cr.OWNER_SOLE}), [])


class DictionaryDecideTests(unittest.TestCase):
    def test_owner_approves_their_own_dictionary_review(self) -> None:
        review = {"kind": "review", "sense_id": "ZD-000001", "decision": "correct", "correction": "",
                  "shown": "x", "reviewer": "O01", "reviewed_on": "2026-11-19"}
        approval_ = {"kind": "approval", "sense_id": "ZD-000001", "decision": "approve", "approver": "O01",
                     "approved_on": "2026-11-19"}
        self.assertEqual(dr.decide([review, approval_])["ZD-000001"].status, dr.READY_FOR_APPROVAL)
        decision = dr.decide([review, {**approval_, "approval": cr.OWNER_SOLE}])["ZD-000001"]
        self.assertEqual((decision.status, decision.owner_sole), (dr.HUMAN_APPROVED, True))


class SzsfTests(unittest.TestCase):
    def record(self, **review) -> dict:
        from test_szsf import good  # type: ignore
        return good(review={"status": "HUMAN_APPROVED", "reviewers": ["O01"], "approver": "O01", **review})

    def test_owner_sole_records_pass_and_unmarked_self_approval_fails(self) -> None:
        self.assertEqual(szsf.check_record(self.record(approval="owner_sole")), [])
        self.assertTrue(any("two different people" in p for p in szsf.check_record(self.record())))
        other = self.record(approval="owner_sole", reviewers=["R01"])
        self.assertTrue(any("owner_sole means" in p for p in szsf.check_record(other)))


class OwnerWorkflowTests(CorpusFixture):
    """The owner rates a batch and decides in the same pass; the rebuild applies the decisions."""

    def setUp(self) -> None:
        super().setUp()
        self.reviews, self.revisions = self.dir / "reviews.jsonl", self.dir / "revisions.jsonl"
        self.roster = self.dir / "roster.csv"
        self.roster.write_text("code,role\nO01,owner\nR01,reviewer\nE01,lead_editor\n", encoding="utf-8")

    def write(self, path: Path, rows: list[dict]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def record(self, reviewer: str, *extra: str) -> int:
        with redirect_stdout(StringIO()):
            return review_main(["record", str(self.review_path), str(self.key_path), "--reviewer", reviewer,
                                "--reviews", str(self.reviews), "--revisions", str(self.revisions),
                                "--roster", str(self.roster), *extra])

    def rated_batch(self, scores: list[tuple[str, str, str]]) -> list[dict]:
        self.review_path, self.key_path, _ = export(self.database, self.dir / "batch", per_model=4, seed="s")
        rows = self.read(self.review_path)
        for row, (meaning, fluency, correction) in zip(rows, scores):
            row["meaning"], row["fluency"], row["correction"] = meaning, fluency, correction
        self.write(self.review_path, rows)
        return rows

    def test_approve_edit_and_approve_reject_and_defer_in_one_pass(self) -> None:
        rows = self.rated_batch([("2", "2", ""), ("1", "1", "ZOMI_OWNER_FIX"), ("0", "0", ""), ("1", "1", "")])
        self.assertEqual(self.record("O01", "--owner-decides"), 0)
        records = cr.load(self.reviews)
        self.assertEqual(cr.roster_problems(records, cr.load_roster(self.roster)), [])
        revisions = corpus_revisions.load(self.revisions)
        self.assertEqual([(r["after"], r["approval"]) for r in revisions], [("ZOMI_OWNER_FIX", "owner_sole")])

        con = sqlite3.connect(self.database)
        apply_reviews(con, cr.decide(records))
        counts = apply_revisions(con, corpus_revisions.latest_revisions(revisions))
        self.assertEqual(counts["applied"], 1)
        state = {
            english: (zomi, raw, verified, flags) for english, zomi, raw, verified, flags in con.execute(
                "SELECT normalized_source_text, normalized_target_text, raw_target_text, verified, quality_flags "
                "FROM parallel_sentences")
        }
        con.close()
        approved, fixed, rejected, deferred = (state[row["english"]] for row in rows[:4])
        self.assertEqual(approved[2], 1)
        self.assertEqual((fixed[0], fixed[2]), ("ZOMI_OWNER_FIX", 1))
        self.assertEqual(fixed[1], rows[1]["zomi"])  # the original Zomi is kept, never overwritten
        self.assertIn("reviewer_rejected", rejected[3])
        self.assertEqual(deferred[2], 0)  # meaning 1 with no fix: still open for a later decision

        statuses = corpus_revisions.linguistic_statuses(cr.decide(records), revisions)
        self.assertEqual(sorted(statuses.values()), ["needs_recheck", "owner_approved", "owner_approved", "rejected"])

    def test_only_the_owner_can_decide_in_the_same_pass(self) -> None:
        self.rated_batch([("2", "2", "")])
        self.assertEqual(self.record("R01", "--owner-decides"), 1)
        self.assertFalse(self.reviews.exists())

    def test_a_fix_on_a_rejected_rating_is_refused(self) -> None:
        self.rated_batch([("0", "0", "ZOMI_OWNER_FIX")])
        self.assertEqual(self.record("O01", "--owner-decides"), 1)
        self.assertFalse(self.reviews.exists())

    def test_without_the_flag_the_owner_records_ratings_only(self) -> None:
        self.rated_batch([("2", "2", "")])
        self.assertEqual(self.record("O01"), 0)
        self.assertEqual({cr.kind_of(r) for r in cr.load(self.reviews)}, {"review"})


class OwnerSheetTests(CorpusFixture):
    """The two-sheet route (approval sheet, corrections sheet) also lets the owner approve their own work."""

    def test_owner_approves_own_review_and_own_fix_others_still_cannot(self) -> None:
        pair, fix_pair = self.hash_of(0), self.hash_of(1)
        records = [rating(pair, 2, 2, "O01"), {**rating(fix_pair, 1, 1, "O01"), "correction": "ZOMI_OWNER_FIX"}]
        con = sqlite3.connect(self.database)
        from review_sample import approval_sheet, correction_sheet  # type: ignore
        rows = [{**row, "decision": "approve"} for row in approval_sheet(records, con)]
        fixes = [{**row, "decision": "approve"} for row in correction_sheet(records, [], con)]
        con.close()

        saved, errors = approve(rows, approver="O01", roster=ROSTER, existing=records, approved_on="d", batch="a")
        self.assertEqual(errors, [])
        self.assertEqual(saved[0]["approval"], cr.OWNER_SOLE)
        self.assertEqual(cr.decide(records + saved)[pair].status, cr.HUMAN_APPROVED)

        revised, errors = revise(fixes, approver="O01", roster=ROSTER, review_records=records,
                                 approved_on="d", batch="c")
        self.assertEqual(errors, [])
        self.assertEqual(revised[0]["approval"], cr.OWNER_SOLE)

        lead_reviews = [{**r, "reviewer": "E01"} for r in records]
        _, errors = approve(rows, approver="E01", roster={**ROSTER, "E01": "lead_editor"},
                            existing=lead_reviews, approved_on="d", batch="a")
        self.assertTrue(errors)  # E01 is not a roster reviewer, and in any case cannot approve their own review


if __name__ == "__main__":
    unittest.main()
