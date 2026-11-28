# Data governance checks

Status: implemented (PR two of the data-governance sequence). It builds on the release contract in [DATA_RELEASES.md](DATA_RELEASES.md) and the rights policy in [RIGHTS_POLICY.md](RIGHTS_POLICY.md). The checks verify mechanical facts. **They do not decide rights, approve language, clear a source or open the paused data-release workflow.**

`ml_pipeline/scripts/data_governance.py` is the one tool. Its output is **counts, ids, file paths and hashes only, never the text of a sentence, headword or evaluation item**, so a log of these checks cannot leak private data (a test enforces this). A failing check exits 1; a warning does not unless `--strict` is given.

## Checks, and where each runs

| Check | What it enforces | Needs | Runs |
|---|---|---|---|
| `registry` | `rights.json` passes the existing rights validator; every source named by `bible_versions.json`, `dictionary_sources.json` and `reference_dictionaries.json` has a rights entry; no forbidden source is referenced; committed `data/versions/*.json` manifests are well formed and hold no restricted path; every pin in `source_files.json` has a full SHA-256 | the app repo only | **app repo CI** (`.github/workflows/data-governance.yml`) |
| `data-repo` | every file in `MANIFEST.sha256` exists and matches; every pinned original matches `source_files.json`; tracked files with no recorded checksum are counted by folder; restricted files present in the archive are reported, and **declared as a pinned or manifest source is a failure** | the private archive | the private repo's CI (template: `docs/templates/siamsil-data-governance.yml`) or locally |
| `exports` | each export manifest admits no uncleared or forbidden source; every exported source is **still** cleared for training in today's register; row counts match the manifest; no exact duplicate across train, validation and test (template variants across splits are warned) | an export folder | locally, or the private CI |
| `release` | a `release.json` against the release contract for the chosen environment; no bundle member or manifest field matches a restricted fragment; evaluation sets and the rights register supplied match the hashes the release declares | a release manifest | locally, and as the gate before publishing |
| `leakage` | evaluation items against training text (an export's files or a language database): exact (normalised), template (numbers and names masked) and near-duplicate (word 3-gram Jaccard, default 0.8) matches | evaluation files and corpus | locally, before freezing an evaluation set and before a release |

The app repo's CI also runs the release-contract tests and the staging drill on small synthetic releases (no private data, no secrets, no artifacts).

## What is forbidden

`forbidden()` combines two sources, so one list cannot silently undo the other:

1. **Derived from `rights.json`:** any source whose training, display and commercial use are all `blocked` or `not_permitted`. Today that is `parallel_corpus`, `zolai_standard_format_2018` and `zomi_bethel_church_web`.
2. **`data/governance.json`:** extra source ids and path fragments that must never appear in a serving, export, training, evaluation or release manifest. It currently names the church website capture, whose entry in `rights.json` records that it holds identifiable people's personal information. This file is an enforcement list written by engineering; it makes no rights decision. **The project owner should confirm or edit it** (`"owner_review": "pending"`).

## Results on the real data (2026-11-28; aggregate only)

- `registry`: passes. 25 rights sources; 9 referenced by configuration; 16 not referenced by any configuration file; 4 committed release manifests; 6 pinned originals.
- `data-repo` on the private archive (commit `70e7f97`, working tree clean): **all 88 files in `MANIFEST.sha256` exist and match; all 6 pinned originals match.** Two warnings:
  - **1,055 of 1,144 tracked files have no recorded checksum** (1,054 under `zomi-data/`, plus `README.md`). They are outside `MANIFEST.sha256`, so a change to them would not be detected.
  - **Two restricted files are present** in the archive (the church website capture, `zomi-data/zomi-data/zomibethelchurch_raw.txt` and `..._norm.txt`). They are not in `MANIFEST.sha256` and not pinned, so they are not in any build input, but they sit in the same repository as the data. The review's recommendation to hold them in a separately access-controlled area is supported by this finding. Moving them is a decision for the owner.
- `leakage`, the 70-sentence English→Zomi **draft** against all 1,775,043 corpus pairs: no exact, near-duplicate or template matches (2 min 19 s). This does not make the draft an evaluation set: it is unreviewed, not frozen, and small.
- `exports`: no export folder exists in this checkout, so it was exercised only by the synthetic tests.
- The private archive has no `.github` folder, so it currently runs no automated checks of its own; the template is the proposed starting point.

## Limitations

- **Presence in a private repository is not isolation.** `data-repo` reports restricted files and refuses to let them become declared sources; it cannot enforce who can read them. Moving them out is a separate, owner-approved step.
- **Near-duplicate detection is lexical** (word 3-grams). It will not find paraphrases or translations of the same meaning. A frozen evaluation set still needs human independence.
- **Leakage over the full corpus takes minutes in pure Python.** Run it locally or in the private CI, not on every pull request.
- **`registry` cannot see the private archive.** Anything that depends on private files is checked only where those files exist.
- **A check passing is not a clearance.** Rights stay `needs_review` until a person records evidence in `rights.json`.

## Decisions, migration and setup (documents for the owner)

- [GOVERNANCE_DECISIONS.md](GOVERNANCE_DECISIONS.md): what `data/governance.json` does and the decisions it needs (it is `owner_review: pending`; the checks report that state and never write it).
- [RESTRICTED_SOURCE_MIGRATION.md](RESTRICTED_SOURCE_MIGRATION.md): a non-destructive plan for the two church-capture files. Nothing has been moved. `data-repo --require-quarantined` fails while they are tracked and passes after an approved migration.
- [PRIVATE_REPO_GOVERNANCE_SETUP.md](PRIVATE_REPO_GOVERNANCE_SETUP.md): the permissions checklist for enabling the workflow in `siamsil-data`.

## Not in this PR (next in the sequence)

Aligning the sole-owner linguistic approval documents and workflows; the protected human evaluation workflow; security headers, secret scanning, an end-to-end smoke test and a restore drill. The protected `data-release.yml` workflow remains paused.
