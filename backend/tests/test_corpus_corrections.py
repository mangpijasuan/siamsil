from __future__ import annotations

import contextlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "tests"))

import corpus_reviews  # type: ignore  # noqa: E402
import corpus_revisions  # type: ignore  # noqa: E402
import szsf_convert  # type: ignore  # noqa: E402
from build_language_db import apply_reviews, apply_revisions  # type: ignore  # noqa: E402
from export_datasets import corpus_records  # type: ignore  # noqa: E402
from review_sample import correction_sheet, revise  # type: ignore  # noqa: E402
from review_sample import main as review_main  # type: ignore  # noqa: E402
from test_corpus_reviews import ROSTER, CorpusFixture, approval, rating  # type: ignore  # noqa: E402

# Zomi-side strings are placeholders, never real language data.


def fix(pair_hash: str, text: str, reviewer: str = "R01", meaning: int = 1, fluency: int = 1) -> dict:
    return {**rating(pair_hash, meaning, fluency, reviewer), "correction": text}


def revision(pair_hash: str, before: str, after: str, proposers: list[str] | None = None, approver: str = "E01") -> dict:
    return {"kind": "revision", "pair_hash": pair_hash, "before": before, "after": after,
            "proposed_by": proposers or ["R01"], "approver": approver, "approved_on": "2026-11-14", "batch": "c1"}


H = "a" * 40


