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
- **Name:** `szsf-master-v<MAJOR.MINOR.PATCH>.jsonl`, with `szsf-master-v<MAJOR.MINOR.PATCH>.manifest.json` beside it.
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
| `origin` | yes | `human_written`, `machine_generated` or `unknown` |
| `model` | no | The machine that wrote the Zomi, when `origin` is `machine_generated` |
| `tier` | yes | `gold`, `silver` or `bronze`, as in `export_datasets.py` |
| `split` | yes | `train`, `validation`, `test` or `excluded`. Human evaluation items are never in the file |
| `quality_score` | no | A number from 0 to 1 from the automatic checks. Ranks review work; says nothing about correctness |
| `quality_flags` | no | The automatic checks that fired (`identical`, `number_mismatch`, …) |
| `reference` | no | Where in the source it came from (a corpus index, a verse, a dictionary ID) |
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

`reviewers` and `approver` are roster codes (`R01`, `E01`), never names. A `gold` record that came from a machine must be
`HUMAN_APPROVED`.

## Rules every record must meet

1. Text has no spaces at its ends, no line breaks or control characters, and is Unicode NFC.
2. **No damaged characters.** Text like `caf√©` or `Ama‚Äô` is what UTF-8 looks like after an export read it as Mac Roman; the Excel
   exports of the parallel corpus have it in about 1% of rows (`siamsil-data/parallel/workbooks/FINDINGS.md`). A record that has it is
   refused.
3. `zomi` is the source's text. The standard form is a separate field, never a replacement.
4. A changed standard form names the adopted rules that changed it. Rules are adopted only by two Zomi reviewers.
5. Every `source` is in `data/rights.json`. For a file meant for training, every source of a record not `excluded` must be `cleared`
   for training; for display, for display. `--purpose training|display` checks this.
6. The review rules above, including that nobody approves their own review.

## The manifest

`szsf.py manifest` writes the manifest of a file that passes the checks:

- the format and version, the file name, size, SHA-256 and record count;
- counts by `kind`, `tier`, `split`, `origin`, `source` and review status;
- the `standard_version` values used;
- a **snapshot** of each source's rights from `data/rights.json` when the manifest was made. The snapshot records what the rights
  were; it clears nothing.

`szsf.py validate --manifest` checks the file still matches its manifest.

## Using it

```bash
python3 ml_pipeline/scripts/szsf.py validate szsf-master-v1.0.0.jsonl --purpose training
python3 ml_pipeline/scripts/szsf.py manifest szsf-master-v1.0.0.jsonl --out szsf-master-v1.0.0.manifest.json
python3 ml_pipeline/scripts/szsf.py validate szsf-master-v1.0.0.jsonl --manifest szsf-master-v1.0.0.manifest.json
```

## Status and next steps

SZSF 1.0 is the format. **No master file has been made yet**, and nothing in the app reads one.

1. The project owner and the Zomi reviewers confirm the fields and the review statuses above.
2. A converter turns what exists into SZSF: the training export (`export_datasets.py`), the corpus reviews, and the dictionary
   senses, with the standard form added by `zolai_standard.py apply`. It starts with the pairs a human has approved.
3. The first master file is made in siamsil-data, checked, given its manifest, and used to train the first reviewed baseline.
