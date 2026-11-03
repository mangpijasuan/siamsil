#!/usr/bin/env python3
"""Convert a trained translation model for serving, and record whether it may be served.

From the repository root:

    python3 ml_pipeline/scripts/export_mt_serving.py --model models/nllb-zomi-bible-v1 \
        --out models/nllb-zomi-bible-v1-serving [--data data/datasets/bible-v1]

Writes a CTranslate2 int8 model (about a quarter of the size, runs on an ordinary CPU,
no PyTorch needed), its tokenizer, and serving.json. serving.json lists every source
in the training and validation data with its current `train` status in data/rights.json;
`cleared_for_serving` is true only when all of them are `cleared`. The backend refuses to
serve a model that is not cleared outside development (docs/ROADMAP.md, Phase 2 decision).

The training data folder comes from the model's train_meta.json unless --data is given;
its manifest must still match the checksum recorded at training time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOKENIZER_FILES = ("tokenizer.json", "tokenizer_config.json")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def training_sources(data: Path) -> Counter[str]:
    """Rows per source in the data the model learned from (train and validation)."""
    counts: Counter[str] = Counter()
    for split in ("train", "validation"):
        with (data / f"{split}.jsonl").open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    row = json.loads(line)
                    for source in {row.get("source"), row.get("english_source")} - {None}:
                        counts[source] += 1
    return counts


def serving_record(model: Path, data: Path, rights_path: Path, name: str) -> dict:
    meta = json.loads((model / "train_meta.json").read_text(encoding="utf-8"))
    manifest = data / "manifest.json"
    recorded = meta.get("data", {}).get("export_manifest_sha256")
    if recorded and file_sha256(manifest) != recorded:
        sys.exit(f"{manifest} changed since training (sha256 differs from train_meta.json); use the exact training data")
    rights = json.loads(rights_path.read_text(encoding="utf-8"))["sources"]
    sources = training_sources(data)
    statuses = {source: rights.get(source, {}).get("train", "unknown") for source in sorted(sources)}
    uncleared = sorted(s for s, status in statuses.items() if status != "cleared")
    return {
        "name": name,
        "version": meta["trained_at"],
        "base_model": meta.get("base_model"),
        "trained_at": meta["trained_at"],
        "git_commit": meta.get("git_commit"),
        "language_token": meta.get("tokenizer_mapping", {}).get("tokens") or meta.get("language_token"),
        "training_data": {
            "dir": str(data),
            "manifest_sha256": file_sha256(manifest),
            "rows_by_source": dict(sorted(sources.items())),
            "train_rights": statuses,
        },
        "uncleared_sources": uncleared,
        "cleared_for_serving": not uncleared,
        "test": meta.get("test"),
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, required=True, help="trained model folder (with train_meta.json)")
    parser.add_argument("--out", type=Path, required=True, help="new folder for the serving copy")
    parser.add_argument("--data", type=Path, help="training data folder (default: from train_meta.json)")
    parser.add_argument("--rights", type=Path, default=ROOT / "data" / "rights.json")
    parser.add_argument("--name", help="model name shown in API responses (default: the model folder name)")
    args = parser.parse_args()

    if args.out.exists() and any(args.out.iterdir()):
        sys.exit(f"{args.out} already has files; choose a new folder")
    meta = json.loads((args.model / "train_meta.json").read_text(encoding="utf-8"))
    # train_meta.json records the folder relative to where training ran: the repository root.
    data = (args.data or Path(meta["data"]["dir"])).resolve()
    record = serving_record(args.model, data, args.rights, args.name or args.model.name)

    import ctranslate2

    ctranslate2.converters.TransformersConverter(str(args.model), copy_files=list(TOKENIZER_FILES)).convert(
        str(args.out), quantization="int8"
    )
    record["weights_sha256"] = file_sha256(args.out / "model.bin")
    (args.out / "serving.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    if record["cleared_for_serving"]:
        print("cleared for serving: every training source is cleared for training")
    else:
        print(f"NOT cleared for serving; uncleared training sources: {', '.join(record['uncleared_sources'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
