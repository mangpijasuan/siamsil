# Filtering the SZSF master and reviewing the best rows first

Status: **runbook.** Run on the computer that holds `siamsil-data`. The corpus is `blocked` in `data/rights.json`: keep every output in the private data repository, never in the public one. "Filtered" does not mean reviewed.

## 1. Filter the master

```bash
python3 ml_pipeline/scripts/filter_szsf_corpus.py \
  --input ../siamsil-data/szsf/szsf-master-v1.1.0.jsonl.gz \
  --out-dir ../siamsil-data/szsf/filtered-v1.1.0
```

It writes, in `--out-dir`:

| File | What it holds |
|---|---|
| `szsf-filtered.jsonl` and `.manifest.json` | Kept rows, unchanged, with counts and a SHA-256 |
| `quarantine.jsonl` | Rows left out, each with its reasons and the full record |
| `review-queue.jsonl` | Kept rows with a soft flag (`length_ratio_outlier`, `extremely_short`, `extremely_long`, `target_reused`) |
| `reaudit-sample.jsonl` | A ranked sample (default 5,000) of kept rows from `gemini-pro` and unknown models, most in need of review first |
| `summary.json` | Counts per reason |

A 300,000-row slice took about 7 seconds, so the full file should take under a minute. Files are written privately (owner-only permissions) into a staging folder and published together with the manifest last, so a folder without a current manifest is an unfinished run. A lock file stops two runs sharing one output folder, an output path that is the input is refused, and the manifest's `created_at` is the input file's modification time, so the same input gives the same manifest. The rules are in the script's header and in [the review notes](#what-the-filter-decides).

## 2. Make a review sitting (about 100 pairs)

```bash
python3 ml_pipeline/scripts/review_sample.py export-queue \
  data/processed/language/siamsil_language.sqlite \
  --ids ../siamsil-data/szsf/filtered-v1.1.0/reaudit-sample.jsonl \
  --out ../siamsil-data/reviews/queue/batch-001 --offset 0 --limit 100
```

It writes `review.csv` for you and `key.csv` (keep away from other reviewers). Queue entries carry a fingerprint of the English; if you rebuilt the database and an id now holds a different sentence, that pair is skipped and reported, and you should re-run the filter on the current master. Rows the filter marks excluded or rejected are quarantined and never queued. Pairs held out for evaluation are never exported. For the next sitting use `--offset 100`, then `200`, and so on. To review the soft-flag rows instead, pass `review-queue.jsonl`.

## 3. Review in Excel

```bash
python3 ml_pipeline/scripts/worksheets.py ratings-sheet ../siamsil-data/reviews/queue/batch-001/review.csv \
  --out Siamsil_Rate_batch-001.xlsx
```

For each pair, use the dropdowns: **meaning** 0, 1 or 2 and **fluency** 0, 1 or 2 (see [GENERATOR_REVIEW.md](GENERATOR_REVIEW.md)). If the Zomi is wrong, write your corrected Zomi in the `correction` column. Do not use any machine tool for the correction.

## 4. Save the results

```bash
python3 ml_pipeline/scripts/worksheets.py ratings-import Siamsil_Rate_batch-001.xlsx \
  --out ../siamsil-data/reviews/queue/batch-001/review.csv
python3 ml_pipeline/scripts/review_sample.py record \
  ../siamsil-data/reviews/queue/batch-001/review.csv ../siamsil-data/reviews/queue/batch-001/key.csv \
  --reviewer R01
```

Use your roster code for `R01`. Ratings take effect on the next `build_language_db.py` run. Corrections go to the lead editor's sheet with `review_sample.py corrections-sheet` and `revise`.

**Owner-only review (built 2026-11-19, [GOVERNANCE.md](GOVERNANCE.md)).** With your code listed as `owner` in the roster, decide in the same pass you rate:

```bash
python3 ml_pipeline/scripts/review_sample.py record ../siamsil-data/reviews/queue/batch-001/review.csv \
  ../siamsil-data/reviews/queue/batch-001/key.csv --reviewer O01 --owner-decides \
  --reviews ../siamsil-data/reviews/corpus-reviews.jsonl --revisions ../siamsil-data/reviews/corpus-revisions.jsonl \
  --roster ../siamsil-data/reviews/roster.csv
```

Meaning 2 with fluency 1 or 2 approves; meaning 0 rejects; a corrected Zomi (with meaning 1 or 2) is edit-and-approve; anything else stays open. Each of your approvals is recorded as `owner_sole`. Approving a pair is a linguistic decision only: the corpus stays `blocked` in `data/rights.json` for display and training until its rights are cleared.

## 5. Rebuild and re-measure

1. Rebuild the language database (`build_language_db.py`) so approved corrections and ratings apply.
2. Re-export and convert to SZSF (`export_datasets.py`, `szsf_convert.py`). Batch your rule and correction changes first, because each rebuilt master adds about 85 MB to `siamsil-data` history.
3. Re-run the filter on the new master and score a model on your frozen evaluation set.

## What the filter decides

- **Quarantined (hard):** empty English or Zomi, English copied as Zomi, or the flags `html_or_script`, `number_mismatch`, `possible_language_mismatch`, `identical`, `suspicious_repeat`.
- **Kept but queued (soft):** `length_ratio_outlier`, `extremely_short`, `extremely_long`, `target_reused`. A short or differently sized sentence is often correct.
- **Duplicates:** within a split the best-scored copy is kept. A train pair identical to a validation or test pair is dropped.
- **Never changed:** text, tier, review status and split.
