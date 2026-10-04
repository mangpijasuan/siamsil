# Generator spot-check

Updated: 2026-10-04
Phase: [ROADMAP.md](ROADMAP.md) Phase 1

The Zomi side of the parallel corpus came from four Gemini models (`gemini-3-flash-preview` 906,543 pairs, `gemini-pro` 450,619, `gemini-2.5-flash` 403,972, `gemini-3-pro-preview` 7,983). Their quality probably differs. A blind spot-check by native speakers estimates each model's quality so Phase 1 can weight or filter pairs by generator.

This measures the training corpus. It does not replace the human evaluation sets in [EVALUATION_SET.md](EVALUATION_SET.md), which measure models.

## Process

1. **Export** after a language build. The sample is about 200 pairs per model, interleaved, with pairs held out for evaluation excluded. Exports go under `data/exports/` (not committed).

   ```bash
   python3 ml_pipeline/scripts/review_sample.py export \
     data/processed/language/siamsil_language.sqlite --out data/exports/generator-review-v1
   ```

2. **Review.** Give reviewers `review.csv` only. `key.csv` maps samples to models and stays with the coordinator so reviews are blind. Reviewers fill in `meaning`, `fluency`, and optional `notes` for each row. A row left blank is skipped, not scored.

3. **Summarize.**

   ```bash
   python3 ml_pipeline/scripts/review_sample.py summarize \
     data/exports/generator-review-v1/review.csv data/exports/generator-review-v1/key.csv \
     --json data/exports/generator-review-v1/summary.json
   ```

   The summary gives, per model, mean scores and the share of acceptable pairs with a 95% confidence interval. With 200 pairs per model the interval is roughly ±7 percentage points.

## Rating scale

Native-speaker editors may revise this scale before the first review; change the export seed when they do, so old and new reviews are not mixed.

| Score | Meaning (does the Zomi say what the English says?) | Fluency (is it Zomi a speaker would write?) |
|---|---|---|
| 0 | Wrong, or important parts missing or added | Not readable as Zomi |
| 1 | Partly right | Understandable, with errors |
| 2 | Fully right | Natural |

A pair is **acceptable** when meaning is 2 and fluency is at least 1.

## Using the result

The per-model acceptable share feeds the silver/bronze tier rules in Phase 1. Record the summary and the reviewers' consent and credit with the dataset release that uses it.
