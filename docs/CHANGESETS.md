# Changesets: applying your decisions, with preview and rollback

Status: **runbook** (PR 5 of the review plan in [AUDIT.md](AUDIT.md)). `ml_pipeline/scripts/changesets.py` turns the decisions you accepted in the dictionary audit ([DICTIONARY_AUDIT.md](DICTIONARY_AUDIT.md)) and in proposals ([PROPOSALS.md](PROPOSALS.md)) into changes, shows them to you, and applies them only when you say so. Every change can be undone.

## How it stays reversible

The originals in `siamsil-data` are never edited, and neither is the reference dictionaries database built from them. Applying a changeset only records your decision in a ledger. `build` then makes a separate **applied copy**: the base database plus every changeset you applied and have not rolled back, oldest first. To undo, you record a rollback and build again.

```text
decisions ──plan──▶ changeset ──preview──▶ you check ──apply──▶ ledger ──build──▶ applied copy
                                                       rollback ──▶ ledger ──build──▶ applied copy without it
```

Each change checks that the dictionary still holds what it expects (the sense or entry it changes). If the dictionary changed since you planned it, that change is skipped as a conflict and reported; plan again.

## What a change may touch

| Your decision | Change | Where it goes |
|---|---|---|
| Accept a duplicate headword | Merge the entries, keeping every sense | the dictionary |
| Accept a spelling variant, or "not in standard form" | Rewrite the sense's Zomi with your adopted Standard Form, keeping each alternative once | the dictionary |
| Accept an inflected form | Record it as an inflected form of its base word | `inflected_forms` (the entry stays) |
| Accept a missing part of speech or missing Zomi | Nothing: it needs your value. It is listed under "needs your input"; fix it in the dictionary review sheet | — |
| Accept an attested word or spelling variant (proposals) | Add it to the Zomi headword list, with its references and your meaning if you wrote one | `zomi_headwords` |
| Edit a definition proposal (your own words) | Set the sense's English definition to your text | the dictionary |
| Accept a model's suggestion as it stands | Keep it beside the sense | `sense_annotations` |

**Model-written text never enters the dictionary's own text.** Only rule-based changes and text you wrote yourself do. A model's suggestion that you accepted without rewriting stays in `sense_annotations`, marked with its origin, and provider-assisted ones with `provider_derived`. The training export reads entries, senses and examples only, so it cannot take in model-written text. Every applied change is listed in `applied_changes` with its changeset, decision, origin, and the text before and after.

## Doing it

Plan from your decisions (repeat `--findings` and `--proposals` for each file you decided):

```bash
python3 ml_pipeline/scripts/changesets.py plan \
  --findings ../siamsil-data/reviews/dictionary-audit-1/findings.jsonl \
  --headword-decisions ../siamsil-data/reviews/dictionary-headword-decisions.jsonl \
  --proposals ../siamsil-data/reviews/proposals/attested-words-1.jsonl \
  --proposal-decisions ../siamsil-data/reviews/proposal-decisions.jsonl \
  --changesets-dir ../siamsil-data/reviews/changesets --ledger ../siamsil-data/reviews/changesets/ledger.jsonl
```

Preview it. This runs the changes on a throwaway copy, lists every change before and after in a CSV, and prints a random sample of 20 for you to spot-check (the seed is recorded, so the same sample can be drawn again):

```bash
python3 ml_pipeline/scripts/changesets.py preview --changeset ../siamsil-data/reviews/changesets/C-XXXXXXXXXXXX.json \
  --base-db data/processed/reference/reference_dictionaries.sqlite
```

If the sample is right, apply it. `apply` refuses a changeset that was not previewed, or that changed after its preview, and only the roster's owner can apply:

```bash
python3 ml_pipeline/scripts/changesets.py apply --changeset ../siamsil-data/reviews/changesets/C-XXXXXXXXXXXX.json \
  --ledger ../siamsil-data/reviews/changesets/ledger.jsonl --roster ../siamsil-data/reviews/roster.csv --owner O01
```

Build the applied copy:

```bash
python3 ml_pipeline/scripts/changesets.py build --base-db data/processed/reference/reference_dictionaries.sqlite \
  --out data/processed/reference/reference_dictionaries.applied.sqlite \
  --ledger ../siamsil-data/reviews/changesets/ledger.jsonl --changesets-dir ../siamsil-data/reviews/changesets
```

To undo a changeset, run `rollback` with the same arguments as `apply`, then `build` again. The ledger keeps both entries.

The training export can use the applied copy with `export_datasets.py --reference-db data/processed/reference/reference_dictionaries.applied.sqlite`.

## Showing your changes on the website

The website's dictionary is built by `build_language_db.py` from the 50K Translation Master's review workbook. Give it the applied copy and it shows your applied changes:

```bash
python3 ml_pipeline/scripts/build_language_db.py \
  --applied-dictionary data/processed/reference/reference_dictionaries.applied.sqlite
```

The applied copy comes from the Master's JSON file and the website from its workbook, and the two number their senses differently, so each change is matched by content: the headword and the exact text the change expects to find. It applies only where exactly one website row matches; anything else is skipped and counted in the build report (`quality_report.json`, `dictionary.owner_applied_changes`), never guessed.

| Applied change | On the website |
|---|---|
| Standard-form Zomi | That sense's Zomi (and search) |
| Your own definition | That sense's English definition |
| Inflected form | A usage note: "Inflected form of 'book'" |
| Merged duplicates | Nothing to do: the website already lists senses one per row |
| A new Zomi headword with your meaning | A new row, "Siamsil owner's Zomi headwords", marked verified |
| A new Zomi headword with no meaning yet | Waits until you write one |
| Anything from an outside provider, or a model's suggestion accepted as it stands | Not shown |

Changes to the Essential 3000 are counted as "not in the live dictionary": the website does not show it. The release manifest records the applied copy's checksum, so each release says which decisions it shows. Rebuild the data bundle (`backend/scripts/package_data.py`) and deploy to put the result online.

## Where things stand

```bash
python3 ml_pipeline/scripts/changesets.py status \
  --corpus-reviews ../siamsil-data/reviews/corpus-reviews.jsonl \
  --corpus-revisions ../siamsil-data/reviews/corpus-revisions.jsonl \
  --findings ../siamsil-data/reviews/dictionary-audit-1/findings.jsonl \
  --headword-decisions ../siamsil-data/reviews/dictionary-headword-decisions.jsonl \
  --proposals ../siamsil-data/reviews/proposals/attested-words-1.jsonl \
  --proposal-decisions ../siamsil-data/reviews/proposal-decisions.jsonl \
  --ledger ../siamsil-data/reviews/changesets/ledger.jsonl
```

It prints corpus pairs by linguistic status (owner approved, owner reviewed, needs recheck, rejected), dictionary findings and proposals by decision, and how many changesets and changes are applied. Every number is counted from the files you name; give only the ones you have. Add `--out status.json` to keep a copy.
