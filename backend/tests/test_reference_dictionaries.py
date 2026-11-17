from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))

from import_reference_dictionaries import main as import_main, notice_flags  # type: ignore  # noqa: E402

# Synthetic fixture text, not real Zomi or Burmese.
MASTER = {
    "title": "Fixture master",
    "entries": [
        {"headword": "Alpha", "part_of_speech": "n.", "senses": [
            {"sense_number": 1, "definition_en": "First fixture.", "zomi": "zom-fixture-a1", "burmese": "my-fixture-a1",
             "review_notice": "[Working reference—verify when important]", "usage_tier": "B"},
            {"sense_number": "2", "definition_en": "Second fixture.", "zomi": "zom-fixture-a2", "burmese": "my-fixture-a2",
             "review_notice": "[Native/editorial review required] [Translation conflict]", "usage_tier": "C"},
        ]},
        {"headword": "beta", "part_of_speech": "adj.", "senses": [
            {"sense_number": 1, "definition_en": "Third fixture.", "zomi": "zom-fixture-b1", "burmese": "my-fixture-b1",
             "usage_tier": "A"},
        ]},
    ],
}

LEARNERS = {
    "title": "Fixture learners",
    "entries": [
        {"id": 7, "headword": "gamma", "ipa": "g", "part_of_speech": "noun", "senses": [
            {"number": 1, "heading": None, "definition_en": "Fixture meaning.", "zomi_equivalents": "zom-fixture-g",
             "explanation_zomi": "zom-fixture-explanation", "usage_en": "Fixture usage.", "usage_zomi": "zom-fixture-usage",
             "common_phrases": [{"english": "a gamma", "zomi": "zom-fixture-phrase"}],
             "examples": [{"english": "Gamma here.", "zomi": "zom-fixture-example [sittel-ding]"}]},
        ]},
    ],
}


class ReferenceDictionaryImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.repo = base / "siamsil-data"
        (self.repo / "roadmap").mkdir(parents=True)
        self.master = self.repo / "roadmap" / "master.json"
        self.learners = self.repo / "roadmap" / "learners.json"
        self.master.write_text(json.dumps(MASTER), encoding="utf-8")
        self.learners.write_text(json.dumps(LEARNERS), encoding="utf-8")
        self.config = base / "config.json"
        self.write_config()
        self.rights = base / "rights.json"
        self.rights.write_text(json.dumps({"sources": {"master": {"display": "needs_review", "train": "needs_review"}}}),
                               encoding="utf-8")
        self.out = base / "out" / "reference.sqlite"
        self.manifest = base / "out" / "manifest.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_config(self, master_sha: str | None = None) -> None:
        def digest(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest()

        self.config.write_text(json.dumps({"sources": {
            "master": {"title": "Fixture master", "version": "1", "format": "translation_master",
                       "path": "roadmap/master.json", "sha256": master_sha or digest(self.master)},
            "learners": {"title": "Fixture learners", "version": "beta", "format": "learners_dictionary",
                         "path": "roadmap/learners.json", "sha256": digest(self.learners)},
        }}), encoding="utf-8")

    def run_import(self, *extra: str) -> int:
        return import_main(["--data-repo", str(self.repo), "--config", str(self.config), "--rights", str(self.rights),
                            "--out", str(self.out), "--manifest", str(self.manifest), *extra])

    def test_every_sense_is_unreviewed_and_text_unchanged(self) -> None:
        self.assertEqual(self.run_import(), 0)
        con = sqlite3.connect(self.out)
        self.assertEqual(con.execute("SELECT DISTINCT review_status FROM senses").fetchall(), [("unreviewed",)])
        self.assertEqual(con.execute("SELECT COUNT(*) FROM senses").fetchone()[0], 4)
        self.assertEqual(con.execute("SELECT zomi, burmese, usage_tier FROM senses WHERE id = 'master:000001:2'").fetchone(),
                         ("zom-fixture-a2", "my-fixture-a2", "C"))
        self.assertEqual(con.execute("SELECT kind, english, zomi FROM examples ORDER BY position").fetchall(),
                         [("phrase", "a gamma", "zom-fixture-phrase"),
                          ("example", "Gamma here.", "zom-fixture-example [sittel-ding]")])
        self.assertEqual(con.execute("SELECT id FROM entries WHERE source_id = 'learners'").fetchone(), ("learners:000007",))

    def test_notices_and_native_tags_become_flags(self) -> None:
        self.run_import()
        con = sqlite3.connect(self.out)
        flags = dict(con.execute("SELECT id, flags FROM senses").fetchall())
        self.assertEqual(json.loads(flags["master:000001:2"]), ["native_editorial_review_required", "translation_conflict"])
        self.assertEqual(json.loads(flags["master:000002:1"]), [])
        self.assertEqual(json.loads(flags["learners:000007:1"]), ["native_confirmation_required"])
        self.assertEqual(notice_flags("[Working reference—verify when important]"), ["working_reference"])

    def test_rights_are_recorded_and_default_to_needs_review(self) -> None:
        self.run_import()
        con = sqlite3.connect(self.out)
        rights = {row[0]: row[1:] for row in con.execute("SELECT id, display_rights, train_rights FROM sources")}
        self.assertEqual(rights, {"master": ("needs_review", "needs_review"), "learners": ("needs_review", "needs_review")})
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertFalse(next(s for s in manifest["sources"] if s["id"] == "learners")["rights_recorded"])

    def test_checksum_mismatch_stops_before_writing(self) -> None:
        self.write_config(master_sha="0" * 64)
        with self.assertRaises(SystemExit) as raised:
            self.run_import()
        self.assertIn("Checksum mismatch", str(raised.exception))
        self.assertFalse(self.out.exists())

    def test_originals_are_not_modified_and_rerun_is_identical(self) -> None:
        before = (self.master.read_bytes(), self.learners.read_bytes())
        self.run_import()
        con = sqlite3.connect(self.out)
        first = con.execute("SELECT * FROM senses ORDER BY id").fetchall()
        con.close()
        self.run_import()
        con = sqlite3.connect(self.out)
        self.assertEqual(con.execute("SELECT * FROM senses ORDER BY id").fetchall(), first)
        self.assertEqual((self.master.read_bytes(), self.learners.read_bytes()), before)

    def test_dry_run_writes_nothing(self) -> None:
        self.assertEqual(self.run_import("--dry-run"), 0)
        self.assertFalse(self.out.exists())
        self.assertFalse(self.manifest.exists())


if __name__ == "__main__":
    unittest.main()
