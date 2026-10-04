# Siamsil phase roadmap

Updated: 2026-10-01

This is the phase-level view: what each phase delivers, what must be true before the next one starts, and how phases map to the releases in [`PRODUCTION_MASTER_BUILD_PROMPT.md`](PRODUCTION_MASTER_BUILD_PROMPT.md). Item-level status lives in [`IMPLEMENTATION_ROADMAP.md`](IMPLEMENTATION_ROADMAP.md); do not duplicate checklists here.

```text
Phase 0  Data rights · human evaluation sets · start audio collection
Phase 1  Data pipeline (dedup → language ID → alignment → scoring → domains → splits)
Phase 2  Baselines → fine-tune → human evaluation gate
Phase 3  /v1 translation API with model metadata, keys, limits, privacy-safe logging
Phase 4  Products: translate + correction loop → dictionary → learn → mobile
Phase 5  Developer platform (after licensing is settled)
Phase 6  Speech · OCR · document translation · Siamsil Chat · Siamsil Intelligence
```

Phases are gates, not a strict waterfall. Phase 0 work (rights, evaluation, audio) runs continuously alongside everything after it.

## The constraint that shapes everything

The 1,775,043 retained parallel pairs are Tatoeba/OPUS English with **machine-generated Zomi** (Gemini models; see [`AUDIT.md`](AUDIT.md)). Zero pairs are human-verified. Three consequences:

1. A model trained only on this corpus learns to imitate Gemini's Zomi, including its errors. It cannot exceed that ceiling.
2. The corpus test split is also Gemini output. BLEU/chrF on it measures agreement with Gemini, not correctness. It is a regression check, never a quality claim.
3. Training and redistribution rights for both the Tatoeba source and the generated output are `needs_review`. This blocks any commercial use in Phase 5 until resolved.

Human-made or human-reviewed sources already in the repository — the Bible (30,734 verses), the dictionary (20,826 entries), and the teacher-reviewed daily-use phrases (62 pairs) — are the only non-generated bilingual signal today and must be tracked as separate, higher-trust sources.

## Phase 0 — Foundations (new; runs first and continuously)

Deliverables:

- License chain documented for the dictionary, Bible translation, Tatoeba/OPUS, and generated Zomi, including whether the generator's terms permit training and commercial redistribution.
- Translation and review guidelines (spelling, dialect, borrowing, names, punctuation).
- Hidden, human-translated evaluation sets in both directions, ~1–2k sentences each, balanced across conversation, education, government, health, religion, and news. Stored under `data/evaluation/`, never used for training, prompting, or filter tuning.
- Consent-based audio collection started (scripture reading, hymns, everyday phrases), because speech data has the longest lead time.
- Language code policy: use ISO 639-3 / BCP 47 identifiers in data and APIs; display "Zomi" in the UI.

Exit gate: evaluation sets frozen with measured reviewer agreement; license status for each source is either cleared or explicitly restricted.

Working documents: [`DATA_RIGHTS.md`](DATA_RIGHTS.md) (rights register and language-code decision) [`EVALUATION_SET.md`](EVALUATION_SET.md) (evaluation-set process, format, and `eval_set.py` tooling), and [`AUDIO_CONSENT.md`](AUDIO_CONSENT.md) (draft recording consent form and records).

Checklist: *Translation-model program → Data and evaluation*; *Language data foundation → Needed* (licensing).

## Phase 1 — Data

Builds on the existing pipeline (`ml_pipeline/scripts/build_language_db.py`), which already does exact deduplication, normalization, basic quality flags, and a deterministic split keyed on English families.

Add:

- **Near-duplicate removal** — Tatoeba contains many template variants that differ only by a name or tense. *Started:* template variants (names and numbers) are grouped and split together; tense and fuzzy variants are not yet.
- **Zomi language identification** — likely in-house: dictionary-coverage scoring plus a small classifier trained on Bible and dictionary text.
- **Alignment checks** — length ratio, numbers, named entities, punctuation, truncation, repeated batches. *Started:* numbers, length ratio, and reused Zomi output are flagged.
- **Source and generator scoring** — record which model produced each Zomi side; human spot-check ~200 pairs per generator to estimate relative quality.
- **Domain labels** and **gold / silver / bronze tiers**: gold = human-reviewed or human-authored; silver = best-scoring generated; bronze = everything else retained.
- Named, checksummed dataset releases under `data/versions/`.

