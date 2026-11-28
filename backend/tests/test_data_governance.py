"""Data-governance checks (docs/DATA_GOVERNANCE.md). Synthetic fixtures only; Zomi-side strings are placeholders."""
from __future__ import annotations

import io
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "scripts"))
sys.path.insert(0, str(ROOT / "ml_pipeline" / "scripts"))
import data_governance as gov  # noqa: E402
import release_contract as contract  # noqa: E402

SECRET = "ITEM_TEXT_THAT_MUST_NEVER_BE_PRINTED"


def cleared(**over: str) -> dict:
    return {"display": "cleared", "train": "cleared", "commercial": "not_permitted", **over}


BLOCKED = {"display": "blocked", "train": "blocked", "commercial": "blocked"}


def write(path: Path, data: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data, indent=2), encoding="utf-8")
    return path


class DataDirCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "data"
        self.rights = {"bible_web": cleared(), "bible_tdb": cleared(), "dict_one": cleared(),
                       "church_capture": {**BLOCKED}}
        self.write_config()

    def write_config(self, **over: object) -> None:
        write(self.data / "rights.json", {"sources": self.rights})
        write(self.data / "bible_versions.json", {"versions": {"web": {}, "tdb": {}}})
        write(self.data / "dictionary_sources.json", {"sources": {"one": {"rights": "dict_one"}}})
        write(self.data / "reference_dictionaries.json", {"sources": {}})
        write(self.data / "source_files.json", {"sources": over.get("pins", {})})
        write(self.data / "governance.json", {"forbidden_sources": {"extra_forbidden": "test"},
                                              "forbidden_path_fragments": {"churchfile": "test"}})


class RegistryTests(DataDirCase):
    def test_a_consistent_registry_passes(self) -> None:
        report = gov.check_registry(self.data)
        self.assertEqual(report.failures, [])
        self.assertIn("church_capture", report.facts["forbidden_sources"])  # derived from the register
        self.assertIn("extra_forbidden", report.facts["forbidden_sources"])  # from governance.json

    def test_an_invalid_rights_state_fails(self) -> None:
        self.rights["bible_web"]["display"] = "maybe"
        self.write_config()
        self.assertTrue(any("not one of" in f for f in gov.check_registry(self.data).failures))

    def test_a_configured_source_without_a_rights_entry_fails(self) -> None:
        write(self.data / "dictionary_sources.json", {"sources": {"two": {"rights": "no_such_source"}}})
        failures = gov.check_registry(self.data).failures
        self.assertTrue(any("no_such_source" in f and "no entry" in f for f in failures))

    def test_a_bible_version_without_a_rights_entry_fails(self) -> None:
        write(self.data / "bible_versions.json", {"versions": {"web": {}, "newversion": {}}})
        self.assertTrue(any("bible_newversion" in f for f in gov.check_registry(self.data).failures))

    def test_a_forbidden_source_referenced_by_configuration_fails(self) -> None:
        self.rights["bible_tdb"] = {**BLOCKED}
        self.write_config()
        failures = gov.check_registry(self.data).failures
        self.assertTrue(any("bible_tdb" in f and "must never be served" in f for f in failures))

    def test_a_malformed_or_restricted_release_manifest_fails(self) -> None:
        write(self.data / "versions" / "bad.json", {"name": "x"})
        write(self.data / "versions" / "restricted.json", {
            "name": "siamsil-language", "version": "v2", "database": {"sha256": "a" * 64},
            "source_files": {"corpus": "zomi-data/churchfile_raw.txt"}})
        failures = gov.check_registry(self.data).failures
        self.assertTrue(any("bad.json" in f for f in failures))
        self.assertTrue(any("restricted.json" in f and "churchfile" in f for f in failures))

    def test_a_pin_without_a_checksum_or_on_a_restricted_path_fails(self) -> None:
        self.write_config(pins={"a": {"path": "x/y.txt", "sha256": "short"},
                                "b": {"path": "zomi/churchfile.txt", "sha256": "b" * 64}})
        failures = gov.check_registry(self.data).failures
        self.assertTrue(any("no full SHA-256" in f for f in failures))
        self.assertTrue(any("restricted fragment" in f for f in failures))

    def test_the_real_registry_passes(self) -> None:
        self.assertEqual(gov.check_registry(ROOT / "data").failures, [])


