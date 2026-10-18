#!/usr/bin/env python3
"""Fine-tune a pretrained translation model on Siamsil's exported pairs.

The default base model is NLLB-200 distilled 600M (CC BY-NC 4.0; acceptable
because Siamsil is non-profit, see docs/DATA_RIGHTS.md). NLLB has no Zomi
language code, so training adds `zom_Latn` and starts it from Mizo
(`lus_Latn`), a closely related Kuki-Chin language that NLLB covers.

Commands:
  train --data DIR --out DIR [--model ID] [--epochs N] ...
      DIR is an export from export_datasets.py (train/validation/test.jsonl).
      Trains English<->Zomi in both directions, keeps the checkpoint with the
      best validation chrF++, then scores the test split.
  translate --model DIR --eval FILE --out HYP.jsonl [--system NAME]
      Translate a human evaluation set (docs/EVALUATION_SET.md format); score
      the output with `mt_eval.py score`.

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
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_MODEL = "facebook/nllb-200-distilled-600M"
LANG = {"en": "eng_Latn", "zom": "zom_Latn"}
INIT_FROM = "lus_Latn"  # Mizo
DIRECTIONS = {"en-zomi": ("en", "zom"), "zomi-en": ("zom", "en")}
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
        text = {"en": pair["english"], "zom": pair["zomi"]}
        for direction in directions:
            src, tgt = DIRECTIONS[direction]
            out.append((text[src], src, text[tgt], tgt))
    return out


def add_zomi(tokenizer, model) -> dict:
    """Add the zom_Latn language token, initialised from Mizo when the base model has it."""
    code = LANG["zom"]
    vocab = tokenizer.get_vocab()
    if code in vocab:
        return {"added": False}
    tokenizer.add_tokens([code], special_tokens=True)
    model.resize_token_embeddings(len(tokenizer))
    new_id = tokenizer.convert_tokens_to_ids(code)
    init = INIT_FROM if INIT_FROM in vocab else LANG["en"]
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
        self.lang_id = {key: tokenizer.convert_tokens_to_ids(code) for key, code in LANG.items()}

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
                max_new_tokens=codec.max_len,
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
        key = {"en": "english", "zom": "zomi"}
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


def cmd_train(args) -> int:
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

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

    del model, optimizer, schedule
    release_cached_memory(device)
    best_model = AutoModelForSeq2SeqLM.from_pretrained(args.out).to(device)
    test = evaluate(best_model, codec, test_pairs, directions, device, args.eval_batch_size, args.beams) if test_pairs else {}
    meta = {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base_model": args.model,
        "language_token": language,
        "directions": directions,
        "device": str(device),
        "minutes": round((time.time() - started) / 60, 1),
        "git_commit": git_commit(),
        "data": {
            "dir": str(args.data),
            "export_manifest_sha256": file_sha256(args.data / "manifest.json"),
            "tiers": sorted(tiers),
            "train_pairs": len(train_pairs),
            "validation_pairs": len(val_pairs),
            "test_pairs": len(test_pairs),
        },
        "hyperparameters": {k: v for k, v in vars(args).items() if k not in {"func", "data", "out", "model"}},
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
    train.add_argument("--eval-batch-size", type=int, default=16)
    train.add_argument("--beams", type=int, default=4)
    train.add_argument("--limit", type=int, help="use only N training pairs (quick trial)")
    train.add_argument("--log-every", type=int, default=50)
    train.add_argument("--seed", type=int, default=13)
    train.add_argument("--device", default="auto", help="auto, mps, cuda, or cpu")
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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
