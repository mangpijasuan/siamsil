"""Review clusters and priority queues (docs/REVIEW_QUEUES.md). Zomi-side strings are placeholders, not language data."""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import review_clusters as rc  # type: ignore  # noqa: E402
from build_language_db import pair_key  # type: ignore  # noqa: E402
from review_sample import export_queue, read_queue  # type: ignore  # noqa: E402
from test_corpus_reviews import CorpusFixture  # type: ignore  # noqa: E402


def row(n: int, english: str, zomi: str, **extra) -> dict:
    record = {"id": f"corpus-{n}", "english": english, "zomi": zomi, "zomi_standard": zomi, "split": "train",
              "model": "gemini-2.5-flash", "quality_score": 0.9, "quality_flags": []}
    record.update(extra)
    return record


ROWS = [
    # One template (numbers set aside), translated two ways: an inconsistency worth reviewing first.
    row(1, "I am 30 years old.", "ZOMI_AGE_A 30"),
    row(2, "I am 45 years old.", "ZOMI_AGE_A 45"),
    row(3, "I am 12 years old.", "ZOMI_AGE_B 12"),
    # Another template, translated one way.
    row(4, "Thank you very much.", "ZOMI_THANKS"),
    row(5, "thank you very much!", "ZOMI_THANKS"),
    # Near duplicates: most word pairs shared, one word different.
    row(6, "The children are playing in the garden behind the house today.", "ZOMI_GARDEN_A"),
    row(7, "The children are playing in the garden behind the school today.", "ZOMI_GARDEN_B"),
    # Singles: one uncertain (old model, soft flag), one not.
    row(8, "Where is the market?", "ZOMI_MARKET", model="gemini-pro", quality_flags=["length_ratio_outlier"],
        quality_score=0.5),
    row(9, "The river is wide.", "ZOMI_RIVER"),
    # Held out, and already reviewed: not queued.
    row(10, "This sentence is held out for testing.", "ZOMI_TEST", split="test"),
    row(11, "This one was already reviewed.", "ZOMI_DONE"),
]


class BuildTests(unittest.TestCase):
    def build(self, **options):
        defaults = {"decided": {pair_key("This one was already reviewed.", "ZOMI_DONE")},
                    "near_scope": {r["id"] for r in ROWS}}
        return rc.build(ROWS, **{**defaults, **options})

    def test_templates_ignore_case_punctuation_and_numbers(self) -> None:
        clusters, _, _ = self.build()
        templates = [sorted(m.id for m in c.members) for c in clusters if c.kind == "template"]
        self.assertIn(["corpus-1", "corpus-2", "corpus-3"], templates)
        self.assertIn(["corpus-4", "corpus-5"], templates)

    def test_near_duplicates_are_grouped_and_verified(self) -> None:
        clusters, singles, _ = self.build()
        near = [sorted(m.id for m in c.members) for c in clusters if c.kind == "near"]
        self.assertEqual(near, [["corpus-6", "corpus-7"]])
        self.assertNotIn("corpus-6", {s.id for s in singles})
        clusters, _, _ = self.build(near_threshold=0.95)  # stricter than their real overlap
        self.assertFalse([c for c in clusters if c.kind == "near"])

    def test_near_duplicates_only_within_scope(self) -> None:
        clusters, _, _ = self.build(near_scope={"corpus-6"})
        self.assertFalse([c for c in clusters if c.kind == "near"])
        clusters, _, _ = self.build(near_scope=None)
        self.assertFalse([c for c in clusters if c.kind == "near"])

    def test_inconsistent_translations_rank_first(self) -> None:
        clusters, _, _ = self.build()
        first = clusters[0]
        self.assertEqual(sorted(m.id for m in first.members), ["corpus-1", "corpus-2", "corpus-3"])
        self.assertEqual(first.scores["zomi_variants"], 2)
        self.assertEqual(first.scores["inconsistency"], 0.5)
        thanks = next(c for c in clusters if "corpus-4" in {m.id for m in c.members})
        self.assertEqual(thanks.scores["inconsistency"], 0.0)

    def test_held_out_and_reviewed_pairs_are_left_out(self) -> None:
        clusters, singles, stats = self.build()
        queued = {m.id for c in clusters for m in c.members} | {s.id for s in singles}
        self.assertNotIn("corpus-10", queued)
        self.assertNotIn("corpus-11", queued)
        self.assertEqual((stats["skipped_held_out"], stats["skipped_already_reviewed"]), (1, 1))
        _, singles, _ = self.build(include_held_out=True)
        self.assertIn("corpus-10", {s.id for s in singles})

    def test_singles_follow_by_uncertainty(self) -> None:
        _, singles, _ = self.build()
        self.assertEqual([s.id for s in singles][:2], ["corpus-8", "corpus-9"])

    def test_large_clusters_show_a_first_few_then_the_rest_last(self) -> None:
        clusters, singles, _ = self.build()
        lines = list(rc.queue_lines(clusters, singles, per_cluster=1))
        ids = [line["id"] for line in lines]
        self.assertEqual(sorted(ids), sorted({*ids}))  # still each row once
        first_part = ids[:len(clusters)]
        self.assertEqual(first_part, [c.representative for c in clusters])
        self.assertEqual(ids[len(clusters):len(clusters) + len(singles)], [s.id for s in singles])
        self.assertTrue(all(line["cluster"] for line in lines[len(clusters) + len(singles):]))

    def test_every_row_is_queued_once(self) -> None:
        clusters, singles, _ = self.build()
        lines = list(rc.queue_lines(clusters, singles))
        ids = [line["id"] for line in lines]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 9)
        self.assertEqual([line["rank"] for line in lines], list(range(1, 10)))
        # Members of one cluster are next to each other, representative first.
        first_cluster = [line for line in lines if line["cluster"] == lines[0]["cluster"]]
        self.assertEqual(lines[:len(first_cluster)], first_cluster)
        self.assertEqual(lines[0]["id"], clusters[0].representative)


