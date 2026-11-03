from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT.parent / "ml_pipeline" / "scripts"))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from database import get_database_engine  # noqa: E402
from dictionary.repository import (  # noqa: E402
    DictionaryImportConflict,
    DictionaryRepository,
    entry_type,
    jsonable,
    match_key,
)
from dictionary_sources import Issue, SourceRead, SourceRecord  # type: ignore  # noqa: E402
from models import (  # noqa: E402
    AuditEvent,
    DictionaryEntry,
    DictionaryEquivalent,
    DictionaryExample,
    DictionaryIssue,
    DictionarySense,
)

# Zomi-side strings are placeholders, never real language data. Headwords are prefixed so
# they cannot collide with a dictionary already imported into the test database.
P = "zzqtest-"
RIGHTS = {"display": "needs_review", "train": "needs_review"}


def issue(issue_id: str) -> Issue:
    return Issue(issue_id, "Category", "CODE", "Describe", "High", "Editor", {"x": 1})


class KeyTests(unittest.TestCase):
    def test_match_key_and_entry_type(self) -> None:
        self.assertEqual(match_key("  Ice  Cream "), "ice cream")
        self.assertEqual(match_key("ÉTUDE"), match_key("étude"))
        self.assertEqual(entry_type("ice cream", "n."), "term")
        self.assertEqual(entry_type("ice-cream", "n."), "word")
        self.assertEqual(entry_type("Aaron", "prop. n."), "name")
        self.assertEqual(entry_type("give up", "phrasal v."), "phrase")

    def test_jsonable(self) -> None:
        import datetime as dt
        import decimal

        self.assertEqual(jsonable({"d": dt.date(2026, 1, 2), "n": decimal.Decimal("1.5"), "l": [1]}),
                         {"d": "2026-01-02", "n": "1.5", "l": [1]})


