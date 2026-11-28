"""The data-release contract: valid, mismatched, missing and tampered release manifests (docs/DATA_RELEASES.md).

Zomi-side strings are placeholders, never real language data.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(PROJECT / "ml_pipeline" / "scripts"))
import build_language_db as build  # noqa: E402
import fetch_data  # noqa: E402
import release_contract as contract  # noqa: E402
import release_manifest  # noqa: E402

ROWS = [
    ("Hello there.", "ZOMI_ONE"),
    ("Good morning.", "ZOMI_TWO"),
    ("Hello there.", "ZOMI_ONE"),  # exact duplicate of row 1
    ("", "ZOMI_EMPTY"),  # empty English side
    ("Thank you.", "ZOMI_THREE"),
    ("Good morning.", "ZOMI_TWO"),  # exact duplicate of row 2
]
PIN_ENV = {"SIAMSIL_ENVIRONMENT": "production"}


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


class ReleaseFixture(unittest.TestCase):
    """Builds a small but real release: a corpus ingested by build_language_db, a bundle, and a schema 2 manifest."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

        self.repo = self.root / "siamsil-data"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "test@example.invalid")
        git(self.repo, "config", "user.name", "Test")
        (self.repo / "README.md").write_text("placeholder\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "placeholder")

        corpus = self.root / "corpus.csv"
        with corpus.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["index", "en", "zomi", "model", "worker"])
            for index, (en, zomi) in enumerate(ROWS):
                writer.writerow([index, en, zomi, "test-model", "test-worker"])
        self.language = self.root / "siamsil_language.sqlite"
        con = build.connect(self.language)
        build.create_schema(con)
        stats = build.ingest_parallel(con, corpus, "2026-11-30T00:00:00+00:00")
        self.record_source(con, build.source_state(self.repo))
        con.commit()
        con.close()
        self.stats = stats
        self.removals = self.root / "parallel-removals.jsonl"
        self.removal_record = build.write_removals(stats["removals"], self.removals)
        self.quality = self.root / "quality_report.json"
        self.quality.write_text(json.dumps({"parallel": {
            "source_rows": stats["counts"]["source_rows"], "unique_pairs_kept": stats["counts"]["ingested"],
            "duplicates_dropped": stats["counts"].get("duplicates", 0), "empty_dropped": stats["counts"].get("empty", 0),
        }}), encoding="utf-8")

        bible = sqlite3.connect(self.root / "bible_versions.sqlite")
        bible.execute("CREATE TABLE example (x INTEGER)")
        bible.commit()
        bible.close()
        self.rights = self.root / "rights.json"
        self.rights.write_text(json.dumps({"sources": {"bible_web": {"display": "cleared"}}}), encoding="utf-8")
        self.bundle = self.root / "siamsil-data.tar.gz"
        self.make_bundle()

        self.evaluation = self.root / "en-zomi-v1.jsonl"
        self.evaluation.write_text('{"id": "ITEM_SECRET_1"}\n{"id": "ITEM_SECRET_2"}\n', encoding="utf-8")

    @staticmethod
    def record_source(con: sqlite3.Connection, state: dict | None) -> None:
        """What build_language_db.py stores: the dataset_versions row, with the siamsil-data commit when known."""
        files = {"parallel_csv": "corpus.csv"}
        if state is not None:
            files["siamsil_data_source"] = state
        con.execute("INSERT INTO dataset_versions (name, version, created_at, script_version, source_files) "
                    "VALUES (?, ?, ?, ?, ?)", ("siamsil-language", "v2", "2026-11-30T00:00:00+00:00", "test", json.dumps(files)))

    def rebuild_language_db(self, state: dict | None) -> None:
        """Replace the language database's recorded source state, then re-pack the bundle."""
        con = sqlite3.connect(self.language)
        con.execute("DELETE FROM dataset_versions")
        self.record_source(con, state)
        con.commit()
        con.close()
        self.make_bundle()

    def make_bundle(self) -> None:
        with tarfile.open(self.bundle, "w:gz") as archive:
            archive.add(self.language, arcname="siamsil_language.sqlite")
            archive.add(self.root / "bible_versions.sqlite", arcname="bible_versions.sqlite")
            archive.add(self.rights, arcname="json/rights.json")

    def manifest(self, **overrides) -> dict:
        parts = dict(
            source=release_manifest.source_record(self.repo, self.language),
            approval=release_manifest.approval_record("Owner", "2026-11-30T09:00:00"),
            exports=release_manifest.exports_record(None),
            evaluation=release_manifest.evaluation_record([self.evaluation]),
            derivation=release_manifest.derivation_record(self.quality, self.removals),
        )
        parts.update(overrides)
        return release_manifest.build_v2(self.bundle, created_at="2026-11-30T09:30:00+00:00", **parts)

    def install_to(self, name: str = "installed") -> Path:
        target = self.root / name
        target.mkdir()
        with tarfile.open(self.bundle, "r:gz") as archive:
            archive.extractall(target)
        return target