class OutputTests(unittest.TestCase):
    def test_run_writes_private_files_and_never_text_in_the_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "rows.jsonl"
            source.write_text("".join(json.dumps(r) + "\n" for r in ROWS), encoding="utf-8")
            out = Path(tmp) / "clusters"
            with redirect_stdout(StringIO()):
                self.assertEqual(rc.main(["--input", str(source), "--out-dir", str(out)]), 0)
            for name in ("cluster-queue.jsonl", "clusters.jsonl", "summary.json"):
                self.assertEqual((out / name).stat().st_mode & 0o777, 0o600, name)
            queue_text = (out / "cluster-queue.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("ZOMI_", queue_text)
            self.assertNotIn("years old", queue_text)
            # The queue reads exactly as export-queue reads a filter queue.
            entries = read_queue(out / "cluster-queue.jsonl")
            self.assertEqual(len(entries), 10)  # all but the held-out row (no --reviews given)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertIn("nothing was reviewed", summary["note"])

    def test_data_raw_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            rc.run(PROJECT_ROOT / "data" / "raw" / "x.jsonl", Path(tempfile.gettempdir()) / "out")


class ExportQueueTests(CorpusFixture):
    """The cluster queue drives the existing export-queue and Excel flow unchanged."""

    def test_cluster_order_reaches_the_review_sheet(self) -> None:
        con = sqlite3.connect(self.database)
        db_rows = con.execute("SELECT id, normalized_source_text, normalized_target_text FROM parallel_sentences "
                              "ORDER BY id").fetchall()
        con.close()
        records = [row(i, english, zomi) for i, english, zomi in db_rows]
        records[2]["model"], records[2]["quality_flags"] = "gemini-pro", ["target_reused"]  # make it the representative
        clusters, singles, _ = rc.build(records)
        self.assertEqual(len(clusters), 1)  # "English sentence number N." is one template
        queue = self.dir / "cluster-queue.jsonl"
        queue.write_text("".join(json.dumps(line) + "\n" for line in rc.queue_lines(clusters, singles)),
                         encoding="utf-8")
        entries = read_queue(queue)
        review_path, _, count, missing, stale = export_queue(
            self.database, self.dir / "batch", [n for n, _ in entries], 0, None, dict(entries))
        self.assertEqual((count, missing, stale), (len(records), [], []))
        first = self.read(review_path)[0]
        self.assertEqual(first["english"], records[2]["english"])


if __name__ == "__main__":
    unittest.main()
