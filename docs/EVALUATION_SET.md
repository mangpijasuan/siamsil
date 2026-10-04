# Human evaluation sets

Updated: 2026-10-04
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
- Phase 1 dataset builds must exclude any training pair whose normalized English or Zomi matches an evaluation item. Pass each set to the build with `--eval`; matching pairs, including English template variants of an item, go to the `eval_holdout` split.
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

Leakage matching uses the same normalization as the corpus build (`normalize_word` in `build_language_db.py`), on both the English and the Zomi side.

## Exit gate (Phase 0)

- Translation guidelines published by native-speaker editors.
- Both sets frozen at version 1, with validation passing, zero leakage, and committed manifests.
- Reviewer agreement reported per domain.
