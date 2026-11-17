from __future__ import annotations

import hashlib
import io
import sqlite3
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import release_manifest  # noqa: E402
import check_release  # noqa: E402


class ReleaseManifestTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bundle = self.root / "bundle.tar.gz"
        for name in ("siamsil_language.sqlite", "bible_versions.sqlite"):
            con = sqlite3.connect(self.root / name)
            con.execute("CREATE TABLE example (x INTEGER)")
            con.commit()
            con.close()

    def make_bundle(self, *, missing_bible=False, unexpected=False):
        with tarfile.open(self.bundle, "w:gz") as archive:
            archive.add(self.root / "siamsil_language.sqlite", arcname="siamsil_language.sqlite")
            if not missing_bible:
                archive.add(self.root / "bible_versions.sqlite", arcname="bible_versions.sqlite")
            if unexpected:
                data = b"bad"
                member = tarfile.TarInfo("../unsafe.txt")
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))

    def test_release_is_pinned_to_full_archive_checksum(self):
        self.make_bundle()
        result = release_manifest.validate(self.bundle, created_at="2026-11-03T00:00:00+00:00")
        checksum = hashlib.sha256(self.bundle.read_bytes()).hexdigest()
        self.assertEqual(result["bundle_sha256"], checksum)
        self.assertEqual(result["object_key"], f"releases/sha256-{checksum}/siamsil-data.tar.gz")
        self.assertEqual(len(result["contents"]), 2)

    def test_missing_bible_rejected(self):
        self.make_bundle(missing_bible=True)
        with self.assertRaisesRegex(ValueError, "Required database missing"):
            release_manifest.validate(self.bundle)

    def test_unsafe_archive_rejected(self):
        self.make_bundle(unexpected=True)
        with self.assertRaisesRegex(ValueError, "Unexpected or unsafe"):
            release_manifest.validate(self.bundle)

    def test_corrupted_sqlite_rejected(self):
        (self.root / "siamsil_language.sqlite").write_bytes(b"not sqlite")
        self.make_bundle()
        with self.assertRaises(sqlite3.DatabaseError):
            release_manifest.validate(self.bundle)


class InstalledReleaseTests(unittest.TestCase):
    def test_expected_marker_and_databases_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checksum = "a" * 64
            with self.assertRaisesRegex(RuntimeError, "marker"):
                check_release.installed_release(root, checksum)
            (root / f".bundle-{checksum}").touch()
            with self.assertRaisesRegex(RuntimeError, "siamsil_language.sqlite"):
                check_release.installed_release(root, checksum)
            for name in ("siamsil_language.sqlite", "bible_versions.sqlite"):
                (root / name).touch()
            self.assertTrue(check_release.installed_release(root, checksum)["installed"])


if __name__ == "__main__":
    unittest.main()
