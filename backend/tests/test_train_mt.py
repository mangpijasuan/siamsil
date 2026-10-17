from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))

# The training helpers tested here need no torch; the training loop itself runs on the training machine.
from train_mt import length_batches, load_pairs, to_examples  # type: ignore  # noqa: E402

# Zomi-side strings are placeholders, never real language data.
PAIRS = [
    {"english": "One.", "zomi": "ZOMI_PLACEHOLDER_1", "tier": "gold"},
    {"english": "Two words.", "zomi": "ZOMI_PLACEHOLDER_2", "tier": "silver"},
    {"english": "Three short words.", "zomi": "ZOMI_PLACEHOLDER_3", "tier": "bronze"},
    {"english": "", "zomi": "ZOMI_PLACEHOLDER_4", "tier": "gold"},
]


class TrainHelpersTests(unittest.TestCase):
    def test_load_pairs_filters_tiers_and_empty_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "train.jsonl"
            path.write_text("".join(json.dumps(p) + "\n" for p in PAIRS), encoding="utf-8")
            self.assertEqual([p["english"] for p in load_pairs(path, {"gold", "silver"}, None)], ["One.", "Two words."])
            self.assertEqual(len(load_pairs(path, set(), None)), 3)
            self.assertEqual(len(load_pairs(path, set(), 2)), 2)

    def test_examples_cover_both_directions(self) -> None:
        examples = to_examples(PAIRS[:1], ["en-zomi", "zomi-en"])
        self.assertEqual(examples, [
            ("One.", "en", "ZOMI_PLACEHOLDER_1", "zom"),
            ("ZOMI_PLACEHOLDER_1", "zom", "One.", "en"),
        ])

    def test_length_batches_keep_every_example_once(self) -> None:
        examples = to_examples(PAIRS[:3] * 7, ["en-zomi"])
        batches = length_batches(examples, 4, seed=1)
        self.assertTrue(all(len(batch) <= 4 for batch in batches))
        self.assertEqual(sorted(ex for batch in batches for ex in batch), sorted(examples))
        self.assertEqual(batches, length_batches(examples, 4, seed=1))


if __name__ == "__main__":
    unittest.main()
