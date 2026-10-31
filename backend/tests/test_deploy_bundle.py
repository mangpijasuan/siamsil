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
