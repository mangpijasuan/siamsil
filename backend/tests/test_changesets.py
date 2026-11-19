"""Changesets: plan, preview, apply, build, roll back (docs/CHANGESETS.md). Zomi-side strings are placeholders,
except the spellings of owner-adopted rule ZS-001, read from data/zomi_standard_form/standard.json."""
from __future__ import annotations

import io
import json
import sqlite3
import sys
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import changesets as cs  # type: ignore  # noqa: E402
import dictionary_audit as da  # type: ignore  # noqa: E402
import proposals as pr  # type: ignore  # noqa: E402
from test_dictionary_audit import STANDARD, STANDARD_FORM, build  # type: ignore  # noqa: E402


def headword_decision(finding: dict, decision: str = "accept") -> dict:
    return {"kind": "headword_decision", "finding_id": finding["finding_id"], "category": finding["category"],
            "decision": decision, "digest": finding["digest"], "decided_by": "O01", "recorded_at": "2026-11-19T10:00:00Z",
            "approval": "owner_sole"}


def proposal_decision(p: dict, decision: str = "accept", edited: str = "") -> dict:
    return {"kind": "proposal_decision", "proposal_id": p["proposal_id"], "decision": decision, "edited_text": edited,
            "origin": p["origin"], "recorded_at": "2026-11-19T10:00:00Z", "approval": "owner_sole"}


class ChangesetTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.base = self.dir / "ref.sqlite"
        build(self.base)
        con = sqlite3.connect(self.base)
        self.findings = da.audit(con, STANDARD)
        con.close()
        (self.dir / "roster.csv").write_text("code,role\nO01,owner\nR01,reviewer\n", encoding="utf-8")
        self.changesets = self.dir / "changesets"
        self.ledger = self.dir / "ledger.jsonl"
        self.out = self.dir / "applied.sqlite"
        model = {"name": "m", "version": "1", "prompt_sha256": "a" * 64, "run_id": "r"}
        self.proposals = [
            pr.make("headword_candidate", {"type": "new"}, {"zomi": "qanew", "occurrences": 4}, "attested",
                    "deterministic", {"name": "mine-words", "version": "1"}, ["bible_tdb"],
                    [{"source": "bible_tdb", "ref": "tdb:1:1:1"}]),
            pr.make("definition", {"type": "sense", "id": "s1"}, {"english": "provider wording"}, "ai_candidate",
                    "provider_assisted", {**model, "provider_terms": {"product": "p", "terms_reference": "t",
                                                                      "reviewed_on": "d"}}, ["bible_web"]),
            pr.make("definition", {"type": "sense", "id": "s3"}, {"english": "model wording"}, "ai_candidate",
                    "local_model", model, ["bible_web"]),
        ]

    def finding(self, category: str, headword: str) -> dict:
        return next(f for f in self.findings if f["category"] == category and f["headword"] == headword)

    def decisions(self):
        headwords = [headword_decision(self.finding("duplicate_headword", "water")),
                     headword_decision(self.finding("zomi_variant", "say")),
                     headword_decision(self.finding("inflected_form", "books")),
                     headword_decision(self.finding("inflected_form", "walked"), "reject"),
                     headword_decision(self.finding("missing_pos", "say"))]
        props = [proposal_decision(self.proposals[0]), proposal_decision(self.proposals[1]),
                 proposal_decision(self.proposals[2], "edit", "the owner's own meaning")]
        return headwords, props

    def cli(self, *args: str) -> int:
        with redirect_stdout(io.StringIO()):
            try:
                return cs.main(list(args))
            except SystemExit as exit_:
                return 1 if exit_.code else 0

    def make_changeset(self) -> Path:
        headwords, props = self.decisions()
        for name, rows in (("findings", self.findings), ("hw", headwords), ("proposals", self.proposals),
                           ("pd", props)):
            (self.dir / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        self.assertEqual(self.cli("plan", "--findings", str(self.dir / "findings.jsonl"), "--headword-decisions",
                                  str(self.dir / "hw.jsonl"), "--proposals", str(self.dir / "proposals.jsonl"),
                                  "--proposal-decisions", str(self.dir / "pd.jsonl"), "--changesets-dir",
                                  str(self.changesets), "--ledger", str(self.ledger)), 0)
        return self.changeset_files()[0]

    def changeset_files(self) -> list[Path]:
        return sorted(f for f in self.changesets.glob("C-*.json") if ".preview" not in f.name)

    def owner(self, command: str, changeset: Path, who: str = "O01") -> int:
        return self.cli(command, "--changeset", str(changeset), "--ledger", str(self.ledger), "--roster",
                        str(self.dir / "roster.csv"), "--owner", who)

    def build_copy(self) -> sqlite3.Connection:
        self.assertEqual(self.cli("build", "--base-db", str(self.base), "--out", str(self.out), "--ledger",
                                  str(self.ledger), "--changesets-dir", str(self.changesets)), 0)
        return sqlite3.connect(self.out)

    def test_plan_turns_accepted_decisions_into_changes_and_asks_for_missing_values(self) -> None:
        changeset = json.loads(self.make_changeset().read_text(encoding="utf-8"))
        ops = Counter(op["op"] for op in changeset["ops"])
        self.assertEqual(ops, Counter({"merge_entries": 1, "standardize_zomi": 1, "mark_inflected": 1,
                                       "add_zomi_headword": 1, "annotate_sense": 1, "set_definition": 1}))
        self.assertEqual(len(changeset["needs_input"]), 1)  # missing part of speech: no value to guess
        provider = next(op for op in changeset["ops"] if op["provider_derived"])
        self.assertEqual(provider["op"], "annotate_sense")  # provider wording never becomes dictionary text

    def test_apply_needs_the_owner_and_a_preview_then_build_applies_and_rollback_restores(self) -> None:
        path = self.make_changeset()
        before_bytes = self.base.read_bytes()
        self.assertEqual(self.owner("apply", path), 1)  # not previewed
        self.assertEqual(self.cli("preview", "--changeset", str(path), "--base-db", str(self.base)), 0)
        self.assertEqual(self.base.read_bytes(), before_bytes)  # the preview ran on a throwaway copy
        self.assertEqual(self.owner("apply", path, "R01"), 1)  # only the owner
        self.assertEqual(self.owner("apply", path), 0)
        self.assertEqual(self.owner("apply", path), 1)  # not twice

        con = self.build_copy()
        self.assertEqual(con.execute("SELECT COUNT(*) FROM entries WHERE headword = 'water'").fetchone()[0], 1)
        self.assertEqual(con.execute("SELECT entry_id FROM senses WHERE id = 's6'").fetchone()[0], "e5")
        self.assertEqual(con.execute("SELECT zomi FROM senses WHERE id = 's7'").fetchone()[0], STANDARD_FORM)
        self.assertEqual(con.execute("SELECT entry_id, base_headword FROM inflected_forms").fetchall(), [("e2", "book")])
        self.assertEqual(con.execute("SELECT definition_en FROM senses WHERE id = 's3'").fetchone()[0],
                         "the owner's own meaning")
        self.assertIsNone(con.execute("SELECT definition_en FROM senses WHERE id = 's1'").fetchone()[0])
        self.assertEqual(con.execute("SELECT provider_derived FROM sense_annotations").fetchall(), [(1,)])
        self.assertEqual(con.execute("SELECT zomi FROM zomi_headwords").fetchall(), [("qanew",)])
        self.assertEqual(con.execute("SELECT COUNT(*) FROM applied_changes").fetchone()[0], 6)
        con.close()
        self.assertEqual(self.base.read_bytes(), before_bytes)  # the originals are never edited

        # Decisions already applied are not planned again.
        self.assertEqual(len(self.changeset_files()), 1)
        with redirect_stdout(io.StringIO()):
            cs.main(["plan", "--findings", str(self.dir / "findings.jsonl"), "--headword-decisions",
                     str(self.dir / "hw.jsonl"), "--proposals", str(self.dir / "proposals.jsonl"),
                     "--proposal-decisions", str(self.dir / "pd.jsonl"), "--changesets-dir", str(self.changesets),
                     "--ledger", str(self.ledger)])
        self.assertEqual(len(self.changeset_files()), 1)

        self.assertEqual(self.owner("rollback", path), 0)
        con = self.build_copy()
        self.assertEqual(con.execute("SELECT COUNT(*) FROM entries WHERE headword = 'water'").fetchone()[0], 2)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM applied_changes").fetchone()[0], 0)
        con.close()
        kinds = [e["kind"] for e in cs.load_jsonl(self.ledger)]
        self.assertEqual(kinds, ["applied", "rolled_back"])  # the ledger keeps both

    def test_a_change_that_no_longer_fits_is_skipped_as_a_conflict(self) -> None:
        path = self.make_changeset()
        con = sqlite3.connect(self.base)
        con.execute("DELETE FROM senses WHERE id = 's7'")
        con.execute("DELETE FROM entries WHERE id = 'e5'")
        con.commit()
        con.close()
        self.cli("preview", "--changeset", str(path), "--base-db", str(self.base))
        self.owner("apply", path)
        con = self.build_copy()
        statuses = Counter(row[0] for row in con.execute("SELECT op FROM applied_changes"))
        con.close()
        self.assertNotIn("merge_entries", statuses)
        self.assertNotIn("standardize_zomi", statuses)

    def test_the_training_export_still_reads_the_applied_copy(self) -> None:
        import export_datasets  # type: ignore

        path = self.make_changeset()
        self.cli("preview", "--changeset", str(path), "--base-db", str(self.base))
        self.owner("apply", path)
        self.build_copy().close()
        rows = list(export_datasets.reference_records(self.out, Counter()))
        self.assertTrue(all("provider wording" not in json.dumps(r) for r in rows))

    def test_status_counts_from_the_files(self) -> None:
        path = self.make_changeset()
        self.cli("preview", "--changeset", str(path), "--base-db", str(self.base))
        self.owner("apply", path)
        report = cs.status(findings_path=self.dir / "findings.jsonl", headword_decisions_path=self.dir / "hw.jsonl",
                           proposals_path=self.dir / "proposals.jsonl",
                           proposal_decisions_path=self.dir / "pd.jsonl", ledger_path=self.ledger)
        self.assertEqual(report["dictionary_findings"]["total"], len(self.findings))
        self.assertEqual(report["dictionary_findings"]["accept"], 4)
        self.assertEqual(report["dictionary_findings"]["reject"], 1)
        self.assertEqual(report["proposals"], {"total": 3, "accept": 2, "edit": 1})
        self.assertEqual(report["changesets"]["applied"], 1)


if __name__ == "__main__":
    unittest.main()
