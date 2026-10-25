# Human evaluation sets

Updated: 2026-10-25
Phase: [ROADMAP.md](ROADMAP.md) Phase 0

The evaluation sets are the only trustworthy measure of Siamsil translation quality. The parallel corpus test split is machine-generated Zomi and measures agreement with Gemini, not correctness. Every model and retrieval change in Phase 2 is judged against these sets.

## What we build

Two hidden sets, one per direction:

| Set | Source text | Reference | Target size |
|---|---|---|---:|
| `en-zomi` | Original English | Human Zomi translation | 1,000–2,000 |
| `zomi-en` | Original Zomi, written by native speakers | Human English translation | 1,000–2,000 |

The Zomi→English set must start from text originally written in Zomi. Translating the English set backwards produces translated-sounding Zomi, which is not what users will type.

### Domains

Balance each set across these domains, roughly equal shares:

`conversation`, `education`, `government`, `health`, `religion`, `news`, `informal`

Within each domain, mix short (1–8 words), medium, and long (25+ words) items, and include names, numbers, dates, and questions.

### Where source sentences come from

- Not from Tatoeba, OPUS, the Siamsil parallel corpus, the Bible file, the dictionary, or the daily-use phrases. These are, or may become, training data.
- English sources: written fresh by contributors, or taken from material whose license permits it. Record the origin of every item.
- Zomi sources: written fresh by native speakers, or taken with permission from Zomi publications.
- `eval_set.py leakage` (below) must report zero overlaps with the corpus before a set is frozen.

## People and process

1. **Guidelines first.** Native-speaker editors publish translation guidelines before any translation starts: spelling standard, dialect, loanwords, names, punctuation, and how to handle ambiguity. These are language decisions; engineers do not make them.
2. **Translate.** One translator per item.
3. **Review.** A second, independent person reviews each item and either accepts it or proposes a correction.
4. **Adjudicate.** A third person resolves disagreements. Record the outcome.
5. **Measure agreement.** Report the share of items reviewers accepted without change, per domain. Low agreement in a domain means the guidelines need work there.
6. **Freeze.** Run validation and leakage checks, write the manifest, and treat the set as read-only. Corrections produce a new version; never edit a frozen file.

Translators and reviewers are credited by their chosen name and paid or formally acknowledged; record their consent to the use described in [DATA_RIGHTS.md](DATA_RIGHTS.md).

## Keeping the sets hidden

- The JSONL files are excluded from git (`data/evaluation/**/*.jsonl` in `.gitignore`). Store them in restricted storage; commit only the manifest (counts and SHA-256).
- Never use them for training, prompt examples, few-shot demonstrations, filter tuning, or dataset debugging.
- Dataset builds exclude any training pair whose normalized English or Zomi matches an evaluation item, including English template variants (numbers masked). `build_language_db.py` moves such pairs to the `eval_holdout` split and `export_datasets.py` never writes them. Both use **every file in `data/evaluation/human/`** automatically (finished sets, drafts, and English source lists), so the exclusion cannot be forgotten; `--eval` overrides the list.
- Protection starts when the English is written: save the source sentences as `data/evaluation/human/<set>-v<N>.sources.csv` (columns `id`, `domain`, `english`) before translation begins. That folder is not committed.
- Anyone who has read the evaluation items should not hand-tune the training data filters.

## File format

One JSON object per line, UTF-8, in `data/evaluation/human/<set>-v<N>.jsonl`:

```json
{
  "id": "en-zomi-0001",
  "direction": "en-zomi",
  "domain": "health",
  "source_text": "<original sentence>",
  "references": ["<adjudicated human translation>"],
  "source_origin": "written by contributor T01",
  "translator": "T01",
  "reviewer": "R02",
  "adjudicator": null,
  "review_outcome": "accepted",
  "notes": ""
}
```

| Field | Rule |
|---|---|
| `id` | Unique within the file |
| `direction` | `en-zomi` or `zomi-en`; must match the file's set |
| `domain` | One of the domains above |
| `source_text` | Non-empty |
| `references` | At least one non-empty human translation |
| `source_origin` | Non-empty; where the source sentence came from |
| `translator`, `reviewer` | Contributor IDs; must differ |
| `adjudicator` | Required when `review_outcome` is `adjudicated`; must differ from both |
| `review_outcome` | `accepted`, `corrected`, or `adjudicated` |
| `notes` | Optional |

Contributor IDs map to names in a separate, access-controlled roster, not in the evaluation file.

## Tooling

`ml_pipeline/scripts/eval_set.py`:

```bash
# Check schema, unique IDs, independent review, domain coverage
python3 ml_pipeline/scripts/eval_set.py validate data/evaluation/human/en-zomi-v1.jsonl

# Report items that also appear in the parallel corpus (must be zero to freeze)
python3 ml_pipeline/scripts/eval_set.py leakage data/evaluation/human/en-zomi-v1.jsonl \
  --corpus data/raw/parallel/zomi_english_sentences.csv

# Write the committed manifest: counts by domain and outcome, SHA-256
python3 ml_pipeline/scripts/eval_set.py manifest data/evaluation/human/en-zomi-v1.jsonl
```

Before translation, check the English sources against the corpus and the English Bibles. Replace every sentence it reports (exact copies and number variants):

```bash
python3 ml_pipeline/scripts/eval_set.py check-sources data/evaluation/human/en-zomi-v1.sources.csv \
  --database data/processed/language/siamsil_language.sqlite \
  --bible-versions data/processed/bible/bible_versions.sqlite
```

Translators and reviewers work in Excel. `ml_pipeline/scripts/worksheets.py` moves their sheets in and out:

```bash
# Translator's sheet from the checked sources list
python3 ml_pipeline/scripts/worksheets.py testset-sheet data/evaluation/human/en-zomi-v1.sources.csv \
  --out Siamsil_TestSet_en-zomi_batch1.xlsx
# Translator's filled "Translate" sheet -> draft items (review pending)
python3 ml_pipeline/scripts/worksheets.py testset-import Siamsil_TestSet_en-zomi_batch1.xlsx \
  --translator T01 --origin "written for Siamsil, 2026-10-17" --out data/evaluation/human/en-zomi-v1.draft.jsonl
# Sheet for the second reader: Accept, or Correct with the corrected Zomi
python3 ml_pipeline/scripts/worksheets.py review-sheet data/evaluation/human/en-zomi-v1.draft.jsonl --out review.xlsx
# Merge the decisions into the set; undecided rows stay out, and the result is validated
python3 ml_pipeline/scripts/worksheets.py review-merge data/evaluation/human/en-zomi-v1.draft.jsonl review.xlsx \
  --reviewer R01 --out data/evaluation/human/en-zomi-v1.jsonl
```

Leakage matching uses the same normalization as the corpus build (`normalize_word` in `build_language_db.py`), on both the English and the Zomi side.

## Exit gate (Phase 0)

- Translation guidelines published by native-speaker editors.
- Both sets frozen at version 1, with validation passing, zero leakage, and committed manifests.
- Reviewer agreement reported per domain.
