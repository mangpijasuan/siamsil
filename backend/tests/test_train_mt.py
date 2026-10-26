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
from train_mt import (  # type: ignore  # noqa: E402
    Codec,
    add_zomi,
    check_output_dir,
    checkpoint_fingerprint,
    embedding_report,
    length_batches,
    load_pairs,
    preflight,
    to_examples,
    translate_texts,
)

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

            def get_vocab(self):
                return {"eng_Latn": 5, "ctd_Latn": 5}

            def __call__(self, text, add_special_tokens=False):
                return {"input_ids": list(range(10, 10 + len(text.split())))}

        codec = Codec(Tokenizer(), max_len=128, pad_multiple=32)
        self.assertEqual([codec.padded(w) for w in (1, 32, 33, 100, 200)], [32, 32, 64, 128, 128])
        batch = codec.batch([("a b c", "en", "x y", "zom")], "cpu")
        self.assertEqual(tuple(batch["input_ids"].shape), (1, 32))
        self.assertEqual(batch["labels"][0][:5].tolist(), [5, 10, 11, 2, -100])

    def test_codec_uses_ctd_and_falls_back_to_legacy_token(self) -> None:
        class Tokenizer:
            eos_token_id, pad_token_id = 2, 1

            def __init__(self, vocab):
                self.vocab = vocab

            def get_vocab(self):
                return self.vocab

        new = Codec(Tokenizer({"eng_Latn": 5, "ctd_Latn": 7, "zom_Latn": 6}), max_len=128)
        old = Codec(Tokenizer({"eng_Latn": 5, "zom_Latn": 6}), max_len=128)
        self.assertEqual(new.lang_id, {"en": 5, "zom": 7})
        self.assertEqual(old.lang_id, {"en": 5, "zom": 6})

    @unittest.skipUnless(importlib.util.find_spec("torch"), "torch is not installed")
    def test_new_token_starts_from_legacy_then_mizo(self) -> None:
        import torch

        class Tokenizer:
            def __init__(self, tokens):
                self.vocab = {t: i for i, t in enumerate(tokens)}

            def get_vocab(self):
                return dict(self.vocab)

            def add_tokens(self, tokens, special_tokens=False):
                for t in tokens:
                    self.vocab.setdefault(t, len(self.vocab))

            def convert_tokens_to_ids(self, t):
                return self.vocab[t]

            def __len__(self):
                return len(self.vocab)

        class Model:
            def __init__(self, n):
                self.emb = torch.nn.Embedding(n, 4)

            def resize_token_embeddings(self, n):
                old = self.emb
                self.emb = torch.nn.Embedding(n, 4)
                with torch.no_grad():
                    self.emb.weight[: old.num_embeddings] = old.weight

            def get_input_embeddings(self):
                return self.emb

            def get_output_embeddings(self):
                return None

        for tokens, expected in (
            (["eng_Latn", "lus_Latn", "zom_Latn"], "zom_Latn"),
            (["eng_Latn", "lus_Latn"], "lus_Latn"),
            (["eng_Latn"], "eng_Latn"),
        ):
            tok, model = Tokenizer(tokens), Model(len(tokens))
            info = add_zomi(tok, model)
            self.assertEqual(info, {"added": True, "token": "ctd_Latn", "initialised_from": expected})
            weight = model.emb.weight
            self.assertTrue(torch.equal(weight[tok.vocab["ctd_Latn"]], weight[tok.vocab[expected]]))
            self.assertEqual(add_zomi(tok, model), {"added": False, "token": "ctd_Latn"})

    @unittest.skipUnless(importlib.util.find_spec("torch"), "torch is not installed")
    def test_v1_and_v2_tokens_in_both_directions(self) -> None:
        import torch

        class Tokenizer:
            eos_token_id, pad_token_id = 2, 1

            def __init__(self, vocab):
                self.vocab = vocab

            def get_vocab(self):
                return self.vocab

            def __call__(self, text, add_special_tokens=False):
                return {"input_ids": [10, 11]}

            def batch_decode(self, ids, skip_special_tokens=True):
                return ["out"] * len(ids)

        class Model:
            def eval(self):
                pass

            def generate(self, input_ids, forced_bos_token_id, **kwargs):
                self.calls.append((input_ids[0, 0].item(), forced_bos_token_id))
                return input_ids

        vocabularies = {"v1": {"eng_Latn": 5, "zom_Latn": 6}, "v2": {"eng_Latn": 5, "zom_Latn": 6, "ctd_Latn": 7}}
        zomi_id = {"v1": 6, "v2": 7}
        for name, vocab in vocabularies.items():
            codec, model = Codec(Tokenizer(vocab), max_len=128), Model()
            model.calls = []
            for direction, (src, tgt) in (("en-zomi", ("en", "zom")), ("zomi-en", ("zom", "en"))):
                translate_texts(model, codec, ["text"], src, tgt, torch.device("cpu"), 1, 1)
            self.assertEqual(model.calls, [(5, zomi_id[name]), (zomi_id[name], 5)], name)

    def test_codec_rejects_tokenizer_without_zomi(self) -> None:
        class Tokenizer:
            eos_token_id, pad_token_id = 2, 1

            def get_vocab(self):
                return {"eng_Latn": 5}

        with self.assertRaises(ValueError):
            Codec(Tokenizer(), max_len=128)

    @unittest.skipUnless(importlib.util.find_spec("torch"), "torch is not installed")
    def test_new_token_copies_into_tied_and_untied_output_layers(self) -> None:
        import torch

        for tied in (True, False):
            tok = FakeTokenizer(["eng_Latn", "lus_Latn", "zom_Latn"])
            model = FakeModel(3, tied)
            add_zomi(tok, model)
            new, old = tok.vocab["ctd_Latn"], tok.vocab["zom_Latn"]
            inputs, outputs = model.get_input_embeddings().weight, model.get_output_embeddings().weight
            self.assertEqual(inputs.shape[0], len(tok))
            self.assertTrue(torch.equal(inputs[new], inputs[old]))
            self.assertTrue(torch.equal(outputs[new], outputs[old]))
            report = embedding_report(tok, model, Codec(tok, max_len=128))
            self.assertEqual(report["tied_input_output_embeddings"], tied)
            self.assertEqual(report["tokens"]["zom"], {"token": "ctd_Latn", "id": new})

    @unittest.skipUnless(importlib.util.find_spec("torch"), "torch is not installed")
    def test_embedding_report_rejects_short_embeddings(self) -> None:
        tok = FakeTokenizer(["eng_Latn", "ctd_Latn", "extra"])
        with self.assertRaises(SystemExit):
            embedding_report(tok, FakeModel(2, True), Codec(tok, max_len=128))

    def test_output_dir_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source, out = Path(tmp) / "v1", Path(tmp) / "v2"
            source.mkdir()
            (source / "model.safetensors").write_text("weights")
            with self.assertRaises(SystemExit):
                check_output_dir(source, str(source))
            check_output_dir(out, str(source))
            out.mkdir()
            check_output_dir(out, str(source))
            (out / "x").write_text("x")
            with self.assertRaises(SystemExit):
                check_output_dir(out, str(source))
            before = checkpoint_fingerprint(str(source))
            self.assertEqual(set(before["sha256"]), {"model.safetensors"})
            self.assertEqual(before, checkpoint_fingerprint(str(source)))
            self.assertEqual(checkpoint_fingerprint("facebook/model"), {"hub_id": "facebook/model"})

    def test_length_batches_keep_every_example_once(self) -> None:
        examples = to_examples(PAIRS[:3] * 7, ["en-zomi"])
        batches = length_batches(examples, 4, seed=1)
        self.assertTrue(all(len(batch) <= 4 for batch in batches))
        self.assertEqual(sorted(ex for batch in batches for ex in batch), sorted(examples))
        self.assertEqual(batches, length_batches(examples, 4, seed=1))


class PreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.bench = self.dir / "bench.jsonl"
        self.bench.write_text(json.dumps({"english": "Benchmark sentence.", "zomi": "ZOMI_PLACEHOLDER_B"}) + "\n")

    def write(self, rows: dict[str, list[dict]], sources: dict[str, dict], uncleared: list[str]) -> Path:
        data = self.dir / "export"
        data.mkdir(exist_ok=True)
        for split in ("train", "validation", "test"):
            (data / f"{split}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows.get(split, [])))
        (data / "manifest.json").write_text(json.dumps({"sources": sources, "uncleared_sources_included": uncleared}))
        return data

    def row(self, source: str, english: str = "Fine.", zomi: str = "ZOMI_PLACEHOLDER_1") -> dict:
        return {"id": "r", "english": english, "zomi": zomi, "source": source}

    def test_cleared_export_passes(self) -> None:
        data = self.write({"train": [self.row("a")]}, {"a": {"train_rights": "cleared", "exported": True}}, [])
        result = preflight(data, False, [self.bench])
        self.assertEqual(result["rows_by_source"], {"a": 1})
        self.assertEqual(result["benchmark_overlap"], 0)

    def test_uncleared_needs_explicit_flag(self) -> None:
        data = self.write({"train": [self.row("a")]}, {"a": {"train_rights": "needs_review", "exported": True}}, ["a"])
        with self.assertRaises(SystemExit):
            preflight(data, False, [])
        self.assertTrue(preflight(data, True, [])["allow_uncleared_data"])

    def test_blocked_or_unexported_sources_stop_training(self) -> None:
        for entry in ({"train_rights": "blocked", "exported": True}, {"train_rights": "cleared", "exported": False}, None):
            sources = {"a": entry} if entry else {}
            data = self.write({"train": [self.row("a")]}, sources, [])
            with self.assertRaises(SystemExit):
                preflight(data, True, [])

    def test_benchmark_overlap_stops_training_but_test_may_hold_it(self) -> None:
        sources = {"a": {"train_rights": "cleared", "exported": True}}
        data = self.write({"test": [self.row("a", zomi="ZOMI_PLACEHOLDER_B")]}, sources, [])
        self.assertEqual(preflight(data, False, [self.bench])["benchmark_overlap"], 0)
        for row in (self.row("a", zomi="zomi_placeholder_b."), self.row("a", english="Benchmark sentence!")):
            data = self.write({"validation": [row]}, sources, [])
            with self.assertRaises(SystemExit):
                preflight(data, False, [self.bench])


class FakeTokenizer:
    eos_token_id, pad_token_id = 2, 1

    def __init__(self, tokens):
        self.vocab = {t: i for i, t in enumerate(tokens)}

    def get_vocab(self):
        return dict(self.vocab)

    def add_tokens(self, tokens, special_tokens=False):
        for t in tokens:
            self.vocab.setdefault(t, len(self.vocab))

    def convert_tokens_to_ids(self, t):
        return self.vocab[t]

    def __len__(self):
        return len(self.vocab)


class FakeModel:
    """Embeddings shaped like NLLB's: shared input embedding, output layer either tied or separate."""

    class Config:
        vocab_size = 0

    def __init__(self, n, tied):
        import torch

        self.config, self.tied = self.Config(), tied
        self.emb = torch.nn.Embedding(n, 4)
        self.head = None if tied else torch.nn.Linear(4, n, bias=False)
        self.config.vocab_size = n

    def resize_token_embeddings(self, n):
        import torch

        def grow(weight):
            new = torch.randn(n, weight.shape[1])
            new[: weight.shape[0]] = weight.detach()
            return new

        self.emb = torch.nn.Embedding.from_pretrained(grow(self.emb.weight), freeze=False)
        if self.head is not None:
            self.head = torch.nn.Linear(4, n, bias=False)
            self.head.weight = torch.nn.Parameter(grow(self.head.weight[: self.head.weight.shape[0]]))
        self.config.vocab_size = n

    def get_input_embeddings(self):
        return self.emb

    def get_output_embeddings(self):
        if self.tied:
            head = type("Tied", (), {})()
            head.weight = self.emb.weight
            return head
        return self.head


if __name__ == "__main__":
    unittest.main()
