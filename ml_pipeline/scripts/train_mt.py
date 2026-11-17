#!/usr/bin/env python3
"""Fine-tune a pretrained translation model on Siamsil's exported pairs.

The default base model is NLLB-200 distilled 600M (CC BY-NC 4.0; acceptable
because Siamsil is non-profit, see docs/DATA_RIGHTS.md). NLLB has no Zomi
language code, so training adds `ctd_Latn` (ISO 639-3 Tedim Chin, the basis
of Standard Zomi) and starts it from Mizo (`lus_Latn`), a closely related
Kuki-Chin language that NLLB covers. Models trained before the rename use
`zom_Latn` (which is really Zou's code); continuing from one copies its trained
token into `ctd_Latn`, and `try`/`translate` still work on the old models.

Commands:
  train --data DIR --out DIR [--model ID] [--epochs N] ...
      DIR is an export from export_datasets.py (train/validation/test.jsonl).
      Trains English<->Zomi in both directions, keeps the checkpoint with the
      best validation chrF++, then scores the test split.
      Before loading a model it refuses to write into the source checkpoint or a
      non-empty --out, to train on an export that includes uncleared sources
      without --allow-uncleared-data, on rows from sources the manifest does
      not admit, or on train/validation rows matching a --benchmark file.
      train_meta.json records the source checkpoint hashes, Git state, language
      token mapping, export manifest, source rights, seed and hyperparameters.
  translate --model DIR --eval FILE --out HYP.jsonl [--system NAME]
      Translate a human evaluation set (docs/EVALUATION_SET.md format); score
      the output with `mt_eval.py score`.
  try --model DIR [--direction en-zomi|zomi-en]
      Type sentences and see the translation; an empty line or Ctrl-D quits.

The export's test split for Bible pairs holds out whole books (Ruth, Mark,
1 John). Its scores measure Bible-style text only; claims about everyday
translation quality need the human evaluation sets.

Needs: torch, transformers, sentencepiece, sacrebleu. On Apple Silicon the
script uses the GPU (MPS) automatically; set PYTORCH_ENABLE_MPS_FALLBACK=1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_MODEL = "facebook/nllb-200-distilled-600M"
LANG = {"en": "eng_Latn", "ctd": "ctd_Latn"}
LEGACY_ZOMI_TOKEN = "zom_Latn"
INIT_FROM = "lus_Latn"  # Mizo
DIRECTIONS = {"en-zomi": ("en", "ctd"), "zomi-en": ("ctd", "en")}
ROOT = Path(__file__).resolve().parents[2]


def pick_device(name: str):
    import torch

    if name != "auto":
        return torch.device(name)
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def release_cached_memory(device) -> None:
    import torch

    if device.type == "mps":
        torch.mps.empty_cache()
    elif device.type == "cuda":
        torch.cuda.empty_cache()


def make_optimizer(model, args):
    """Adafactor keeps factored statistics instead of AdamW's two full copies of every weight
    (about 5 GB for NLLB-600M), which is what lets training fit on a 24 GB Mac."""
    import torch

    if args.optimizer == "adamw":
        return torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    from transformers.optimization import Adafactor

    return Adafactor(model.parameters(), lr=args.lr, scale_parameter=False, relative_step=False, warmup_init=False)


def read_jsonl(path: Path, limit: int | None = None) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
                if limit and len(rows) >= limit:
                    break
    return rows


def load_pairs(path: Path, tiers: set[str], limit: int | None) -> list[dict]:
    pairs = [
        row for row in read_jsonl(path)
        if row.get("english") and row.get("zomi") and (not tiers or row.get("tier") in tiers)
    ]
    if limit:
        random.Random(0).shuffle(pairs)
        pairs = pairs[:limit]
    return pairs


def to_examples(pairs: list[dict], directions: list[str]) -> list[tuple[str, str, str, str]]:
    """(source text, source lang, target text, target lang) for every pair and direction."""
    out = []
    for pair in pairs:
        text = {"en": pair["english"], "ctd": pair["zomi"]}
        for direction in directions:
            src, tgt = DIRECTIONS[direction]
            out.append((text[src], src, text[tgt], tgt))
    return out


def add_zomi(tokenizer, model) -> dict:
    """Add the Zomi language token, starting from a legacy trained token, else Mizo, else English."""
    code = LANG["ctd"]
    vocab = tokenizer.get_vocab()
    if code in vocab:
        return {"added": False, "token": code}
    tokenizer.add_tokens([code], special_tokens=True)
    model.resize_token_embeddings(len(tokenizer))
    new_id = tokenizer.convert_tokens_to_ids(code)
    init = next(t for t in (LEGACY_ZOMI_TOKEN, INIT_FROM, LANG["en"]) if t in vocab)
    init_id = tokenizer.convert_tokens_to_ids(init)
    import torch

    with torch.no_grad():
        model.get_input_embeddings().weight[new_id] = model.get_input_embeddings().weight[init_id]
        out = model.get_output_embeddings()
        if out is not None and out.weight.data_ptr() != model.get_input_embeddings().weight.data_ptr():
            out.weight[new_id] = out.weight[init_id]
    return {"added": True, "token": code, "initialised_from": init}


class Codec:
    """NLLB-style sequences built by hand: [lang] tokens </s>. Works for any tokenizer version."""

    def __init__(self, tokenizer, max_len: int, pad_multiple: int = 32):
        self.tok = tokenizer
        self.max_len = max_len
        # Few distinct tensor shapes: Apple's GPU backend compiles and keeps a graph per shape,
        # and with free-length batches that cache grows until memory runs out.
        self.pad_multiple = max(1, pad_multiple)
        self.eos = tokenizer.eos_token_id
        self.pad = tokenizer.pad_token_id
        vocab = tokenizer.get_vocab()
        self.lang_token = {
            key: code if code in vocab or key != "ctd" else LEGACY_ZOMI_TOKEN for key, code in LANG.items()
        }
        missing = [token for token in self.lang_token.values() if token not in vocab]
        if missing:
            raise ValueError(f"tokenizer has no language token {', '.join(missing)}")
        self.lang_id = {key: vocab[token] for key, token in self.lang_token.items()}

    def encode(self, text: str, lang: str) -> list[int]:
        ids = self.tok(text, add_special_tokens=False)["input_ids"][: self.max_len - 2]
        return [self.lang_id[lang], *ids, self.eos]

    def padded(self, width: int) -> int:
        return min(self.max_len, -(-width // self.pad_multiple) * self.pad_multiple)

    def batch(self, examples, device):
        import torch

        sources = [self.encode(s, sl) for s, sl, _, _ in examples]
        targets = [self.encode(t, tl) for _, _, t, tl in examples]
        width_s = self.padded(max(map(len, sources)))
        width_t = self.padded(max(map(len, targets)))
        input_ids = torch.full((len(sources), width_s), self.pad, dtype=torch.long)
        attention = torch.zeros_like(input_ids)
        labels = torch.full((len(targets), width_t), -100, dtype=torch.long)
        for i, (src, tgt) in enumerate(zip(sources, targets)):
            input_ids[i, : len(src)] = torch.tensor(src)
            attention[i, : len(src)] = 1
            labels[i, : len(tgt)] = torch.tensor(tgt)
        return {"input_ids": input_ids.to(device), "attention_mask": attention.to(device), "labels": labels.to(device)}


def length_batches(examples, batch_size: int, seed: int) -> list[list]:
    """Group similar lengths to waste less padding, then shuffle the batches."""
    rng = random.Random(seed)
    order = examples[:]
    rng.shuffle(order)
    batches = []
    pool = batch_size * 50
    for start in range(0, len(order), pool):
        chunk = sorted(order[start : start + pool], key=lambda ex: len(ex[0]) + len(ex[2]))
        batches += [chunk[i : i + batch_size] for i in range(0, len(chunk), batch_size)]
    rng.shuffle(batches)
    return batches


def translate_texts(model, codec: Codec, texts: list[str], src: str, tgt: str, device, batch_size: int, beams: int) -> list[str]:
    import torch

    model.eval()
    outputs = []
    with torch.no_grad():
        for start in range(0, len(texts), batch_size):
            chunk = texts[start : start + batch_size]
            batch = codec.batch([(t, src, "", tgt) for t in chunk], device)
            generated = model.generate(
                input_ids=batch["input_ids"],
                attention_mask=batch["attention_mask"],
                forced_bos_token_id=codec.lang_id[tgt],
                decoder_start_token_id=codec.eos,
                num_beams=beams,
                # max_length, not max_new_tokens: NLLB's config sets max_length=200 and the two conflict.
                # +2 for the start token and the language token.
                max_length=codec.max_len + 2,
                use_cache=True,
            )
            outputs += codec.tok.batch_decode(generated, skip_special_tokens=True)
            release_cached_memory(device)
    return [text.strip() for text in outputs]


def score(hypotheses: list[str], references: list[str]) -> dict:
    import sacrebleu

    return {
        "chrf++": round(sacrebleu.corpus_chrf(hypotheses, [references], word_order=2).score, 2),
        "bleu": round(sacrebleu.corpus_bleu(hypotheses, [references]).score, 2),
        "items": len(hypotheses),
    }


def evaluate(model, codec, pairs, directions, device, batch_size, beams, limit=None) -> dict:
    sample = pairs[:limit] if limit else pairs
    results = {}
    for direction in directions:
        src, tgt = DIRECTIONS[direction]
        key = {"en": "english", "ctd": "zomi"}
        hyps = translate_texts(model, codec, [p[key[src]] for p in sample], src, tgt, device, batch_size, beams)
        results[direction] = score(hyps, [p[key[tgt]] for p in sample])
    results["mean_chrf++"] = round(sum(results[d]["chrf++"] for d in directions) / len(directions), 2)
    return results


def validation_loss(model, codec, examples, device, batch_size) -> float:
    import torch

    model.eval()
    total, count = 0.0, 0
    with torch.no_grad():
        for start in range(0, len(examples), batch_size):
            chunk = examples[start : start + batch_size]
            total += float(model(**codec.batch(chunk, device)).loss) * len(chunk)
            count += len(chunk)
    return round(total / max(1, count), 4)


def file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or None
    except OSError:
        return None


def git_uncommitted_code() -> list[str]:
    """Changed or untracked code files; data files are tracked through their own fingerprints."""
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain", "--", "ml_pipeline", "backend"],
            capture_output=True, text=True,
        ).stdout
    except OSError:
        return []
    return sorted(line[3:] for line in out.splitlines() if line.strip())


CHECKPOINT_FILES = ("config.json", "generation_config.json", "model.safetensors", "tokenizer.json",
                    "tokenizer_config.json", "train_meta.json")


def checkpoint_fingerprint(model: str) -> dict:
    path = Path(model)
    if not path.is_dir():
        return {"hub_id": model}
    files = {name: file_sha256(path / name) for name in CHECKPOINT_FILES if (path / name).exists()}
    return {"path": str(path), "sha256": files}


def check_output_dir(out: Path, model: str) -> None:
    """Never write into the source checkpoint or over an earlier run."""
    if Path(model).is_dir() and out.resolve() == Path(model).resolve():
        sys.exit(f"--out {out} is the source checkpoint; choose a new directory")
    if out.exists() and any(out.iterdir()):
        sys.exit(f"--out {out} already has files; choose a new directory")


def benchmark_keys(paths: list[Path]) -> tuple[set[str], set[str], list[dict]]:
    """English and Zomi match keys for benchmark items, the same keys the export excludes with --eval."""
    from build_language_db import eval_match_keys, load_eval_items

    files = []
    for path in paths:
        files.append({"file": str(path), "sha256": file_sha256(path), "items": len(load_eval_items([path]))})
    english, zomi = eval_match_keys(load_eval_items(paths), set())
    return english, zomi, files


def preflight(data: Path, allow_uncleared: bool, benchmarks: list[Path]) -> dict:
    """Refuse to train on data the export manifest does not admit, or that overlaps a benchmark."""
    from build_language_db import normalize_word, template_key

    manifest_path = data / "manifest.json"
    if not manifest_path.exists():
        sys.exit(f"No export manifest at {manifest_path}; export with export_datasets.py")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rights = manifest.get("sources", {})
    uncleared = manifest.get("uncleared_sources_included", [])
    if uncleared and not allow_uncleared:
        sys.exit(f"Export includes sources not cleared for training ({', '.join(uncleared)}); "
                 "pass --allow-uncleared-data only for an internal experiment")

    bench_english, bench_zomi, bench_files = benchmark_keys(benchmarks)
    sources: Counter[str] = Counter()
    overlap: Counter[str] = Counter()
    for split in ("train", "validation", "test"):
        for row in read_jsonl(data / f"{split}.jsonl"):
            for source in {row.get("source"), row.get("english_source")} - {None}:
                sources[source] += 1
                entry = rights.get(source)
                if not entry or not entry.get("exported") or entry.get("train_rights") == "blocked":
                    sys.exit(f"{split}.jsonl row {row.get('id')} comes from {source}, which the manifest does not admit")
            if split != "test" and (
                template_key(row.get("english") or "", set()) in bench_english
                or normalize_word(row.get("zomi")) in bench_zomi
            ):
                overlap[split] += 1
    if overlap:
        sys.exit(f"Training data overlaps a benchmark: {dict(overlap)}; re-export with --eval")
    return {
        "export_manifest_sha256": file_sha256(manifest_path),
        "language_release": manifest.get("language_release"),
        "export_inputs": manifest.get("inputs"),
        "rows_by_source": dict(sorted(sources.items())),
        "source_rights": {name: rights[name] for name in sorted(sources)},
        "uncleared_sources_included": uncleared,
        "allow_uncleared_data": allow_uncleared,
        "benchmarks_checked": bench_files,
        "benchmark_overlap": 0,
    }


def embedding_report(tokenizer, model, codec: "Codec") -> dict:
    """Language-token ids and embedding shapes, checked for consistency before training."""
    inputs = model.get_input_embeddings()
    outputs = model.get_output_embeddings()
    tied = outputs is not None and outputs.weight.data_ptr() == inputs.weight.data_ptr()
    if len(tokenizer) > inputs.num_embeddings:
        sys.exit(f"tokenizer has {len(tokenizer)} tokens but the model only {inputs.num_embeddings} embeddings")
    if outputs is not None and outputs.weight.shape[0] != inputs.num_embeddings:
        sys.exit("input and output embedding sizes differ")
    return {
        "tokens": {key: {"token": codec.lang_token[key], "id": codec.lang_id[key]} for key in LANG},
        "tokenizer_size": len(tokenizer),
        "embedding_rows": inputs.num_embeddings,
        "config_vocab_size": model.config.vocab_size,
        "tied_input_output_embeddings": tied,
    }


def cmd_train(args) -> int:
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    check_output_dir(args.out, args.model)
    data_check = preflight(args.data, args.allow_uncleared_data, args.benchmark)
    source_checkpoint = checkpoint_fingerprint(args.model)
    code = {"git_commit": git_commit(), "uncommitted_code_files": git_uncommitted_code()}
    if code["uncommitted_code_files"]:
        print(f"WARNING: uncommitted code changes: {', '.join(code['uncommitted_code_files'])}", flush=True)

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = pick_device(args.device)
    directions = args.directions.split(",")
    tiers = set(filter(None, args.tiers.split(",")))
    train_pairs = load_pairs(args.data / "train.jsonl", tiers, args.limit)
    val_pairs = load_pairs(args.data / "validation.jsonl", tiers, None)
    test_pairs = load_pairs(args.data / "test.jsonl", tiers, None)
    if not train_pairs:
        sys.exit(f"No training pairs in {args.data / 'train.jsonl'} for tiers {sorted(tiers) or 'all'}")
    random.Random(1).shuffle(val_pairs)
    val_pairs = val_pairs[: args.val_size]
    print(f"device {device} | train pairs {len(train_pairs):,} | validation {len(val_pairs):,} | test {len(test_pairs):,}")

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model)
    language = add_zomi(tokenizer, model)
    if args.gradient_checkpointing:
        # Recompute activations in the backward pass instead of storing them: far less memory, ~25% slower.
        model.gradient_checkpointing_enable()
        model.config.use_cache = False
    model.to(device)
    codec = Codec(tokenizer, args.max_len, args.pad_multiple)
    embeddings = embedding_report(tokenizer, model, codec)
    print(f"language tokens: {json.dumps(embeddings['tokens'])}", flush=True)

    train_examples = to_examples(train_pairs, directions)
    val_examples = to_examples(val_pairs, directions)
    steps_per_epoch = math.ceil(len(length_batches(train_examples, args.batch_size, 0)) / args.grad_accum)
    total_steps = steps_per_epoch * args.epochs
    warmup = max(1, int(total_steps * args.warmup))
    optimizer = make_optimizer(model, args)
    schedule = torch.optim.lr_scheduler.LambdaLR(
        optimizer, lambda step: min((step + 1) / warmup, max(0.0, (total_steps - step) / max(1, total_steps - warmup)))
    )

    args.out.mkdir(parents=True, exist_ok=True)
    history, best, step = [], -1.0, 0
    started = time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        batches = length_batches(train_examples, args.batch_size, args.seed + epoch)
        running = 0.0
        for index, batch in enumerate(batches, 1):
            loss = model(**codec.batch(batch, device)).loss / args.grad_accum
            loss.backward()
            running += loss.detach().item() * args.grad_accum
            if index % args.grad_accum == 0 or index == len(batches):
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                schedule.step()
                optimizer.zero_grad()
                step += 1
                if step % args.empty_cache_every == 0:
                    release_cached_memory(device)
                if step % args.log_every == 0:
                    elapsed = time.time() - started
                    eta = elapsed / step * (total_steps - step)
                    print(f"epoch {epoch} step {step}/{total_steps} loss {running / index:.4f} "
                          f"lr {schedule.get_last_lr()[0]:.2e} elapsed {elapsed / 60:.1f}m eta {eta / 60:.1f}m", flush=True)
        release_cached_memory(device)
        val = evaluate(model, codec, val_pairs, directions, device, args.eval_batch_size, args.beams, args.val_translate)
        val["loss"] = validation_loss(model, codec, val_examples, device, args.eval_batch_size)
        val["epoch"] = epoch
        history.append(val)
        print(f"epoch {epoch} validation: {json.dumps(val)}", flush=True)
        if val["mean_chrf++"] > best:
            best = val["mean_chrf++"]
            model.save_pretrained(args.out)
            tokenizer.save_pretrained(args.out)
            print(f"saved best checkpoint to {args.out}", flush=True)

    train_minutes = round((time.time() - started) / 60, 1)
    del model, optimizer, schedule
    release_cached_memory(device)
    best_model = AutoModelForSeq2SeqLM.from_pretrained(args.out).to(device)
    # A quick trial (--limit) scores a sample of the test split; translating all of it takes about an hour on a Mac.
    test_translate = args.test_translate if args.test_translate is not None else (200 if args.limit else None)
    test_count = min(len(test_pairs), test_translate or len(test_pairs))
    print(f"translating {test_count:,} test pairs in {len(directions)} directions", flush=True)
    test = evaluate(best_model, codec, test_pairs, directions, device, args.eval_batch_size, args.beams, test_translate) if test_pairs else {}
    source_after = checkpoint_fingerprint(args.model)
    meta = {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base_model": args.model,
        "source_checkpoint": {**source_checkpoint, "unchanged_after_training": source_after == source_checkpoint},
        "language_token": language,
        "tokenizer_mapping": embeddings,
        "directions": directions,
        "device": str(device),
        "minutes": round((time.time() - started) / 60, 1),
        "train_minutes": train_minutes,
        **code,
        "data": {
            "dir": str(args.data),
            **data_check,
            "tiers": sorted(tiers),
            "train_pairs": len(train_pairs),
            "validation_pairs": len(val_pairs),
            "test_pairs": len(test_pairs),
            "test_translated": test_count,
        },
        "hyperparameters": {
            k: [str(p) for p in v] if k == "benchmark" else v
            for k, v in vars(args).items() if k not in {"func", "data", "out", "model"}
        },
        "validation_history": history,
        "test": test,
        "test_note": "Export test split: whole Bible books held out (Bible-style text only). Not a claim about everyday quality.",
    }
    (args.out / "train_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"test: {json.dumps(test)}")
    print(f"wrote {args.out / 'train_meta.json'}")
    return 0


def cmd_translate(args) -> int:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    device = pick_device(args.device)
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model).to(device)
    codec = Codec(tokenizer, args.max_len)
    items = read_jsonl(args.eval)
    system = args.system or args.model.name
    rows = []
    for direction in DIRECTIONS:
        chosen = [item for item in items if item.get("direction") == direction]
        if not chosen:
            continue
        src, tgt = DIRECTIONS[direction]
        hyps = translate_texts(model, codec, [item["source_text"] for item in chosen], src, tgt, device, args.batch_size, args.beams)
        rows += [{"id": item["id"], "hypothesis": hyp, "system": system} for item, hyp in zip(chosen, hyps)]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} translations to {args.out}")
    return 0


def cmd_try(args) -> int:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    device = pick_device(args.device)
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model).to(device)
    codec = Codec(tokenizer, args.max_len)
    src, tgt = DIRECTIONS[args.direction]
    print(f"{args.direction}: type a sentence and press Enter (empty line to quit)", flush=True)
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            break
        if not line:
            break
        print(translate_texts(model, codec, [line], src, tgt, device, 1, args.beams)[0], flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    train = commands.add_parser("train", help="fine-tune on an export directory")
    train.add_argument("--data", type=Path, required=True, help="export dir with train/validation/test.jsonl")
    train.add_argument("--out", type=Path, required=True, help="where to save the best checkpoint")
    train.add_argument("--model", default=DEFAULT_MODEL, help="base model id or local path")
    train.add_argument("--directions", default="en-zomi,zomi-en")
    train.add_argument("--tiers", default="gold,silver", help="comma list; empty for all")
    train.add_argument("--epochs", type=int, default=2)
    # 8 x 4 = 32 sentences per update. NLLB's 256k-word output layer makes larger batches
    # exceed a 24 GB Mac; lower --batch-size and raise --grad-accum if memory runs out.
    train.add_argument("--batch-size", type=int, default=8)
    train.add_argument("--grad-accum", type=int, default=4)
    train.add_argument("--lr", type=float, default=1e-4)
    train.add_argument("--optimizer", choices=("adafactor", "adamw"), default="adafactor",
                       help="adafactor fits in far less memory; adamw needs about 5 GB more for NLLB-600M")
    train.add_argument("--no-gradient-checkpointing", dest="gradient_checkpointing", action="store_false",
                       help="faster, but stores all activations (needs much more memory)")
    train.add_argument("--warmup", type=float, default=0.05, help="share of steps")
    train.add_argument("--max-len", type=int, default=128, help="tokens per sentence")
    train.add_argument("--pad-multiple", type=int, default=32,
                       help="round sentence lengths up to this many tokens (keeps Apple GPU memory stable)")
    train.add_argument("--empty-cache-every", type=int, default=50, help="release cached GPU memory every N updates")
    train.add_argument("--val-size", type=int, default=2000, help="validation pairs used for loss")
    train.add_argument("--val-translate", type=int, default=300, help="validation pairs translated for chrF++ each epoch")
    train.add_argument("--test-translate", type=int, help="test pairs translated at the end (default: all; 200 with --limit)")
    train.add_argument("--eval-batch-size", type=int, default=16)
    train.add_argument("--beams", type=int, default=4)
    train.add_argument("--limit", type=int, help="use only N training pairs (quick trial)")
    train.add_argument("--log-every", type=int, default=50)
    train.add_argument("--seed", type=int, default=13)
    train.add_argument("--device", default="auto", help="auto, mps, cuda, or cpu")
    train.add_argument("--allow-uncleared-data", action="store_true",
                       help="accept an export that includes needs_review sources (internal experiments only)")
    train.add_argument("--benchmark", type=Path, action="append",
                       help="benchmark file that must not overlap train/validation; repeatable (default: "
                            "data/evaluation/translation/sample.jsonl and every human evaluation file)")
    train.set_defaults(func=cmd_train)

    translate = commands.add_parser("translate", help="translate a human evaluation set")
    translate.add_argument("--model", type=Path, required=True)
    translate.add_argument("--eval", type=Path, required=True)
    translate.add_argument("--out", type=Path, required=True)
    translate.add_argument("--system", help="name used in mt_eval results (default: model dir name)")
    translate.add_argument("--batch-size", type=int, default=32)
    translate.add_argument("--beams", type=int, default=4)
    translate.add_argument("--max-len", type=int, default=128)
    translate.add_argument("--device", default="auto")
    translate.set_defaults(func=cmd_translate)

    try_ = commands.add_parser("try", help="type sentences and see the translation")
    try_.add_argument("--model", type=Path, required=True)
    try_.add_argument("--direction", choices=sorted(DIRECTIONS), default="en-zomi")
    try_.add_argument("--beams", type=int, default=4)
    try_.add_argument("--max-len", type=int, default=128)
    try_.add_argument("--device", default="auto")
    try_.set_defaults(func=cmd_try)

    args = parser.parse_args(argv)
    if args.command == "train" and args.benchmark is None:
        from build_language_db import EVAL_TRANSLATION, default_eval_paths

        args.benchmark = [path for path in (EVAL_TRANSLATION, *default_eval_paths()) if path.exists()]
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
