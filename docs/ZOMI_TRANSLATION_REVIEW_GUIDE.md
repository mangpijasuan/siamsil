# Zomi translation review guide (draft for community approval)

This guide supports qualified Zomi reviewers. It is **not** an approved spelling or dialect standard. A lead Zomi editor must decide the preferred variety, orthography, and acceptable alternatives before review decisions are used for training or publication. Record a valid alternative instead of silently rewriting it to one dialect.

## What reviewers judge

Read the English source first, then the Zomi candidate. Judge meaning and naturalness separately. Do not approve a sentence merely because it is grammatical or resembles an existing machine output. If either side is unclear, mark it `uncertain` for adjudication.

Use exactly one decision per sentence:

| Decision | Use when |
| --- | --- |
| `approve` | Meaning is preserved, Zomi is natural for the agreed variety, and no edit is needed. |
| `edit` | A human correction can make the pair usable. Supply the full corrected Zomi sentence. |
| `reject` | The source or candidate is unusable, unrelated, harmful, or cannot be corrected confidently from the source alone. |
| `uncertain` | Reviewer cannot decide meaning, dialect, or terminology; an adjudicator must resolve it. |

Record one or more `error_tags` when relevant: `meaning`, `omission`, `addition`, `grammar`, `unnatural`, `dialect`, `spelling`, `name`, `number`, `terminology`, `wrong_language`, `source_problem`, `unsafe`, `other`. A tag describes an observed issue; it does not replace the decision. Use `notes` for context and proposed alternatives.

Preserve names, numbers, dates, negation, questions, and speaker intent. Do not invent a missing fact. Keep culturally appropriate expressions when they preserve meaning; do not force word-for-word translation. For religious, medical, legal, or governmental terminology, flag uncertain cases for a domain reviewer. Do not auto-import Bible verses, lyrics, or dictionary glosses as training references until their rights and intended use are documented.

## Roles and adjudication

1. A lead editor approves the variety/orthography policy and a small calibration packet with examples of acceptable variation.
2. Reviewers work independently. For the random audit, double-review at least a subset across models and error categories; send disagreements and all `uncertain` cases to an adjudicator. Preserve both original decisions.
3. The adjudicator records the final decision and rationale. Do not replace the machine candidate in the source packet; corrections are separate records keyed by `sentence_id`.
4. Before any training release, a rights owner verifies source permissions separately. Human approval is not a license.

## First representative audit

From the app repository root:

```bash
python3 ml_pipeline/scripts/prepare_translation_audit.py
```

The first packet is already generated locally at `data/exports/translation_audit_v1/`. It has 600 uniformly selected records from the 1,597,938-row deduplicated **training** split, plus 120 flagged diagnostic records. `random.jsonl`, `flagged.jsonl`, and `decisions_template.jsonl` are unreviewed and Git-ignored. The `manifest.json` records the fixed seed, population, counts, and packet checksums. The existing 100-row flagged pilot remains a separate diagnostic exercise.

Fill a **copy** of the decisions template with `reviewer_id`, `decision`, `corrected_zomi` when edited, `error_tags`, and `notes`. Keep sentence IDs and sample kinds unchanged. Do not edit the source packets. After every case has a resolved decision:

```bash
python3 ml_pipeline/scripts/summarize_translation_audit.py \
  --packet-dir data/exports/translation_audit_v1 \
  --decisions data/exports/translation_audit_v1/decisions_reviewed.jsonl \
  --output data/exports/translation_audit_v1/review_summary.json
```

The summary reports the share approved **without edits** and a 95% Wilson interval for the uniform random packet only. It also lists counts by generating model. The 120 flagged cases are diagnostic and **must not be pooled** into the population estimate. A single reviewer's decisions are not a gold test or a measure of model accuracy; record agreement and adjudication separately. Do not present a quality percentage while cases are incomplete or uncertain.

All packets contain rights-sensitive source text. Keep them out of the public app repository, public issues, model prompts, and public datasets until rights are resolved.
