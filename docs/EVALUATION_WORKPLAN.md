# Evaluation work plan and translator guidelines (draft)

Status: **draft for the owner and native-speaker editors to approve.** Editors decide the guidelines; this file only proposes them. It puts into steps what [EVALUATION_SET.md](EVALUATION_SET.md) specifies. It contains **no test sentences**: those stay out of this public repository (`data/evaluation/**` is git-ignored and sets are stored in restricted storage).

## Goal

A hidden, human-translated test set per direction, so that retrieval, a hosted model and any Siamsil model are judged the same way ([MODEL_EVALUATION.md](MODEL_EVALUATION.md)). The first batch is **70 English sentences** (`en-zomi`, 10 per domain). The full set should reach 1,000 to 2,000 per direction.

## Roles

| Role | Who | Rule |
|---|---|---|
| Owner | Project owner | Approves the guidelines, the sources and the freeze. |
| Translator (T01, T02 ...) | Native Tedim speaker | Translates a batch. Sees only the sources sheet. |
| Reviewer (R01, R02 ...) | A different native speaker | Accepts or corrects each item. |
| Adjudicator | A third person | Resolves disagreements. Differs from translator and reviewer. |

**Working-phase exception (owner decision, 2026-11-18):** the owner may be translator, reviewer and approver of an evaluation set. Such a set is labelled "owner-only, single reviewer" in its manifest and cannot be described as independently reviewed. See [SZSF.md](SZSF.md), "Owner-approved records".

IDs map to names in a separate, access-controlled roster. A person never reviews their own translation (`eval_set.py validate` checks this).

## Translator guidelines (proposed)

1. **Language.** Standard Tedim-based Zomi, language code `ctd`. Do not mix in Mizo, Zou, Falam or Hakha words.
2. **Spelling.** Follow the Siamsil Zomi Standard Form ([ZOMI_STANDARD_FORM.md](ZOMI_STANDARD_FORM.md), `data/zomi_standard_form/standard.json`) where a rule applies. Write the translation the way you would naturally write it. Do not copy from the app or any machine tool.
3. **Meaning first.** Translate the meaning and tone, not word for word. Keep negation, questions, numbers, dates and quantities exactly. Do not add or leave out information.
4. **Register.** Match the source. Everyday and informal sentences use everyday speech; religion, government and news may be more formal. Say in `notes` if you chose a register.
5. **Names.** Keep personal names as written. Place names and titles: follow common local usage; note unusual choices. For English names that have a Zomi form in the names scheme ([ZOMI_NAMES.md](ZOMI_NAMES.md)), keep the English name unless the sentence calls for a Zomi name; ask the editor when unsure.
6. **Numbers and dates.** Keep digits as digits. Write units and months in Zomi where an established word exists; note it if not.
7. **Loanwords.** Use an established Zomi word when one exists. Where the usual practice is to borrow, borrow and note it. Do not invent new words.
8. **Ambiguity.** If the English can be read two ways, translate the likelier meaning and write the other in `notes`. If a sentence cannot be translated, say why instead of guessing.
9. **Punctuation.** Use the punctuation of the source sentence type (question mark for questions, and so on).
10. **No machine help.** Do not use a machine translation tool or an AI model to produce or correct a translation. Reviewers must also work without one. This keeps the set independent of any system under test.
11. **Consent.** Translators and reviewers record their consent to the use in [DATA_RIGHTS.md](DATA_RIGHTS.md) and are credited by chosen name or paid or formally acknowledged.

## Steps

### Phase A: approve the plan (owner, one sitting)

- [ ] Read and edit the guidelines above; record the approved version and date.
- [ ] Approve the roles and name the first translator, reviewer and adjudicator.
- [ ] Decide how translators are paid or acknowledged.

### Phase B: sources (done for the first batch)

The first batch of 70 English sentences covers conversation, education, government, health, religion, news and informal speech, with short, medium and long sentences, names, numbers, dates, questions and negation.

- [ ] The owner reads every sentence and replaces any that is unsuitable.
- [ ] **Origin note:** the 70 sentences were drafted by an AI assistant for Siamsil on 2026-11-17 and must be approved by the owner. Record `source_origin` as "drafted by AI assistant, approved by project owner, 2026-11-17". The English text is a test source only; no Zomi text was produced.
- [ ] Keep the sources file at `data/evaluation/human/en-zomi-v1.sources.csv` (git-ignored). Do not commit it, paste it into a prompt or send it to an outside service.
- [ ] Check for leakage before translation:

```bash
python3 ml_pipeline/scripts/eval_set.py check-sources data/evaluation/human/en-zomi-v1.sources.csv \
  --database data/processed/language/siamsil_language.sqlite \
  --bible-versions data/processed/bible/bible_versions.sqlite
```

The first batch checked clean against the corpus and the Bibles (0 of 70 overlaps after six short sentences were replaced).

- [ ] Rebuild the language database and export after the sources file exists, so the sentences are held out of training from day one (`build_language_db.py`, `export_datasets.py`).

### Phase C: translate

```bash
python3 ml_pipeline/scripts/worksheets.py testset-sheet data/evaluation/human/en-zomi-v1.sources.csv \
  --out Siamsil_TestSet_en-zomi_batch1.xlsx
```

- [ ] T01 fills the "Translate" sheet by hand, without machine help.
- [ ] Import the draft:

```bash
python3 ml_pipeline/scripts/worksheets.py testset-import Siamsil_TestSet_en-zomi_batch1.xlsx \
  --translator T01 --origin "drafted by AI assistant, approved by project owner, 2026-11-17" \
  --out data/evaluation/human/en-zomi-v1.draft.jsonl
```

### Phase D: review and adjudicate

- [ ] R01 (not T01) accepts or corrects each item. Under the owner's working-phase decision, the owner may do this pass alone, on another day, with `eval_set.py owner-approve` (see EVALUATION_SET.md, "Owner-only review").
- [ ] A third person resolves disagreements.
- [ ] Record the share accepted without change per domain. Low agreement in a domain means that guideline needs work.

### Phase E: freeze

```bash
python3 ml_pipeline/scripts/eval_set.py validate data/evaluation/human/en-zomi-v1.jsonl
python3 ml_pipeline/scripts/eval_set.py leakage data/evaluation/human/en-zomi-v1.jsonl \
  --corpus data/raw/parallel/zomi_english_sentences.csv
python3 ml_pipeline/scripts/eval_set.py manifest data/evaluation/human/en-zomi-v1.jsonl
```

- [ ] All three exit cleanly; leakage reports zero.
- [ ] Commit only the manifest. Store the JSONL in restricted storage.
- [ ] A frozen set is read-only. Corrections produce `v2`.

### Phase F: use it

- [ ] Score retrieval and, if approved, the hosted pilot on the set with `mt_eval.py` ([MODEL_EVALUATION.md](MODEL_EVALUATION.md)).
- [ ] Only evaluation text approved for provider processing may be sent to a provider. The hidden set is never sent without separate written approval from the owner.

## Zomi to English (the second set)

The `zomi-en` set must start from text **originally written in Zomi** by native speakers, not from translated English. Collect 1,000 to 2,000 sentences across the same domains with the authors' consent, then follow Phases B to E with `zomi` as the source column.

## Rules for the AI assistant

- It does not write, correct or translate any Zomi text for the evaluation sets.
- Having read the source sentences, it does not hand-tune training data filters (EVALUATION_SET.md, "Keeping the sets hidden").
- Evaluation sentences are not used as examples, prompts or cache entries anywhere.
