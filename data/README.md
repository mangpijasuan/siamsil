# Siamsil language data

Raw files in this tree are **immutable**. Never edit them in place.

```text
data/
├── raw/           acquired originals (do not modify)
├── processed/     cleaned, indexed, reproducible outputs
├── datasets/      train / validation / test splits
├── evaluation/    permanent evaluation slices
├── exports/
└── versions/      named dataset releases
```

Large raw files are gitignored. Place them locally, then build the language database:

```bash
python3 -m pip install -r ml_pipeline/requirements.txt
python3 ml_pipeline/scripts/build_language_db.py
# with hidden evaluation sets held out of every split:
python3 ml_pipeline/scripts/build_language_db.py --eval data/evaluation/human/en-zomi-v1.jsonl
```

Export tiered train / validation / test files (gold, silver, bronze) to `data/datasets/`. Only sources whose training rights are `cleared` in `data/rights.json` are exported; `--allow-uncleared` admits `needs_review` sources for internal experiments and records that in the export manifest.

```bash
python3 ml_pipeline/scripts/export_datasets.py --workbook ml_pipeline/raw_data/Zomi_Bible_Final_v14.xlsx \
  --eval data/evaluation/human/en-zomi-v1.jsonl \
  --generator-summary data/exports/generator-review-v1/summary.json
```

Expected raw files:

- `raw/dictionary/Zomi_Standard_Dictionary_AI_Cleaned.xlsx`
- `raw/parallel/zomi_english_sentences.csv`