class DataRepoTests(DataDirCase):
    def make_repo(self, files: dict[str, str], declare: list[str] | None = None) -> Path:
        repo = self.root / "archive"
        repo.mkdir()
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True)
        lines = []
        for name, content in files.items():
            write(repo / name, content)
            if declare is None or name in declare:
                lines.append(f"{contract.sha256_text(content)}  {name}")
        write(repo / "MANIFEST.sha256", "\n".join(lines) + "\n")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "x"], check=True)
        return repo

    def test_a_matching_archive_passes(self) -> None:
        repo = self.make_repo({"a/one.txt": "one", "b/two.txt": "two"})
        report = gov.check_data_repo(repo, self.data)
        self.assertEqual(report.failures, [])
        self.assertEqual(report.facts["declared_files"], 2)
        self.assertEqual(len(report.facts["archive_commit"]), 40)

    def test_a_changed_or_missing_declared_file_fails(self) -> None:
        repo = self.make_repo({"a/one.txt": "one", "b/two.txt": "two"})
        (repo / "a" / "one.txt").write_text("changed", encoding="utf-8")
        (repo / "b" / "two.txt").unlink()
        failures = gov.check_data_repo(repo, self.data).failures
        self.assertTrue(any("checksum mismatch: a/one.txt" in f for f in failures))
        self.assertTrue(any("missing: b/two.txt" in f for f in failures))

    def test_undeclared_tracked_files_are_counted_by_folder(self) -> None:
        repo = self.make_repo({"a/one.txt": "one", "extra/x.txt": "x", "extra/y.txt": "y"}, declare=["a/one.txt"])
        report = gov.check_data_repo(repo, self.data)
        self.assertEqual(report.facts["tracked_files_not_in_MANIFEST"], 2)
        self.assertEqual(report.facts["undeclared_by_top_folder"], {"extra": 2})
        self.assertTrue(report.warnings)
        self.assertEqual(report.failures, [])

    def test_restricted_material_present_is_a_warning_but_declared_as_a_source_is_a_failure(self) -> None:
        present = self.make_repo({"a/one.txt": "one", "zomi/churchfile_raw.txt": "private"}, declare=["a/one.txt"])
        report = gov.check_data_repo(present, self.data)
        self.assertEqual(report.facts["restricted_paths_present"], 1)
        self.assertEqual(report.failures, [])
        self.assertTrue(any("restricted files are present" in w for w in report.warnings))
        self.assertNotIn("private", json.dumps(report.as_dict()))
        self.root.joinpath("archive").rename(self.root / "archive-old")
        declared = self.make_repo({"zomi/churchfile_raw.txt": "private"})
        self.assertTrue(any("declared as a pinned source" in f for f in gov.check_data_repo(declared, self.data).failures))

    def test_a_pinned_original_that_changed_fails(self) -> None:
        repo = self.make_repo({"a/one.txt": "one"})
        self.write_config(pins={"one": {"path": "a/one.txt", "sha256": "0" * 64}})
        self.assertTrue(any("does not match source_files.json" in f for f in gov.check_data_repo(repo, self.data).failures))

    def test_a_missing_manifest_fails(self) -> None:
        repo = self.root / "empty"
        repo.mkdir()
        self.assertTrue(gov.check_data_repo(repo, self.data).failures)


class ExportTests(DataDirCase):
    def export(self, manifest: dict, **splits: list[tuple[str, str]]) -> Path:
        folder = self.root / "exports" / "run1"
        write(folder / "manifest.json", manifest)
        for split, rows in splits.items():
            write(folder / f"{split}.jsonl", "\n".join(json.dumps({"english": e, "zomi": z}) for e, z in rows) + "\n")
        return self.root / "exports"

    def good(self, **over: object) -> dict:
        return {"uncleared_sources_included": [], "sources": {"bible_web": {"exported": True}},
                "splits": {"train": {"total": 2}, "test": {"total": 1}}, **over}

    TRAIN = [("Hello there.", "ZOMI_A"), ("Good morning.", "ZOMI_B")]

    def test_a_clean_export_passes(self) -> None:
        folder = self.export(self.good(), train=self.TRAIN, test=[("Thank you.", "ZOMI_C")])
        self.assertEqual(gov.check_exports(folder, self.data).failures, [])

    def test_uncleared_forbidden_and_no_longer_cleared_sources_fail(self) -> None:
        for manifest, text in (
                (self.good(uncleared_sources_included=["dict_one"]), "uncleared"),
                (self.good(sources={"church_capture": {"exported": True}}), "must never be used"),
                (self.good(sources={"dict_one": {"exported": True}}), "now")):
            with self.subTest(text):
                self.rights["dict_one"] = cleared(train="needs_review")
                self.write_config()
                folder = self.export(manifest, train=self.TRAIN, test=[("Thank you.", "ZOMI_C")])
                self.assertTrue(any(text in f for f in gov.check_exports(folder, self.data).failures))

    def test_an_exact_duplicate_across_splits_fails(self) -> None:
        folder = self.export(self.good(), train=self.TRAIN, test=[("hello   there", "zomi_a")])
        self.assertTrue(any("exact duplicate pair across train and test" in f
                            for f in gov.check_exports(folder, self.data).failures))

    def test_a_template_variant_across_splits_is_a_warning(self) -> None:
        folder = self.export(self.good(), train=[("I have 3 cats.", "ZOMI_A"), ("Good morning.", "ZOMI_B")],
                             test=[("I have 7 cats.", "ZOMI_Z")])
        report = gov.check_exports(folder, self.data)
        self.assertEqual(report.failures, [])
        self.assertTrue(any("template variants straddle" in w for w in report.warnings))

    def test_a_row_count_that_differs_from_the_manifest_fails(self) -> None:
        folder = self.export(self.good(splits={"train": {"total": 5}, "test": {"total": 1}}),
                             train=self.TRAIN, test=[("Thank you.", "ZOMI_C")])
        self.assertTrue(any("has 2 rows but the manifest says 5" in f for f in gov.check_exports(folder, self.data).failures))