class ValidManifestTests(ReleaseFixture):
    def test_a_complete_release_verifies_in_production(self) -> None:
        manifest = self.manifest()
        installed = self.install_to()
        contract.verify(manifest, environment="production", root=installed, full=True,
                        expected_bundle_sha256=manifest["bundle_sha256"])
        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(manifest["source"]["siamsil_data_commit"], release_manifest.source_record(self.repo)["siamsil_data_commit"])
        self.assertTrue(manifest["source"]["working_tree_clean"])
        self.assertEqual(manifest["source"]["binding"], "database")

    def test_schema_1_fields_are_kept(self) -> None:
        manifest, legacy = self.manifest(), release_manifest.validate(self.bundle, created_at="2026-11-30T09:30:00+00:00")
        for key in ("release_id", "bundle_sha256", "bundle_bytes", "object_key", "contents", "created_at_utc"):
            self.assertEqual(manifest[key], legacy[key], key)

    def test_the_duplicate_removal_is_reproducible_row_by_row(self) -> None:
        manifest = self.manifest()
        corpus = manifest["derivation"]["parallel_corpus"]
        self.assertEqual(corpus["source_rows"], 6)
        self.assertEqual(corpus["kept"], 3)
        self.assertEqual(corpus["removed"], {"duplicate_pair": 2, "empty_side": 1})
        self.assertEqual(corpus["source_rows"], corpus["kept"] + sum(corpus["removed"].values()))
        lines = [json.loads(line) for line in self.removals.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(r["source_row"], r["reason"]) for r in lines],
                         [(3, "duplicate_pair"), (4, "empty_side"), (6, "duplicate_pair")])
        self.assertNotIn("Hello", self.removals.read_text(encoding="utf-8"))  # positions and hashes only, no text
        self.assertEqual(contract.check_derivation(manifest, self.removals, self.language), [])

    def test_an_unapproved_release_is_fine_in_development_and_refused_in_production(self) -> None:
        manifest = self.manifest(approval=release_manifest.approval_record(None, None))
        self.assertEqual(manifest["approval"]["status"], "unapproved")
        contract.verify(manifest, environment="development")
        with self.assertRaisesRegex(contract.ReleaseVerificationError, "unapproved"):
            contract.verify(manifest, environment="production")

    def test_nothing_approves_a_release_by_default(self) -> None:
        self.assertEqual(release_manifest.approval_record(None, None)["status"], "unapproved")
        with self.assertRaises(ValueError):
            release_manifest.approval_record("Owner", None)

    def test_a_legacy_manifest_is_accepted_only_for_development_and_test(self) -> None:
        legacy = release_manifest.validate(self.bundle)
        contract.verify(legacy, environment="development")
        contract.verify(legacy, environment="test")
        for environment in ("staging", "production"):
            with self.assertRaisesRegex(contract.ReleaseVerificationError, "legacy"):
                contract.verify(legacy, environment=environment)

    def test_export_counts_come_from_the_export_manifest_and_refuse_uncleared_sources(self) -> None:
        export = self.root / "manifest.json"
        export.write_text(json.dumps({"splits": {"train": {"total": 10}, "validation": {"total": 2}, "test": {"total": 3}},
                                      "uncleared_sources_included": []}), encoding="utf-8")
        record = release_manifest.exports_record(export)
        self.assertEqual(record["approved_counts"], {"train": 10, "validation": 2, "test": 3})
        contract.verify(self.manifest(exports=record), environment="production")
        export.write_text(json.dumps({"splits": {}, "uncleared_sources_included": ["parallel_corpus"]}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "uncleared"):
            release_manifest.exports_record(export)

    def test_evaluation_sets_are_recorded_by_hash_only(self) -> None:
        record = release_manifest.evaluation_record([self.evaluation])
        self.assertEqual(record["sets"], [{"name": "en-zomi-v1.jsonl", "sha256": hashlib.sha256(
            self.evaluation.read_bytes()).hexdigest(), "items": 2, "frozen": False}])
        self.assertFalse(record["sets"][0]["frozen"])  # nothing is frozen unless a person declares it
        self.assertNotIn("ITEM_SECRET", json.dumps(record))

    def test_a_build_from_a_dirty_data_repository_is_recorded_and_refused_in_production(self) -> None:
        self.rebuild_language_db({**build.source_state(self.repo), "working_tree_clean": False})
        manifest = self.manifest()
        self.assertFalse(manifest["source"]["working_tree_clean"])
        with self.assertRaisesRegex(contract.ReleaseVerificationError, "working_tree_clean"):
            contract.verify(manifest, environment="production")
        contract.verify(manifest, environment="development")

    def test_the_source_commit_must_be_the_one_the_shipped_database_was_built_from(self) -> None:
        (self.repo / "later.txt").write_text("a later commit", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "later")
        with self.assertRaisesRegex(ValueError, "built from siamsil-data"):
            release_manifest.source_record(self.repo, self.language)

    def test_an_operator_supplied_commit_is_labelled_and_refused_in_production(self) -> None:
        self.rebuild_language_db(None)  # a database built before the commit was recorded
        manifest = self.manifest()
        self.assertEqual(manifest["source"]["binding"], "operator_supplied")
        contract.verify(manifest, environment="development")
        with self.assertRaisesRegex(contract.ReleaseVerificationError, "binding"):
            contract.verify(manifest, environment="production")

    def test_freezing_an_evaluation_set_is_explicit_and_tied_to_its_hash(self) -> None:
        named_like_final = self.root / "eval.jsonl"  # a draft with an innocent-looking name
        named_like_final.write_text('{"id": "x"}\n', encoding="utf-8")
        self.assertFalse(release_manifest.evaluation_record([named_like_final])["sets"][0]["frozen"])
        digest = hashlib.sha256(named_like_final.read_bytes()).hexdigest()
        self.assertTrue(release_manifest.evaluation_record([named_like_final], {"eval.jsonl": digest})["sets"][0]["frozen"])
        with self.assertRaisesRegex(ValueError, "not the version declared frozen"):
            release_manifest.evaluation_record([named_like_final], {"eval.jsonl": "0" * 64})
        with self.assertRaisesRegex(ValueError, "declared frozen but not supplied"):
            release_manifest.evaluation_record([named_like_final], {"other.jsonl": digest})
        named_like_final.write_text('{"id": "changed"}\n', encoding="utf-8")  # edited after the declaration
        with self.assertRaisesRegex(ValueError, "not the version declared frozen"):
            release_manifest.evaluation_record([named_like_final], {"eval.jsonl": digest})


class MismatchedManifestTests(ReleaseFixture):
    def test_a_rights_hash_that_disagrees_with_the_bundle_is_refused(self) -> None:
        manifest = self.manifest()
        manifest["rights_registry"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(contract.ReleaseVerificationError, "rights_registry.sha256"):
            contract.verify(manifest, environment="production")

    def test_the_configured_rights_snapshot_must_match_the_release(self) -> None:
        manifest = self.manifest()
        contract.verify(manifest, environment="production", expected_rights_sha256=manifest["rights_registry"]["sha256"])
        with self.assertRaisesRegex(contract.ReleaseVerificationError, "configured rights snapshot"):
            contract.verify(manifest, environment="production", expected_rights_sha256="1" * 64)

    def test_a_rights_override_must_be_the_verified_register_in_strict_environments(self) -> None:
        manifest = self.manifest()
        other = self.root / "other-rights.json"
        other.write_text(json.dumps({"sources": {"bible_web": {"display": "cleared"}, "extra": {}}}), encoding="utf-8")
        with self.assertRaisesRegex(contract.ReleaseVerificationError, "SIAMSIL_RIGHTS_FILE"):
            contract.verify(manifest, environment="production", rights_override=other)
        with self.assertRaisesRegex(contract.ReleaseVerificationError, "SIAMSIL_RIGHTS_FILE"):
            contract.verify(manifest, environment="production", rights_override=self.root / "absent.json")
        contract.verify(manifest, environment="production", rights_override=self.rights)  # the same bytes: fine
        contract.verify(manifest, environment="development", rights_override=other)  # a developer's own register

    def test_the_api_refuses_to_start_with_a_different_rights_register_in_production(self) -> None:
        from settings import Settings
        data_dir = self.root / "json"
        data_dir.mkdir()
        (data_dir / "rights.json").write_text("{}", encoding="utf-8")
        common = dict(environment="production", database_url="postgresql+psycopg://u:p@h/db", data_dir=data_dir,
                      _env_file=None)
        Settings(**common)
        Settings(**common, rights_file=data_dir / "rights.json")
        with self.assertRaisesRegex(ValueError, "SIAMSIL_RIGHTS_FILE"):
            Settings(**common, rights_file=self.root / "elsewhere.json")
        Settings(environment="development", rights_file=self.root / "elsewhere.json", _env_file=None)

    def test_a_manifest_for_another_bundle_is_refused(self) -> None:
        manifest = self.manifest()
        with self.assertRaisesRegex(contract.ReleaseVerificationError, "not the bundle this deployment expects"):
            contract.verify(manifest, environment="production", expected_bundle_sha256="2" * 64)

    def test_a_derivation_that_does_not_add_up_is_refused(self) -> None:
        manifest = self.manifest()
        manifest["derivation"]["parallel_corpus"]["kept"] += 1
        with self.assertRaisesRegex(contract.ReleaseVerificationError, "does not add up"):
            contract.verify(manifest, environment="development")

    def test_an_approved_release_must_name_who_approved_it(self) -> None:
        manifest = self.manifest()
        manifest["approval"]["approved_by"] = ""
        with self.assertRaisesRegex(contract.ReleaseVerificationError, "approved_by"):
            contract.verify(manifest, environment="production")

    def test_release_id_and_object_key_must_follow_the_bundle_digest(self) -> None:
        for field in ("release_id", "object_key"):
            manifest = self.manifest()
            manifest[field] = "wrong"
            with self.assertRaises(contract.ReleaseVerificationError, msg=field):
                contract.verify(manifest, environment="development")


class MissingPartsTests(ReleaseFixture):
    def test_every_schema_2_declaration_is_required(self) -> None:
        for key in ("source", "rights_registry", "approval", "exports", "protected_evaluation", "derivation"):
            for environment in ("development", "production"):
                manifest = self.manifest()
                del manifest[key]
                with self.subTest(key=key, environment=environment):
                    with self.assertRaises(contract.ReleaseVerificationError):
                        contract.verify(manifest, environment=environment)

    def test_every_problem_is_reported_not_just_the_first(self) -> None:
        manifest = self.manifest()
        del manifest["source"]
        del manifest["approval"]
        with self.assertRaises(contract.ReleaseVerificationError) as raised:
            contract.verify(manifest, environment="production")
        self.assertGreaterEqual(len(raised.exception.problems), 2)

    def test_a_missing_installed_file_is_refused(self) -> None:
        manifest = self.manifest()
        installed = self.install_to()
        (installed / "bible_versions.sqlite").unlink()
        with self.assertRaisesRegex(contract.ReleaseVerificationError, "missing installed file"):
            contract.verify(manifest, environment="production", root=installed)

    def test_a_bundle_without_a_rights_register_cannot_be_released(self) -> None:
        with tarfile.open(self.bundle, "w:gz") as archive:
            archive.add(self.language, arcname="siamsil_language.sqlite")
            archive.add(self.root / "bible_versions.sqlite", arcname="bible_versions.sqlite")
        with self.assertRaisesRegex(ValueError, "rights"):
            self.manifest()

    def test_a_missing_removal_record_is_reported(self) -> None:
        problems = contract.check_derivation(self.manifest(), self.root / "absent.jsonl", self.language)
        self.assertTrue(any("not found" in p for p in problems))

    def test_unknown_schema_and_non_objects_are_refused(self) -> None:
        for bad in ({"schema_version": 99}, [], None, {}):
            with self.assertRaises(contract.ReleaseVerificationError):
                contract.verify(bad, environment="development")


class TamperedManifestTests(ReleaseFixture):
    def test_a_changed_database_is_caught_by_the_full_check_even_at_the_same_size(self) -> None:
        manifest = self.manifest()
        installed = self.install_to()
        path = installed / "siamsil_language.sqlite"
        data = bytearray(path.read_bytes())
        data[-1] ^= 0xFF
        path.write_bytes(bytes(data))
        with self.assertRaisesRegex(contract.ReleaseVerificationError, "does not match the manifest"):
            contract.verify(manifest, environment="production", root=installed, full=True)
        contract.verify(manifest, environment="production", root=installed, full=False)  # the cheap check is size-based

    def test_a_changed_size_is_caught_by_the_cheap_check(self) -> None:
        manifest = self.manifest()
        installed = self.install_to()
        with (installed / "siamsil_language.sqlite").open("ab") as handle:
            handle.write(b"x")
        with self.assertRaisesRegex(contract.ReleaseVerificationError, "size mismatch"):
            contract.verify(manifest, environment="production", root=installed, full=False)

    def test_a_changed_rights_register_is_caught_even_by_the_cheap_check(self) -> None:
        manifest = self.manifest()
        installed = self.install_to()
        (installed / "json" / "rights.json").write_text(json.dumps({"sources": {"x": {"display": "cleared"}}}), encoding="utf-8")
        with self.assertRaises(contract.ReleaseVerificationError) as raised:
            contract.verify(manifest, environment="production", root=installed, full=False)
        self.assertTrue(any("rights" in p for p in raised.exception.problems))

    def test_edited_manifest_fields_are_caught(self) -> None:
        manifest = self.manifest()
        cases = {
            "evaluation hash": lambda m: m["protected_evaluation"]["sets"][0].update(sha256="3" * 64),
            "contents hash": lambda m: m["contents"]["json/rights.json"].update(sha256="4" * 64),
            "removal count": lambda m: m["derivation"]["parallel_corpus"]["removals_file"].update(records=0),
            "commit": lambda m: m["source"].update(siamsil_data_commit="not-a-sha"),
        }
        for name, edit in cases.items():
            edited = copy.deepcopy(manifest)
            edit(edited)
            with self.subTest(name), self.assertRaises(contract.ReleaseVerificationError):
                contract.verify(edited, environment="production")

    def test_a_tampered_removal_record_is_caught(self) -> None:
        manifest = self.manifest()
        self.removals.write_text(self.removals.read_text(encoding="utf-8").replace("duplicate_pair", "empty_side", 1),
                                 encoding="utf-8")
        problems = contract.check_derivation(manifest, self.removals, self.language)
        self.assertTrue(any("SHA-256" in p for p in problems))
        self.assertTrue(any("counts do not match" in p for p in problems))

    def test_a_removed_duplicate_with_no_kept_pair_is_caught(self) -> None:
        manifest = self.manifest()
        con = sqlite3.connect(self.language)
        con.execute("DELETE FROM parallel_sentences WHERE id = 1")
        con.commit()
        con.close()
        problems = contract.check_derivation(manifest, self.removals, self.language)
        self.assertTrue(any("no matching kept pair" in p or "holds" in p for p in problems))


class InstallAndRestartTests(ReleaseFixture):
    def env(self, manifest_bytes: bytes, **extra: str) -> dict[str, str]:
        return {"SIAMSIL_ENVIRONMENT": "production",
                "SIAMSIL_DATA_RELEASE_MANIFEST_SHA256": hashlib.sha256(manifest_bytes).hexdigest(), **extra}

    def release(self) -> tuple[dict, bytes, str]:
        manifest = self.manifest()
        raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        return manifest, raw, manifest["bundle_sha256"]

    def test_a_verified_bundle_installs_and_keeps_its_manifest(self) -> None:
        manifest, raw, digest = self.release()
        volume = self.root / "volume"
        volume.mkdir()
        fetch_data.install(self.bundle, volume, digest, manifest, raw, self.env(raw))
        self.assertTrue((volume / "siamsil_language.sqlite").is_file())
        self.assertEqual((volume / ".release.json").read_bytes(), raw)
        self.assertTrue((volume / f".bundle-{digest}").exists())

    def test_a_bundle_that_disagrees_with_its_manifest_installs_nothing(self) -> None:
        manifest, raw, digest = self.release()
        manifest["contents"]["bible_versions.sqlite"]["sha256"] = "5" * 64
        volume = self.root / "volume"
        volume.mkdir()
        (volume / "existing.txt").write_text("keep", encoding="utf-8")
        with self.assertRaises(SystemExit) as raised:
            fetch_data.install(self.bundle, volume, digest, manifest, raw, self.env(raw))
        self.assertIn("release verification failed", str(raised.exception))
        self.assertEqual([p.name for p in volume.iterdir()], ["existing.txt"])

    def test_production_refuses_to_start_without_a_pinned_manifest(self) -> None:
        _, _, digest = self.release()
        with mock.patch.dict(os.environ, {"SIAMSIL_ENVIRONMENT": "production", "SIAMSIL_DATA_BUNDLE_SHA256": digest,
                                          "SIAMSIL_DATA_ROOT": str(self.root / "volume")}, clear=True):
            with self.assertRaisesRegex(SystemExit, "SIAMSIL_DATA_RELEASE_MANIFEST_SHA256"):
                fetch_data.main()

    def test_production_refuses_a_bundle_with_no_manifest_but_development_allows_it(self) -> None:
        _, _, digest = self.release()
        base = {"SIAMSIL_DATA_BUNDLE_SHA256": digest, "SIAMSIL_DATA_ROOT": str(self.root / "volume"),
                "SIAMSIL_DATA_BUNDLE_URL": self.bundle.as_uri()}
        with mock.patch.dict(os.environ, {**base, "SIAMSIL_ENVIRONMENT": "production",
                                          "SIAMSIL_DATA_RELEASE_MANIFEST_SHA256": "6" * 64}, clear=True):
            with self.assertRaisesRegex(SystemExit, "requires a release manifest"):
                fetch_data.main()
        with mock.patch.dict(os.environ, {**base, "SIAMSIL_ENVIRONMENT": "development"}, clear=True):
            fetch_data.main()
        self.assertTrue((self.root / "volume" / "siamsil_language.sqlite").is_file())

    def test_production_with_a_valid_pin_but_no_bundle_to_install_fails_instead_of_skipping(self) -> None:
        _, raw, digest = self.release()
        env = {**self.env(raw), "SIAMSIL_DATA_BUNDLE_SHA256": digest, "SIAMSIL_DATA_ROOT": str(self.root / "volume")}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(SystemExit, "no verified data bundle"):
                fetch_data.main()
        with mock.patch.dict(os.environ, {"SIAMSIL_ENVIRONMENT": "development",
                                          "SIAMSIL_DATA_ROOT": str(self.root / "volume")}, clear=True):
            fetch_data.main()  # development with nothing configured still starts

    def test_a_second_process_re_verifies_a_bundle_another_process_just_installed(self) -> None:
        manifest, raw, digest = self.release()
        volume = self.root / "volume"
        volume.mkdir()
        env = {**self.env(raw), "SIAMSIL_DATA_BUNDLE_SHA256": digest, "SIAMSIL_DATA_ROOT": str(volume),
               "SIAMSIL_DATA_BUNDLE_URL": self.bundle.as_uri(), "SIAMSIL_DATA_RELEASE_MANIFEST_URL": self.root.joinpath(
                   "release.json").as_uri()}
        (self.root / "release.json").write_bytes(raw)

        def installed_by_a_competitor_with_a_tampered_register(*_args, **_kwargs):
            # The moment the lock is granted, the other process has finished installing... a changed rights.json.
            fetch_data.install(self.bundle, volume, digest, manifest, raw, self.env(raw))
            (volume / "json" / "rights.json").write_text(json.dumps({"sources": {}}), encoding="utf-8")

        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(fetch_data.fcntl, "flock", side_effect=installed_by_a_competitor_with_a_tampered_register):
            with self.assertRaises(SystemExit) as raised:
                fetch_data.main()
        self.assertIn("release verification failed", str(raised.exception))

    def test_a_failed_download_says_why_without_printing_the_address(self) -> None:
        url = "http://127.0.0.1:9/siamsil-data.tar.gz?X-Amz-Signature=SECRETSIGNATURE"
        with self.assertRaises(SystemExit) as raised:
            fetch_data.download_manifest(url)
        self.assertIn("cannot download the release manifest", str(raised.exception))
        self.assertNotIn("SECRETSIGNATURE", str(raised.exception))

    def test_a_manifest_that_does_not_match_its_pin_is_refused(self) -> None:
        _, raw, _ = self.release()
        with self.assertRaisesRegex(SystemExit, "does not match SIAMSIL_DATA_RELEASE_MANIFEST_SHA256"):
            fetch_data.parse_manifest(raw, "7" * 64)

    def test_a_restart_rechecks_the_stored_manifest_and_catches_a_changed_rights_register(self) -> None:
        manifest, raw, digest = self.release()
        volume = self.root / "volume"
        volume.mkdir()
        fetch_data.install(self.bundle, volume, digest, manifest, raw, self.env(raw))
        env = {**self.env(raw), "SIAMSIL_DATA_BUNDLE_SHA256": digest, "SIAMSIL_DATA_ROOT": str(volume)}
        with mock.patch.dict(os.environ, env, clear=True):
            fetch_data.main()  # unchanged volume: passes
            (volume / "json" / "rights.json").write_text(json.dumps({"sources": {}}), encoding="utf-8")
            with self.assertRaises(SystemExit):
                fetch_data.main()

    def test_a_restart_in_production_without_a_stored_manifest_is_refused(self) -> None:
        manifest, raw, digest = self.release()
        volume = self.root / "volume"
        volume.mkdir()
        (volume / f".bundle-{digest}").touch()
        env = {**self.env(raw), "SIAMSIL_DATA_BUNDLE_SHA256": digest, "SIAMSIL_DATA_ROOT": str(volume)}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(SystemExit, "installed release manifest"):
                fetch_data.main()

    def test_the_manifest_address_sits_beside_the_bundle_key(self) -> None:
        base = {"SIAMSIL_DATA_BUNDLE_S3_ENDPOINT": "https://example.r2.cloudflarestorage.com",
                "SIAMSIL_DATA_BUNDLE_S3_BUCKET": "bucket", "SIAMSIL_DATA_BUNDLE_S3_ACCESS_KEY_ID": "id",
                "SIAMSIL_DATA_BUNDLE_S3_SECRET_ACCESS_KEY": "secret"}
        folder = {**base, "SIAMSIL_DATA_BUNDLE_S3_KEY": "releases/sha256-abc/siamsil-data.tar.gz"}
        self.assertIn("/bucket/releases/sha256-abc/release.json?", fetch_data.manifest_url(folder))
        flat = {**base, "SIAMSIL_DATA_BUNDLE_S3_KEY": "siamsil-data-2026-11-30.tar.gz"}
        self.assertIn("/bucket/siamsil-data-2026-11-30.release.json?", fetch_data.manifest_url(flat))
        explicit = {**flat, "SIAMSIL_DATA_RELEASE_MANIFEST_KEY": "manifests/one.json"}
        self.assertIn("/bucket/manifests/one.json?", fetch_data.manifest_url(explicit))


if __name__ == "__main__":
    unittest.main()
