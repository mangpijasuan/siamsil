from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import unittest
from hashlib import sha256
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import corpus_reviews  # type: ignore  # noqa: E402
from build_language_db import release_counts  # type: ignore  # noqa: E402
from database import get_database_engine  # noqa: E402
from models import AuditEvent, CorpusReviewRecord, ReviewImport  # noqa: E402
from reviews.repository import (  # noqa: E402
    ReviewImportConflict,
    ReviewRecordRepository,
    canonical,
    record_ids,
)

sys.path.insert(0, str(PROJECT_ROOT / "backend" / "scripts"))
from export_reviews import write_export  # type: ignore  # noqa: E402

HASH_A, HASH_B = "a" * 40, "b" * 40


def rating(pair_hash: str, meaning: int, fluency: int, reviewer: str = "R01", **extra: object) -> dict:
    return {
        "kind": "review",
        "pair_hash": pair_hash,
        "meaning": meaning,
        "fluency": fluency,
        "reviewer": reviewer,
        "reviewed_on": "2026-10-25",
        "recorded_at": "2026-10-25T18:00:00Z",
        "batch": "test",
        "notes": "",
        "correction": "",
        **extra,
    }


def approval(pair_hash: str, decision: str = "approve", approver: str = "E01") -> dict:
    return {
        "kind": "approval",
        "pair_hash": pair_hash,
        "decision": decision,
        "approver": approver,
        "approved_on": "2026-10-26",
        "recorded_at": "2026-10-26T09:00:00Z",
        "batch": "approval-1",
        "notes": "",
    }


def sample_records() -> list[dict]:
    # Placeholder text only; never real Zomi language data.
    legacy = rating(HASH_B, 1, 1, reviewer="R02")
    del legacy["kind"], legacy["recorded_at"]  # saved before approvals existed
    return [
        rating(HASH_A, 2, 2, notes="reads well", correction="placeholder correction ✓"),
        legacy,
        approval(HASH_A),
        rating(HASH_B, 0, 1),
        approval(HASH_B, "reject", approver="E02"),
    ]


class RecordIdentityTests(unittest.TestCase):
    def test_identity_ignores_key_order(self) -> None:
        record = rating(HASH_A, 2, 1)
        reordered = dict(reversed(list(record.items())))
        self.assertEqual(canonical(record), canonical(reordered))
        self.assertEqual(record_ids([record]), record_ids([reordered]))

    def test_identical_records_keep_separate_identities(self) -> None:
        ids = record_ids([rating(HASH_A, 2, 1), rating(HASH_A, 2, 1)])
        self.assertEqual(len(set(ids)), 2)

    def test_identity_depends_only_on_earlier_records(self) -> None:
        records = sample_records()
        self.assertEqual(record_ids(records)[:3], record_ids(records[:3]))


ROSTER = {"R01": "reviewer", "R02": "reviewer", "E01": "lead_editor", "E02": "lead_editor"}


class ImportCheckTests(unittest.TestCase):
    def test_boolean_scores_are_not_scores(self) -> None:
        record = rating(HASH_A, 2, 2)
        record["meaning"] = True
        self.assertEqual(corpus_reviews.validate(record), ["meaning and fluency must each be 0, 1, or 2"])

    def test_every_actor_must_be_in_the_roster_with_the_right_role(self) -> None:
        self.assertEqual(corpus_reviews.roster_problems(sample_records(), ROSTER), [])
        forged = [rating(HASH_A, 2, 2, reviewer="R09"), approval(HASH_A, approver="R01")]
        self.assertEqual(
            corpus_reviews.roster_problems(forged, ROSTER),
            [
                "record 1: R09 is not listed as a reviewer in the roster",
                "record 2: R01 is not listed as a lead_editor in the roster",
            ],
        )


class ExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.dir = Path(self.folder.name)
        self.out = self.dir / "corpus-reviews.jsonl"
        self.records = sample_records()

    def tearDown(self) -> None:
        self.folder.cleanup()

    def reference(self, records: list[dict]) -> bytes:
        path = self.dir / "reference.jsonl"
        path.unlink(missing_ok=True)
        corpus_reviews.append(path, records)
        data = path.read_bytes()
        path.unlink()
        return data

    def leftovers(self) -> list[str]:
        return sorted(path.name for path in self.dir.iterdir() if path.name != self.out.name)

    def test_writes_the_same_bytes_as_the_offline_workflow(self) -> None:
        write_export(self.records, self.out)
        self.assertEqual(self.out.read_bytes(), self.reference(self.records))
        self.assertEqual(corpus_reviews.load(self.out), self.records)
        self.assertEqual(self.leftovers(), [])

    def test_extends_a_file_the_database_has_moved_past(self) -> None:
        corpus_reviews.append(self.out, self.records[:2])
        write_export(self.records, self.out)
        self.assertEqual(self.out.read_bytes(), self.reference(self.records))

    def test_keeps_a_file_holding_decisions_the_database_lacks(self) -> None:
        corpus_reviews.append(self.out, self.records)
        before = self.out.read_bytes()
        with self.assertRaisesRegex(ValueError, "not stored in the database"):
            write_export(self.records[:3], self.out)
        self.assertEqual(self.out.read_bytes(), before)
        self.assertEqual(self.leftovers(), [])

    def test_keeps_a_file_whose_history_differs(self) -> None:
        changed = sample_records()
        changed[0] = rating(HASH_A, 1, 1)
        corpus_reviews.append(self.out, changed[:2])
        before = self.out.read_bytes()
        with self.assertRaises(ValueError):
            write_export(self.records, self.out)
        self.assertEqual(self.out.read_bytes(), before)

    def test_keeps_a_malformed_file(self) -> None:
        self.out.write_text("not json\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            write_export(self.records, self.out)
        self.assertEqual(self.out.read_text(encoding="utf-8"), "not json\n")


class ReleaseCountTests(unittest.TestCase):
    def test_release_records_how_many_review_records_it_used(self) -> None:
        self.assertEqual(
            release_counts(10, 20, sample_records()),
            {"dictionary_entries": 10, "parallel_sentences": 20, "corpus_review_records": 5},
        )

    def test_release_without_reviews_has_no_review_count(self) -> None:
        self.assertEqual(release_counts(10, 20, []), {"dictionary_entries": 10, "parallel_sentences": 20})


@unittest.skipUnless(os.getenv("SIAMSIL_DATABASE_URL"), "application database is not configured")
class ReviewImportIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = get_database_engine()
        if engine is None:
            self.skipTest("application database is not configured")
        # Check before opening the test transaction: tearDown does not run after a skip.
        with Session(engine) as probe:
            if probe.scalar(select(func.count()).select_from(CorpusReviewRecord)):
                self.skipTest("corpus_review_records is not empty; these tests need an empty table")
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.session = Session(bind=self.connection, expire_on_commit=False)
        self.repository = ReviewRecordRepository(self.session)
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "corpus-reviews.jsonl"

    def tearDown(self) -> None:
        self.session.close()
        self.transaction.rollback()
        self.connection.close()
        self.folder.cleanup()

    def write(self, records: list[dict]) -> list[dict]:
        """Write records the way review_sample.py does, then read them back the way the importer does."""
        self.path.unlink(missing_ok=True)
        corpus_reviews.append(self.path, records)
        return corpus_reviews.load(self.path)

    def import_file(self, records: list[dict]):
        return self.repository.import_records(
            records,
            source_name=self.path.name,
            source_sha256=sha256(self.path.read_bytes()).hexdigest(),
            request_id="review-import-test",
        )

    def test_round_trip_is_exact_and_decides_the_same(self) -> None:
        records = self.write(sample_records())
        result = self.import_file(records)

        self.assertEqual((result.records_in_file, result.already_stored, result.added), (5, 0, 5))
        stored = self.repository.records()
        self.assertEqual(stored, records)
        exported = Path(self.folder.name) / "exported.jsonl"
        corpus_reviews.append(exported, stored)
        self.assertEqual(exported.read_bytes(), self.path.read_bytes())
        self.assertEqual(corpus_reviews.decide(stored), corpus_reviews.decide(records))
        self.assertEqual(
            {pair: decision.status for pair, decision in corpus_reviews.decide(stored).items()},
            {HASH_A: corpus_reviews.HUMAN_APPROVED, HASH_B: corpus_reviews.REJECTED},
        )

    def test_import_then_export_reproduces_the_file(self) -> None:
        self.import_file(self.write(sample_records()))
        exported = Path(self.folder.name) / "exported" / "corpus-reviews.jsonl"
        write_export(self.repository.records(), exported)
        self.assertEqual(exported.read_bytes(), self.path.read_bytes())

    def test_typed_columns_match_each_record(self) -> None:
        self.import_file(self.write(sample_records()))
        rows = self.session.execute(
            select(
                CorpusReviewRecord.position,
                CorpusReviewRecord.kind,
                CorpusReviewRecord.actor_code,
                CorpusReviewRecord.decided_on,
                CorpusReviewRecord.meaning,
                CorpusReviewRecord.decision,
            ).order_by(CorpusReviewRecord.position)
        ).all()
        self.assertEqual(
            [tuple(row) for row in rows],
            [
                (0, "review", "R01", "2026-10-25", 2, None),
                (1, "review", "R02", "2026-10-25", 1, None),
                (2, "approval", "E01", "2026-10-26", None, "approve"),
                (3, "review", "R01", "2026-10-25", 0, None),
                (4, "approval", "E02", "2026-10-26", None, "reject"),
            ],
        )

    def test_order_is_kept_because_it_changes_decisions(self) -> None:
        # The same two records in the other order: the approval predates the review, so it does not count.
        approved = self.write([rating(HASH_A, 2, 2), approval(HASH_A)])
        self.import_file(approved)
        stored = self.repository.records()
        self.assertEqual(corpus_reviews.decide(stored)[HASH_A].status, corpus_reviews.HUMAN_APPROVED)
        self.assertEqual(
            corpus_reviews.decide(list(reversed(stored)))[HASH_A].status, corpus_reviews.READY_FOR_APPROVAL
        )

    def test_reimporting_the_same_file_adds_nothing(self) -> None:
        records = self.write(sample_records())
        first = self.import_file(records)
        again = self.import_file(records)

        self.assertEqual((again.already_stored, again.added), (5, 0))
        self.assertNotEqual(again.import_id, first.import_id)
        self.assertEqual(len(self.repository.records()), 5)
        # The check that added nothing is still on record.
        logged = self.session.get(ReviewImport, again.import_id)
        self.assertEqual((logged.records_in_file, logged.records_added), (5, 0))

    def test_appended_records_are_added_after_the_stored_ones(self) -> None:
        self.import_file(self.write(sample_records()[:3]))
        result = self.import_file(self.write(sample_records()))

        self.assertEqual((result.already_stored, result.added), (3, 2))
        self.assertEqual(self.repository.records(), corpus_reviews.load(self.path))
        positions = self.session.scalars(
            select(CorpusReviewRecord.position)
            .where(CorpusReviewRecord.import_id == result.import_id)
            .order_by(CorpusReviewRecord.position)
        ).all()
        self.assertEqual(positions, [3, 4])

    def test_an_older_copy_of_the_file_adds_nothing(self) -> None:
        self.import_file(self.write(sample_records()))
        result = self.import_file(self.write(sample_records()[:2]))
        self.assertEqual((result.records_in_file, result.already_stored, result.added), (2, 5, 0))

    def test_a_file_with_a_different_history_is_refused(self) -> None:
        original = self.write(sample_records())
        self.import_file(original)
        changed = sample_records()
        changed[1] = rating(HASH_B, 2, 2, reviewer="R02")

        with self.assertRaisesRegex(ReviewImportConflict, "record 2 differs"):
            self.import_file(self.write(changed + [rating(HASH_A, 1, 1)]))
        self.assertEqual(self.repository.records(), original)

    def test_identical_lines_are_both_kept(self) -> None:
        records = self.write([rating(HASH_A, 2, 1), rating(HASH_A, 2, 1)])
        self.assertEqual(self.import_file(records).added, 2)
        self.assertEqual(self.import_file(records).added, 0)
        self.assertEqual(self.repository.records(), records)

    def test_each_import_is_audited(self) -> None:
        result = self.import_file(self.write(sample_records()))
        event = self.session.scalar(select(AuditEvent).where(AuditEvent.target_id == str(result.import_id)))
        self.assertEqual(event.action, "reviews.records_imported")
        self.assertEqual(event.request_id, "review-import-test")
        self.assertEqual(event.event_data["records_added"], 5)
        self.assertEqual(event.event_data["source_sha256"], sha256(self.path.read_bytes()).hexdigest())

    def test_stored_records_cannot_be_edited_or_deleted(self) -> None:
        self.import_file(self.write(sample_records()))
        for statement in (
            "UPDATE corpus_review_records SET meaning = 0 WHERE position = 0",
            "DELETE FROM corpus_review_records WHERE position = 0",
            "TRUNCATE corpus_review_records",
        ):
            with self.subTest(statement=statement):
                savepoint = self.connection.begin_nested()
                with self.assertRaisesRegex(DBAPIError, "append-only"):
                    self.connection.execute(text(statement))
                savepoint.rollback()

    def test_database_rejects_a_review_without_scores(self) -> None:
        self.import_file(self.write(sample_records()))
        import_id = self.session.scalar(select(ReviewImport.id))
        for kind, decision in (("review", None), ("approval", None)):
            with self.subTest(kind=kind):
                savepoint = self.connection.begin_nested()
                with self.assertRaises(IntegrityError):
                    self.connection.execute(
                        text(
                            "INSERT INTO corpus_review_records (position, record_id, import_id, kind, pair_hash,"
                            " actor_code, decided_on, meaning, fluency, decision, record)"
                            " VALUES (5, 'x', :import_id, :kind, :pair, 'R01', '2026-10-25', NULL, NULL, :decision, '{}')"
                        ),
                        {"import_id": import_id, "pair": HASH_A, "kind": kind, "decision": decision},
                    )
                savepoint.rollback()

    def test_database_rejects_a_record_with_fields_of_the_wrong_kind(self) -> None:
        self.import_file(self.write(sample_records()))
        import_id = self.session.scalar(select(ReviewImport.id))
        savepoint = self.connection.begin_nested()
        with self.assertRaises(IntegrityError):
            self.connection.execute(
                text(
                    "INSERT INTO corpus_review_records (position, record_id, import_id, kind, pair_hash,"
                    " actor_code, decided_on, meaning, fluency, decision, record)"
                    " VALUES (5, 'x', :import_id, 'approval', :pair, 'E01', '2026-10-26', 2, 2, 'approve', '{}')"
                ),
                {"import_id": import_id, "pair": HASH_A},
            )
        savepoint.rollback()


@unittest.skipUnless(os.getenv("SIAMSIL_DATABASE_URL"), "application database is not configured")
class ConcurrentImportTests(unittest.TestCase):
    """Two imports of the same file at once must not store anything twice.

    Imports here commit, so this runs only against the CI/test database and only when the
    review tables start empty; it empties them again afterwards.
    """

    def setUp(self) -> None:
        if os.getenv("SIAMSIL_ENVIRONMENT") != "test":
            self.skipTest("commits to the database; runs only with SIAMSIL_ENVIRONMENT=test")
        self.engine = get_database_engine()
        with Session(self.engine) as session:
            if session.scalar(select(func.count()).select_from(CorpusReviewRecord)):
                self.skipTest("corpus_review_records is not empty")

    def tearDown(self) -> None:
        with self.engine.begin() as connection:
            # The table refuses TRUNCATE; only this test's own cleanup lifts that, inside one transaction.
            connection.execute(text("ALTER TABLE corpus_review_records DISABLE TRIGGER corpus_review_records_no_truncate"))
            connection.execute(text("TRUNCATE corpus_review_records, review_imports"))
            connection.execute(text("ALTER TABLE corpus_review_records ENABLE TRIGGER corpus_review_records_no_truncate"))
            connection.execute(text("DELETE FROM audit_events WHERE action = 'reviews.records_imported'"))

    def test_two_imports_at_once_store_each_record_once(self) -> None:
        records = sample_records()
        start = threading.Barrier(2)
        results, errors = [], []

        def run() -> None:
            try:
                with Session(self.engine) as session:
                    start.wait(timeout=10)
                    results.append(
                        ReviewRecordRepository(session).import_records(
                            records, source_name="corpus-reviews.jsonl", source_sha256="0" * 64
                        )
                    )
                    session.commit()
            except Exception as error:  # surfaced below
                errors.append(error)

        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(errors, [])
        self.assertEqual(sorted(result.added for result in results), [0, 5])
        with Session(self.engine) as session:
            self.assertEqual(ReviewRecordRepository(session).records(), records)
            self.assertEqual(session.scalar(select(func.count()).select_from(ReviewImport)), 2)


@unittest.skipUnless(os.getenv("SIAMSIL_DATABASE_URL"), "application database is not configured")
class ImportCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "corpus-reviews.jsonl"
        self.roster = Path(self.folder.name) / "roster.csv"
        self.roster.write_text(
            "code,role\n" + "".join(f"{code},{role}\n" for code, role in ROSTER.items()), encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.folder.cleanup()

    def run_command(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "backend" / "scripts" / "import_reviews.py"), *args],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

    def stored_count(self) -> int:
        with Session(get_database_engine()) as session:
            return session.scalar(select(func.count()).select_from(CorpusReviewRecord))

    def test_dry_run_reports_without_saving(self) -> None:
        if self.stored_count():
            self.skipTest("corpus_review_records is not empty")
        corpus_reviews.append(self.path, sample_records())
        completed = self.run_command(str(self.path), "--roster", str(self.roster), "--dry-run")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("5 records in corpus-reviews.jsonl; 0 already stored; would add 5", completed.stdout)
        self.assertEqual(self.stored_count(), 0)

    def test_records_by_people_outside_the_roster_import_nothing(self) -> None:
        if self.stored_count():
            self.skipTest("corpus_review_records is not empty")
        corpus_reviews.append(self.path, [rating(HASH_A, 2, 2), rating(HASH_A, 2, 2, reviewer="R09"), approval(HASH_A)])
        completed = self.run_command(str(self.path), "--roster", str(self.roster))
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("record 2: R09 is not listed as a reviewer in the roster", completed.stderr)
        self.assertEqual(self.stored_count(), 0)

    def test_the_roster_is_required(self) -> None:
        corpus_reviews.append(self.path, sample_records())
        completed = self.run_command(str(self.path))
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--roster", completed.stderr)

    def test_a_malformed_file_imports_nothing(self) -> None:
        self.path.write_text('{"kind": "review", "pair_hash": "short"}\n', encoding="utf-8")
        completed = self.run_command(str(self.path), "--roster", str(self.roster))
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Nothing imported", completed.stderr)

if __name__ == "__main__":
    unittest.main()