class LeakageTests(DataDirCase):
    def eval_file(self, *sentences: str) -> Path:
        rows = [{"id": f"item-{i}", "direction": "en-zomi", "source_text": text, "references": [f"ZOMI_REF_{i}"]}
                for i, text in enumerate(sentences, 1)]
        return write(self.root / "eval.jsonl", "\n".join(json.dumps(r) for r in rows) + "\n")

    def train_file(self, *pairs: tuple[str, str]) -> Path:
        return write(self.root / "train.jsonl", "\n".join(json.dumps({"english": e, "zomi": z}) for e, z in pairs) + "\n")

    def run_check(self, eval_path: Path, train: Path, **kw):
        return gov.check_leakage([eval_path], None, [train], **kw)

    def test_no_overlap_passes(self) -> None:
        report = self.run_check(self.eval_file("The river is cold today."), self.train_file(("Hello there.", "ZOMI_A")))
        self.assertEqual(report.failures, [])
        self.assertEqual(report.facts["training_pairs_scanned"], 1)

    def test_exact_and_normalised_matches_fail(self) -> None:
        report = self.run_check(self.eval_file("The river is cold today."),
                                self.train_file(("the   RIVER is cold, today!", "ZOMI_X")))
        self.assertTrue(any("exact" in f and "item-1" in f for f in report.failures))

    def test_a_zomi_side_match_fails(self) -> None:
        report = self.run_check(self.eval_file("The river is cold today."),
                                self.train_file(("Unrelated sentence here.", "zomi_ref_1")))
        self.assertTrue(report.failures)

    def test_a_near_duplicate_fails_and_a_distant_sentence_does_not(self) -> None:
        item = "the farmer carried the heavy water jar up the long hill road"
        near = self.run_check(self.eval_file(item), self.train_file(
            ("the farmer carried the heavy water jar up the long hill", "ZOMI_X")), threshold=0.7)
        self.assertTrue(any("near-duplicate" in f for f in near.failures))
        far = self.run_check(self.eval_file(item), self.train_file(
            ("a child sang a quiet song beside the fire last night", "ZOMI_Y")))
        self.assertEqual(far.failures, [])

    def test_a_template_variant_is_a_warning_not_a_failure(self) -> None:
        report = self.run_check(self.eval_file("I bought 3 apples."), self.train_file(("I bought 9 apples.", "ZOMI_X")))
        self.assertEqual(report.failures, [])
        self.assertTrue(any("share a template" in w for w in report.warnings))

    def test_a_language_database_is_scanned(self) -> None:
        db = self.root / "corpus.sqlite"
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE parallel_sentences (raw_source_text TEXT, raw_target_text TEXT)")
        con.execute("INSERT INTO parallel_sentences VALUES ('The river is cold today.', 'ZOMI_Q')")
        con.commit()
        con.close()
        report = gov.check_leakage([self.eval_file("The river is cold today.")], db, [])
        self.assertTrue(report.failures)

    def test_nothing_to_compare_against_fails(self) -> None:
        self.assertTrue(gov.check_leakage([self.eval_file("x y z")], None, []).failures)

    def test_the_report_never_contains_sentence_text(self) -> None:
        report = self.run_check(self.eval_file(SECRET), self.train_file((SECRET, "ZOMI_X")))
        output = io.StringIO()
        with redirect_stdout(output):
            report.show()
        self.assertTrue(report.failures)
        self.assertNotIn(SECRET, output.getvalue() + json.dumps(report.as_dict()))


