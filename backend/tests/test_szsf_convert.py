from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml_pipeline" / "scripts"))

import corpus_reviews  # type: ignore  # noqa: E402
import szsf  # type: ignore  # noqa: E402
import szsf_convert as conv  # type: ignore  # noqa: E402
import zolai_standard  # type: ignore  # noqa: E402

# Placeholder text only: no Zomi language data is invented here.
H1 = hashlib.sha1(b"pair one").hexdigest()
H2 = hashlib.sha1(b"pair two").hexdigest()
H3 = hashlib.sha1(b"pair three").hexdigest()


def export_record(n: int, **changes) -> dict:
    record = {
        "id": f"corpus-{n}", "english": f"English sentence {n}.", "zomi": f"ZOMI_PLACEHOLDER_{n}",
        "source": "parallel_corpus", "tier": "bronze", "human_reviewed": False, "split": "train",
        "model": "model-name", "quality_score": 0.8, "quality_flags": [],
    }
    record.update(changes)
    return record


def standard(rules: list[dict] | None = None) -> tuple[zolai_standard.Standard, dict]:
    data = {"version": "1.0.0" if rules else "0.0.0", "rules": rules or []}
    return zolai_standard.parse(data), {"version": data["version"], "rules": {rule["id"] for rule in data["rules"]}}


RULE = {"id": "ZS-001", "standard": "ZSTD", "variants": ["ZVAR"], "mode": "replace",
        "approved_by": ["R01", "E01"], "approved_on": "2026-11-08", "reason": "placeholder rule for tests"}


class RecordTests(unittest.TestCase):
    def test_a_plain_corpus_pair(self) -> None:
        std, _ = standard()
        out = conv.to_szsf(export_record(1), std, None, set())
        self.assertEqual(szsf.check_record(out, {"version": "0.0.0", "rules": set()}), [])
        self.assertEqual((out["kind"], out["origin"], out["model"], out["provider_derived"]), ("translation_pair", "machine_generated", "model-name", True))
        self.assertEqual(out["zomi_standard"], out["zomi"])
        self.assertEqual(out["review"], {"status": "UNREVIEWED", "reviewers": [], "approver": None})
        self.assertEqual(out["reference"], "corpus index 1")
        self.assertNotIn("zomi_standard_rules", out)

    def test_an_own_model_is_not_provider_derived(self) -> None:
        std, _ = standard()
        self.assertFalse(conv.to_szsf(export_record(1, model="siamsil-mt-1"), std, None, {"siamsil-mt-1"})["provider_derived"])
        self.assertTrue(conv.to_szsf(export_record(1, model=None), std, None, set())["provider_derived"])  # unknown model: safe default
        self.assertEqual(conv.to_szsf(export_record(1, model=None), std, None, set())["model"], "unknown")

    def test_adopted_rules_change_only_the_standard_form(self) -> None:
        std, check = standard([RULE])
        out = conv.to_szsf(export_record(1, zomi="a ZVAR b"), std, None, set())
        self.assertEqual((out["zomi"], out["zomi_standard"], out["zomi_standard_rules"]), ("a ZVAR b", "a ZSTD b", ["ZS-001"]))
        self.assertEqual(szsf.check_record(out, check), [])

    def test_origin_by_source_and_bible_version_pairs(self) -> None:
        std, _ = standard()
        bible = {"id": "bible-tdb-kjv-1-1-1", "english": "E", "zomi": "ZOMI_PLACEHOLDER", "source": "bible_tdb",
                 "english_source": "bible_kjv", "tier": "gold", "split": "train", "reference": "Genesis 1:1"}
        out = conv.to_szsf(bible, std, None, set())
        self.assertEqual((out["origin"], out["english_source"], out["reference"]), ("human_written", "bible_kjv", "Genesis 1:1"))
        self.assertNotIn("model", out)
        self.assertEqual(conv.origin_of("daily_use_phrases"), "human_written")
        self.assertEqual(conv.origin_of("translation_master_50k"), "unknown")  # not recorded, so not guessed

    def test_review_results_come_from_decisions_and_must_agree_with_the_export(self) -> None:
        std, _ = standard()
        approved = corpus_reviews.Decision("HUMAN_APPROVED", ("R01",), "E01")
        out = conv.to_szsf(export_record(1, human_reviewed=True, tier="silver"), std, approved, set())
        self.assertEqual(out["review"], {"status": "HUMAN_APPROVED", "reviewers": ["R01"], "approver": "E01"})
        with self.assertRaisesRegex(conv.ConversionError, "no saved review decision"):
            conv.to_szsf(export_record(1, human_reviewed=True), std, None, set())
        waiting = corpus_reviews.Decision("READY_FOR_APPROVAL", ("R01",), None)
        with self.assertRaisesRegex(conv.ConversionError, "different runs"):
            conv.to_szsf(export_record(1, human_reviewed=True), std, waiting, set())
        rejected = corpus_reviews.Decision("REJECTED", ("R01",), None)
        self.assertEqual(conv.to_szsf(export_record(1), std, rejected, set())["split"], "excluded")


class FileTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.rights = self.root / "rights.json"
        self.rights.write_text(json.dumps({"sources": {"parallel_corpus": {"train": "needs_review", "display": "needs_review"}}}), encoding="utf-8")
        self.roster = self.root / "roster.csv"
        self.roster.write_text("code,role\nR01,reviewer\nE01,lead_editor\n", encoding="utf-8")
        self.db = self.root / "language.sqlite"
        con = sqlite3.connect(self.db)
        con.execute("CREATE TABLE parallel_sentences (id INTEGER PRIMARY KEY, pair_hash TEXT)")
        con.executemany("INSERT INTO parallel_sentences VALUES (?, ?)", [(1, H1), (2, H2), (3, H3)])
        con.commit()
        con.close()
        self.reviews = self.root / "reviews.jsonl"
        records = [
            {"kind": "review", "pair_hash": H1, "meaning": 2, "fluency": 2, "reviewer": "R01", "reviewed_on": "2026-11-01"},
            {"kind": "approval", "pair_hash": H1, "decision": "approve", "approver": "E01", "approved_on": "2026-11-02"},
            {"kind": "review", "pair_hash": H2, "meaning": 2, "fluency": 2, "reviewer": "R01", "reviewed_on": "2026-11-01"},
        ]
        self.reviews.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
        self.export = self.root / "train.jsonl"
        rows = [export_record(1, human_reviewed=True, tier="silver"), export_record(2), export_record(3)]
        self.export.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        self.out = self.root / "out" / "szsf-master-v1.0.0.jsonl"

    def run_main(self, *extra: str) -> tuple[int, str, str]:
        argv = ["pairs", "--input", str(self.export), "--out", str(self.out), "--rights", str(self.rights),
                "--db", str(self.db), "--reviews", str(self.reviews), "--roster", str(self.roster), *extra]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = conv.main(argv)
            except SystemExit as stop:
                code = int(stop.code or 0)
        return code, out.getvalue(), err.getvalue()

    def test_a_master_file_and_its_manifest_are_written_and_valid(self) -> None:
        code, shown, error = self.run_main()
        self.assertEqual(code, 0, error)
        self.assertIn("Wrote 3 records", shown)
        rows = [json.loads(line) for line in self.out.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["review"]["status"] for r in rows], ["HUMAN_APPROVED", "READY_FOR_APPROVAL", "UNREVIEWED"])
        manifest = json.loads(self.out.with_name("szsf-master-v1.0.0.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual((manifest["records"], manifest["counts"]["source"]), (3, {"parallel_corpus": 3}))
        rights = szsf.load_rights(self.rights)
        self.assertEqual(szsf.validate(self.out, rights, manifest=manifest), [])
        # Provider-derived records stay out of training, and the corpus is not training-cleared.
        found = szsf.validate(self.out, rights, "training")
        self.assertTrue(any("not cleared for training" in problem for problem in found))
        self.assertEqual([p for p in self.root.rglob(".szsf-convert-*")], [])  # no staging left behind

    def test_a_master_file_is_never_overwritten(self) -> None:
        self.assertEqual(self.run_main()[0], 0)
        before = self.out.read_bytes()
        code, _, error = self.run_main()
        self.assertEqual(code, 2)
        self.assertEqual(self.out.read_bytes(), before)

    def test_records_that_break_the_format_go_to_the_rejects_file(self) -> None:
        rows = [export_record(1, human_reviewed=True, tier="silver"), export_record(2, zomi=" leading space"), export_record(3)]
        self.export.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        rejects = self.root / "rejects.jsonl"
        code, _, error = self.run_main("--rejects", str(rejects))
        self.assertEqual(code, 0, error)
        written = [json.loads(line)["id"] for line in self.out.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(written, ["corpus-1", "corpus-3"])
        rejected = [json.loads(line) for line in rejects.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(rejected[0]["id"], "corpus-2")
        self.assertIn("spaces at its start", rejected[0]["problems"][0])
        self.assertIn("Left out 1 records", error)

    def test_inconsistent_inputs_stop_the_run_and_write_nothing(self) -> None:
        rows = [export_record(3, human_reviewed=True, tier="silver")]  # says reviewed; no decision exists
        self.export.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        code, _, error = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("no saved review decision", error)
        self.assertFalse(self.out.exists())
        self.assertEqual(list(self.out.parent.glob("*")), [])

    def test_a_reviewer_outside_the_roster_stops_the_run(self) -> None:
        self.roster.write_text("code,role\nR01,reviewer\n", encoding="utf-8")  # no lead editor E01
        code, _, error = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("roster", error)
        self.assertFalse(self.out.exists())

    def test_arguments_are_checked(self) -> None:
        bad_name = self.root / "master.jsonl"
        for argv in (["pairs", "--input", str(self.export), "--out", str(bad_name)],
                     ["pairs", "--input", str(self.export), "--out", str(self.out), "--reviews", str(self.reviews)]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                conv.main(argv)


if __name__ == "__main__":
    unittest.main()