Exit gate: a versioned dataset release with tier counts, a quality report, and documented split isolation from Phase 0 evaluation sets.

Checklist: *Language data foundation → Needed*.

## Phase 2 — Model

- Baselines first: translation-memory retrieval (what ships today), an untuned hosted LLM, and a fine-tuned pretrained multilingual seq2seq model.
- **Base-model license must permit the intended use.** Some widely used translation models (e.g. NLLB-200) are non-commercial; that is incompatible with Phase 5 billing.
- Measure tokenizer coverage of Zomi before choosing a base.
- Train gold-weighted, then gold + silver experiments; record dataset, code, seed, and hyperparameters per run.
- Human evaluation is a recurring gate: a reviewer panel scores a fixed blinded sample for every candidate, not a one-time step at the end.

Exit gate: a candidate beats retrieval and the untuned LLM on the Phase 0 human evaluation sets and passes the safety/robustness suites. Until then, production stays retrieval-only and generated Zomi is not shown as a translation.

Checklist: *Translation-model program → Training*, *Evaluation and production*.

## Phase 3 — API

`/api/v1` already exists. For model-backed translation, add:

- A separate inference service with batching, timeouts, and translation-memory-first routing.
- Every translation response carries `model_version`, dataset release, `verified`, and source labels.
- Authentication (existing OIDC identity for first-party clients; API keys come in Phase 5), rate limits, and request IDs.
- **Privacy-safe logging**: do not store submitted text by default. Retain text for training only with explicit opt-in consent.
- Model registry with canary rollout and instant rollback.
- Remove the unversioned `/api` aliases.

Exit gate: a model can be promoted, canaried, and rolled back without a client release.

## Phase 4 — Products

Order matters:

1. **translate** — first, with a visible **"suggest a better translation"** action feeding the editorial review queue. Native-speaker corrections are the data that cannot be bought; this loop should go live as early as possible.
2. **dictionary** — already live on the 20k index; improve through the reviewed dictionary workflow.
3. **learn** — Release 2 scope.
4. **mobile app** — Release 5 scope, offline dictionary first.

Exit gate per product: privacy policy, dataset disclosures, and machine-translation labeling are in place.

Checklist: *Existing web product*, *Editorial and translation-review system*, *Learning and citizenship*, *Mobile application*.

## Phase 5 — Developer platform

API keys, SDKs, usage dashboard, and billing come after:

- licensing allows commercial redistribution of model output, and
- a data-governance policy states who owns community corrections and how contributors are credited.

The paying market for a Zomi API is small; community trust is worth more than early revenue. Free, rate-limited keys for community and education partners can precede billing.

## Phase 6 — Speech, OCR, and intelligence

- **Speech** — depends on audio collected since Phase 0 under explicit consent.
- **OCR** — consider moving earlier: digitizing hymnals and printed Zomi material yields new human-authored text for Phase 1.
- **Document translation, multimodal, Siamsil Chat, Siamsil Intelligence** — only after text translation passes Phase 2 gates; generated Zomi stays labeled.

## Mapping to releases

| Release (master prompt) | Phases |
|---|---|
| Release 1 — Language MVP | Phase 0, Phase 1, retrieval-only Phase 3, translate + dictionary from Phase 4 |
| Release 2 — Learning | learn from Phase 4 |
| Release 3 — Community | correction loop moderation; community per *Community and chat* checklist |
| Release 4 — Intelligence | Phase 2 model in production, Phase 6 |
| Release 5 — Native iOS / Android | mobile app from Phase 4 |

The Phase 5 developer platform is not in the master prompt's release list; schedule it only after its licensing and governance gates are met.
