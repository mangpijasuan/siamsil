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


class CreatorAdoptedRulesTests(unittest.TestCase):
    """P-001..P-011 were adopted by the creator alone on 2026-11-13 (governance block in standard.json)."""

    def test_the_eleven_rules_are_adopted_by_the_creator_and_say_so(self) -> None:
        standard = zs.load()
        self.assertEqual(standard.version, "1.0.0")
        self.assertEqual([r.id for r in standard.rules], [f"ZS-{n:03d}" for n in range(1, 14)])
        self.assertTrue(all(r.adopted_by == "creator" and r.approved_by == () for r in standard.rules))
        got = {r.id: (list(r.variants), r.standard) for r in standard.rules}
        self.assertEqual(got["ZS-001"], (["uhi", "uhhi"], "uh hi"))
        self.assertEqual(got["ZS-002"], (["thil"], "na"))
        self.assertEqual(standard.rules[1].mode, "flag")  # changed 2026-11-13: other thil depend on context
        self.assertEqual(got["ZS-003"], (["uhiam", "uhhiam"], "uh hiam"))
        self.assertEqual(got["ZS-011"], (["ke'"], "keia"))
        self.assertEqual(got["ZS-012"], (["thilte", "thil te", "na te"], "nate"))
        self.assertEqual(got["ZS-013"], (["thil khat", "na khat"], "nakhat"))
        data = json.loads(zs.DEFAULT_STANDARD.read_text(encoding="utf-8"))
        self.assertTrue(data["governance"]["creator_may_adopt_alone"])
        self.assertEqual({r["source_proposal"] for r in data["rules"]} - {"suggested thilte -> nate", "owner, 2026-11-13"}, {f"P-{n:03d}" for n in range(1, 12)})

    def test_the_standard_is_applied_and_the_original_kept(self) -> None:
        standard = zs.load()
        result = zs.standardize("ZOMI uhi ZOMI thil ZOMI chih harsa cu tlai ZOMI", standard)
        self.assertEqual(result.text, "ZOMI uh hi ZOMI thil ZOMI cih haksa pen ziakai ZOMI")  # thil is only flagged
        self.assertEqual([f["rule"] for f in result.flags], ["ZS-002"])
        self.assertEqual(len(result.rules), 5)
        # Something and things are one word each; the longer phrase wins over the flagged thil inside it.
        self.assertEqual(zs.standardize("thil khat, na khat, thil te, na te, thilte", standard).text, "nakhat, nakhat, nate, nate, nate")
        # Whole words only, and the apostrophe form: nothing inside a longer word changes.
        self.assertEqual(zs.standardize("ZOMI ke' ZOMI ke'n ZOMI cuting", standard).text, "ZOMI keia ZOMI ke'n ZOMI cuting")

    def test_proposals_file_keeps_the_record_and_the_open_questions(self) -> None:
        data = json.loads(zs.DEFAULT_PROPOSALS.read_text(encoding="utf-8"))
        self.assertEqual(data["proposals"], [])
        records = data["adopted_by_creator"]["records"]
        self.assertEqual([p["id"] for p in records], [f"P-{n:03d}" for n in range(1, 12)])
        self.assertEqual(records[0]["owner_example"]["zomi"], "Amaute pai ding uh hi.")
        self.assertEqual(data["suggested_not_decided"], [])  # thilte -> nate was adopted as ZS-012
        self.assertEqual(zs.standardize("ZOMI thilte ZOMI", zs.load()).text, "ZOMI nate ZOMI")
        accepted = {w["word"]: w for w in data["accepted_in_owner_corrections"]["words"]}
        self.assertEqual(list(accepted), ["minit", "me"])
        self.assertEqual([w["word"] for w in data["not_one_to_one"]["words"]], ["chi", "ti", "tih", "poimawh", "tlawm", "sami", "lungleng", "thit", "tengteng", "hmel"])
        zs.load_proposals(zs.DEFAULT_PROPOSALS, zs.DEFAULT_CHECKS, zs.load())  # an empty list still loads


class CreatorGovernanceTests(unittest.TestCase):
    RULE = {"id": "ZS-001", "standard": "qa qo", "variants": ["qaqo"], "mode": "replace", "check": None,
            "adopted_by": "creator", "approved_by": [], "approved_on": "2026-11-13", "reason": "test"}
    GOVERNANCE = {"creator_may_adopt_alone": True, "decided_by": "owner", "decided_on": "2026-11-13", "owner_words": "my rule"}

    def test_creator_adoption_needs_the_recorded_decision(self) -> None:
        zs.parse({"version": "0.1.0", "governance": self.GOVERNANCE, "rules": [self.RULE]})
        for governance in (None, {**self.GOVERNANCE, "creator_may_adopt_alone": False}, {**self.GOVERNANCE, "owner_words": ""}):
            data = {"version": "0.1.0", "rules": [self.RULE]}
            if governance is not None:
                data["governance"] = governance
            with self.assertRaises(zs.StandardError):
                zs.parse(data)

    def test_creator_rules_carry_no_reviewer_codes_and_other_values_are_refused(self) -> None:
        for change in ({"approved_by": ["R01", "E01"]}, {"adopted_by": "anyone"}):
            with self.assertRaises(zs.StandardError):
                zs.parse({"version": "0.1.0", "governance": self.GOVERNANCE, "rules": [{**self.RULE, **change}]})


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
        first = {"reviewer": "A", "kind": "Zomi speaker review", "decided_on": "2026-11-13", "code": "R01"}
        self.refused([proposal(reviews=[first, {**first, "reviewer": "B", "code": "E01"}])], "two reviewers with codes")
        self.refused([proposal(reviews=[{"reviewer": "A"}])], "each review needs")
        self.refused([proposal(reviews=[{**first, "code": "Ann Smith"}])], "must look like R01")
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
