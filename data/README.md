# Siamsil language data

```text
../siamsil-data/   the originals: primary source, versioned, never edited (private repository)
data/
├── *.json         settings the code depends on (rights, Bible names, pinned sources)
├── processed/     databases built from siamsil-data (rebuildable)
├── datasets/      train / validation / test splits (rebuildable)
├── evaluation/    evaluation slices
├── exports/       review sheets and bundles (rebuildable)
└── versions/      release manifests: which originals and checksums each build used
```

**siamsil-data is the primary source.** Every original (dictionaries, Bibles, the corpus, books) lives in the private `siamsil-data` repository; keep its clone **beside** this one (`../siamsil-data`), or set `SIAMSIL_DATA_REPO` to where it is. The build scripts read the originals there directly, after checking each against the checksum pinned in [`source_files.json`](source_files.json). A changed or missing file stops the build. Its README lists every file with its source, checksum, and rights.

This folder holds only settings the code depends on (`rights.json`, `bible_versions.json`, `source_files.json`, …) and what the scripts build from siamsil-data (`processed/`, `datasets/`, `exports/`, `evaluation/`). You can delete the built folders at any time and rebuild them. `raw/` is no longer needed; `restore_private_data.py` still unpacks it for tools that expect the older layout, and `build_language_db.py --raw data/raw` builds from it.

The language database's dictionary is the 50K Translation Master (`--dictionary standard` for the Zomi Standard Dictionary; [DICTIONARY.md](../docs/DICTIONARY.md)). Build the language database:

```bash
python3 -m pip install -r ml_pipeline/requirements.txt
python3 ml_pipeline/scripts/build_language_db.py
# with hidden evaluation sets held out of every split:
python3 ml_pipeline/scripts/build_language_db.py --eval data/evaluation/human/en-zomi-v1.jsonl
```

Export tiered train / validation / test files (gold, silver, bronze) to `data/datasets/`. Only sources whose training rights are `cleared` in `data/rights.json` are exported; `--allow-uncleared` admits `needs_review` sources for internal experiments and records that in the export manifest.

```bash
python3 ml_pipeline/scripts/export_datasets.py --workbook ../siamsil-data/bible/Zomi_Bible_Final_v14.xlsx \
  --eval data/evaluation/human/en-zomi-v1.jsonl \
  --generator-summary data/exports/generator-review-v1/summary.json
```

Import Bible versions from USX folders (each with `metadata.xml` and `USX_1/` or `USX/`, as in ProPresenter bundles) or USFM folders (one `.usfm` file per book, as in eBible.org downloads; name and language come from `data/bible_versions.json`) into `data/processed/bible/bible_versions.sqlite`. Unzip the bundle under `data/raw/bible/usx/`; the text stays out of git. When the folder is elsewhere, pass `--source`; point the backend at a database elsewhere with `SIAMSIL_BIBLE_VERSIONS_DB`.

```bash
python3 ml_pipeline/scripts/import_usx_bibles.py --dry-run   # report versions, verse counts, issues
python3 ml_pipeline/scripts/import_usx_bibles.py
```

`data/bible_versions.json` sets how versions are named in the app. The Tedim Bibles (TDB, TB77) are shown as Zomi Bibles with code `ctd`; the publisher's title, language code, and copyright are kept as `source_name`, `source_language_iso`, and `copyright`. A version can also list its own book names under `book_names` (USFM code → name); TDB's 66 names (Piancilna for Genesis, and so on, in Title Case) come from the project owner and TB77 uses the same names, with the source in `book_names_source`. Re-run `import_usx_bibles.py` after changing them.

Add the Bible versions to a dataset export with `--bible-versions data/processed/bible/bible_versions.sqlite`. Each Zomi version is paired verse by verse with each English version (for example the World English Bible, unzipped to `data/raw/bible/usx/web/`). A pair is exported only when both versions' training rights allow it. Splits are by whole book for every version and the workbook: Ruth, Mark, and 1 John are test; Joel, Jonah, Philippians, and Titus are validation. Merged verse ranges are not paired.

Import the reference dictionaries (the English–Zomi–Burmese Translation Master and the Essential 3000 Learner's Dictionary) straight from the private `siamsil-data` clone into `data/processed/reference/reference_dictionaries.sqlite`. The originals are read in place and must match the SHA-256 in `data/reference_dictionaries.json`; `data/raw/` is not used. Every sense is stored as `unreviewed`, and rights come from `data/rights.json` (`translation_master_50k`, `essential_3000`).

```bash
python3 ml_pipeline/scripts/import_reference_dictionaries.py --data-repo siamsil-data --dry-run
python3 ml_pipeline/scripts/import_reference_dictionaries.py --data-repo siamsil-data
```

Expected raw files:

- `raw/dictionary/Zomi_Standard_Dictionary_AI_Cleaned.xlsx`
- `raw/parallel/zomi_english_sentences.csv`
