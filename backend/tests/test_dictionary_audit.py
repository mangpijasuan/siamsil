"""Dictionary audit and owner one-pass dictionary decisions (docs/DICTIONARY_AUDIT.md).

Zomi-side strings are placeholders, except the two spellings of one rule the owner adopted (ZS-001 in
data/zomi_standard_form/standard.json), read from that file at test time so nothing is invented here.
"""
from __future__ import annotations

import csv
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "scripts"))

import dictionary_audit as da  # type: ignore  # noqa: E402
import dictionary_reviews as dr  # type: ignore  # noqa: E402
import zolai_standard  # type: ignore  # noqa: E402
from import_reference_dictionaries import SCHEMA  # type: ignore  # noqa: E402

STANDARD = zolai_standard.load()
RULE = next(r for r in STANDARD.rules if r.id == "ZS-001")
VARIANT, STANDARD_FORM = RULE.variants[0], RULE.standard  # both chosen by the owner
ROSTER = {"O01": "owner", "R01": "reviewer", "E01": "lead_editor"}


def build(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    entries = [
        ("e1", "m", 1, "book", "book", "n."),
        ("e2", "m", 2, "books", "books", "n."),
        ("e3", "m", 3, "walk", "walk", "v."),
        ("e4", "m", 4, "walked", "walked", "v."),
        ("e5", "m", 5, "water", "water", "n."),
        ("e6", "m", 6, "water", "water", "n"),       # same headword and part of speech: a duplicate
        ("e7", "m", 7, "say", "say", None),           # no part of speech
        ("e8", "m", 8, "bus", "bus", "n."),          # 'bu' is no base: -us is excluded
        ("e9", "other", 1, "booking", "booking", "n."),  # base 'book' is in another source only
    ]
    con.executemany("INSERT INTO entries VALUES (?,?,?,?,?,?,?)", [(*e, None) for e in entries])
    senses = [
        ("s1", "e1", "ZOMI_BOOK"), ("s2", "e2", "ZOMI_BOOKS"), ("s3", "e3", "ZOMI_WALK"),
        ("s4", "e4", "ZOMI_WALKED"), ("s5", "e5", "ZOMI_WATER"), ("s6", "e6", "ZOMI_WATER"),
        ("s7", "e7", f"{VARIANT}; {STANDARD_FORM}"),  # one word in two spellings
        ("s8", "e8", ""),                            # no Zomi
        ("s9", "e9", "ZOMI_BOOKING"),
    ]
    con.executemany("INSERT INTO senses VALUES (?,?,1,NULL,NULL,?,NULL,NULL,NULL,NULL,NULL,NULL,'[]','unreviewed')",
                    senses)
    con.commit()
    con.close()


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.tmp.name) / "ref.sqlite"
        build(cls.db)
        con = sqlite3.connect(cls.db)
        cls.found = da.audit(con, STANDARD)
        con.close()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def of(self, category: str) -> list[dict]:
        return [f for f in self.found if f["category"] == category]

    def test_duplicate_headwords_ignore_a_trailing_full_stop_in_the_part_of_speech(self) -> None:
        dups = self.of("duplicate_headword")
        self.assertEqual([(d["headword"], d["entries"]) for d in dups], [("water", ["e5", "e6"])])

    def test_inflected_forms_are_candidates_within_one_source(self) -> None:
        pairs = {(f["headword"], f["detail"].split("'")[3]) for f in self.of("inflected_form")}
        self.assertEqual(pairs, {("books", "book"), ("walked", "walk")})  # not 'booking': other source; not 'bus'

    def test_base_forms(self) -> None:
        self.assertIn("city", da.base_forms("cities"))
        self.assertIn("box", da.base_forms("boxes"))
        self.assertIn("run", da.base_forms("running"))
        self.assertIn("bake", da.base_forms("baked"))
        self.assertEqual(da.base_forms("glass"), [])
        self.assertEqual(da.base_forms("bus"), [])

    def test_spelling_variants_use_the_owners_adopted_rules(self) -> None:
        variants = self.of("zomi_variant")
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0]["headword"], "say")
        self.assertIn(zolai_standard.norm(STANDARD_FORM), variants[0]["proposal"])
        standard = self.of("not_standard_form")
        self.assertEqual([f["senses"] for f in standard], [["s7"]])
        self.assertIn(RULE.id, standard[0]["detail"])

    def test_missing_data(self) -> None:
        self.assertEqual([f["headword"] for f in self.of("missing_pos")], ["say"])
        self.assertEqual([f["senses"] for f in self.of("missing_zomi")], [["s8"]])

    def test_findings_are_ordered_and_ids_are_stable(self) -> None:
        order = [f["category"] for f in self.found]
        self.assertEqual(order, sorted(order, key=da.CATEGORIES.index))
        con = sqlite3.connect(self.db)
        again = da.audit(con, STANDARD)
        con.close()
        self.assertEqual([f["finding_id"] for f in again], [f["finding_id"] for f in self.found])

    def test_the_dictionary_is_never_changed(self) -> None:
        before = self.db.read_bytes()
        con = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        da.audit(con, STANDARD)
        con.close()
        self.assertEqual(self.db.read_bytes(), before)


class RecordTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        build(self.dir / "ref.sqlite")
        (self.dir / "roster.csv").write_text("code,role\nO01,owner\nR01,reviewer\n", encoding="utf-8")
        self.out = self.dir / "audit"

    def run_cli(self, *args: str) -> int:
        with redirect_stdout(io.StringIO()):
            return da.main(list(args))

    def sheet_rows(self) -> list[dict]:
        with (self.out / "headword-review.csv").open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def write_rows(self, rows: list[dict]) -> None:
        with (self.out / "headword-review.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=da.SHEET_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    def test_owner_decides_and_settled_findings_are_not_offered_again(self) -> None:
        decisions = self.dir / "decisions.jsonl"
        common = ["--findings", str(self.out / "findings.jsonl"), "--decisions", str(decisions),
                  "--roster", str(self.dir / "roster.csv"), "--sheet", str(self.out / "headword-review.csv")]
        self.assertEqual(self.run_cli("audit", "--db", str(self.dir / "ref.sqlite"), "--out-dir", str(self.out)), 0)
        self.assertEqual((self.out / "findings.jsonl").stat().st_mode & 0o777, 0o600)
        rows = self.sheet_rows()
        total = len(rows)
        rows[0]["decision"], rows[1]["decision"], rows[2]["decision"] = "accept", "reject", "defer"
        self.write_rows(rows)
        self.assertEqual(self.run_cli("record", "--owner", "R01", *common), 1)  # only the owner
        self.assertFalse(decisions.exists())
        self.assertEqual(self.run_cli("record", "--owner", "O01", *common), 0)
        saved = da.load_jsonl(decisions)
        self.assertEqual([r["decision"] for r in saved], ["accept", "reject", "defer"])
        self.assertTrue(all(r["approval"] == "owner_sole" for r in saved))
        # Accepted and rejected findings drop out; the deferred one comes back.
        self.run_cli("audit", "--db", str(self.dir / "ref.sqlite"), "--out-dir", str(self.out),
                     "--decisions", str(decisions))
        self.assertEqual(len(self.sheet_rows()), total - 2)

    def test_edited_proposals_and_unknown_decisions_are_refused(self) -> None:
        self.run_cli("audit", "--db", str(self.dir / "ref.sqlite"), "--out-dir", str(self.out))
        findings = da.load_jsonl(self.out / "findings.jsonl")
        rows = self.sheet_rows()
        edited = [{**rows[0], "decision": "accept", "proposal": "something else"}]
        _, errors = da.record(edited, findings, owner="O01", roster=ROSTER, decided_on="d", recorded_at="t")
        self.assertIn("edited", errors[0])
        _, errors = da.record([{**rows[0], "decision": "maybe"}], findings, owner="O01", roster=ROSTER,
                              decided_on="d", recorded_at="t")
        self.assertIn("decision must be", errors[0])


class OwnerDictionaryDecisionTests(unittest.TestCase):
    """dictionary_review.py record --owner-decides, without the database: the decision logic only."""

    def setUp(self) -> None:
        import dictionary_review  # type: ignore

        self.tool = dictionary_review

    def review(self, sense: str, decision: str, shown_text: str, correction: str = "", reviewer: str = "O01") -> dict:
        return {"kind": "review", "sense_id": sense, "decision": decision, "correction": correction,
                "shown": dr.shown_digest(shown_text), "reviewer": reviewer, "reviewed_on": "2026-11-19"}

    def test_correct_approves_fix_edits_and_approves_wrong_rejects(self) -> None:
        rows = [{"Sense ID": "ZD-000001", "Zomi to check": "QAVO ONE"}, {"Sense ID": "ZD-000002", "Zomi to check": "QAVO TWO"},
                {"Sense ID": "ZD-000003", "Zomi to check": "QAVO THREE"}]
        records = [self.review("ZD-000001", "correct", "QAVO ONE"),
                   self.review("ZD-000002", "fix", "QAVO TWO", "QAVO FIXED"),
                   self.review("ZD-000003", "wrong", "QAVO THREE")]
        approvals, revisions, errors = self.tool.owner_decisions(
            records, rows, owner="O01", roster=ROSTER, approved_on="2026-11-19", recorded_at="t", batch="b")
        self.assertEqual(errors, [])
        self.assertEqual([a["sense_id"] for a in approvals], ["ZD-000001"])
        self.assertEqual([(r["before"], r["after"], r["approval"]) for r in revisions],
                         [("QAVO TWO", "QAVO FIXED", "owner_sole")])
        self.assertEqual([dr.validate(r) for r in approvals + revisions], [[], []])
        statuses = {k: d.status for k, d in dr.decide(records + approvals).items()}
        self.assertEqual(statuses, {"ZD-000001": dr.HUMAN_APPROVED, "ZD-000002": dr.NEEDS_CORRECTION,
                                    "ZD-000003": dr.REJECTED})
        self.assertEqual(dr.roster_problems(records + approvals, ROSTER), [])

    def test_only_the_owner_and_only_unedited_zomi(self) -> None:
        rows = [{"Sense ID": "ZD-000002", "Zomi to check": "QAVO EDITED IN SHEET"}]
        records = [self.review("ZD-000002", "fix", "QAVO TWO", "QAVO FIXED")]
        _, _, errors = self.tool.owner_decisions(records, rows, owner="R01", roster=ROSTER, approved_on="d",
                                                 recorded_at="t", batch="b")
        self.assertIn("not the owner", errors[0])
        _, revisions, errors = self.tool.owner_decisions(records, rows, owner="O01", roster=ROSTER, approved_on="d",
                                                         recorded_at="t", batch="b")
        self.assertEqual(revisions, [])
        self.assertIn("edited", errors[0])


if __name__ == "__main__":
    unittest.main()
