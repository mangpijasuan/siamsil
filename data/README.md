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

Large raw files are gitignored. On a new computer, copy them from a clone of the private `siamsil-data` repository (Windows, macOS and Linux; existing files are never overwritten):

```bash
python3 ml_pipeline/scripts/restore_private_data.py --data-repo ../siamsil-data
```

Then build the language database:

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

Import Bible versions from USX folders (each with `metadata.xml` and `USX_1/` or `USX/`, as in ProPresenter bundles) or USFM folders (one `.usfm` file per book, as in eBible.org downloads; name and language come from `data/bible_versions.json`) into `data/processed/bible/bible_versions.sqlite`. Unzip the bundle under `data/raw/bible/usx/`; the text stays out of git. When the folder is elsewhere, pass `--source`; point the backend at a database elsewhere with `SIAMSIL_BIBLE_VERSIONS_DB`.

```bash
python3 ml_pipeline/scripts/import_usx_bibles.py --dry-run   # report versions, verse counts, issues
python3 ml_pipeline/scripts/import_usx_bibles.py
```

`data/bible_versions.json` sets how versions are named in the app. The Tedim Bibles (TDB, TB77) are shown as Zomi Bibles with code `zom`; the publisher's title, language code (`ctd`), and copyright are kept as `source_name`, `source_language_iso`, and `copyright`. A version can also list its own book names under `book_names` (USFM code → name); TDB's 66 names (Piancilna for Genesis, and so on, in Title Case) come from the project owner and TB77 uses the same names, with the source in `book_names_source`. Re-run `import_usx_bibles.py` after changing them.

Add the Bible versions to a dataset export with `--bible-versions data/processed/bible/bible_versions.sqlite`. Each Zomi version is paired verse by verse with each English version (for example the World English Bible, unzipped to `data/raw/bible/usx/web/`). A pair is exported only when both versions' training rights allow it. Splits are by whole book for every version and the workbook: Ruth, Mark, and 1 John are test; Joel, Jonah, Philippians, and Titus are validation. Merged verse ranges are not paired.

Expected raw files:

- `raw/dictionary/Zomi_Standard_Dictionary_AI_Cleaned.xlsx`
- `raw/parallel/zomi_english_sentences.csv`
