# Dictionary audit: headword problems for the owner to decide

Status: **runbook** (PR 3 of the review plan in [AUDIT.md](AUDIT.md)). Run on the computer that holds `siamsil-data`. The reference dictionaries are `needs_review` in `data/rights.json`, so every output stays in the private data repository.

`ml_pipeline/scripts/dictionary_audit.py` lists problems in the reference dictionaries (the 50K Translation Master and the Essential 3000) and gives you a sheet to decide them. It changes nothing in the dictionary. Your decisions are saved, and a later step (PR 5) applies the accepted ones with a preview and rollback.

## What it finds

| Category | What it means | Proposal |
|---|---|---|
| `duplicate_headword` | The same English headword with the same part of speech, entered more than once in one source | Merge into one headword, keeping every sense |
| `zomi_variant` | Two spellings in one entry that your adopted Standard Form makes the same word | Keep one spelling: the standard form |
| `inflected_form` | An English headword that is a regular inflection of another headword in the same source ("books" beside "book", "walked" beside "walk") | List it under the base word, or keep it as its own headword |
| `missing_zomi` | A sense with no Zomi | Add the Zomi, or remove the sense |
| `missing_pos` | An entry with no part of speech | Add it |
| `not_standard_form` | Zomi your adopted rules would spell differently | Shows the standard form beside it |

Where the Zomi comes in, the tool uses only your adopted rules (`data/zomi_standard_form/standard.json`). It has no Zomi of its own and never suggests new words. The English check uses regular English inflection only (-s, -es, -ies, -ed, -ing), so it finds candidates: a word like "building" can be a headword in its own right, which is why you decide each one.

## Running it

Build the reference dictionary database if you don't have it yet (it reads the originals in `siamsil-data` and checks their checksums):

```bash
python3 ml_pipeline/scripts/import_reference_dictionaries.py --data-repo ../siamsil-data
```

Find the problems:

```bash
python3 ml_pipeline/scripts/dictionary_audit.py audit \
  --db data/processed/reference/reference_dictionaries.sqlite \
  --decisions ../siamsil-data/reviews/dictionary-headword-decisions.jsonl \
  --out-dir ../siamsil-data/reviews/dictionary-audit-1
```

Open `headword-review.csv` in Excel. For each row you want to decide, write `accept`, `reject` or `defer` in the **decision** column, and anything else in **notes**. Leave a row blank to skip it. Don't change the detail or proposal columns; a changed row is refused. Save as CSV, then record your decisions:

```bash
python3 ml_pipeline/scripts/dictionary_audit.py record \
  --sheet ../siamsil-data/reviews/dictionary-audit-1/headword-review.csv \
  --findings ../siamsil-data/reviews/dictionary-audit-1/findings.jsonl \
  --decisions ../siamsil-data/reviews/dictionary-headword-decisions.jsonl \
  --roster ../siamsil-data/reviews/roster.csv --owner O01
```

Only the roster's owner can record decisions, and each is saved as `approval: owner_sole`. The decisions file is append-only. When you run `audit` again with `--decisions`, accepted and rejected findings drop out while their content is unchanged; deferred ones come back.

## Reviewing senses in one pass

The sense review sheet (`backend/scripts/dictionary_review.py`, [DICTIONARY.md](DICTIONARY.md)) now has the same one-pass owner mode as the corpus:

```bash
python backend/scripts/dictionary_review.py record --sheet batch-O01-1.xlsx --reviewer O01 --owner-decides
```

| Decision on a row | What is recorded |
|---|---|
| `correct` | Approved (`owner_sole`) |
| `fix` with your corrected Zomi | Edit and approve: the correction is approved (`owner_sole`) and written by `apply` |
| `not_tedim`, `wrong` | Rejected |

Then run `apply` as before to write the approved corrections and statuses into the editorial dictionary.