class RevisionRecordTests(unittest.TestCase):
    def test_a_good_revision_and_the_rules(self) -> None:
        self.assertEqual(corpus_revisions.validate(revision(H, "ZOMI_OLD", "ZOMI_NEW")), [])
        cases = [
            (revision(H, "ZOMI_OLD", "ZOMI_NEW", ["E01"]), "own correction"),
            (revision(H, "ZOMI_OLD", "ZOMI_OLD  "), "does not change"),  # only spaces differ
            (revision(H, "ZOMI_OLD", "line one\nline two"), "one line"),
            (revision("short", "ZOMI_OLD", "ZOMI_NEW"), "40-character"),
            (revision(H, "ZOMI_OLD", "ZOMI_NEW", approver="Ann Smith"), "roster code"),
            ({**revision(H, "ZOMI_OLD", "ZOMI_NEW"), "kind": "vote"}, "unknown kind"),
            ({k: v for k, v in revision(H, "ZOMI_OLD", "ZOMI_NEW").items() if k != "before"}, "missing before"),
        ]
        for record, message in cases:
            self.assertIn(message, "; ".join(corpus_revisions.validate(record)), message)

    def test_loading_stops_on_a_bad_line_and_keeps_the_newest_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "revisions.jsonl"
            self.assertEqual(corpus_revisions.load(path), [])  # no file yet
            records = [revision(H, "A", "B"), revision(H, "B", "C"),
                       {"kind": "declined", "pair_hash": H, "after": "D", "approver": "E01", "approved_on": "d"}]
            path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
            loaded = corpus_revisions.load(path)
            self.assertEqual(corpus_revisions.latest_revisions(loaded)[H]["after"], "C")
            self.assertEqual(corpus_revisions.declined(loaded), {(H, "D")})
            path.write_text("{not json\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not JSON"):
                corpus_revisions.load(path)
            path.write_text(json.dumps(revision(H, "A", "A")) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not change"):
                corpus_revisions.load(path)

    def test_proposals_use_each_reviewers_latest_review(self) -> None:
        records = [fix(H, "OLD_FIX", "R01"), fix(H, "NEW_FIX", "R01"), fix(H, "NEW_FIX", "R02"), rating(H, 1, 1, "R03")]
        self.assertEqual(corpus_revisions.proposals(records), {H: {"NEW_FIX": ["R01", "R02"]}})


class CorrectionFlowTests(CorpusFixture):
    def setUp(self) -> None:
        super().setUp()
        self.reviews = [
            fix(self.hash_of(0), "ZOMI_FIXED_0"),                                          # needs correction, one fix
            fix(self.hash_of(1), "ZOMI_FIXED_1", "R01"), fix(self.hash_of(1), "ZOMI_FIXED_1", "R02"),  # same fix, two reviewers
            rating(self.hash_of(2), 2, 2), approval(self.hash_of(2)),                      # approved: nothing to correct
            fix(self.hash_of(3), "ZOMI_PLACEHOLDER_3"),                                    # "fix" equals the current Zomi
            rating(self.hash_of(4), 1, 1),                                                 # needs correction, no fix written
        ]

    def sheet(self, revisions: list[dict] | None = None) -> list[dict]:
        con = sqlite3.connect(self.database)
        try:
            return correction_sheet(self.reviews, revisions or [], con)
        finally:
            con.close()

    def test_the_sheet_offers_only_fixes_a_lead_editor_can_decide(self) -> None:
        rows = self.sheet()
        self.assertEqual([(r["zomi"], r["corrected_zomi"], r["proposed_by"]) for r in rows],
                         [("ZOMI_PLACEHOLDER_0", "ZOMI_FIXED_0", "R01"), ("ZOMI_PLACEHOLDER_1", "ZOMI_FIXED_1", "R01, R02")])
        # A declined fix is not offered again.
        declined = {"kind": "declined", "pair_hash": self.hash_of(0), "after": "ZOMI_FIXED_0", "approver": "E01", "approved_on": "d"}
        self.assertEqual([r["corrected_zomi"] for r in self.sheet([declined])], ["ZOMI_FIXED_1"])

    def decided(self, **changes) -> list[dict]:
        rows = self.sheet()
        for row in rows:
            row["decision"] = "approve"
        for index, values in changes.items():
            rows[int(index)].update(values)
        return rows

    def revise_rows(self, rows: list[dict], approver: str = "E01") -> tuple[list[dict], list[str]]:
        return revise(rows, approver=approver, roster=ROSTER, review_records=self.reviews, approved_on="2026-11-14", batch="c1")

    def test_approving_saves_a_revision_whose_proposers_come_from_the_reviews(self) -> None:
        records, errors = self.revise_rows(self.decided(**{"0": {"proposed_by": "E01"}}))  # the sheet's proposers are not trusted
        self.assertEqual(errors, [])
        self.assertEqual([(r["kind"], r["after"], r["before"], r["proposed_by"]) for r in records],
                         [("revision", "ZOMI_FIXED_0", "ZOMI_PLACEHOLDER_0", ["R01"]),
                          ("revision", "ZOMI_FIXED_1", "ZOMI_PLACEHOLDER_1", ["R01", "R02"])])
        self.assertEqual(corpus_revisions.validate(records[0]), [])
        declined, errors = self.revise_rows(self.decided(**{"0": {"decision": "decline"}}))
        self.assertEqual((errors, [r["kind"] for r in declined]), ([], ["declined", "revision"]))
        self.assertEqual(self.revise_rows([{**r, "decision": ""} for r in self.sheet()]), ([], []))  # blank: decide later

    def test_what_a_lead_editor_may_not_do(self) -> None:
        for rows, approver, message in (
            (self.decided(), "R01", "not listed as a lead_editor"),
            (self.decided(**{"0": {"decision": "maybe"}}), "E01", "approve or decline"),
            (self.decided(**{"0": {"zomi": "ZOMI_PLACEHOLDER_0 edited"}}), "E01", "differs from the sheet"),
            (self.decided(**{"0": {"corrected_zomi": "ZOMI_TYPED_BY_THE_LEAD_EDITOR"}}), "E01", "no reviewer wrote"),
        ):
            _, errors = self.revise_rows(rows, approver)
            self.assertIn(message, "; ".join(errors))
        # A reviewer who proposed a fix cannot approve it, and one pair gets only one approved fix.
        self.reviews.append({**fix(self.hash_of(0), "ZOMI_OTHER_0", "R02")})
        rows = self.sheet()
        for row in rows:
            row["decision"] = "approve"
        _, errors = self.revise_rows([r for r in rows if r["pair_hash"] == self.hash_of(0)])
        self.assertIn("only one correction", "; ".join(errors))
        # Another reviewer rejects the pair in the meantime: the sheet is out of date.
        stale = [r for r in self.decided() if r["pair_hash"] == self.hash_of(1)]
        self.reviews.append(rating(self.hash_of(1), 0, 0, "R03"))
        _, errors = self.revise_rows(stale)
        self.assertIn("no longer needs correction", "; ".join(errors))

    def test_a_lead_editor_who_proposed_the_fix_is_refused(self) -> None:
        roster = {**ROSTER, "E01": "lead_editor"}
        self.reviews[:] = [fix(self.hash_of(0), "ZOMI_FIXED_0", "E01")]  # the roster would not allow this review; the check is the point
        rows = self.sheet()
        rows[0]["decision"] = "approve"
        _, errors = revise(rows, approver="E01", roster=roster, review_records=self.reviews, approved_on="d", batch="b")
        self.assertIn("proposed this fix", "; ".join(errors))


class ApplyRevisionTests(CorpusFixture):
    def setUp(self) -> None:
        super().setUp()
        self.con = sqlite3.connect(self.database)
        self.addCleanup(self.con.close)

    def row(self, n: int) -> tuple:
        return self.con.execute(
            "SELECT normalized_target_text, raw_target_text, verified, quality_score, quality_flags, pair_hash "
            "FROM parallel_sentences WHERE pair_hash = ?", (self.hash_of(n),)).fetchone()

    def test_an_approved_correction_becomes_the_pairs_text(self) -> None:
        revisions = {self.hash_of(0): revision(self.hash_of(0), "ZOMI_PLACEHOLDER_0", "ZOMI_FIXED_0")}
        counts = apply_revisions(self.con, revisions)
        self.assertEqual(counts["applied"], 1)
        text, raw, verified, score, flags, pair_hash = self.row(0)
        self.assertEqual((text, raw, verified, score, pair_hash), ("ZOMI_FIXED_0", "ZOMI_PLACEHOLDER_0", 1, 1.0, self.hash_of(0)))
        self.assertIn("human_corrected", json.loads(flags))
        # Search finds the new text, not the old.
        found = lambda word: self.con.execute(  # noqa: E731
            "SELECT COUNT(*) FROM parallel_fts WHERE parallel_fts MATCH ?", (word,)).fetchone()[0]
        self.assertEqual((found("ZOMI_FIXED_0"), found("ZOMI_PLACEHOLDER_0")), (1, 0))
        # Running it again changes nothing, and the export carries the correction as a human-reviewed silver pair.
        self.assertEqual(apply_revisions(self.con, revisions)["already_applied"], 1)
        exported = {r["english"]: r for r in corpus_records(self.con, silver=set(), min_score=0.5)}["English sentence number 0."]
        self.assertEqual((exported["zomi"], exported["tier"], exported["human_reviewed"]), ("ZOMI_FIXED_0", "silver", True))
        self.assertIn("human_corrected", exported["quality_flags"])

    def test_it_never_applies_to_other_text_or_to_rejected_pairs(self) -> None:
        apply_reviews(self.con, corpus_reviews.decide([rating(self.hash_of(1), 0, 1)]))  # rejected by a reviewer
        counts = apply_revisions(self.con, {
            self.hash_of(0): revision(self.hash_of(0), "ZOMI_SOMETHING_ELSE", "ZOMI_FIXED_0"),  # the text changed since
            self.hash_of(1): revision(self.hash_of(1), "ZOMI_PLACEHOLDER_1", "ZOMI_FIXED_1"),
            "f" * 40: revision("f" * 40, "X", "Y"),
        })
        self.assertEqual((counts["applied"], counts["skipped_changed_text"], counts["skipped_rejected"], counts["not_in_corpus"]), (0, 1, 1, 1))
        self.assertEqual((self.row(0)[0], self.row(0)[2]), ("ZOMI_PLACEHOLDER_0", 0))
        self.assertEqual(self.row(1)[0], "ZOMI_PLACEHOLDER_1")

    def test_build_refuses_a_revisions_path_that_does_not_exist(self) -> None:
        import build_language_db  # type: ignore

        argv = ["build_language_db.py", "--raw", str(self.dir), "--revisions", str(self.dir / "typo.jsonl")]
        with patch.object(sys, "argv", argv), self.assertRaisesRegex(SystemExit, "Revisions file not found"):
            build_language_db.main()


class CommandLineTests(CorpusFixture):
    def test_from_review_to_a_saved_revision(self) -> None:
        reviews, revisions, roster = self.dir / "reviews.jsonl", self.dir / "revisions.jsonl", self.dir / "roster.csv"
        roster.write_text("code,role\nR01,reviewer\nE01,lead_editor\n", encoding="utf-8")
        reviews.write_text(json.dumps(fix(self.hash_of(0), "ZOMI_FIXED_0")) + "\n", encoding="utf-8")
        sheet = self.dir / "corrections.csv"
        common = ["--reviews", str(reviews), "--revisions", str(revisions)]
        with contextlib.redirect_stdout(io.StringIO()) as shown:
            self.assertEqual(review_main(["corrections-sheet", "--database", str(self.database), "--out", str(sheet), *common]), 0)
        self.assertIn("wrote 1 corrections", shown.getvalue())
        rows = self.read(sheet)
        rows[0]["decision"] = "approve"
        import csv

        with sheet.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        revise_args = ["revise", str(sheet), "--approver", "E01", "--roster", str(roster), "--date", "2026-11-14", *common]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(review_main([*revise_args, "--dry-run"]), 0)
            self.assertFalse(revisions.exists())  # a dry run saves nothing
            self.assertEqual(review_main(revise_args), 0)
        saved = corpus_revisions.load(revisions)
        self.assertEqual([(r["kind"], r["pair_hash"], r["before"], r["after"]) for r in saved],
                         [("revision", self.hash_of(0), "ZOMI_PLACEHOLDER_0", "ZOMI_FIXED_0")])
        # With the fix decided, the next sheet no longer offers it.
        with contextlib.redirect_stdout(io.StringIO()) as shown:
            review_main(["corrections-sheet", "--database", str(self.database), "--out", str(sheet), *common])
        self.assertIn("wrote 0 corrections", shown.getvalue())


class ExcelSheetTests(CorpusFixture):
    def make_csv(self, reviews: list[dict]) -> Path:
        path = self.dir / "reviews.jsonl"
        path.write_text("".join(json.dumps(r) + "\n" for r in reviews), encoding="utf-8")
        out = self.dir / "corrections.csv"
        with contextlib.redirect_stdout(io.StringIO()):
            review_main(["corrections-sheet", "--database", str(self.database), "--reviews", str(path),
                         "--revisions", str(self.dir / "none.jsonl"), "--out", str(out)])
        return out

    def worksheets(self, *argv: str) -> str:
        import worksheets  # type: ignore

        shown = io.StringIO()
        with contextlib.redirect_stdout(shown):
            worksheets.main(list(argv))
        return shown.getvalue()

    def test_the_excel_sheet_has_a_dropdown_hidden_checks_and_safe_text(self) -> None:
        import openpyxl

        # A fix that starts with "=" must stay text: Excel would otherwise run it as a formula when the sheet is opened.
        csv_path = self.make_csv([fix(self.hash_of(0), "ZOMI_FIXED_0"), fix(self.hash_of(1), "=ZOMI_LOOKS_LIKE_A_FORMULA")])
        xlsx = self.dir / "Siamsil_Corrections_E01.xlsx"
        self.assertIn("wrote corrections sheet for 2 fixes", self.worksheets("corrections-sheet", str(csv_path), "--out", str(xlsx)))
        book = openpyxl.load_workbook(xlsx)
        self.assertEqual(book.sheetnames, ["Instructions", "Corrections"])
        sheet = book["Corrections"]
        self.assertEqual([c.value for c in sheet[1]][:7], ["ID", "English", "Zomi now", "Corrected Zomi (a reviewer's fix)",
                                                          "Proposed by", "Decision", "Notes"])
        validation = sheet.data_validations.dataValidation[0]
        self.assertEqual((validation.formula1, str(validation.sqref)), ('"approve,decline"', "F2:F3"))
        self.assertTrue(sheet.column_dimensions["H"].hidden and sheet.column_dimensions["I"].hidden)
        self.assertEqual(sheet["D3"].data_type, "s")
        self.assertEqual(sheet["D3"].value, "=ZOMI_LOOKS_LIKE_A_FORMULA")

    def test_decisions_in_excel_reach_revise_unchanged(self) -> None:
        import openpyxl

        reviews = [fix(self.hash_of(0), "ZOMI_FIXED_0"), fix(self.hash_of(1), "ZOMI_FIXED_1")]
        csv_path = self.make_csv(reviews)
        xlsx = self.dir / "sheet.xlsx"
        self.worksheets("corrections-sheet", str(csv_path), "--out", str(xlsx))
        book = openpyxl.load_workbook(xlsx)
        book["Corrections"]["F2"], book["Corrections"]["F3"] = "Approve ", "decline"
        book["Corrections"]["G2"] = "checked with a speaker"
        book.save(xlsx)
        imported = self.dir / "decided.csv"
        self.assertIn("1 approved, 1 declined, 0 left for later", self.worksheets("corrections-import", str(xlsx), "--out", str(imported)))
        rows = self.read(imported)
        self.assertEqual([(r["decision"], r["notes"]) for r in rows], [("approve", "checked with a speaker"), ("decline", "")])
        # Everything else in the rows is what review_sample.py wrote, so revise accepts them.
        original = self.read(csv_path)
        for row, before in zip(rows, original):
            self.assertEqual({k: v for k, v in row.items() if k not in ("decision", "notes")},
                             {k: v for k, v in before.items() if k not in ("decision", "notes")})
        records, errors = revise(rows, approver="E01", roster=ROSTER, review_records=reviews, approved_on="2026-11-14", batch="b")
        self.assertEqual(errors, [])
        self.assertEqual([r["kind"] for r in records], ["revision", "declined"])
        self.assertEqual(records[0]["notes"], "checked with a speaker")
        # An edited row is still refused: the hidden checks no longer match.
        book = openpyxl.load_workbook(xlsx)
        book["Corrections"]["C2"], book["Corrections"]["F2"] = "ZOMI_PLACEHOLDER_0 edited", "approve"
        book.save(xlsx)
        self.worksheets("corrections-import", str(xlsx), "--out", str(imported))
        _, errors = revise(self.read(imported), approver="E01", roster=ROSTER, review_records=reviews, approved_on="d", batch="b")
        self.assertIn("differs from the sheet", "; ".join(errors))

    def test_a_wrong_decision_or_file_is_refused(self) -> None:
        import openpyxl

        csv_path = self.make_csv([fix(self.hash_of(0), "ZOMI_FIXED_0")])
        xlsx = self.dir / "sheet.xlsx"
        self.worksheets("corrections-sheet", str(csv_path), "--out", str(xlsx))
        book = openpyxl.load_workbook(xlsx)
        book["Corrections"]["F2"] = "maybe"
        book.save(xlsx)
        with self.assertRaisesRegex(SystemExit, "approve or decline"):
            self.worksheets("corrections-import", str(xlsx), "--out", str(self.dir / "o.csv"))
        self.assertFalse((self.dir / "o.csv").exists())
        other = self.dir / "other.csv"
        other.write_text("sample_id,english,zomi\nS1,E,Z\n", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "not a corrections file"):
            self.worksheets("corrections-sheet", str(other), "--out", str(self.dir / "x.xlsx"))


class SzsfConverterTests(unittest.TestCase):
    def test_pairs_with_an_approved_correction_are_left_out_and_counted(self) -> None:
        import collections

        import zolai_standard  # type: ignore

        std = zolai_standard.parse({"version": "0.0.0", "rules": []})
        plain = {"id": "corpus-1", "english": "E1", "zomi": "ZOMI_1", "source": "parallel_corpus", "tier": "bronze",
                 "human_reviewed": False, "split": "train", "model": "m", "quality_score": 1.0, "quality_flags": []}
        corrected = {**plain, "id": "corpus-2", "human_reviewed": True, "tier": "silver", "quality_flags": ["human_corrected"]}
        left_out: collections.Counter[str] = collections.Counter()
        done = list(szsf_convert.convert([plain, corrected], std, {}, set(), None, left_out))
        self.assertEqual([record["id"] for record, _ in done], ["corpus-1"])
        self.assertEqual(sum(left_out.values()), 1)


if __name__ == "__main__":
    unittest.main()
