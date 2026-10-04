from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))

from eval_set import DOMAINS, build_manifest, find_leaks, main, validate_items  # type: ignore  # noqa: E402

# Zomi-side strings are placeholders, never real language data.


def make_item(**overrides) -> dict:
    item = {
        "_line": 1,
        "id": "en-zomi-0001",
        "direction": "en-zomi",
        "domain": "health",
        "source_text": "Where is the nearest clinic?",
        "references": ["ZOMI_PLACEHOLDER_REFERENCE_1"],
        "source_origin": "written by contributor T01",
        "translator": "T01",
        "reviewer": "R01",
        "adjudicator": None,
        "review_outcome": "accepted",
        "notes": "",
    }
    item.update(overrides)
    return item


def full_coverage() -> list[dict]:
    return [
        make_item(_line=n, id=f"en-zomi-{n:04d}", domain=domain, source_text=f"English sentence {n}.")
        for n, domain in enumerate(DOMAINS, start=1)
    ]


class ValidateTests(unittest.TestCase):
    def test_complete_set_has_no_errors_or_warnings(self) -> None:
        errors, warnings = validate_items(full_coverage())
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_reviewer_must_differ_from_translator(self) -> None:
        errors, _ = validate_items([make_item(reviewer="T01")])
        self.assertTrue(any("reviewer must differ" in e for e in errors))

    def test_adjudicated_item_requires_independent_adjudicator(self) -> None:
        errors, _ = validate_items([make_item(review_outcome="adjudicated")])
        self.assertTrue(any("need an adjudicator" in e for e in errors))
        errors, _ = validate_items([make_item(review_outcome="adjudicated", adjudicator="R01")])
        self.assertTrue(any("adjudicator must differ" in e for e in errors))

    def test_duplicate_ids_and_bad_enums_are_errors(self) -> None:
        items = [make_item(), make_item(_line=2, domain="sports", direction="en-fr")]
        errors, _ = validate_items(items)
        self.assertTrue(any("duplicate id" in e for e in errors))
        self.assertTrue(any("domain must be" in e for e in errors))
        self.assertTrue(any("direction must be" in e for e in errors))

    def test_empty_references_are_errors(self) -> None:
        for references in ([], [""], None, "not a list"):
            errors, _ = validate_items([make_item(references=references)])
            self.assertTrue(any("references" in e for e in errors), references)

    def test_mixed_directions_are_an_error(self) -> None:
        items = [make_item(), make_item(_line=2, id="zomi-en-0001", direction="zomi-en")]
        errors, _ = validate_items(items)
        self.assertTrue(any("one direction" in e for e in errors))

    def test_missing_domains_are_warnings_not_errors(self) -> None:
        errors, warnings = validate_items([make_item()])
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)


class LeakageTests(unittest.TestCase):
    def test_matches_normalized_english_and_zomi(self) -> None:
        items = [
            make_item(id="a", source_text="Where is the nearest clinic?"),
            make_item(id="b", source_text="Unseen sentence.", references=["ZOMI_PLACEHOLDER_SHARED"]),
            make_item(id="c", source_text="Another unseen sentence."),
        ]
        corpus = [
            ("where is the NEAREST clinic", "ZOMI_PLACEHOLDER_OTHER"),
            ("Unrelated corpus sentence.", "zomi_placeholder_shared!"),
        ]
        self.assertEqual(find_leaks(items, corpus), {"a": {"en"}, "b": {"zomi"}})

    def test_reverse_direction_checks_source_as_zomi(self) -> None:
        item = make_item(
            id="z", direction="zomi-en", source_text="ZOMI_PLACEHOLDER_SOURCE", references=["Good morning."]
        )
        corpus = [("Good morning.", "x"), ("y", "ZOMI_PLACEHOLDER_SOURCE")]
        self.assertEqual(find_leaks([item], corpus), {"z": {"en", "zomi"}})


class CommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def write_set(self, items: list[dict]) -> Path:
        path = self.dir / "en-zomi-v1.jsonl"
        lines = [json.dumps({k: v for k, v in item.items() if k != "_line"}) for item in items]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def run_main(self, *argv: str) -> int:
        with redirect_stdout(StringIO()):
            return main(list(argv))

    def test_manifest_written_for_valid_set(self) -> None:
        path = self.write_set(full_coverage())
        self.assertEqual(self.run_main("validate", str(path)), 0)
        self.assertEqual(self.run_main("manifest", str(path)), 0)
        manifest = json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["items"], len(DOMAINS))
        self.assertEqual(manifest["direction"], "en-zomi")
        self.assertEqual(manifest, build_manifest(path, full_coverage()))

    def test_manifest_refused_for_invalid_set(self) -> None:
        path = self.write_set([make_item(reviewer="T01")])
        self.assertEqual(self.run_main("validate", str(path)), 1)
        self.assertEqual(self.run_main("manifest", str(path)), 1)
        self.assertFalse(path.with_suffix(".manifest.json").exists())

    def test_leakage_command_reads_corpus_csv(self) -> None:
        path = self.write_set(full_coverage())
        corpus = self.dir / "corpus.csv"
        with corpus.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["index", "en", "zomi"])
            writer.writerow([1, "Unrelated.", "ZOMI_PLACEHOLDER_OTHER"])
        self.assertEqual(self.run_main("leakage", str(path), "--corpus", str(corpus)), 0)
        with corpus.open("a", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerow([2, "English sentence 3.", "ZOMI_PLACEHOLDER_OTHER"])
        self.assertEqual(self.run_main("leakage", str(path), "--corpus", str(corpus)), 1)


if __name__ == "__main__":
    unittest.main()
