# Siamsil Zomi Standard Format (SZSF)

Version 1.0 · Updated 2026-11-08

> The Siamsil Zomi Standard Format (SZSF) is the authoritative data schema and linguistic file standard developed by Siamsil
> for Zomi language preservation, improvement, and digital localization.

The project owner chose this name and definition on 2026-11-08. SZSF is the format of Siamsil's **master file**: the one file
that holds the trained and reviewed Zomi data, each record with its original text, its standard form, where it came from, who
reviewed it, and what it may be used for. Training sets, test sets and the dictionary release are all drawn from it.

## Three names, three things

| Name | What it is | Where |
| --- | --- | --- |
| **Siamsil Zomi Standard Format (SZSF)** | The data schema and file standard in this document | `docs/SZSF.md`, `ml_pipeline/scripts/szsf.py` |
| **Siamsil Zomi Standard Form** | The spelling rules Zomi reviewers adopt; SZSF records carry the text in this form beside the original | `docs/ZOMI_STANDARD_FORM.md` |
| *Zolai Standard Format* (Lian Than Tuang, 2018) | A third party's spelling guide, one of the sources compared for the Standard Form. **Not Siamsil's and not permitted for training** | `data/rights.json`: `zolai_standard_format_2018` |

Always write "Siamsil" in front of the first two, and "SZSF" for this format. The abbreviation `ZSF` in older files means the
third party's guide.

## What SZSF is not

- It does **not** make anything correct, reviewed or cleared. A file that passes `szsf.py validate` follows the format; whether the
  Zomi is right is for reviewers, and whether a source may be used is in `data/rights.json`.
- It does **not** replace the review records (`reviews/*.jsonl`) or the rights file. SZSF carries their results beside each record.
- It is **not** a place for text Siamsil may not hold. Private source text stays in siamsil-data, never in this repository.

## The file

- **Encoding:** UTF-8, Unicode NFC, no byte-order mark. Zomi is `ctd` (ISO 639-3, Tedim); English is `en`.
- **Layout:** JSON Lines, one record per line, one JSON object per record. Blank lines are allowed and ignored.
- **Name:** `szsf-master-v<MAJOR.MINOR.PATCH>.jsonl`, with `szsf-master-v<MAJOR.MINOR.PATCH>.manifest.json` beside it. `validate` refuses other file names.
- **Immutable:** a released file is never edited. A change is a new version, and the old one is kept for rollback.
- **Where:** the private siamsil-data repository, in `szsf/` (created with the first file; none exists yet).

## One record

Placeholder text only; the example is checked by the tests.

```json
{
  "szsf_version": "1.0",
  "id": "corpus-123",
  "kind": "translation_pair",
  "english": "ENGLISH_PLACEHOLDER",
  "zomi": "ZOMI_PLACEHOLDER",
  "zomi_standard": "ZOMI_PLACEHOLDER_STANDARD",
  "zomi_standard_rules": ["ZS-001"],
  "standard_version": "1.0.0",
  "source": "parallel_corpus",
  "origin": "machine_generated",
  "model": "model-name",
  "provider_derived": false,
  "tier": "silver",
  "split": "train",
  "quality_score": 1.0,
  "quality_flags": [],
  "reference": "corpus index 123",
  "review": {
    "status": "HUMAN_APPROVED",
    "reviewers": ["R01"],
    "approver": "E01",
    "batch": "batch-1"
  }
}
```

### Fields

| Field | Required | Meaning |
| --- | --- | --- |
| `szsf_version` | yes | The format version, `"1.0"` |
| `id` | yes | Stable ID, unique in the file, with no spaces. For a `dictionary_sense` it is the sense ID (`ZD-000123`, `ZS-000123`) |
| `kind` | yes | `translation_pair` or `dictionary_sense`. For a sense, `english` is the headword and `zomi` its Zomi equivalents |
| `english` | yes | The English text, as in the source |
| `zomi` | yes | The Zomi text **exactly as in the source**. Never edited |
| `zomi_standard` | yes | The Zomi in the Siamsil Zomi Standard Form. Equal to `zomi` when no adopted rule applies |
| `zomi_standard_rules` | no | The adopted rule IDs (`ZS-nnn`) that changed `zomi_standard`. Required whenever it differs from `zomi` |
| `zomi_standard_flags` | no | Matches of "flag" rules, left unchanged for a reviewer |
| `standard_version` | yes | The version of the adopted rule set used (`data/zomi_standard_form/standard.json`) |
| `source` | yes | The key of the source in `data/rights.json`. Its rights decide how the record may be used |
| `english_source` | no | The rights key of the English text, when it comes from a different source than the Zomi. Both keys are checked against the rights file |
| `origin` | yes | `human_written`, `machine_generated` or `unknown` |
| `model` | when `machine_generated` | The machine that wrote the Zomi. `unknown` says it was not recorded |
| `provider_derived` | when `machine_generated` | `true` when the Zomi or its labels come from an outside provider's output. Such records are left out of training by default (`docs/QUALITY_OPERATOR_ARCHITECTURE.md`); `--allow-provider-derived` keeps them only when the provider's terms allow it |
| `tier` | yes | `gold`, `silver` or `bronze`, as in `export_datasets.py` |
| `split` | yes | `train`, `validation`, `test` or `excluded`. Human evaluation items are never in the file |
| `quality_score` | no | A number from 0 to 1 from the automatic checks. Ranks review work; says nothing about correctness |
| `quality_flags` | no | The automatic checks that fired (`identical`, `number_mismatch`, …) |
| `reference` | no | Where in the source it came from (a corpus index, a verse, a dictionary ID) |
| `license_status`, `verified_at`, `prompt_version`, `release_version` | no | The lineage a published record needs (`docs/ARCHITECTURE.md`): license status, when it was verified (UTC, `2026-11-08T12:00:00Z`), the prompt version when generated, and the dataset release. Checked for form here; the release builder will require them |
| `review` | yes | The review result, below |

