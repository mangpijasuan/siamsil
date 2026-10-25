# Generator spot-check

Updated: 2026-10-25
Phase: [ROADMAP.md](ROADMAP.md) Phase 1

The Zomi side of the parallel corpus came from four Gemini models (`gemini-3-flash-preview` 906,543 pairs, `gemini-pro` 450,619, `gemini-2.5-flash` 403,972, `gemini-3-pro-preview` 7,983). Their quality probably differs. A blind spot-check by native speakers estimates each model's quality so Phase 1 can weight or filter pairs by generator.

This measures the training corpus. It does not replace the human evaluation sets in [EVALUATION_SET.md](EVALUATION_SET.md), which measure models.

## Process

1. **Export** after a language build. The sample is about 200 pairs per model, interleaved, with pairs held out for evaluation excluded. Exports go under `data/exports/` (not committed).

   ```bash
   python3 ml_pipeline/scripts/review_sample.py export \
     data/processed/language/siamsil_language.sqlite --out data/exports/generator-review-v1
   ```

2. **Review.** Give each reviewer a rating sheet, never `key.csv`: it maps samples to models and stays with the coordinator so reviews are blind. Make the sheet with dropdowns, and read it back when it is returned:

   ```bash
   python3 ml_pipeline/scripts/worksheets.py ratings-sheet data/exports/generator-review-v1/review.csv \
     --out Siamsil_Corpus_Review_R01.xlsx
   python3 ml_pipeline/scripts/worksheets.py ratings-import Siamsil_Corpus_Review_R01.xlsx \
     --out data/exports/generator-review-v1/review-R01.csv
   ```

   Reviewers fill in `meaning` and `fluency` (see the scale below), and optionally a `correction` (the right Zomi, if they know it) and `notes`. A row left blank is skipped, not scored. Corrections are kept for the lead editor; they never replace the stored text.

3. **Summarize** to estimate each generator's quality.

   ```bash
   python3 ml_pipeline/scripts/review_sample.py summarize \
     data/exports/generator-review-v1/review-R01.csv data/exports/generator-review-v1/key.csv \
     --json data/exports/generator-review-v1/summary.json
   ```

   The summary gives, per model, mean scores and the share of acceptable pairs with a 95% confidence interval. With 200 pairs per model the interval is roughly ±7 percentage points.

4. **Record the ratings** so they outlive the database. Only people in the private roster can be recorded. The roster is a CSV with `code`, `role` (`reviewer` or `lead_editor`) and, optionally, `name`; keep it in the `siamsil-data` repository, never in this one.

   ```bash
   python3 ml_pipeline/scripts/review_sample.py record \
     data/exports/generator-review-v1/review-R01.csv data/exports/generator-review-v1/key.csv \
     --reviewer R01 --reviews ../siamsil-data/reviews/corpus-reviews.jsonl \
     --roster ../siamsil-data/reviews/roster.csv
   ```

   Each rated pair is appended to the reviews file as one JSON line: the pair's stable hash, meaning, fluency, correction, notes, reviewer code, review date, the time it was recorded, and batch. It holds no sentence text and is never edited. A reviewer who rates a pair again adds a newer line, which replaces their earlier one; running `record` twice on the same sheet saves nothing new, and the same pair rated again in a later batch is saved as a new review. If any row is wrong (a score other than 0-2, English or Zomi text changed in the sheet, even only punctuation or capital letters, or a reviewer not in the roster), nothing is saved and the rows are listed. Sheets exported before `key.csv` had `pair_hash` need `--database` with the database they were exported from.

5. **Lead-editor approval.** A rating alone never verifies a machine-made pair. Pairs that enough reviewers rated acceptable are listed for a lead editor, who must not have reviewed them:

   ```bash
   python3 ml_pipeline/scripts/review_sample.py approval-sheet \
     --database data/processed/language/siamsil_language.sqlite \
     --reviews ../siamsil-data/reviews/corpus-reviews.jsonl --out approve-1.csv
   # the lead editor writes approve or reject in the decision column (blank = later)
   python3 ml_pipeline/scripts/review_sample.py approve approve-1.csv --approver E01 \
     --reviews ../siamsil-data/reviews/corpus-reviews.jsonl --roster ../siamsil-data/reviews/roster.csv
   ```

   The sheet shows each pair with its reviewers' scores, notes and corrections. `approve` saves one approval line per decision (approver code, date, time recorded, batch, notes). It refuses an approver who is not a roster lead editor or who reviewed the pair, a pair whose text was changed in the sheet, and a pair that is no longer ready (for example because a newer review arrived).

6. **Rebuild** with the same file. Every rebuild applies it. A `--reviews` path that does not exist stops the build, so a typo cannot quietly drop every decision:

   ```bash
   python3 ml_pipeline/scripts/build_language_db.py --reviews ../siamsil-data/reviews/corpus-reviews.jsonl
   ```

   Status per pair follows the SOP manual:

   | Status | Rule | Effect |
   |---|---|---|
   | `HUMAN_APPROVED` | at least `--min-reviewers` reviewers (default 1) rated it acceptable, then a lead editor who was not one of them approved it | `verified = 1` and quality score 1 (people outrank the automatic checks; their flags stay for the record); the app labels it "approved by Zomi reviewers"; the dataset export puts it in the silver tier |
   | `READY_FOR_APPROVAL` | enough acceptable reviews, no approval yet (or only one older than the latest review) | unchanged, still unverified |
   | `NEEDS_CORRECTION` | reviewed, but not acceptable | unchanged, still unverified |
   | `REJECTED` | any reviewer's latest meaning is 0, or the lead editor rejected it | flagged `reviewer_rejected`, quality score 0; never shown in the app and never exported |

   The build prints and records (`quality_report.json`, `human_review`) the count of each status and of saved decisions whose pair is no longer in the corpus. The release manifest records the reviews file's checksum. Approved pairs are still exported only when the corpus is cleared for training in `data/rights.json`.

7. **Copy into the application database** (optional; the start of the Review Center). With `SIAMSIL_DATABASE_URL` set and `alembic upgrade head` run from `backend/`:

   ```bash
   python backend/scripts/import_reviews.py ../siamsil-data/reviews/corpus-reviews.jsonl --dry-run
   python backend/scripts/import_reviews.py ../siamsil-data/reviews/corpus-reviews.jsonl
   ```

   The file is checked the same way the build checks it, then each record is stored exactly as written, in file order, which `decide()` depends on. Run it again after more reviews are appended: it adds only the new records, and each import is written to the audit log. If an earlier line of the file was changed, the import is refused and nothing is saved, because the file must only ever be appended to. The database itself refuses to edit or delete stored records. The file stays the source of truth for rebuilds until the Review Center can export back to it.

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
