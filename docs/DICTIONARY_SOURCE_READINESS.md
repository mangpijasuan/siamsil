# Dictionary source readiness (path to 100,000 headwords)

Counts come from the editorial database (`siamsil_local`), 2026-11-15. A headword is counted once per source, lower-cased. Every sense in every source is `draft` / `unreviewed`. Nothing here adds or invents Zomi text.

## Headword count

| Source | Senses | Headwords | Only in this source | Also in another |
|---|---:|---:|---:|---:|
| English–Zomi–Burmese Translation Master (50K) | 50,282 | 47,060 | 35,424 | 11,636 |
| Zomi Standard Dictionary | 20,826 | 19,254 | 7,743 | 11,511 |
| Haokip–Lind 2011 | 11,829 | 11,173 | 1,154 | 10,019 |
| Essential 3000 | 5,342 | 2,992 | 70 | 2,922 |
| TongDot (partial, first 5,000 of 75,931 lines) | 4,999 | 2,022 | 730 | 1,292 |
| **Union** | 93,278 | **59,241** | | |

Gap to 100,000: about 40,760 headwords.

## What blocks each source

| Source | Display | Train | Blocker | Who can clear it |
|---|---|---|---|---|
| Translation Master 50K | needs_review | needs_review | Corrected 2026-11-17: compiled by the owner from internet sources, not authored by the owner. Sources, licenses and rights holders are being identified; the 2026-10-26 training sign-off does not cover third-party material. Display not granted; 0 senses human-reviewed | Owner identifies each source; rights holders where licensed; then a second person |
| Essential 3000 | needs_review | needs_review (owner signed off) | Same as above | Owner + a second person |
| Haokip–Lind 2011 | needs_review | needs_review | Written permission reported from both holders; need each permission's date and where the copy is kept, plus second-person confirmation. Source PDF came from a third-party upload (kupdf.net). Redistribution and commercial use not granted | Owner records evidence; second person confirms |
| TongDot | needs_review | needs_review | Permission is verbal or by message, not written. Only 5,000 of ~75,931 lines held; the full file is pending from TongDot | TongDot (written permission and the full file) |
| Zomi Standard Dictionary | needs_review | needs_review | Compiler and copyright holder not recorded; file name says it was AI-cleaned and what changed is not recorded | Whoever compiled it, if known |

## Biggest gains

- TongDot's full file is the largest unused source: about 75,931 lines against the 5,000 held now. It needs written permission first.
- Zomi Standard Dictionary adds 7,743 headwords found nowhere else, but its provenance is unknown.
- The 50K source already covers 47,060 headwords. It is the base, and its blocker is identifying where its content came from.

## Steps for each source (DATA_RIGHTS.md, "Closing an item")

1. Record the evidence (written permission, date, where kept) in `docs/DATA_RIGHTS.md`.
2. Update `data/raw/**/provenance.json` and `data/rights.json`.
3. A second person confirms before anything changes to `cleared`.

Human editorial decisions are final; this file only reports status.
