# Generator spot-check

Updated: 2026-10-24
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

   Reviewers who rate in Excel return the "Rate" sheet; convert it first:
   ```bash
   python3 ml_pipeline/scripts/worksheets.py ratings-import Siamsil_Corpus_Review_240.xlsx \
     --out data/exports/generator-review-v1/review.csv
   ```
3. **Summarize.**

   ```bash
   python3 ml_pipeline/scripts/review_sample.py summarize \
     data/exports/generator-review-v1/review.csv data/exports/generator-review-v1/key.csv \
     --json data/exports/generator-review-v1/summary.json
   ```

   The summary gives, per model, mean scores and the share of acceptable pairs with a 95% confidence interval. With 200 pairs per model the interval is roughly ±7 percentage points.

4. **Save the ratings** so they outlive the database. Each reviewer's completed sheet is recorded once, under their roster code (R01, R02…; names stay in the private roster):

   ```bash
   python3 ml_pipeline/scripts/review_sample.py record \
     data/exports/generator-review-v1/review.csv data/exports/generator-review-v1/key.csv \
     --reviewer R01 --reviews ../siamsil-data/reviews/corpus-reviews.jsonl
   ```

   Ratings are appended to that file, one JSON line each: the pair's stable hash, meaning, fluency, reviewer code, date, batch and notes. It holds no sentence text and is never edited; a reviewer who rates a pair again adds a newer line, which replaces their earlier one. Running `record` twice on the same sheet saves nothing new; the same pair rated again in a later batch is saved as a new review, even with the same scores. If any row is wrong (a score other than 0–2, or English or Zomi text changed in the sheet, even only punctuation or capital letters), nothing is saved and the rows are listed. Keep the file in the private `siamsil-data` repository so it is backed up; `data/reviews/` in this repository is the default location and is not committed.

5. **Rebuild** with the same file. Every rebuild applies it. A `--reviews` path that does not exist stops the build, so a typo cannot quietly drop every decision:

   ```bash
   python3 ml_pipeline/scripts/build_language_db.py --reviews ../siamsil-data/reviews/corpus-reviews.jsonl
   ```

   | Decision | Rule | Effect |
   |---|---|---|
   | Accepted | at least `--min-reviewers` reviewers (default 1), and every reviewer's latest rating is acceptable | `verified = 1` and quality score 1 (reviewers outrank the automatic checks; their flags stay for the record); the app labels it "accepted by Zomi reviewers"; the dataset export puts it in the silver tier |
   | Rejected | any reviewer's latest meaning is 0 | flagged `reviewer_rejected`, quality score 0; never shown in the app and never exported |
   | Undecided | anything else | unchanged, still unverified |

   The build prints and records (`quality_report.json`, `human_review`) how many pairs were verified, rejected and undecided, and how many saved ratings no longer match a pair in the corpus. The release manifest records the reviews file's checksum.

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
