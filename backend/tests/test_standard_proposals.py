from __future__ import annotations

import contextlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml_pipeline" / "scripts"))

import zolai_standard as zs  # type: ignore  # noqa: E402

# Sentences around the two spellings are placeholders; "uhi" and "thil" are the spellings the owner asked about.


def proposal(**changes) -> dict:
    item = {"id": "P-001", "standard": "ZSTD_ONE", "variants": ["ZVAR_ONE"], "mode": "replace", "check": None,
            "proposed_by": "project owner", "proposed_on": "2026-11-13", "approved_by": [], "reason": "test"}
    item.update(changes)
    return item


def write(directory: Path, proposals: list[dict], name: str = "proposed.json") -> Path:
    path = directory / name
    path.write_text(json.dumps({"proposals": proposals}), encoding="utf-8")
    return path


class RealProposalsTests(unittest.TestCase):
    def test_the_owners_two_proposals_are_recorded_and_not_adopted(self) -> None:
        adopted = zs.load()
        preview, records = zs.load_proposals(zs.DEFAULT_PROPOSALS, zs.DEFAULT_CHECKS, adopted)
        self.assertEqual(sorted(records), ["P-001", "P-002"])
        one, two = records["P-001"], records["P-002"]
        self.assertEqual((one["standard"], one["variants"], one["mode"]), ("uh hi", ["uhi", "uhhi"], "replace"))
        self.assertEqual((two["standard"], two["variants"], two["mode"]), ("na", ["thil"], "replace"))
        for record in records.values():
            self.assertEqual(record["approved_by"], [])  # a rule is adopted only by two reviewers
            self.assertEqual(record["proposed_by"], "project owner")
        self.assertIn("uh hi", one["owner_words"])
        self.assertIn("thil", two["owner_words"])
        self.assertTrue(two["evidence"]["caution"])  # the reviewer is told 'na' has other meanings
        # Nothing is applied: the adopted standard does not change a text that uses either spelling.
        text = "ZOMI uhi ZOMI thil ZOMI"
        self.assertEqual(zs.standardize(text, adopted).text, text)
        self.assertEqual(zs.standardize(text, preview).text, "ZOMI uh hi ZOMI na ZOMI")

    def test_the_suggestion_the_owner_has_not_decided_is_kept_apart(self) -> None:
        data = json.loads(zs.DEFAULT_PROPOSALS.read_text(encoding="utf-8"))
        self.assertEqual([p["id"] for p in data["proposals"]], ["P-001", "P-002"])
        suggested = data["suggested_not_decided"]
        self.assertEqual([(s["standard"], s["variants"]) for s in suggested], [("nate", ["thilte"])])
        self.assertIn("owner has not decided", suggested[0]["note"])


class ProposalRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def refused(self, proposals: list[dict], message: str, adopted: zs.Standard | None = None) -> None:
        with self.assertRaisesRegex(zs.StandardError, message):
            zs.load_proposals(write(self.dir, proposals), None, adopted)

    def test_good_proposals_load(self) -> None:
        preview, records = zs.load_proposals(write(self.dir, [proposal(), proposal(id="P-002", standard="ZSTD_TWO", variants=["ZVAR_TWO"])]), None)
        self.assertEqual(sorted(records), ["P-001", "P-002"])
        self.assertEqual(len(preview.rules), 2)

    def test_what_is_refused(self) -> None:
        self.refused([proposal(approved_by=["R01", "E01"])], "already has two reviewers")
        self.refused([proposal(id="ZS-001")], "id must look like P-001")
        self.refused([proposal(), proposal()], "used twice")
        self.refused([proposal(proposed_by="")], "who asked for it")
        self.refused([proposal(), proposal(id="P-002", standard="OTHER")], "also in")  # the same variant in two proposals
        self.refused([proposal(variants=["ZSTD_ONE"])], "standard spelling itself")
        adopted = zs.parse({"version": "1.0.0", "rules": [
            {"id": "ZS-001", "standard": "ZVAR_ONE", "variants": ["OLD"], "mode": "replace",
             "approved_by": ["R01", "E01"], "approved_on": "2026-11-01", "reason": "x"}]})
        self.refused([proposal()], "already uses", adopted)

    def test_an_unknown_check_is_refused(self) -> None:
        checks = self.dir / "checks.json"
        checks.write_text(json.dumps({"checks": [{"id": "known"}]}), encoding="utf-8")
        with self.assertRaisesRegex(zs.StandardError, "not in rule_checks"):
            zs.load_proposals(write(self.dir, [proposal(check="unknown")]), checks)
        zs.load_proposals(write(self.dir, [proposal(check="known")], "ok.json"), checks)


class PreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.rows = [
            ("corpus-1", "English one.", "ZOMI uhi"),
            ("corpus-2", "English two.", "ZOMI uhi ZOMI uhi"),
            ("corpus-3", "English three.", "ZOMI kuhi ZOMI"),  # inside a longer word: not a match
            ("corpus-4", "English four.", "ZOMI thil"),
        ]
        self.proposals = write(self.dir, [
            proposal(standard="uh hi", variants=["uhi", "uhhi"]),
            proposal(id="P-002", standard="na", variants=["thil"]),
        ])

    def test_counts_and_examples_without_changing_anything(self) -> None:
        preview, records = zs.load_proposals(self.proposals, None)
        report = zs.preview_changes(self.rows, preview, records, examples=1)
        self.assertEqual((report["P-001"]["occurrences"], report["P-001"]["pairs"]), (3, 2))
        self.assertEqual((report["P-002"]["occurrences"], report["P-002"]["pairs"]), (1, 1))
        self.assertEqual(report["P-001"]["examples"], [
            {"id": "corpus-1", "english": "English one.", "before": "ZOMI uhi", "after": "ZOMI uh hi"}])
        self.assertEqual(self.rows[0][2], "ZOMI uhi")  # the rows are untouched

    def database(self) -> Path:
        path = self.dir / "language.sqlite"
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE parallel_sentences (id INTEGER PRIMARY KEY, normalized_source_text TEXT, normalized_target_text TEXT)")
        con.executemany("INSERT INTO parallel_sentences VALUES (?,?,?)", [(int(i.split('-')[1]), e, z) for i, e, z in self.rows])
        con.commit()
        con.close()
        return path

    def test_the_command_reports_and_never_writes(self) -> None:
        db = self.database()
        before = db.read_bytes()
        standard = self.dir / "standard.json"
        standard.write_text(json.dumps({"version": "0.0.0", "rules": []}), encoding="utf-8")
        argv = ["--standard", str(standard), "preview", "--proposals", str(self.proposals), "--db", str(db), "--examples", "1"]
        shown = io.StringIO()
        with contextlib.redirect_stdout(shown):
            self.assertEqual(zs.main(argv), 0)
        text = shown.getvalue()
        self.assertIn("NOT adopted", text)
        self.assertIn("3 occurrences in 2 pairs", text)
        self.assertIn("after:  ZOMI uh hi", text)
        self.assertEqual(db.read_bytes(), before)
        bad = write(self.dir, [proposal(approved_by=["R01", "E01"])], "bad.json")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(zs.main(["--standard", str(standard), "preview", "--proposals", str(bad), "--db", str(db)]), 1)


if __name__ == "__main__":
    unittest.main()
