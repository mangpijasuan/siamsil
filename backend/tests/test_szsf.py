from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml_pipeline" / "scripts"))

import szsf  # type: ignore  # noqa: E402

# Placeholder text stands in for Zomi; no Zomi language data is invented here.


def good(**changes) -> dict:
    record = {
        "szsf_version": "1.0", "id": "corpus-1", "kind": "translation_pair",
        "english": "English sentence one.", "zomi": "ZOMI_PLACEHOLDER_ONE", "zomi_standard": "ZOMI_PLACEHOLDER_ONE",
        "standard_version": "0.0.0", "source": "parallel_corpus", "origin": "machine_generated",
        "model": "model-name", "provider_derived": False,
        "tier": "bronze", "split": "train",
        "review": {"status": "UNREVIEWED", "reviewers": [], "approver": None},
    }
    record.update(changes)
    return record


def approved(**changes) -> dict:
    return good(review={"status": "HUMAN_APPROVED", "reviewers": ["R01"], "approver": "E01"}, **changes)


class RecordTests(unittest.TestCase):
    def problems(self, record: dict) -> str:
        return "; ".join(szsf.check_record(record))

    def test_a_good_record_and_a_good_dictionary_sense_pass(self) -> None:
        self.assertEqual(szsf.check_record(good()), [])
        sense = good(id="ZD-000123", kind="dictionary_sense", english="headword", source="translation_master_50k",
                     reference="ZD-000123", quality_score=0.6, quality_flags=["identical"], model="unknown")
        self.assertEqual(szsf.check_record(sense), [])
        self.assertIn("looks like ZD-000123", self.problems(good(kind="dictionary_sense", id="sense-1")))

    def test_required_and_unknown_fields(self) -> None:
        record = good()
        del record["split"], record["review"]
        self.assertEqual(self.problems(record), "missing review, split")
        self.assertIn("unknown field 'notes'", self.problems(good(notes="x")))
        self.assertIn("szsf_version", self.problems(good(szsf_version="2.0")))
        self.assertIn("a record must be a JSON object", szsf.check_record(["x"]))

    def test_choices_are_checked(self) -> None:
        for name, bad in (("kind", "poem"), ("tier", "platinum"), ("split", "dev"), ("origin", "ai")):
            self.assertIn(f"{name} must be one of", self.problems(good(**{name: bad})), name)

    def test_text_must_be_clean(self) -> None:
        self.assertIn("english is empty", self.problems(good(english="  ")))
        self.assertIn("zomi has spaces at its start or end", self.problems(good(zomi=" ZOMI_PLACEHOLDER_ONE", zomi_standard=" ZOMI_PLACEHOLDER_ONE")))
        self.assertIn("line-break", self.problems(good(english="one\ntwo")))
        self.assertIn("not Unicode NFC", self.problems(good(english="café")))
        # UTF-8 read as Mac Roman: the damage found in the Excel export of the corpus.
        self.assertIn("damaged characters", self.problems(good(english="caf√©")))
        self.assertIn("damaged characters", self.problems(good(zomi="ZOMI_PLACEHOLDER‚Äô", zomi_standard="ZOMI_PLACEHOLDER‚Äô")))
        self.assertEqual(szsf.check_record(good(english="café, “quoted” and Ama’")), [])

    def test_a_changed_standard_form_names_its_rules(self) -> None:
        self.assertIn("must name the rules", self.problems(good(zomi_standard="ZOMI_PLACEHOLDER_STANDARD")))
        self.assertEqual(szsf.check_record(good(zomi_standard="ZOMI_PLACEHOLDER_STANDARD", zomi_standard_rules=["ZS-001"])), [])
        self.assertIn("zomi_standard_rules", self.problems(good(zomi_standard_rules=["rule-1"])))
        self.assertIn("standard_version", self.problems(good(standard_version="one")))

    def test_numbers_and_lists(self) -> None:
        self.assertIn("quality_score", self.problems(good(quality_score=1.5)))
        self.assertIn("quality_score", self.problems(good(quality_score=True)))
        self.assertIn("quality_flags must be a list of text", self.problems(good(quality_flags="identical")))

    def test_review_follows_the_two_person_rule(self) -> None:
        self.assertEqual(szsf.check_record(approved()), [])
        review = lambda status, reviewers, approver, **extra: good(  # noqa: E731
            review={"status": status, "reviewers": reviewers, "approver": approver}, **extra)
        self.assertIn("no reviewers or approver", self.problems(review("UNREVIEWED", ["R01"], None)))
        self.assertIn("needs at least one reviewer", self.problems(review("READY_FOR_APPROVAL", [], None)))
        self.assertIn("has no approver yet", self.problems(review("READY_FOR_APPROVAL", ["R01"], "E01")))
        self.assertIn("needs a lead editor", self.problems(review("HUMAN_APPROVED", ["R01"], None)))
        self.assertIn("two different people", self.problems(review("HUMAN_APPROVED", ["R01"], "R01")))
        self.assertIn("reviewer code", self.problems(review("HUMAN_APPROVED", ["R01"], "Mangpi")))
        self.assertIn("review.status must be one of", self.problems(review("APPROVED", ["R01"], "E01")))
        self.assertIn("review has unknown field", self.problems(good(review={"status": "UNREVIEWED", "reviewers": [],
                                                                            "approver": None, "score": 1})))
        self.assertIn("review needs approver", self.problems(good(review={"status": "UNREVIEWED", "reviewers": []})))

    def test_a_rejected_record_is_excluded_and_gold_from_a_machine_needs_approval(self) -> None:
        rejected = {"status": "REJECTED", "reviewers": ["R01"], "approver": None}
        self.assertIn("must have split 'excluded'", self.problems(good(review=rejected)))
        self.assertEqual(szsf.check_record(good(review=rejected, split="excluded")), [])
        self.assertIn("must be HUMAN_APPROVED", self.problems(good(tier="gold")))
        self.assertEqual(szsf.check_record(approved(tier="gold")), [])
        self.assertEqual(szsf.check_record(good(tier="gold", origin="human_written")), [])


class FileTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.rights = {
            "parallel_corpus": {"train": "needs_review", "display": "needs_review", "redistribute": "needs_review"},
            "daily_use_phrases": {"train": "cleared", "display": "cleared"},
        }

    def write(self, *records, name: str = "szsf-master-v1.0.0.jsonl") -> Path:
        path = self.root / name
        path.write_text("".join((r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)) + "\n" for r in records),
                        encoding="utf-8")
        return path

    def test_problems_name_their_line(self) -> None:
        path = self.write(good(), "{not json", good(id="corpus-1"), good(id="corpus-2", tier="gold"))
        problems = szsf.validate(path)
        self.assertEqual(len(problems), 3)
        self.assertIn("line 2: not JSON", problems[0])
        self.assertIn("line 3: id 'corpus-1' repeats line 1", problems[1])
        self.assertIn("line 4: a gold record", problems[2])
        self.assertEqual(szsf.validate(self.write()), ["the file has no records"])

    def test_every_source_must_be_in_the_rights_file(self) -> None:
        path = self.write(good(), good(id="corpus-2", source="unlisted_source"))
        self.assertEqual(szsf.validate(path, self.rights), ["line 2: source 'unlisted_source' is not in the rights file"])
        self.assertEqual(szsf.validate(path), [])  # rights checking is off without a rights file

    def test_a_purpose_needs_cleared_sources_but_excluded_records_are_skipped(self) -> None:
        phrase = good(id="phrase-1", source="daily_use_phrases", origin="human_written", tier="gold")
        excluded = good(id="corpus-9", split="excluded")
        path = self.write(phrase, good(), excluded)
        problems = szsf.validate(path, self.rights, "training")
        self.assertEqual(problems, ["line 2: source 'parallel_corpus' is not cleared for training (train: needs_review)"])
        self.assertEqual(szsf.validate(self.write(phrase, excluded), self.rights, "training"), [])
        self.assertEqual(szsf.validate(self.write(phrase), self.rights, "display"), [])

    def test_the_manifest_counts_hashes_and_snapshots_rights(self) -> None:
        records = [good(), approved(id="corpus-2", tier="silver", source="daily_use_phrases"), good(id="corpus-3", split="validation")]
        path = self.write(*records)
        manifest = szsf.build_manifest(path, self.rights, created_at="2026-11-08T00:00:00Z")
        self.assertEqual((manifest["format"], manifest["szsf_version"], manifest["records"]), ("SZSF", "1.0", 3))
        self.assertEqual(manifest["counts"]["split"], {"train": 2, "validation": 1})
        self.assertEqual(manifest["counts"]["review_status"], {"HUMAN_APPROVED": 1, "UNREVIEWED": 2})
        self.assertEqual(manifest["counts"]["source"], {"daily_use_phrases": 1, "parallel_corpus": 2})
        self.assertEqual(manifest["standard_versions"], ["0.0.0"])
        self.assertEqual(manifest["rights_snapshot"]["daily_use_phrases"],
                         {"train": "cleared", "display": "cleared", "redistribute": "not recorded", "commercial": "not recorded"})
        self.assertEqual(szsf.validate(path, self.rights, manifest=manifest), [])
        # Changing the file breaks it against its manifest.
        path.write_text(path.read_text(encoding="utf-8") + json.dumps(good(id="corpus-4")) + "\n", encoding="utf-8")
        found = szsf.validate(path, self.rights, manifest=manifest)
        self.assertEqual(len(found), 2)
        self.assertIn("SHA-256", found[0])
        self.assertIn("manifest counts 3 records, the file has 4", found[1])

    def test_the_command_line(self) -> None:
        path = self.write(good(), approved(id="corpus-2"))
        rights_file = self.root / "rights.json"
        rights_file.write_text(json.dumps({"sources": self.rights}), encoding="utf-8")
        out = self.root / "szsf-master-v1.0.0.manifest.json"
        with contextlib.redirect_stdout(io.StringIO()) as shown:
            self.assertEqual(szsf.main(["validate", str(path), "--rights", str(rights_file)]), 0)
            self.assertEqual(szsf.main(["manifest", str(path), "--out", str(out), "--rights", str(rights_file)]), 0)
            self.assertEqual(szsf.main(["validate", str(path), "--rights", str(rights_file), "--manifest", str(out)]), 0)
        self.assertIn("follows the Siamsil Zomi Standard Format 1.0", shown.getvalue())
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["records"], 2)
        # A purpose the sources are not cleared for fails, and a failing file gets no manifest.
        bad = self.write(good(english=""), name="szsf-master-v2.0.0.jsonl")
        unwritten = self.root / "szsf-master-v2.0.0.manifest.json"
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(szsf.main(["validate", str(path), "--rights", str(rights_file), "--purpose", "training"]), 1)
            self.assertEqual(szsf.main(["manifest", str(bad), "--out", str(unwritten), "--rights", str(rights_file)]), 1)
        self.assertIn("does not follow the Siamsil Zomi Standard Format", errors.getvalue())
        self.assertFalse(unwritten.exists())

    def test_review_findings(self) -> None:
        # --no-rights cannot be used to pass a purpose
        path = self.write(good())
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            szsf.main(["validate", str(path), "--no-rights", "--purpose", "training"])
        self.assertEqual(szsf.validate(path, None, "training"), ["a purpose can only be checked against the rights file: do not skip it"])
        # the file name, invalid UTF-8, and JSON values that are not objects give diagnostics, not crashes
        self.assertIn("file name", szsf.validate(self.write(good(), name="data.jsonl"))[0])
        raw = self.root / "szsf-master-v3.0.0.jsonl"
        raw.write_bytes(b"\xff\xfe\n42\nnull\n")
        found = szsf.validate(raw)
        self.assertTrue(any("line 1: not valid UTF-8" in p for p in found))
        self.assertTrue(any("line 2: a record must be a JSON object" in p for p in found))
        # both sides' sources are checked
        pair = self.write(good(english_source="unlisted_source"))
        self.assertEqual(szsf.validate(pair, self.rights), ["line 1: english_source 'unlisted_source' is not in the rights file"])
        # roster: a stranger or the wrong role is not an approval
        roster = {"R01": "reviewer", "E01": "lead_editor"}
        self.assertEqual(szsf.validate(self.write(approved()), roster=roster), [])
        strange = self.write(good(review={"status": "HUMAN_APPROVED", "reviewers": ["R09"], "approver": "R01"}))
        self.assertEqual(len(szsf.validate(strange, roster=roster)), 2)
        # provider-derived records stay out of training by default
        derived = self.write(good(provider_derived=True, source="daily_use_phrases"))
        self.assertIn("provider-derived", szsf.validate(derived, self.rights, "training")[0])
        self.assertEqual(szsf.validate(derived, self.rights, "training", allow_provider_derived=True), [])
        # a manifest whose summary was edited is refused even when the hash and count still match
        manifest = szsf.build_manifest(pair if False else self.write(good()), self.rights)
        manifest["counts"]["split"] = {"test": 1}
        self.assertEqual(szsf.validate(self.write(good()), self.rights, manifest=manifest), ["the manifest's counts does not match the file"])

    def test_record_review_findings(self) -> None:
        self.assertIn("model", "; ".join(szsf.check_record({k: v for k, v in good().items() if k != "model"})))
        self.assertIn("provider_derived", "; ".join(szsf.check_record({k: v for k, v in good().items() if k != "provider_derived"})))
        self.assertTrue(szsf.check_record(good(zomi="A\u2028B", zomi_standard="A\u2028B")))     # line separator
        self.assertTrue(szsf.check_record(good(reference="a\nb")))                               # metadata is checked too
        self.assertTrue(szsf.check_record(good(review={"status": "REJECTED", "reviewers": ["R01"], "approver": "R01"}, split="excluded")))
        self.assertEqual(szsf.check_record(good(review={"status": "UNREVIEWED", "reviewers": [], "approver": None},
                                                license_status="needs_review", verified_at="2026-11-08T12:00:00Z",
                                                prompt_version="p1", release_version="r1")), [])
        self.assertTrue(szsf.check_record(good(verified_at="yesterday")))
        self.assertEqual(szsf.check_record(good(review={"status": "READY_FOR_APPROVAL", "reviewers": ["RA0123"], "approver": None})), [])
        # cited rules must be in the adopted set, under its version
        standard = {"version": "1.0.0", "rules": {"ZS-001"}}
        base = {"zomi_standard": "CHANGED", "zomi_standard_rules": ["ZS-001"], "standard_version": "1.0.0"}
        self.assertEqual(szsf.check_record(good(**base), standard), [])
        self.assertIn("not an adopted rule", "; ".join(szsf.check_record(good(**{**base, "zomi_standard_rules": ["ZS-009"]}), standard)))
        self.assertIn("standard_version", "; ".join(szsf.check_record(good(**{**base, "standard_version": "0.0.0"}), standard)))

    def test_a_manifest_is_written_whole(self) -> None:
        path = self.write(good())
        out = self.root / "szsf-master-v1.0.0.manifest.json"
        out.write_text("old", encoding="utf-8")
        rights_file = self.root / "rights.json"
        rights_file.write_text(json.dumps({"sources": self.rights}), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(szsf.main(["manifest", str(path), "--out", str(out), "--rights", str(rights_file)]), 0)
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["records"], 1)
        self.assertEqual(list(self.root.glob("*.part")), [])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):  # the name must match the file
            szsf.main(["manifest", str(path), "--out", str(self.root / "other.json"), "--rights", str(rights_file)])


class SpecTests(unittest.TestCase):
    def test_the_spec_names_every_field_and_the_owners_definition(self) -> None:
        spec = (ROOT / "docs" / "SZSF.md").read_text(encoding="utf-8")
        for name in sorted(szsf.REQUIRED | szsf.OPTIONAL):
            self.assertIn(f"`{name}`", spec, f"docs/SZSF.md does not describe {name}")
        for status in szsf.REVIEW_STATUSES:
            self.assertIn(status, spec)
        self.assertIn("authoritative data schema and linguistic file standard developed by Siamsil", spec)

    def test_the_example_record_in_the_spec_follows_the_format(self) -> None:
        spec = (ROOT / "docs" / "SZSF.md").read_text(encoding="utf-8")
        block = spec.split("```json\n", 1)[1].split("\n```", 1)[0]
        self.assertEqual(szsf.check_record(json.loads(block)), [])


if __name__ == "__main__":
    unittest.main()
