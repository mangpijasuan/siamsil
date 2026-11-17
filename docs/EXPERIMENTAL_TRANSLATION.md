# Experimental machine translation

An opt-in mode on the Translate page, allowed by the project owner's decision of 2026-10-28 ([ROADMAP.md](ROADMAP.md), Phase 2). Retrieval stays the default; the model's output is always labelled experimental and is never presented as a verified translation.

## Export a model for serving

From the repository root, after training with `train_mt.py`:

```bash
python3 ml_pipeline/scripts/export_mt_serving.py --model models/nllb-zomi-bible-v1 --out models/nllb-zomi-bible-v1-serving
```

This writes a CTranslate2 int8 copy (about 630 MB instead of 2.4 GB; runs on an ordinary CPU in roughly 100–350 ms a sentence, without PyTorch), its tokenizer, and `serving.json`. `serving.json` lists every source in the training and validation data with its current `train` status in `data/rights.json`; `cleared_for_serving` is true only when all are `cleared`. The training data must still match the manifest checksum recorded at training time.

Quality is unchanged by the conversion: on 200 test sentences per direction the int8 copy scored within half a chrF++ point of the original.

## Serve it

Set `SIAMSIL_EXPERIMENTAL_MT_DIR` to the exported folder. The backend loads it on first use and offers:

- `GET /api/v1/translate/experimental`: whether the mode is available, and which model.
- `POST /api/v1/translate/experimental` with `{"text": ..., "direction": "en-ctd" | "ctd-en"}`: the translation, labelled experimental, with the model's name and version. Up to 500 characters.

Outside development the backend refuses a model whose `serving.json` is not cleared, and says which sources are not cleared. `SIAMSIL_EXPERIMENTAL_MT_ALLOW_UNCLEARED=true` lets a developer try such a model locally; settings reject it in staging and production.

Models trained before Zomi was labelled `ctd` use the language token `zom_Latn`; they are served unchanged.

## Status (2026-10-28)

| Model | Cleared for serving |
|---|---|
| `nllb-zomi-bible-v1` | Yes: TB77, TDB, KJV and WEB are cleared for training. Bible-style output only. |
| everyday pilot (`nllb-zomi-everyday-v2-exp`) | No: the Essential 3000, the 50K Master and the parallel corpus are still `needs_review`. Development only. |

## Try hosted generation locally

A local development server can use an OpenAI model to generate new translations in both directions. Set `SIAMSIL_EXPERIMENTAL_MT_OPENAI_API_KEY` and `SIAMSIL_EXPERIMENTAL_MT_OPENAI_MODEL` in your local, untracked `.env`. Use a model or snapshot enabled in your API project. Leave `SIAMSIL_EXPERIMENTAL_MT_DIR` unset and restart the API.

Open the Translate page, enter text, submit it to the page, then select **Generate translation (experimental)**. Only the submitted text and translation instructions go to the provider. The hosted path does not use the dictionary, corpus, Bible, or model training system. The default retrieval endpoint still serves stored matches.

Before proposing production use, compare meaning, naturalness, dialect, omissions, and additions in both directions with Tedim-speaking reviewers. Also check latency and the failure rate. Use evaluation inputs authorized for provider processing, and keep protected sets and reviewer corrections out of provider requests unless separately approved. The hosted pilot is development-only while production authorization and usage controls are pending.

Hosted translations, and any reviewer corrections made to them, are provider-derived. They are excluded from Siamsil's own model training unless the provider's current terms explicitly allow it, and the pilot never saves them to the corpus, the dictionary or any dataset.
