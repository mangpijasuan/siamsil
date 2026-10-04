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

Expected raw files:

- `raw/dictionary/Zomi_Standard_Dictionary_AI_Cleaned.xlsx`
- `raw/parallel/zomi_english_sentences.csv`
