from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[2] / "ml_pipeline" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from build_language_db import english_family_key  # noqa: E402
from gold_test_workflow import finalize, prepare as prepare_gold, read_jsonl  # noqa: E402
from prepare_translation_audit import prepare as prepare_audit  # noqa: E402
from summarize_translation_audit import summarize  # noqa: E402


def save_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


class TranslationQualityWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.db = self.root / "language.sqlite"
        with sqlite3.connect(self.db) as con:
            con.execute("""CREATE TABLE parallel_sentences (
                id INTEGER PRIMARY KEY, raw_source_text TEXT, raw_target_text TEXT,
                normalized_source_text TEXT, normalized_target_text TEXT,
                source_reference TEXT, model TEXT, quality_flags TEXT,
                quality_score REAL, dataset_split TEXT, version TEXT, family_hash TEXT
            )""")
            for row_id in range(1, 31):
                english = f"English corpus sentence {row_id}"
                zomi = f"Zomi corpus sentence {row_id}"
                flags = ["identical"] if row_id % 3 == 0 else []
                con.execute(
                    """INSERT INTO parallel_sentences VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (row_id, english, zomi, english, zomi, "test-source", "test-model",
                     json.dumps(flags), 0.3 if flags else 1.0, "train", "test-v1",
                     english_family_key(english)),
                )

    def test_audit_packets_are_disjoint_repeatable_and_unreviewed(self) -> None:
        first = self.root / "audit-a"
        second = self.root / "audit-b"
        prepare_audit(self.db, first, 5, 2, "fixed-seed")
        prepare_audit(self.db, second, 5, 2, "fixed-seed")
        random_rows = read_jsonl(first / "random.jsonl")
        flagged_rows = read_jsonl(first / "flagged.jsonl")
        self.assertEqual(random_rows, read_jsonl(second / "random.jsonl"))
        self.assertEqual(len(random_rows), 5)
        self.assertEqual(len(flagged_rows), 2)
        self.assertFalse({r["sentence_id"] for r in random_rows} & {r["sentence_id"] for r in flagged_rows})
        self.assertEqual({r["review_status"] for r in random_rows}, {"pending"})
        self.assertEqual(len(read_jsonl(first / "decisions_template.jsonl")), 7)
        self.assertEqual(json.loads((first / "manifest.json").read_text())["population_count"], 30)

        decisions = []
        for row in [*random_rows, *flagged_rows]:
            decisions.append({"sentence_id": row["sentence_id"], "reviewer_id": "reviewer-1",
                              "decision": "approve", "corrected_zomi": "", "error_tags": []})
        decisions_path = self.root / "decisions.jsonl"
        save_jsonl(decisions_path, decisions)
        report = summarize(first, decisions_path, self.root / "report.json")
        self.assertEqual(report["random_sample"]["approve_without_edit_rate"], 1.0)
        self.assertEqual(report["flagged_diagnostic"]["n"], 2)
        save_jsonl(self.root / "incomplete.jsonl", decisions[:-1])
        with self.assertRaisesRegex(ValueError, "Missing human decisions"):
            summarize(first, self.root / "incomplete.jsonl", self.root / "bad-report.json")

    def test_gold_packets_are_blind_and_require_three_distinct_humans(self) -> None:
        source_items = [
            {"source_id": "en-1", "source_language": "en", "source_text": "A new independent English sentence.",
             "domain": "daily", "source_origin": "community-authored", "rights_reference": "consent-1"},
            {"source_id": "zom-1", "source_language": "zom", "source_text": "A new independent Zomi sentence.",
             "domain": "daily", "source_origin": "community-authored", "rights_reference": "consent-2"},
        ]
        source_file = self.root / "sources.jsonl"
        save_jsonl(source_file, source_items)
        output = self.root / "gold"
        result = prepare_gold(source_file, self.db, output)
        self.assertEqual(result["source_count"], 2)
        blind = read_jsonl(output / "reviewer_a_blank.jsonl")
        self.assertTrue(all(row["translation"] == "" for row in blind))
        self.assertTrue(all("candidate" not in row for row in blind))

        for name, reviewer in (("a", "reviewer-a"), ("b", "reviewer-b"), ("judge", "adjudicator")):
            save_jsonl(self.root / f"{name}.jsonl", [
                {"source_id": row["source_id"], "reviewer_id": reviewer,
                 "translation": f"Human translation of {row['source_id']}", "notes": "checked"}
                for row in source_items
            ])
        self.assertEqual(finalize(output, self.root / "a.jsonl", self.root / "b.jsonl",
                                  self.root / "judge.jsonl"), 2)
        final = read_jsonl(output / "gold_test.jsonl")
        self.assertEqual({row["reference_status"] for row in final}, {"human_adjudicated"})
        self.assertEqual(json.loads((output / "gold_test.manifest.json").read_text())["reference_count"], 2)

    def test_gold_rejects_exact_corpus_overlap_and_machine_candidates(self) -> None:
        sources = [
            {"source_id": "en-1", "source_language": "en", "source_text": "English corpus sentence 4",
             "domain": "daily", "source_origin": "test", "rights_reference": "permission"},
            {"source_id": "zom-1", "source_language": "zom", "source_text": "Independent Zomi source",
             "domain": "daily", "source_origin": "test", "rights_reference": "permission"},
        ]
        path = self.root / "overlap.jsonl"
        save_jsonl(path, sources)
        with self.assertRaisesRegex(ValueError, "overlap"):
            prepare_gold(path, self.db, self.root / "gold")
        sources[0]["source_text"] = "Independent English source"
        sources[1]["source_text"] = "Zomi corpus sentence 5"
        save_jsonl(self.root / "zomi-overlap.jsonl", sources)
        with self.assertRaisesRegex(ValueError, "overlap"):
            prepare_gold(self.root / "zomi-overlap.jsonl", self.db, self.root / "gold")
        sources[1]["source_text"] = "Independent Zomi source"
        sources[0]["zomi_candidate"] = "machine output"
        save_jsonl(self.root / "candidate.jsonl", sources)
        with self.assertRaisesRegex(ValueError, "machine candidates"):
            prepare_gold(self.root / "candidate.jsonl", self.db, self.root / "gold")


if __name__ == "__main__":
    unittest.main()
