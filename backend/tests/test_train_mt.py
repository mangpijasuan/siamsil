from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))

# Torch is installed on the training machine, not in CI; the Codec test is skipped without it.
from train_mt import Codec, length_batches, load_pairs, to_examples  # type: ignore  # noqa: E402

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

    @unittest.skipUnless(importlib.util.find_spec("torch"), "torch is not installed")
    def test_lengths_round_up_to_few_shapes(self) -> None:
        class Tokenizer:
            eos_token_id, pad_token_id = 2, 1

            def convert_tokens_to_ids(self, code):
                return 5

            def __call__(self, text, add_special_tokens=False):
                return {"input_ids": list(range(10, 10 + len(text.split())))}

        codec = Codec(Tokenizer(), max_len=128, pad_multiple=32)
        self.assertEqual([codec.padded(w) for w in (1, 32, 33, 100, 200)], [32, 32, 64, 128, 128])
        batch = codec.batch([("a b c", "en", "x y", "zom")], "cpu")
        self.assertEqual(tuple(batch["input_ids"].shape), (1, 32))
        self.assertEqual(batch["labels"][0][:5].tolist(), [5, 10, 11, 2, -100])

    def test_length_batches_keep_every_example_once(self) -> None:
        examples = to_examples(PAIRS[:3] * 7, ["en-zomi"])
        batches = length_batches(examples, 4, seed=1)
        self.assertTrue(all(len(batch) <= 4 for batch in batches))
        self.assertEqual(sorted(ex for batch in batches for ex in batch), sorted(examples))
        self.assertEqual(batches, length_batches(examples, 4, seed=1))


if __name__ == "__main__":
    unittest.main()
