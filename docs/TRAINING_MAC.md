# Training the Zomi translator on a Mac

Updated: 2026-10-17
Phase: [ROADMAP.md](ROADMAP.md) Phase 2

`ml_pipeline/scripts/train_mt.py` fine-tunes NLLB-200 distilled 600M on the pairs that `export_datasets.py` clears for training. NLLB has no Zomi code, so the script adds `zom_Latn` and starts it from Mizo (`lus_Latn`), a close Kuki-Chin relative. NLLB weights are CC BY-NC 4.0; Siamsil may use them because it is non-profit ([DATA_RIGHTS.md](DATA_RIGHTS.md)).

Tested target: Apple Silicon (M-series) with 16 GB or more. The script uses the Mac's GPU (MPS) automatically.

## 1. Set up once

```bash
# Python 3.11 or newer (python.org installer or Homebrew)
cd siamsil
python3 -m venv .venv
source .venv/bin/activate
pip install -r ml_pipeline/requirements.txt -r ml_pipeline/requirements-train.txt
export PYTORCH_ENABLE_MPS_FALLBACK=1   # add to ~/.zshrc to keep it
```

Free disk space needed: about 15 GB (language database, model download, checkpoints).

## 2. Prepare the data

Raw files come from the private `siamsil-data` repository. Never edit them; the scripts only read them.

```bash
# Dictionary and corpus, as data/raw expects them
#   data/raw/dictionary/Zomi_Standard_Dictionary_AI_Cleaned.xlsx  (copy of dictionary/Zomi_Dictionary_Master_Data.xlsx)
#   data/raw/parallel/zomi_english_sentences.csv
python3 ml_pipeline/scripts/build_language_db.py                     # about 5 minutes

# Bibles: unzip Chin-Bible.zip and engwebu_usfm.zip under data/raw/bible/usx/
#   data/raw/bible/usx/chin/...   data/raw/bible/usx/web/...
python3 ml_pipeline/scripts/import_usx_bibles.py

# Training files: only sources cleared in data/rights.json are exported
python3 ml_pipeline/scripts/export_datasets.py \
  --bible-versions data/processed/bible/bible_versions.sqlite \
  --out data/datasets/bible-v1
```

Expected with today's rights: about 117,000 training, 1,000 validation and 3,500 test pairs, all from the Zomi Bibles paired with the King James and World English Bibles. Test and validation are whole books (test: Ruth, Mark, 1 John), so no verse is in both training and test.

## 3. Quick trial (about 10 minutes)

The first run downloads the base model (about 2.5 GB).

```bash
python3 ml_pipeline/scripts/train_mt.py train \
  --data data/datasets/bible-v1 --out models/trial \
  --limit 2000 --epochs 1 --val-translate 50
```

Check that it prints steps with a falling `loss` and an `eta`. The ETA tells you how long the full run will take. At the end it translates 200 test pairs in each direction, which takes a few minutes. The full run translates all 3,462. Stop it any time with Ctrl-C.

## 4. Full training run

```bash
caffeinate -i python3 ml_pipeline/scripts/train_mt.py train \
  --data data/datasets/bible-v1 --out models/nllb-zomi-bible-v1 --epochs 2
```

`caffeinate -i` keeps the Mac awake. Keep it plugged in. A run takes hours; overnight is normal.

The defaults (Adafactor optimizer, gradient checkpointing, `--batch-size 8 --grad-accum 4`, 32 sentences per update) need about 8 GB for one training step (measured on CPU with NLLB-600M's architecture; the Mac GPU adds some overhead) and fit a 24 GB M5. AdamW (`--optimizer adamw`) needs about 5 GB more. If it runs out of memory, close other apps, then halve the batch and double the accumulation (same effective batch):

```bash
  --batch-size 4 --grad-accum 8
```

The Mac GPU keeps a compiled graph for every batch shape it sees, so sentence lengths are rounded up to steps of 32 tokens (`--pad-multiple`) and the GPU cache is emptied every 50 updates (`--empty-cache-every`). Without these, "other allocations" in an out-of-memory error keeps growing until the run stops.

## 5. Try it

Type sentences and read the translation (empty line to quit):

```bash
python3 ml_pipeline/scripts/train_mt.py try --model models/nllb-zomi-bible-v1
python3 ml_pipeline/scripts/train_mt.py try --model models/nllb-zomi-bible-v1 --direction zomi-en
```

Try Bible-like and everyday sentences. A model trained only on Bible pairs is expected to sound formal and to struggle with modern topics.

## 6. Read the results

`models/nllb-zomi-bible-v1/train_meta.json` records the base model, data manifest checksum, settings, validation scores per epoch, and the test scores (chrF++ and BLEU, both directions).

The test split is Bible text only. It shows whether training worked; it does not show how well the model translates everyday Zomi. That needs the human evaluation set ([EVALUATION_SET.md](EVALUATION_SET.md)):

```bash
python3 ml_pipeline/scripts/train_mt.py translate \
  --model models/nllb-zomi-bible-v1 --eval data/evaluation/human/en-zomi-v1.jsonl \
  --out data/exports/hyp-nllb-zomi-bible-v1.jsonl --system nllb-zomi-bible-v1
python3 ml_pipeline/scripts/mt_eval.py translate --system retrieval \
  --eval data/evaluation/human/en-zomi-v1.jsonl --db data/processed/language/siamsil_language.sqlite \
  --out data/exports/hyp-retrieval.jsonl
python3 ml_pipeline/scripts/mt_eval.py score --eval data/evaluation/human/en-zomi-v1.jsonl \
  --hyp data/exports/hyp-retrieval.jsonl --hyp data/exports/hyp-nllb-zomi-bible-v1.jsonl \
  --out data/exports/results-en-zomi.json
python3 ml_pipeline/scripts/mt_eval.py gate --results data/exports/results-en-zomi.json \
  --candidate nllb-zomi-bible-v1 --baseline retrieval
```

A model reaches the app only after it passes the gate and a Zomi speaker approves a sample of its output ([MODEL_EVALUATION.md](MODEL_EVALUATION.md)).

## Keep out of git

Model checkpoints (`models/`), exports (`data/datasets/`, `data/exports/`) and evaluation sets are gitignored. Store checkpoints you want to keep in private storage, and record which checkpoint is in use with its `train_meta.json`.
