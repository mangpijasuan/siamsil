from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml_pipeline" / "scripts"))

import filter_szsf_corpus as f  # type: ignore  # noqa: E402


def row(i: str, english: str, zomi: str, split: str = "train", flags=None, model: str = "gemini-3-flash-preview",
        quality: float = 0.9) -> dict:
    # Placeholder text only: no Zomi language data is invented here.
    record = {"szsf_version": "1.0", "id": i, "kind": "translation_pair", "english": english, "zomi": zomi,
              "zomi_standard": zomi, "standard_version": "1.0.0", "source": "parallel_corpus",
              "origin": "machine_generated", "tier": "bronze", "split": split,
              "review": {"status": "UNREVIEWED", "reviewers": [], "approver": None}, "model": model,
              "provider_derived": True, "quality_score": quality, "reference": i}
    if flags:
        record["quality_flags"] = flags
    return record


class FilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def run_filter(self, rows: list[dict], sample: int = 10) -> tuple[dict, Path]:
        source = self.dir / "in.jsonl"
        source.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        out = self.dir / "out"
        return f.run(source, out, sample, {"parallel_corpus": {"train": "blocked"}}), out

    def lines(self, out: Path, name: str) -> list[dict]:
        return [json.loads(l) for l in (out / name).read_text(encoding="utf-8").splitlines()]

    def test_hard_reasons_quarantine_with_a_reason_and_soft_flags_only_queue(self) -> None:
        rows = [
            row("ok", "Hello there.", "ZOMI_A"),
            row("empty", "No Zomi.", ""),
            row("copy", "Same text", "same text"),
            row("num", "I have 5 cats.", "ZOMI_B", flags=["number_mismatch"]),
            row("short", "Yes.", "ZOMI_C", flags=["extremely_short", "length_ratio_outlier"]),
        ]
        summary, out = self.run_filter(rows)
        kept = [r["id"] for r in self.lines(out, "szsf-filtered.jsonl")]
        self.assertEqual(kept, ["ok", "short"])
        quarantined = {r["id"]: r["reasons"] for r in self.lines(out, "quarantine.jsonl")}
        self.assertEqual(quarantined["empty"], ["empty_zomi"])
        self.assertEqual(quarantined["copy"], ["english_copied_as_zomi"])
        self.assertEqual(quarantined["num"], ["number_mismatch"])
        queue = self.lines(out, "review-queue.jsonl")
        self.assertEqual([(q["id"], q["reasons"]) for q in queue], [("short", ["extremely_short", "length_ratio_outlier"])])
        self.assertEqual(summary["quarantined"], 3)

    def test_records_are_never_changed(self) -> None:
        original = row("ok", "Hello there.", "ZOMI_A")
        _, out = self.run_filter([original])
        self.assertEqual(self.lines(out, "szsf-filtered.jsonl"), [original])

    def test_duplicates_keep_the_best_scored_row_within_a_split(self) -> None:
        rows = [row("low", "Same.", "ZOMI_D", quality=0.5), row("high", "Same.", "ZOMI_D", quality=0.9),
                row("tie", "Same.", "ZOMI_D", quality=0.9)]
        _, out = self.run_filter(rows)
        self.assertEqual([r["id"] for r in self.lines(out, "szsf-filtered.jsonl")], ["high"])
        reasons = {r["id"]: r["reasons"] for r in self.lines(out, "quarantine.jsonl")}
        self.assertEqual(reasons, {"low": ["duplicate_pair"], "tie": ["duplicate_pair"]})

    def test_a_train_pair_that_matches_a_test_pair_is_dropped_and_the_test_pair_is_kept(self) -> None:
        rows = [row("tr", "Held out.", "ZOMI_E", split="train"), row("te", "Held out.", "ZOMI_E", split="test")]
        _, out = self.run_filter(rows)
        self.assertEqual([r["id"] for r in self.lines(out, "szsf-filtered.jsonl")], ["te"])
        self.assertEqual(self.lines(out, "quarantine.jsonl")[0]["reasons"], ["duplicate_of_held_out_pair"])

    def test_reaudit_sample_is_ranked_and_limited_to_older_models(self) -> None:
        rows = [row("n", "New model.", "ZOMI_F", model="gemini-3-flash-preview"),
                row("old1", "Old one.", "ZOMI_G", model="gemini-pro", quality=0.9),
                row("old2", "Old two.", "ZOMI_H", model="gemini-pro", quality=0.2, flags=["extremely_short"]),
                row("unk", "Unknown.", "ZOMI_I", model="unknown", quality=0.5)]
        summary, out = self.run_filter(rows, sample=2)
        sample = [r["id"] for r in self.lines(out, "reaudit-sample.jsonl")]
        self.assertEqual(sample, ["old2", "unk"])
        self.assertEqual(summary["reaudit_sample"], 2)

    def test_manifest_matches_the_filtered_file_and_validates_counts(self) -> None:
        _, out = self.run_filter([row("a", "One.", "ZOMI_J"), row("b", "Two.", "ZOMI_K", flags=["html_or_script"])])
        manifest = json.loads((out / "szsf-filtered.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["records"], 1)
        self.assertEqual(manifest["rights_snapshot"]["parallel_corpus"]["train"], "blocked")
        self.assertIn("Filtered does not mean reviewed", manifest["note"])

    def test_refuses_to_write_under_data_raw(self) -> None:
        source = self.dir / "in.jsonl"
        source.write_text(json.dumps(row("a", "One.", "ZOMI_J")) + "\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            f.run(source, ROOT / "data" / "raw" / "filtered-test")

    def test_a_crash_leaves_no_partial_output(self) -> None:
        source = self.dir / "in.jsonl"
        source.write_text(json.dumps(row("a", "One.", "ZOMI_J")) + "\nnot json\n", encoding="utf-8")
        out = self.dir / "out"
        with self.assertRaises(json.JSONDecodeError):
            f.run(source, out)
        self.assertEqual([p.name for p in out.glob("*") if p.is_file()], [])


if __name__ == "__main__":
    unittest.main()
