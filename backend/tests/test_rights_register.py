"""The parallel corpus rights are split by component; the combined pairs stay blocked (docs/DATA_RIGHTS.md)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
USES = ("display", "train", "redistribute", "commercial")


class ParallelCorpusRightsSplitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sources = json.loads((PROJECT_ROOT / "data" / "rights.json").read_text(encoding="utf-8"))["sources"]

    def test_combined_pairs_stay_blocked_and_name_their_components(self) -> None:
        combined = self.sources["parallel_corpus"]
        self.assertEqual({combined[use] for use in USES}, {"blocked"})
        for component in combined["components"]:
            self.assertEqual(self.sources[component]["part_of"], "parallel_corpus")

    def test_components_are_not_permissive(self) -> None:
        for component in self.sources["parallel_corpus"]["components"]:
            for use in USES:
                self.assertEqual(self.sources[component][use], "needs_review", f"{component} {use}")

    def test_combined_is_never_looser_than_a_component(self) -> None:
        combined = self.sources["parallel_corpus"]
        for component in combined["components"]:
            for use in USES:
                if self.sources[component][use] != "cleared":
                    self.assertNotEqual(combined[use], "cleared", f"{use} cleared while {component} is not")


if __name__ == "__main__":
    unittest.main()
