# Private English–Zomi gold-test workflow

The existing synthetic corpus and its test split are **not** a human gold benchmark. Build a new hidden set from independently authored or licensed source sentences, with English→Zomi and Zomi→English both represented. Use domains such as everyday conversation, education, government, health, news, and religion only where source and translation rights permit. A practical first target is roughly 500 or more adjudicated items per direction, balanced by domain; finalize the sampling plan with Zomi reviewers before using scores as a release gate.

## 1. Collect independent source sentences

Create a local JSONL file with one object per sentence. Required fields:

```json
{"source_id":"en-0001","source_language":"en","source_text":"An independently authored sentence.","domain":"daily","source_origin":"community-authored","rights_reference":"signed-consent-record-123"}
```

Use `zom` for independently authored Zomi source sentences. Supply a real rights-evidence reference; the script checks presence, not legal sufficiency. Do not include any translation, model candidate, or dictionary definition in the source file. Do not seed this set from the 1.77M machine-generated pairs. Have a Zomi editor check source clarity and dialect.

The source file must include both directions. Prepare blind packets locally:

```bash
python3 ml_pipeline/scripts/gold_test_workflow.py prepare \
  --sources /path/to/approved_independent_sources.jsonl
```

The command writes to the Git-ignored `data/evaluation/gold_private/v1/` folder. It rejects duplicate IDs/text and normalized **exact** matches against the existing synthetic corpus. This is only one leakage check: the team must also review near-paraphrases, shared source documents, memorized prompts, and any overlap with model development data. Do not put hidden source or reference text into training, prompt examples, filtering development, or public test fixtures.

## 2. Translate independently and adjudicate

`reviewer_a_blank.jsonl` and `reviewer_b_blank.jsonl` contain source text but no model output. Give them to separate qualified translators without showing one another's work. Each fills `reviewer_id`, `translation`, and optional `notes` in a **copy** of the blank file. An independent adjudicator reviews both versions and fills a copy of `adjudicator_blank.jsonl` with the chosen or corrected full translation and rationale. The three reviewer IDs must differ for each item.

Finalize only after all three files cover every source ID:

```bash
python3 ml_pipeline/scripts/gold_test_workflow.py finalize \
  --reviewer-a /path/to/reviewer_a_completed.jsonl \
  --reviewer-b /path/to/reviewer_b_completed.jsonl \
  --adjudicator /path/to/adjudicator_completed.jsonl
```

The final local `gold_test.jsonl` retains provenance and reviewer IDs; its manifest records a checksum. It is **not** published or automatically approved for model training. Freeze and version the completed test set after rights review and manual duplicate-family inspection. Future model comparisons must use exactly the same frozen set and report each direction separately, alongside native-speaker judgments. Never tune repeatedly against the hidden test; use a separate development set.

No independent source sentences or human translations have been supplied yet, so this workflow currently has **zero gold references**. The scripts and tests are ready; qualified contributors, source rights, and adjudication are the next human inputs.
