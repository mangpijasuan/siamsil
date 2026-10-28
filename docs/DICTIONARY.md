# Siamsil Dictionary: editorial store

The dictionary's master copy lives in PostgreSQL, so it can grow past 100,000 headwords and be reviewed by several people at once. Published entries are copied into the read-only SQLite language release that the app searches ([ARCHITECTURE.md](ARCHITECTURE.md)). Spreadsheets are for review batches, not for the master copy.

## Structure

| Table | One row per | Notes |
|---|---|---|
| `dictionary_sources` | imported file | Pinned by SHA-256, with the `data/rights.json` entry as it was at import |
| `dictionary_entries` | headword and part of speech | `ZE-000001`…; type `word`, `term` (multi-word), `name`, or `phrase` |
| `dictionary_senses` | meaning, as one source record gives it | 50K Master ids kept (`ZD-…`); Siamsil mints `ZS-…`; original row kept in `raw` |
| `dictionary_equivalents` | Zomi (`ctd`) or reference Burmese (`my`) translation | `;`-separated alternatives become separate rows; a `gloss` is kept whole |
| `dictionary_examples` | example sentence or phrase | |
| `dictionary_issues` | quality-control finding | `open`, `resolved` or `dismissed`; some belong to a source, not a sense |

Every sense starts as `draft` and `unreviewed`. Senses from different sources join the same entry when their headword (case-folded, Unicode-normalised) and part of speech match. Nothing is merged, corrected, translated or approved automatically.

Ids are never reused. They are numbered under the import lock rather than by database sequences, so a dry run or a rolled-back import leaves no gaps.

## Sources

Listed in import order in [`data/dictionary_sources.json`](../data/dictionary_sources.json), each pinned by checksum, with rights in [DATA_RIGHTS.md](DATA_RIGHTS.md).

| Source | Senses | Notes |
|---|---:|---|
| 50K Translation Master, native-review workbook | 50,282 | 49,844 open QC issues, 7,017 of them about the source as a whole |
| Essential 3000 | 5,342 | 26,685 example sentences and phrases |
| Zomi Standard Dictionary (live dictionary) | 20,826 | Zomi definitions; 1,773 flagged rows become issues |
| Haokip-Lind 2011 (*Zomi Ordbog*) | 11,831 | From the original PDF; a headword repeated under several Danish labels with identical Zomi is one sense listing every label and page |

First import (2026-10-27): 62,927 entries (43,651 words, 19,270 multi-word terms); 13,633 entries have two or more sources.

## Importing

```bash
python backend/scripts/import_dictionary_sources.py --data-repo ../siamsil-data --dry-run
python backend/scripts/import_dictionary_sources.py --data-repo ../siamsil-data
```

Every file's checksum is checked before anything is written, and all selected sources are imported in one transaction. Re-running adds nothing. A source whose file changed is refused; updating an imported source is not supported yet. PDF sources need poppler's `pdftotext`.

## Known gaps

- Records without a part of speech (mostly 1,451 from the Zomi Standard Dictionary) get their own entry instead of joining one with a part of speech: 788 entries, 499 of which share a headword with another entry. Reviewers merge them.
- Haokip-Lind: one entry (page 182, *bevy*) has the next entry joined to it in the book's own text; it carries a `MERGED_ENTRY` issue. Three entries with no English headword are skipped.

## Next steps

1. Review batches: export about 500 senses per reviewer file, import decisions back (as for corpus reviews).
2. New headwords: candidates from the corpus and community, matched against existing entries before they are added.
3. Release: copy published senses into the SQLite language release, showing each source only as its rights allow.
