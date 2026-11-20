from __future__ import annotations

import io
import os
import sqlite3
import sys
import tarfile
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

import fetch_data  # type: ignore  # noqa: E402
import package_data  # type: ignore  # noqa: E402


class PresignTests(unittest.TestCase):
    def test_matches_the_aws_signature_v4_example(self) -> None:
        # AWS's published example for a presigned GET ("Authenticating Requests: Using Query Parameters").
        url = fetch_data.presigned_url(
            "https://s3.amazonaws.com", "examplebucket", "test.txt", "AKIAIOSFODNN7EXAMPLE",
            "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", region="us-east-1", expires=86400,
            now=datetime(2013, 5, 24, tzinfo=timezone.utc), path_style=False)
        self.assertTrue(url.startswith("https://examplebucket.s3.amazonaws.com/test.txt?X-Amz-Algorithm="))
        self.assertTrue(url.endswith("X-Amz-Signature=aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404"))

    def test_r2_links_are_path_style(self) -> None:
        env = {
            "SIAMSIL_DATA_BUNDLE_S3_ENDPOINT": "https://acct.r2.cloudflarestorage.com",
            "SIAMSIL_DATA_BUNDLE_S3_BUCKET": "siamsil-data-bundle",
            "SIAMSIL_DATA_BUNDLE_S3_ACCESS_KEY_ID": "id",
            "SIAMSIL_DATA_BUNDLE_S3_SECRET_ACCESS_KEY": "secret",
        }
        url = fetch_data.bundle_url(env)
        self.assertTrue(url.startswith("https://acct.r2.cloudflarestorage.com/siamsil-data-bundle/siamsil-data.tar.gz?"))
        self.assertIn("%2Fauto%2Fs3%2Faws4_request", url)
        self.assertNotIn("secret", url)
        with self.assertRaisesRegex(ValueError, "SIAMSIL_DATA_BUNDLE_S3_BUCKET"):
            fetch_data.bundle_url({**env, "SIAMSIL_DATA_BUNDLE_S3_BUCKET": ""})
        with self.assertRaisesRegex(ValueError, "https"):
            fetch_data.bundle_url({**env, "SIAMSIL_DATA_BUNDLE_S3_ENDPOINT": "http://acct.example"})
        self.assertEqual(fetch_data.bundle_url({"SIAMSIL_DATA_BUNDLE_URL": " https://x/b.tar.gz "}), "https://x/b.tar.gz")
        self.assertEqual(fetch_data.bundle_url({}), "")


def make_language_db(path: Path) -> None:
    """A tiny database with the real schema, a dictionary, and a corpus that must not travel."""
    sys.path.insert(0, str(BACKEND_ROOT.parent / "ml_pipeline" / "scripts"))
    from build_language_db import create_schema  # type: ignore

    con = sqlite3.connect(path)
    create_schema(con)
    for number in range(1, 4):
        con.execute(
            "INSERT INTO dictionary_entries (id, source_word, normalized_word, verification_status, letter, version, "
            "created_at, zomi, definition) VALUES (?, ?, ?, 'unreviewed', 'w', 'v2', 'now', ?, ?)",
            (number, f"word{number}", f"word{number}", f"ZOMI_PLACEHOLDER_{number}", f"ZOMI_PLACEHOLDER_{number}"))
        con.execute("INSERT INTO dictionary_fts (rowid, source_word, definition, part_of_speech) VALUES (?, ?, ?, 'n.')",
                    (number, f"word{number}", f"ZOMI_PLACEHOLDER_{number}"))
    for number in range(1, 6):
        con.execute(
            "INSERT INTO parallel_sentences (id, raw_source_text, raw_target_text, normalized_source_text, "
            "normalized_target_text, dataset_split, pair_hash, family_hash, version, created_at) "
            "VALUES (?, 'en', 'zo', 'en', 'zo', 'train', ?, ?, 'v2', 'now')", (number, f"h{number}", f"f{number}"))
        con.execute("INSERT INTO parallel_fts (rowid, normalized_source_text, normalized_target_text) VALUES (?, 'en', 'zo')",
                    (number,))
    con.execute("INSERT INTO dataset_versions (name, version, created_at, script_version, source_files) "
                "VALUES ('siamsil-language', 'v2', 'now', '1.4.0', ?)",
                ('{"dictionary_master": "d.xlsx", "parallel_csv": "parallel (9 parts)"}',))
    con.commit()
    con.close()


class LeanBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.language = self.root / "siamsil_language.sqlite"
        make_language_db(self.language)
        bible = sqlite3.connect(self.root / "bible_versions.sqlite")
        bible.execute("CREATE TABLE t (x TEXT)")
        bible.commit()
        bible.close()

    def test_the_lean_copy_keeps_the_dictionary_and_empties_the_corpus(self) -> None:
        target = self.root / "lean.sqlite"
        stats = package_data.lean_snapshot(self.language, target)
        self.assertEqual(stats, {"dictionary_entries": 3, "parallel_sentences": 0})
        con = sqlite3.connect(target)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM dictionary_entries").fetchone()[0], 3)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM parallel_sentences").fetchone()[0], 0)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM parallel_fts").fetchone()[0], 0)
        # Search still works, and the full-text index still points at the same rows.
        self.assertEqual(con.execute("SELECT rowid FROM dictionary_fts WHERE dictionary_fts MATCH 'word2'").fetchall(), [(2,)])
        self.assertEqual(con.execute("SELECT zomi FROM dictionary_entries WHERE id = 2").fetchone()[0], "ZOMI_PLACEHOLDER_2")
        files = con.execute("SELECT source_files FROM dataset_versions").fetchone()[0]
        self.assertIn("not included", files)
        self.assertNotIn("parallel (9 parts)", files)
        self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        con.close()

    def test_the_source_database_is_untouched(self) -> None:
        package_data.lean_snapshot(self.language, self.root / "lean.sqlite")
        con = sqlite3.connect(self.language)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM parallel_sentences").fetchone()[0], 5)
        con.close()

    def test_an_unknown_database_is_refused(self) -> None:
        con = sqlite3.connect(self.language)
        con.execute("CREATE TABLE something_new (x TEXT)")
        con.commit()
        con.close()
        with self.assertRaisesRegex(ValueError, "something_new"):
            package_data.lean_snapshot(self.language, self.root / "lean.sqlite")

    def test_a_lean_bundle_carries_no_corpus_and_says_so(self) -> None:
        bundle, _ = package_data.package(self.root / "dist", self.language, self.root / "bible_versions.sqlite",
                                         self.root / "no-json", lean=True)
        with tarfile.open(bundle) as tar:
            self.assertEqual(sorted(tar.getnames()), ["bible_versions.sqlite", "bundle.json", "siamsil_language.sqlite"])
            tar.extractall(self.root / "out")
        info = __import__("json").loads((self.root / "out" / "bundle.json").read_text(encoding="utf-8"))
        self.assertEqual((info["lean"], info["corpus_rows"], info["dictionary_entries"]), (True, 0, 3))
        con = sqlite3.connect(self.root / "out" / "siamsil_language.sqlite")
        self.assertEqual(con.execute("SELECT COUNT(*) FROM parallel_sentences").fetchone()[0], 0)
        con.close()

    def test_the_full_bundle_still_carries_the_corpus_when_asked(self) -> None:
        bundle, _ = package_data.package(self.root / "dist", self.language, self.root / "bible_versions.sqlite",
                                         self.root / "no-json", lean=False)
        with tarfile.open(bundle) as tar:
            tar.extractall(self.root / "out")
        con = sqlite3.connect(self.root / "out" / "siamsil_language.sqlite")
        self.assertEqual(con.execute("SELECT COUNT(*) FROM parallel_sentences").fetchone()[0], 5)
        con.close()

    def test_the_command_is_lean_unless_the_corpus_is_cleared(self) -> None:
        with mock.patch.object(package_data, "package", return_value=(self.root / "b.tar.gz", "x" * 64)) as packaged, \
                mock.patch.object(Path, "stat", return_value=mock.Mock(st_size=1_000_000)), redirect_stdout(io.StringIO()):
            package_data.main([str(self.root / "dist")])
            self.assertTrue(packaged.call_args.kwargs["lean"])
        # The real register blocks the corpus, so asking for it is refused and nothing is packaged.
        with mock.patch.object(package_data, "package") as packaged:
            with self.assertRaises(SystemExit) as stop:
                package_data.main([str(self.root / "dist"), "--include-corpus"])
            self.assertIn("may not be shown", str(stop.exception))
            packaged.assert_not_called()


class BundleTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for name in ("siamsil_language.sqlite", "bible_versions.sqlite"):
            con = sqlite3.connect(self.root / name)
            con.execute("CREATE TABLE t (x TEXT)")
            con.execute("INSERT INTO t VALUES (?)", (name,))
            con.commit()
            con.close()
        self.json_dir = self.root / "json-src"
        self.json_dir.mkdir()
        (self.json_dir / "daily_use_pairs.json").write_text("[]", encoding="utf-8")
        (self.json_dir / "bible_verses.json").write_text("[]", encoding="utf-8")

    def package(self) -> tuple[Path, str]:
        return package_data.package(self.root / "dist", self.root / "siamsil_language.sqlite",
                                    self.root / "bible_versions.sqlite", self.json_dir)

    def test_bundle_holds_both_databases_and_not_the_uncleared_bible(self) -> None:
        bundle, _ = self.package()
        with tarfile.open(bundle) as tar:
            self.assertEqual(sorted(tar.getnames()),
                             ["bible_versions.sqlite", "json/daily_use_pairs.json", "siamsil_language.sqlite"])

    def test_a_missing_database_stops_packaging(self) -> None:
        (self.root / "bible_versions.sqlite").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "bible_versions.sqlite"):
            self.package()

    def test_fetch_unpacks_where_the_api_looks(self) -> None:
        bundle, sha256 = self.package()
        data = self.root / "data"
        env = {"SIAMSIL_DATA_BUNDLE_URL": bundle.as_uri(), "SIAMSIL_DATA_BUNDLE_SHA256": sha256,
               "SIAMSIL_DATA_ROOT": str(data)}
        with mock.patch.dict(os.environ, env, clear=True), redirect_stdout(io.StringIO()) as out:
            fetch_data.main()
            fetch_data.main()
        self.assertIn("bundle already present", out.getvalue())
        # The paths backend/Dockerfile gives the API.
        dockerfile = (BACKEND_ROOT / "Dockerfile").read_text(encoding="utf-8")
        for name in ("siamsil_language.sqlite", "bible_versions.sqlite"):
            self.assertIn(f"/data/{name}", dockerfile)
            con = sqlite3.connect(data / name)
            self.assertEqual(con.execute("SELECT x FROM t").fetchone()[0], name)
            con.close()
        self.assertTrue((data / "json" / "daily_use_pairs.json").exists())

    def test_a_wrong_checksum_installs_nothing(self) -> None:
        bundle, _ = self.package()
        data = self.root / "data"
        env = {"SIAMSIL_DATA_BUNDLE_URL": bundle.as_uri(), "SIAMSIL_DATA_BUNDLE_SHA256": "0" * 64,
               "SIAMSIL_DATA_ROOT": str(data)}
        with mock.patch.dict(os.environ, env, clear=True), redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                fetch_data.main()
        # Nothing from the bundle, no marker, and no leftover download.
        self.assertEqual(sorted(p.name for p in data.iterdir()), [".fetch.lock"])

    def test_a_failed_download_leaves_nothing_behind(self) -> None:
        data = self.root / "data"
        env = {"SIAMSIL_DATA_BUNDLE_URL": (self.root / "missing.tar.gz").as_uri(),
               "SIAMSIL_DATA_BUNDLE_SHA256": "0" * 64, "SIAMSIL_DATA_ROOT": str(data)}
        with mock.patch.dict(os.environ, env, clear=True), redirect_stdout(io.StringIO()):
            with self.assertRaises(OSError):
                fetch_data.main()
        self.assertEqual(sorted(p.name for p in data.iterdir()), [".fetch.lock"])

    def test_an_installed_bundle_starts_without_download_credentials(self) -> None:
        data = self.root / "data"
        data.mkdir()
        (data / f".bundle-{'a' * 64}").touch()
        env = {"SIAMSIL_DATA_BUNDLE_S3_ENDPOINT": "https://acct.r2.cloudflarestorage.com",  # keys missing
               "SIAMSIL_DATA_BUNDLE_SHA256": "a" * 64, "SIAMSIL_DATA_ROOT": str(data)}
        with mock.patch.dict(os.environ, env, clear=True), redirect_stdout(io.StringIO()) as out:
            fetch_data.main()
        self.assertIn("already present", out.getvalue())

    def test_a_new_bundle_removes_files_the_old_one_had(self) -> None:
        data = self.root / "data"
        (data / "json").mkdir(parents=True)
        (data / "json" / "bible_verses.json").write_text("[]", encoding="utf-8")  # from an older bundle
        (data / "stale.sqlite").write_text("old", encoding="utf-8")
        (data / ".bundle-old").touch()
        bundle, sha256 = self.package()
        env = {"SIAMSIL_DATA_BUNDLE_URL": bundle.as_uri(), "SIAMSIL_DATA_BUNDLE_SHA256": sha256,
               "SIAMSIL_DATA_ROOT": str(data)}
        with mock.patch.dict(os.environ, env, clear=True), redirect_stdout(io.StringIO()):
            fetch_data.main()
        self.assertEqual(sorted(p.relative_to(data).as_posix() for p in data.rglob("*")),
                         [f".bundle-{sha256}", ".fetch.lock", "bible_versions.sqlite", "json",
                          "json/daily_use_pairs.json", "siamsil_language.sqlite"])


if __name__ == "__main__":
    unittest.main()