class ReleaseTests(DataDirCase):
    def release(self, **over: object) -> dict:
        digest = "a" * 64
        sets = [{"name": "en-zomi-v1.jsonl", "sha256": "b" * 64, "items": 2, "frozen": True}]
        base = {
            "schema_version": 2, "release_id": f"sha256-{digest[:16]}", "bundle_sha256": digest,
            "bundle_bytes": 1, "object_key": f"releases/sha256-{digest}/siamsil-data.tar.gz",
            "created_at_utc": "2026-11-30T00:00:00+00:00",
            "contents": {"json/rights.json": {"bytes": 1, "sha256": "c" * 64},
                         "siamsil_language.sqlite": {"bytes": 1, "sha256": "d" * 64}},
            "source": {"siamsil_data_commit": "e" * 40, "working_tree_clean": True, "binding": "database"},
            "rights_registry": {"member": "json/rights.json", "sha256": "c" * 64},
            "approval": {"status": "approved", "approved_by": "Someone", "approved_at_utc": "2026-11-30T09:00:00"},
            "exports": {"approved_counts": {}, "export_manifest_sha256": None},
            "protected_evaluation": {"sets": sets, "sets_sha256": contract.canonical_hash(sets)},
            "derivation": {"parallel_corpus": {
                "source_rows": 3, "kept": 2, "removed": {"duplicate_pair": 1, "empty_side": 0},
                "removals_file": {"name": "parallel-removals.jsonl", "sha256": "f" * 64, "records": 1}}},
        }
        base.update(over)
        return base

    def check(self, manifest: dict, environment: str = "production", **kw):
        return gov.check_release(write(self.root / "release.json", manifest), environment, self.data, **kw)

    def test_a_complete_release_passes_in_production(self) -> None:
        self.assertEqual(self.check(self.release()).failures, [])

    def test_an_unapproved_or_legacy_release_fails_in_production_only(self) -> None:
        unapproved = self.release(approval={"status": "unapproved", "approved_by": None, "approved_at_utc": None})
        self.assertTrue(self.check(unapproved).failures)
        self.assertEqual(self.check(unapproved, "development").failures, [])
        legacy = {k: v for k, v in self.release().items() if k in (
            "release_id", "bundle_sha256", "bundle_bytes", "object_key", "created_at_utc", "contents")}
        legacy["schema_version"] = 1
        self.assertTrue(any("legacy" in f for f in self.check(legacy).failures))

    def test_a_bundle_listing_restricted_material_fails(self) -> None:
        contents = {**self.release()["contents"], "json/churchfile_raw.json": {"bytes": 1, "sha256": "9" * 64}}
        self.assertTrue(any("churchfile" in f for f in self.check(self.release(contents=contents)).failures))

    def test_evaluation_sets_and_rights_register_are_checked_against_their_declarations(self) -> None:
        wrong = write(self.root / "en-zomi-v1.jsonl", '{"id": "x"}\n')
        self.assertTrue(any("does not match the hash" in f for f in self.check(self.release(), evaluation=[wrong]).failures))
        unknown = write(self.root / "other.jsonl", "{}\n")
        self.assertTrue(any("not declared" in f for f in self.check(self.release(), evaluation=[unknown]).failures))
        other_rights = write(self.root / "r.json", {"sources": {}})
        self.assertTrue(any("not the one this release declares" in f
                            for f in self.check(self.release(), rights_file=other_rights).failures))

    def test_a_draft_evaluation_set_is_a_warning(self) -> None:
        sets = [{"name": "draft.jsonl", "sha256": "b" * 64, "items": 1, "frozen": False}]
        manifest = self.release(protected_evaluation={"sets": sets, "sets_sha256": contract.canonical_hash(sets)})
        report = self.check(manifest)
        self.assertEqual(report.failures, [])
        self.assertTrue(any("draft" in w for w in report.warnings))


class CommandLineTests(DataDirCase):
    def test_exit_status_follows_failures_and_strict_warnings(self) -> None:
        with redirect_stdout(io.StringIO()):  # the report is printed; keep test logs quiet
            self.assertEqual(gov.main(["--data-dir", str(self.data), "registry"]), 0)
            self.rights["bible_web"]["display"] = "maybe"
            self.write_config()
            self.assertEqual(gov.main(["--data-dir", str(self.data), "registry"]), 1)

    def test_a_json_report_is_written(self) -> None:
        out = self.root / "report.json"
        with redirect_stdout(io.StringIO()):
            gov.main(["--data-dir", str(self.data), "--json", str(out), "registry"])
        self.assertTrue(json.loads(out.read_text(encoding="utf-8"))["passed"])


if __name__ == "__main__":
    unittest.main()
