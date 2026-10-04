from __future__ import annotations

import csv
import hashlib
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))

from build_language_db import (  # type: ignore  # noqa: E402
    DATASET_VERSION,
    apply_corpus_checks,
    connect,
    create_schema,
    ingest_parallel,
    release_manifest,
    write_release_manifest,
)
from review_sample import export, summarize, wilson_interval  # type: ignore  # noqa: E402

# Zomi-side strings are placeholders, never real language data.


class ReleaseManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def write(self, name: str, content: bytes) -> Path:
        path = self.dir / name
        path.write_bytes(content)
        return path

    def test_manifest_hashes_inputs_and_database(self) -> None:
        database = self.write("language.sqlite", b"database bytes")
        corpus = self.write("corpus.csv", b"en,zomi\n")
        eval_set = self.write("en-zomi-v1.jsonl", b'{"id": "x"}\n')
        manifest = release_manifest(
            database=database,
            source_files={"parallel_csv": corpus},
            eval_files=[eval_set],
            counts={"parallel_sentences": 0},
            created_at="2026-10-04T00:00:00+00:00",
        )
        self.assertEqual(manifest["version"], DATASET_VERSION)
        self.assertEqual(manifest["database"]["sha256"], hashlib.sha256(b"database bytes").hexdigest())
        self.assertEqual(manifest["database"]["bytes"], len(b"database bytes"))
        self.assertEqual(manifest["source_files"]["parallel_csv"]["sha256"], hashlib.sha256(b"en,zomi\n").hexdigest())
        self.assertEqual(
            manifest["evaluation_sets"],
            [{"file": "en-zomi-v1.jsonl", "sha256": hashlib.sha256(b'{"id": "x"}\n').hexdigest()}],
        )

    def test_versioned_copy_is_named_by_database_hash(self) -> None:
        database = self.write("language.sqlite", b"database bytes")
        manifest = release_manifest(database, {}, [], {}, "2026-10-04T00:00:00+00:00")
        current = self.dir / "processed" / "manifest.json"
        versioned = write_release_manifest(manifest, current, self.dir / "versions")
        digest = hashlib.sha256(b"database bytes").hexdigest()
        self.assertEqual(versioned.name, f"siamsil-language-{DATASET_VERSION}-{digest[:12]}.json")
        self.assertEqual(json.loads(versioned.read_text()), manifest)
        self.assertEqual(current.read_text(), versioned.read_text())


class ReviewSampleTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        corpus = self.dir / "corpus.csv"
        with corpus.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["index", "en", "zomi", "model", "worker"])
            for n in range(12):
                model = "model-a" if n % 2 else "model-b"
                writer.writerow([n, f"English sentence number {n}.", f"ZOMI_PLACEHOLDER_{n}", model, "w"])
            writer.writerow([12, "Held out sentence.", "ZOMI_PLACEHOLDER_HELD", "model-a", "w"])
        self.database = self.dir / "language.sqlite"
        con = connect(self.database)
        create_schema(con)
        with redirect_stdout(StringIO()):
            ingest_parallel(con, corpus, "2026-10-04T00:00:00+00:00")
        held_out = {"direction": "en-zomi", "source_text": "Held out sentence.", "references": ["x"]}
        apply_corpus_checks(con, [held_out])
        con.close()

    def read(self, path: Path) -> list[dict]:
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_export_is_blind_balanced_and_deterministic(self) -> None:
        review_path, key_path, count = export(self.database, self.dir / "a", per_model=3, seed="s")
        self.assertEqual(count, 6)
        review, key = self.read(review_path), self.read(key_path)
        self.assertNotIn("model", review[0])
        self.assertEqual(sorted(row["model"] for row in key), ["model-a"] * 3 + ["model-b"] * 3)
        self.assertNotIn("Held out sentence.", [row["english"] for row in review])

        again, _, _ = export(self.database, self.dir / "b", per_model=3, seed="s")
        self.assertEqual(review_path.read_text(), again.read_text())

    def test_summary_scores_each_model(self) -> None:
        key = [
            {"sample_id": "R00001", "model": "model-a"},
            {"sample_id": "R00002", "model": "model-a"},
            {"sample_id": "R00003", "model": "model-b"},
            {"sample_id": "R00004", "model": "model-b"},
        ]
        review = [
            {"sample_id": "R00001", "meaning": "2", "fluency": "2"},
            {"sample_id": "R00002", "meaning": "2", "fluency": "0"},
            {"sample_id": "R00003", "meaning": "1", "fluency": "2"},
            {"sample_id": "R00004", "meaning": "", "fluency": ""},
        ]
        summary, errors = summarize(review, key)
        self.assertEqual(errors, [])
        self.assertEqual(summary["model-a"]["rated"], 2)
        self.assertEqual(summary["model-a"]["acceptable_share"], 0.5)
        self.assertEqual(summary["model-a"]["mean_fluency"], 1.0)
        self.assertEqual(summary["model-b"]["rated"], 1)
        self.assertEqual(summary["model-b"]["unrated"], 1)
        self.assertEqual(summary["model-b"]["acceptable_share"], 0.0)

    def test_invalid_scores_and_unknown_ids_are_errors(self) -> None:
        key = [{"sample_id": "R00001", "model": "model-a"}]
        review = [
            {"sample_id": "R00001", "meaning": "3", "fluency": "1"},
            {"sample_id": "R99999", "meaning": "2", "fluency": "2"},
        ]
        _, errors = summarize(review, key)
        self.assertEqual(len(errors), 2)

    def test_wilson_interval(self) -> None:
        self.assertEqual(wilson_interval(0, 0), (0.0, 0.0))
        low, high = wilson_interval(10, 10)
        self.assertEqual(high, 1.0)
        self.assertLess(low, 1.0)
        low, high = wilson_interval(50, 100)
        self.assertAlmostEqual(low, 0.404, places=3)
        self.assertAlmostEqual(high, 0.596, places=3)


if __name__ == "__main__":
    unittest.main()
