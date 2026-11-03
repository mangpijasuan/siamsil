from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml_pipeline" / "scripts"))

import data_repo as dr  # type: ignore  # noqa: E402
from build_language_db import connect, create_schema, ingest_parallel  # type: ignore  # noqa: E402

# Placeholder text only: these tests check reading and checksums, not Zomi.
HEADER = ["index", "en", "zomi"]
ROWS = [[str(i), f"Sentence {i}.", f"Qa vo {i} zu."] for i in range(1, 8)]
ROWS[3][1] = 'With a "quote", a comma\nand a line break.'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def csv_bytes(rows: list[list[str]], lineterminator: str) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator=lineterminator)
    writer.writerow(HEADER)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


class RepoFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "siamsil-data"
        (self.repo / "dictionary").mkdir(parents=True)
        (self.repo / "parallel").mkdir()
        (self.repo / "bible").mkdir()
        self.dictionary = b"not really a workbook"
        (self.repo / "dictionary" / "master.xlsx").write_bytes(self.dictionary)

        # The original CSV has LF endings; the parts are written with CRLF and repeat the header,
        # as package_private_parallel.py does.
        self.original = csv_bytes(ROWS, "\n")
        parts = []
        for number, chunk in enumerate((ROWS[:3], ROWS[3:5], ROWS[5:]), start=1):
            name = f"zomi_english_sentences.part-{number:04d}.csv.gz"
            data = gzip.compress(csv_bytes(chunk, "\r\n"))
            (self.repo / "parallel" / name).write_bytes(data)
            parts.append({"file": name, "rows": len(chunk), "bytes": len(data), "sha256": sha(data)})
        manifest = {"source_sha256": sha(self.original), "total_rows": len(ROWS), "parts": parts}
        manifest_bytes = json.dumps(manifest).encode("utf-8")
        (self.repo / "parallel" / "manifest.json").write_bytes(manifest_bytes)

        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("Version/metadata.xml", "<x/>")
        self.zip_bytes = archive.getvalue()
        (self.repo / "bible" / "bundle.zip").write_bytes(self.zip_bytes)

        self.config = Path(self.tmp.name) / "source_files.json"
        self.write_config({
            "dictionary_master": {"path": "dictionary/master.xlsx", "sha256": sha(self.dictionary)},
            "parallel_manifest": {"path": "parallel/manifest.json", "sha256": sha(manifest_bytes)},
            "bible_zip": {"path": "bible/bundle.zip", "sha256": sha(self.zip_bytes), "unzip_to": "chin"},
        })

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_config(self, sources: dict) -> None:
        self.config.write_text(json.dumps({"sources": sources}), encoding="utf-8")

    def open_repo(self) -> dr.DataRepo:
        return dr.DataRepo(self.repo, self.config)


class DataRepoTests(RepoFixture):
    def test_default_location_and_environment(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(dr.default_data_repo(), ROOT.parent / "siamsil-data")
        with mock.patch.dict(os.environ, {"SIAMSIL_DATA_REPO": str(self.repo)}):
            self.assertEqual(dr.default_data_repo(), self.repo)

    def test_missing_repository_is_explained(self) -> None:
        with self.assertRaisesRegex(dr.SourceError, "siamsil-data not found"):
            dr.DataRepo(self.repo / "nope", self.config)

    def test_verified_checks_the_pinned_checksum(self) -> None:
        repo = self.open_repo()
        self.assertEqual(repo.verified("dictionary_master"), self.repo / "dictionary" / "master.xlsx")
        (self.repo / "dictionary" / "master.xlsx").write_bytes(b"changed")
        with self.assertRaisesRegex(dr.SourceError, "expected"):
            repo.verified("dictionary_master")
        (self.repo / "dictionary" / "master.xlsx").unlink()
        with self.assertRaisesRegex(dr.SourceError, "missing"):
            repo.verified("dictionary_master")

    def test_parallel_parts_give_the_original_csv(self) -> None:
        parallel = self.open_repo().parallel()
        joined = "".join(parallel.lines()).encode("utf-8")
        self.assertEqual(joined, self.original)
        record = parallel.finish()
        self.assertEqual(record["sha256"], sha(self.original))
        self.assertEqual(record["bytes"], len(self.original))
        self.assertIn("3 parts", record["path"])

    def test_a_changed_part_is_refused(self) -> None:
        part = self.repo / "parallel" / "zomi_english_sentences.part-0002.csv.gz"
        part.write_bytes(gzip.compress(csv_bytes(ROWS[3:5], "\r\n").replace(b"Sentence", b"Sentense")))
        with self.assertRaisesRegex(dr.SourceError, "differs"):
            self.open_repo().parallel()

    def test_finish_refuses_an_incomplete_read(self) -> None:
        parallel = self.open_repo().parallel()
        lines = parallel.lines()
        next(lines)
        with self.assertRaisesRegex(dr.SourceError, "not the original"):
            parallel.finish()

    def test_unzipped_is_temporary_and_named(self) -> None:
        with self.open_repo().unzipped(["bible_zip"]) as base:
            self.assertTrue((base / "chin" / "Version" / "metadata.xml").is_file())
            kept = base
        self.assertFalse(kept.exists())

    def test_unsafe_zip_paths_are_refused(self) -> None:
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("../escape.txt", "x")
        (self.repo / "bible" / "bundle.zip").write_bytes(archive.getvalue())
        config = json.loads(self.config.read_text())["sources"]
        config["bible_zip"]["sha256"] = sha(archive.getvalue())
        self.write_config(config)
        with self.assertRaisesRegex(dr.SourceError, "unsafe"):
            with self.open_repo().unzipped(["bible_zip"]):
                pass


class IngestFromPartsTests(RepoFixture):
    def test_ingest_from_parts_matches_ingest_from_the_csv(self) -> None:
        csv_path = Path(self.tmp.name) / "original.csv"
        csv_path.write_bytes(self.original)
        results = []
        for source in (csv_path, self.open_repo().parallel()):
            con = connect(Path(self.tmp.name) / f"db-{len(results)}.sqlite")
            create_schema(con)
            ingest_parallel(con, source, "2026-10-30T00:00:00+00:00")
            rows = con.execute(
                "SELECT raw_source_text, raw_target_text, pair_hash FROM parallel_sentences ORDER BY id"
            ).fetchall()
            con.close()
            results.append(rows)
        self.assertEqual(len(results[0]), len(ROWS))
        self.assertEqual(results[0], results[1])


class ConfigTests(unittest.TestCase):
    def test_repository_config_pins_every_source(self) -> None:
        sources = json.loads((ROOT / "data" / "source_files.json").read_text(encoding="utf-8"))["sources"]
        for key in ("dictionary_master", "parallel_manifest", "bible_chin_usx", "bible_web_usfm", "bible_workbook"):
            with self.subTest(key=key):
                self.assertRegex(sources[key]["sha256"], r"^[0-9a-f]{64}$")
                self.assertFalse(sources[key]["path"].startswith(("/", "..")))


if __name__ == "__main__":
    unittest.main()
