# Building Siamsil's own translation model (step-by-step plan)

Status: **plan.** The pipeline exists for a Bible-only model (`nllb-zomi-bible-v1`). This plan says what is needed to make a model good enough for everyday Zomi and legal for Pro. It builds on [TRAINING_MAC.md](TRAINING_MAC.md), [MODEL_EVALUATION.md](MODEL_EVALUATION.md), [EXPERIMENTAL_TRANSLATION.md](EXPERIMENTAL_TRANSLATION.md) and [DATA_RIGHTS.md](DATA_RIGHTS.md). Nothing here is run or approved.

## What exists today

| Piece | Script or doc | Status |
|---|---|---|
| Export cleared pairs | `ml_pipeline/scripts/export_datasets.py` | Built. Exports only sources whose `train` right is `cleared`. |
| Fine-tune | `ml_pipeline/scripts/train_mt.py train` | Built. Refuses uncleared data without an explicit flag. Records hashes, rights and settings in `train_meta.json`. |
| Score on human sets | `ml_pipeline/scripts/mt_eval.py` (`translate`, `score`, `gate`) | Built. chrF++ with confidence intervals and an automatic gate. |
| Export for serving | `ml_pipeline/scripts/export_mt_serving.py` | Built. CTranslate2 int8, runs on an ordinary CPU. |
| Serve | `SIAMSIL_EXPERIMENTAL_MT_DIR` | Built. Refuses uncleared models outside development. |
| Human evaluation sets | [EVALUATION_SET.md](EVALUATION_SET.md) | **Not yet written.** This is the main gap. |

## Blockers for a Pro model

1. **Base model license.** `train_mt.py` defaults to NLLB-200 (CC BY-NC 4.0). That is acceptable for the free non-profit app and **not** for Pro. A Pro model needs a base whose license allows commercial use. Candidates to check (not yet checked): MADLAD-400 (Apache 2.0 per its model card), Gemma (its own terms), Qwen (varies by size). For each: license text, commercial terms, and whether it handles Tedim Zomi or a close language to start from.
2. **Commercial clearance of every training source.** `commercial` is `not_permitted` or `needs_review` for the Bible versions, worship songs, the parallel corpus, the 50K and the dictionaries. Today no everyday source is commercial-cleared.
3. **Everyday data.** Cleared data today is Bible and songs. A Bible-only model sounds formal and fails on modern topics.
4. **Evaluation set.** No hidden human set exists yet.
5. **Provider outputs.** Do not train on text an AI provider generated, unless its current terms explicitly allow it.

## Plan, in order

### Step 1: Decide the model line

- **Free model (non-commercial):** can keep NLLB-200, trained on sources cleared for training. Served only in the free app.
- **Pro model (commercial):** needs a commercial base model and commercial-cleared data. It is a separate model with its own model card.

### Step 2: Build the evaluation sets first

1. Write translation guidelines with native-speaker editors (EVALUATION_SET.md).
2. Translate, review and adjudicate 1,000 to 2,000 sentences per direction.
3. Run `eval_set.py leakage` and freeze the sets only at zero overlap with the corpus.
4. Keep them out of training, prompts and caches.

### Step 3: Collect cleared everyday data

Order of value:

1. Owner and reviewer corrections of corpus pairs (`review_sample.py`, `corpus_revisions.py`), approved by a lead editor.
2. Daily-use phrases reviewed by teachers.
3. New sentences written by native speakers, with consent recorded.
4. Sources where the holder gives written permission, recorded in DATA_RIGHTS.md and confirmed by a second person.

Do not count the 1.77M machine pairs as training data until they are reviewed and cleared. The 50K stays out until its sources are identified.

### Step 4: Export

```bash
python3 ml_pipeline/scripts/export_datasets.py --out data/datasets/<name>
```

Check the manifest's `uncleared_sources_included` is empty. For Pro, also check every included source is commercial-cleared.

### Step 5: Quick trial, then full run

```bash
python3 ml_pipeline/scripts/train_mt.py train --data data/datasets/<name> --out models/trial --limit 2000 --epochs 1 --val-translate 50
python3 ml_pipeline/scripts/train_mt.py train --data data/datasets/<name> --out models/<model-name> --epochs 2
```

Run on your workstation, a rented GPU or Colab. Training data from `siamsil-data` must not leave machines you control without scoped rights and consent.

### Step 6: Score against baselines

```bash
python3 ml_pipeline/scripts/mt_eval.py translate --model models/<model-name> ... 
python3 ml_pipeline/scripts/mt_eval.py score ...
python3 ml_pipeline/scripts/mt_eval.py gate ... --baseline retrieval --baseline hosted-llm
```

The model must beat retrieval and the hosted-provider baseline on chrF++ in both directions, then pass blinded review by Zomi reviewers.

### Step 7: Export, serve, label

```bash
python3 ml_pipeline/scripts/export_mt_serving.py --model models/<model-name> --out models/<model-name>-serving
```

Serve behind the Pro API, labelled as machine translation until reviewers approve. Keep the model card (base model and license, every data source with its rights, training date, scores) with the model.

### Step 8: Keep improving

Corrections from reviewers feed the next training round, with a new version, a new evaluation run and an updated model card each time.

## Checklist before any Pro use

- [ ] Base model license reviewed in writing, commercial use confirmed
- [ ] Every training source commercial-cleared, second person confirmed
- [ ] `uncleared_sources_included` is empty in the export manifest
- [ ] Evaluation sets frozen with zero leakage
- [ ] Automatic gate passed in both directions
- [ ] Reviewer rating completed
- [ ] Model card written
- [ ] Owner's signed Pro decision recorded (see [PRO_PLAN.md](PRO_PLAN.md))