Any other field is refused. A local addition belongs in a separate file that points at `id`.

### Review

| `review.status` | Meaning |
| --- | --- |
| `UNREVIEWED` | No human has judged it. No reviewers, no approver |
| `NEEDS_CORRECTION` | A reviewer asked for a fix. At least one reviewer |
| `READY_FOR_APPROVAL` | Enough reviewers found it acceptable; no lead editor yet |
| `HUMAN_APPROVED` | Reviewed, then approved by a **different** lead editor (SOP-07). Needs `approver`, who is not in `reviewers` |
| `REJECTED` | A reviewer or the lead editor rejected it. Its `split` must be `excluded` |

`reviewers` and `approver` are roster codes (`R01`, `E01`; the form `corpus_reviews.py` accepts), never names, and nobody is both. With `--roster` (the private roster CSV) every reviewer must be listed as a reviewer and the approver as a lead editor; without it the codes are checked for form only. A `gold` record that came from a machine must be
`HUMAN_APPROVED`.

## Rules every record must meet

1. Text has no spaces at its ends, no line breaks (including U+2028 and U+2029) or control characters, and is Unicode NFC. The character rules apply to every text value in the record, not only the three main fields.
2. **No damaged characters.** Text like `caf√©` or `Ama‚Äô` is what UTF-8 looks like after an export read it as Mac Roman; the Excel
   exports of the parallel corpus have it in about 1% of rows (`siamsil-data/parallel/workbooks/FINDINGS.md`). A record that has it is
   refused.
3. `zomi` is the source's text. The standard form is a separate field, never a replacement.
4. A changed standard form names the adopted rules that changed it, and each must be in the adopted rule set (`data/zomi_standard_form/standard.json`) under the `standard_version` the record states. Rules are adopted only by two Zomi reviewers.
5. Every `source` is in `data/rights.json`. For a file meant for training, every source of a record not `excluded` must be `cleared`
   for training; for display, for display. `--purpose training|display` checks this, and cannot be combined with `--no-rights`.
6. The review rules above, including that nobody approves their own review.

## The manifest

`szsf.py manifest` writes the manifest of a file that passes the checks:

- the format and version, the file name, size, SHA-256 and record count;
- counts by `kind`, `tier`, `split`, `origin`, `source` and review status;
- the `standard_version` values used;
- a **snapshot** of each source's rights from `data/rights.json` when the manifest was made. The snapshot records what the rights
  were; it clears nothing.

`szsf.py validate --manifest` checks the file still matches its manifest: hash, count, and every derived field (counts, size, versions, rights snapshot). A manifest is written whole or not at all, and must be named for its file.

## Using it

```bash
python3 ml_pipeline/scripts/szsf.py validate szsf-master-v1.0.0.jsonl --purpose training --roster roster.csv
python3 ml_pipeline/scripts/szsf.py manifest szsf-master-v1.0.0.jsonl --out szsf-master-v1.0.0.manifest.json
python3 ml_pipeline/scripts/szsf.py validate szsf-master-v1.0.0.jsonl --manifest szsf-master-v1.0.0.manifest.json
```

## Converting the training export

`ml_pipeline/scripts/szsf_convert.py pairs` turns the output of `export_datasets.py` into a master file and its manifest:

```bash
python3 ml_pipeline/scripts/szsf_convert.py pairs \
  --input data/datasets/train.jsonl data/datasets/validation.jsonl data/datasets/test.jsonl \
  --db data/processed/language/siamsil_language.sqlite --reviews data/reviews/corpus-reviews.jsonl \
  --roster roster.csv --out szsf-master-v1.0.0.jsonl --rejects rejects.jsonl
```

- `english` and `zomi` are copied as they are; `zomi_standard` comes from the adopted rules (`zolai_standard.py`), and equals `zomi` while none is adopted.
- A corpus pair's review result comes from the saved review records (SOP-07), found through its pair hash. An export record marked human-reviewed that has no `HUMAN_APPROVED` decision stops the run: the export and the reviews are from different runs.
- Corpus Zomi is `machine_generated` with the generator's `model`, and `provider_derived: true` unless `--own-model` names a model Siamsil trained itself. Sources whose origin is not recorded are `unknown`. Bible and the reviewed daily-use phrases are `human_written`; their `review` stays `UNREVIEWED`, because SZSF's review block records the SOP-07 pipeline, not who wrote the text.
- Records that fail `szsf.py` go to `--rejects` with their problems and are never corrected. The written file is checked as a whole (rights file, adopted rules, roster) before it is put in place, and an existing master file is never overwritten.
- Converting clears nothing. `szsf.py validate --purpose training` still refuses sources that are not cleared and provider-derived records.

Tried on 2026-11-13 on a 913-pair sample of the local corpus: every record followed the format, and the training check refused all of them (rights `needs_review`; Gemini-made). No sample is kept.

## Status and next steps

SZSF 1.0 is the format, with a validator, a manifest writer and a converter for translation pairs. **No master file has been made yet**, and nothing in the app reads one.

1. The project owner and the Zomi reviewers confirm the fields and the review statuses above.
2. The converter handles translation pairs. Dictionary senses (`kind: dictionary_sense`) are not converted yet, and the converter has not been run on the full export or on the Bible and phrase sources.
3. The first master file is made in siamsil-data, checked, given its manifest, and used to train the first reviewed baseline, once the training rights of its sources are settled.
