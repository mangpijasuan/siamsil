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

**Primary source (project owner's decision, 2026-10-30): the 50K Translation Master.** Having compared a review batch of all five sources side by side, the project owner, a Zomi speaker, judged it the best. Its senses are the ones reviewed and published. The other four sources are kept as **reference**: imported and unchanged, shown to reviewers beside each 50K sense under "Other sources say", but not reviewed or published on their own. The `role` of each source in `data/dictionary_sources.json` records this; `dictionary_review.py export --all-sources` or `--source ID` reaches the reference sources when needed.

Listed in import order in [`data/dictionary_sources.json`](../data/dictionary_sources.json), each pinned by checksum, with rights in [DATA_RIGHTS.md](DATA_RIGHTS.md).

| Source | Senses | Notes |
|---|---:|---|
| 50K Translation Master, native-review workbook | 50,282 | 49,844 open QC issues, 7,017 of them about the source as a whole |
| Essential 3000 | 5,342 | 26,685 example sentences and phrases |
| Zomi Standard Dictionary (live dictionary) | 20,826 | Zomi definitions; 1,773 flagged rows become issues |
| Haokip-Lind 2011 (*Zomi Ordbog*) | 11,831 | From the original PDF; a headword repeated under several Danish labels with identical Zomi is one sense listing every label and page |
| TongDot (tongdot.com), partial interim copy | 4,999 | First 5,000 of 75,931 lines, until TongDot sends the full file. Labels no languages: 1,593 Burmese glosses become `my`; 3,406 others become `ctd` glosses, each with an open `VARIETY_CHECK` issue, because many are Hakha, Falam or other Chin, not Tedim. 1,092 of its headword–part-of-speech pairs join existing entries; 986 headwords are new |

First import (2026-10-27): 62,927 entries (43,651 words, 19,270 multi-word terms); 13,633 entries have two or more sources.

## What the app shows

Since 2026-10-30 the Dictionary page, Translate, and Siamsil AI show the **50K Translation Master**: 50,282 senses, English headword → Zomi equivalents, with the simple English definition, domain and usage tier. `build_language_db.py` reads it from siamsil-data (`data/source_files.json`, key `dictionary_50k`) into the read-only language release. Every entry is labelled unreviewed until reviewers approve it. Zomi → English searches put entries whose Zomi is exactly the word searched first. `build_language_db.py --dictionary standard` still builds from the Zomi Standard Dictionary.

Next: publish from the editorial dictionary instead, showing each approved 50K sense as reviewed.

## Importing

```bash
python backend/scripts/import_dictionary_sources.py --data-repo ../siamsil-data --dry-run
python backend/scripts/import_dictionary_sources.py --data-repo ../siamsil-data
```

Every file's checksum is checked before anything is written, and all selected sources are imported in one transaction. Re-running adds nothing. A source whose file changed is refused; updating an imported source is not supported yet. PDF sources need poppler's `pdftotext`.

## Known gaps

- TongDot: a reviewer must confirm each Chin gloss is Tedim (`VARIETY_CHECK`) before approving it; reject the others. 186 Burmese glosses also contain English or Chin words (`MIXED_SCRIPT`).

- Records without a part of speech (mostly 1,451 from the Zomi Standard Dictionary) get their own entry instead of joining one with a part of speech: 788 entries, 499 of which share a headword with another entry. Reviewers merge them.
- Haokip-Lind: one entry (page 182, *bevy*) has the next entry joined to it in the book's own text; it carries a `MERGED_ENTRY` issue. Three entries with no English headword are skipped.

## Reviewing

Senses are reviewed in batches with `backend/scripts/dictionary_review.py`, in the same two human steps as corpus reviews (SOP-07): a reviewer judges each sense, then a lead editor who did not review it approves it. Nothing is approved automatically. Decisions are appended to `reviews/dictionary-reviews.jsonl` in the private siamsil-data repository and never edited. Each exported batch is recorded in `reviews/dictionary-batches.jsonl`, so no two reviewers get the same senses. Reviewer codes are checked against `reviews/roster.csv` (`code,role`, roles `reviewer` and `lead_editor`). Names never appear in the decisions.

```bash
python backend/scripts/dictionary_review.py export --reviewer R01 --out batch-R01-1.xlsx   # 500 senses
python backend/scripts/dictionary_review.py export --reviewer R02 --out tongdot-R02.xlsx --source tongdot --issue VARIETY_CHECK
python backend/scripts/dictionary_review.py record --sheet batch-R01-1.xlsx --reviewer R01
python backend/scripts/dictionary_review.py approval-sheet --out approve-1.xlsx
python backend/scripts/dictionary_review.py approve --sheet approve-1.xlsx --approver E01
python backend/scripts/dictionary_review.py apply      # sets review_status in the database
python backend/scripts/dictionary_review.py status
```

A batch holds 50K senses only, starting with words that the most sources share, then common words (usage tiers A1 to C2). Next to the Zomi to check it shows what the other sources say and any open flags. Reviewers choose one decision per row:

| Decision | Meaning | Result |
|---|---|---|
| `correct` | Right and natural Tedim for this meaning | Ready for the lead editor; `approved` once approved |
| `fix` | Should change; the full corrected Zomi goes in *Corrected Zomi* | `needs_correction`; the correction is kept for editors and never replaces the text automatically |
| `not_tedim` | Another Chin language, or not Zomi | `rejected` |
| `wrong` | The Zomi does not mean this | `rejected` |

Each review records a fingerprint of the Zomi the reviewer saw. If that text changes later, the review no longer counts, and the sense goes back for review.

### Corrections

A `fix` changes the dictionary only after a lead editor who did not propose it approves it:

```bash
python backend/scripts/dictionary_review.py corrections-sheet --out corrections-1.xlsx
python backend/scripts/dictionary_review.py revise --sheet corrections-1.xlsx --approver E01
python backend/scripts/dictionary_review.py apply      # writes approved corrections, then sets statuses
```

- The corrections sheet lists each reviewer's correction beside the current Zomi. The lead editor chooses `approve` or `decline`.
- `revise` appends each decision to `reviews/dictionary-revisions.jsonl` in siamsil-data:
  - an approval is a `revision` record with the Zomi before and after, who proposed it and who approved it;
  - a declined correction is not offered again, and the sense stays open for review.
- `apply` writes approved corrections into the editorial database and marks those senses `approved`, since a reviewer wrote the correction and a lead editor approved it.
- `build_language_db.py` applies the same file to the language release, so Dictionary, Translate and Siamsil AI show the corrected Zomi as verified.
- Both steps change a sense only while it still holds the text that was corrected. The 50K workbook itself is never edited.

### Terms

Some English words need the same Zomi decision across many senses. For example, the project owner said on 2026-10-31 that *refugee* is **galtaimi**: **cimawh**, **dongtuak** and **galtaimi** all mean refugee, chosen by context, and **cimawh**, **dongtuak**, **liangvai** and **genthei** all mean someone helpless.

`data/dictionary_terms.json` records each such term:
- the English words it covers;
- the Zomi words to choose from;
- who decided it and when, and whether a second person has confirmed it;
- optional mechanical replacements, which draft a suggestion (for refugee: `gamtaik mi` → `galtaimi`, so `gamtaik mite` → `galtaimite`).

```bash
python backend/scripts/dictionary_review.py export --reviewer R01 --term refugee --out refugee-R01.xlsx
```

A term sheet holds every unreviewed 50K sense whose headword uses the term: 348 senses for *refugee*, 279 of them with a suggested draft. Each row has two extra columns:
- *Term words*: the term's Zomi words and when to use each;
- *Suggested Zomi (AI draft)*: the Zomi with the replacements applied.

The draft is only a starting point: the reviewer chooses `fix` and writes the right wording (the draft, or another word if the context needs it), or `correct` if the Zomi is already right. Corrections then follow the steps above. Nothing is replaced in bulk.

## Next steps

1. New headwords: candidates from the corpus and community, matched against existing entries before they are added.
2. Release: copy published senses into the SQLite language release, showing each source only as its rights allow. Approved corrections already reach it (see Corrections).