@unittest.skipUnless(os.getenv("SIAMSIL_DATABASE_URL"), "application database is not configured")
class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = get_database_engine()
        if engine is None:
            self.skipTest("application database is not configured")
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.session = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.repo = DictionaryRepository(self.session)

    def tearDown(self) -> None:
        self.session.close()
        self.transaction.rollback()
        self.connection.close()

    def highest(self, column, prefix: str) -> int:
        ids = self.session.scalars(select(column).where(column.like(f"{prefix}%"))).all()
        return max((int(i[len(prefix):]) for i in ids), default=0)

    def load(self, source_id: str, records: list[SourceRecord], sha: str = "a" * 64, **kwargs):
        read = kwargs.pop("read", None) or SourceRead(records, {}, kwargs.pop("unlinked", []))
        return self.repo.import_source(
            source_id, title=source_id, version=None, file_name=f"{source_id}.x", sha256=sha,
            rights_key=source_id, rights=kwargs.pop("rights", RIGHTS), read=read,
        )

    def master(self) -> list[SourceRecord]:
        return [
            SourceRecord("ZD-990001", f"{P}Abandon", "v.", sense_id="ZD-990001", sense_number=1,
                         definition_en="Leave.", usage_tier="A",
                         equivalents=[("ctd", "equivalent", "ZOMI_A1"), ("ctd", "equivalent", "ZOMI_A2"),
                                      ("my", "equivalent", "MY_A")],
                         issues=[issue("OI-990001")], raw={"Entry ID": "ZD-990001"}),
            SourceRecord("ZD-990002", f"{P}abandon", "n.", sense_id="ZD-990002", raw={}),
        ]

    def test_senses_join_entries_by_headword_and_part_of_speech(self) -> None:
        entries_before = self.highest(DictionaryEntry.id, "ZE-")
        first = self.load("test_master", self.master(), unlinked=[issue("OI-990002")])
        self.assertEqual((first.senses, first.entries_created, first.entries_joined), (2, 2, 0))
        self.assertEqual((first.equivalents, first.issues), (3, 2))

        learner = SourceRecord("000001:1", f"{P}ABANDON ", "v.", explanation_ctd="ZOMI_EX",
                               equivalents=[("ctd", "equivalent", "ZOMI_C")],
                               examples=[("phrase", "a phrase", "ZOMI_P"), ("example", "A sentence.", "ZOMI_S"),
                                         ("example", "Two.", "ZOMI_T")], raw={})
        new_word = SourceRecord("000002:1", f"{P}brand new", None, raw={})
        second = self.load("test_learners", [learner, new_word])
        self.assertEqual((second.entries_created, second.entries_joined, second.examples), (1, 1, 3))

        verb = self.session.scalars(select(DictionaryEntry).where(
            DictionaryEntry.match_key == f"{P}abandon", DictionaryEntry.pos_key == "v.")).one()
        self.assertEqual(verb.headword, f"{P}Abandon")
        self.assertEqual(verb.id, f"ZE-{entries_before + 1:06d}")
        senses = self.session.scalars(select(DictionarySense).where(DictionarySense.entry_id == verb.id)
                                      .order_by(DictionarySense.source_id)).all()
        self.assertEqual([s.source_id for s in senses], ["test_learners", "test_master"])
        self.assertRegex(senses[0].id, r"^ZS-\d{6}$")
        self.assertEqual(senses[1].id, "ZD-990001")
        self.assertEqual(senses[0].review_status, "unreviewed")
        self.assertEqual(senses[0].status, "draft")

        brand_new = self.session.scalars(select(DictionaryEntry).where(
            DictionaryEntry.match_key == f"{P}brand new")).one()
        self.assertEqual((brand_new.entry_type, brand_new.part_of_speech, brand_new.pos_key), ("term", None, ""))

        positions = self.session.execute(select(DictionaryEquivalent.language, DictionaryEquivalent.position,
                                                DictionaryEquivalent.text)
                                         .where(DictionaryEquivalent.sense_id == "ZD-990001")
                                         .order_by(DictionaryEquivalent.language, DictionaryEquivalent.position)).all()
        self.assertEqual([tuple(p) for p in positions],
                         [("ctd", 1, "ZOMI_A1"), ("ctd", 2, "ZOMI_A2"), ("my", 1, "MY_A")])
        examples = self.session.execute(select(DictionaryExample.kind, DictionaryExample.position)
                                        .where(DictionaryExample.sense_id == senses[0].id)
                                        .order_by(DictionaryExample.kind, DictionaryExample.position)).all()
        self.assertEqual([tuple(e) for e in examples], [("example", 1), ("example", 2), ("phrase", 1)])

        unlinked = self.session.scalars(select(DictionaryIssue).where(
            DictionaryIssue.source_issue_id == "OI-990002")).one()
        self.assertIsNone(unlinked.sense_id)
        self.assertEqual(unlinked.status, "open")
        audit = self.session.scalars(select(AuditEvent).where(
            AuditEvent.action == "dictionary.source_imported", AuditEvent.target_id == "test_master")).one()
        self.assertEqual(audit.event_data["senses"], 2)

    def test_same_file_adds_nothing_and_a_different_file_is_refused(self) -> None:
        self.load("test_master", self.master())
        count = self.session.scalar(select(func.count()).select_from(DictionarySense))
        again = self.load("test_master", self.master())
        self.assertTrue(again.already_imported)
        self.assertEqual(self.session.scalar(select(func.count()).select_from(DictionarySense)), count)
        with self.assertRaises(DictionaryImportConflict):
            self.load("test_master", self.master(), sha="b" * 64)

    def test_source_without_rights_is_refused(self) -> None:
        with self.assertRaises(DictionaryImportConflict):
            self.load("test_master", self.master(), rights={})

    def test_rolled_back_import_leaves_no_gap_in_ids(self) -> None:
        records = [SourceRecord("1", f"{P}gap", "n.", raw={})]
        savepoint = self.session.begin_nested()
        first = self.load("test_gap", records)
        first_id = self.session.scalars(select(DictionaryEntry.id).where(
            DictionaryEntry.match_key == f"{P}gap")).one()
        savepoint.rollback()
        self.load("test_gap", records)
        second_id = self.session.scalars(select(DictionaryEntry.id).where(
            DictionaryEntry.match_key == f"{P}gap")).one()
        self.assertEqual(first.entries_created, 1)
        self.assertEqual(first_id, second_id)

    def test_summary_counts_sources_per_entry(self) -> None:
        before = self.repo.summary()
        self.load("test_master", self.master())
        self.load("test_learners", [SourceRecord("1", f"{P}abandon", "v.", raw={})])
        after = self.repo.summary()
        self.assertEqual(after["entries"] - before["entries"], 2)
        self.assertEqual(after["senses_by_source"]["test_master"], 2)
        two = after["entries_by_number_of_sources"].get(2, 0) - before["entries_by_number_of_sources"].get(2, 0)
        self.assertEqual(two, 1)


if __name__ == "__main__":
    unittest.main()
