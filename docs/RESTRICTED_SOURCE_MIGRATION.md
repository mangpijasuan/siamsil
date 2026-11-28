# Plan: moving the church-capture files to restricted storage

Status: **a plan for the owner's decision. Nothing has been moved, copied, deleted or committed in `siamsil-data`.** Every step below that changes anything needs your explicit approval, one step at a time. It records no rights decision and requests no permission from the church.

## 1. What is affected (read-only facts, 2026-11-29)

| | `zomi-data/zomi-data/zomibethelchurch_raw.txt` | `zomi-data/zomi-data/zomibethelchurch_norm.txt` |
|---|---|---|
| Size | 40,675 bytes, 89 lines | 0 bytes (an empty file) |
| SHA-256 | `cf458e558677008158b8f2091de2a679a9f5c9a26d243747a8827c64fd9522f0` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (the empty-file hash) |
| Added to the archive | commit `affbd03`, 2026-10-30 ("Make the Aug 18 dictionary the master; move the Paumkim dataset to zomi-data/") | same commit |
| Rights register | `zomi_bethel_church_web`: display, training and commercial use all `not_permitted`; `rights.json` records that the capture holds identifiable people's personal information and says never to use or show it | same source |

Where they are mentioned: `siamsil-data/README.md` (one table row); `zomi-data/siamsil-source-manifest.json` (an upstream snapshot manifest listing both files with their hashes); `zomi-data/zomi-data/extract.py` (a script in the upstream dataset that mentions them); and, in the app repo, `data/rights.json`, `docs/DATA_RIGHTS.md`, `data/governance.json` and `docs/DATA_GOVERNANCE.md`.

Checks already made:
- **Not a build input.** They are not in `MANIFEST.sha256`, not pinned in `data/source_files.json`, and no script in the app repo reads the `zomi-data/` folder. Moving them cannot break a build.
- **Not duplicated elsewhere in the archive.** 31 of the capture's 89 lines are long enough to be distinctive. None of them appears as an exact line in any of the other 1,052 files under `zomi-data/` (counts only; nothing was printed). This does not rule out re-encoded or re-normalised copies.
- **Not the only exposure.** The files also exist in the upstream public dataset the capture came from (per `rights.json`); this plan cannot change that.

## 2. Goals and non-goals

Goals: put the files behind access control that is **separate** from the archive that builds and releases data; keep the originals byte-identical; keep their provenance; keep builds and checks unaffected; leave an audit trail.

Non-goals: this does not delete anything irreversibly, change any rights status, contact the church, or approve any use of the content.

## 3. A limit you should know about first: git history

Removing the files from the working tree does **not** remove them from the repository's history. Anyone with read access to `siamsil-data` can still fetch them from commit `affbd03` onward. Moving the files makes the archive's current state clean and keeps them out of every manifest and bundle; it does not make the repository itself a safe place for the content. Three options:

| Option | Effect | Cost and risk |
|---|---|---|
| **A. Move, and keep `siamsil-data` access as narrow as it is now** | working tree and releases clean; history still holds the files | simple, reversible; relies on who can read the repo (please confirm) |
| **B. A, plus rewrite history** (`git filter-repo`) to drop the two paths | the files leave the repository entirely | **destructive.** Changes every commit hash after `affbd03`. Invalidates the recorded source commit (`70e7f97…`) and every clone; any release manifest that names an old commit stops matching. Needs a verified backup, a re-record of provenance, and your explicit approval |
| **C. Leave in place, rely on `data-repo` warnings** | nothing changes | not recommended: the files stay beside the build data |

Recommendation: **A now**, and decide on B only if the people who can read `siamsil-data` are not all people who may see members' personal information.

## 4. Destination options

| Option | Fit |
|---|---|
| **1. A separate private repository** (for example `siamsil-data-restricted`) with owner-only access, no Actions, no forks, no LFS | keeps git provenance; simplest; **recommended** |
| **2. An encrypted archive in storage only you control** (checksum and provenance record kept in `siamsil-data`) | no cloud copy of the content; more manual |
| **3. Delete after verified backup elsewhere** | only with your explicit decision; irreversible in practice |

## 5. Steps (none executed; each needs your approval)

0. **Decisions needed:** destination (4), history option (3), who may read the destination, and where the provenance record lives.
1. **Freeze and back up.** `git bundle create` a full backup of `siamsil-data` and record its SHA-256. Re-verify the two files' hashes against section 1.
2. **Provenance record**, written before any move: for each file, the upstream dataset and path (`paumkim/zomi-dataset` per `rights.json`), the path in the archive, bytes, SHA-256, the commit and date it was added (`affbd03`, 2026-10-30), the rights status and reason (without repeating the personal information), the date and the name of the person who approved this move. No file content in the record.
3. **Copy, do not move.** Copy both files to the destination, then verify byte-identical hashes.
4. **Remove from `siamsil-data`** in one reviewed commit: delete the two files and add `zomi-data/QUARANTINE_NOTICE.md` pointing at the provenance record (no content). Update the README row. **Leave `zomi-data/siamsil-source-manifest.json` untouched** (it is an upstream snapshot); the notice explains why it still lists them.
5. **Verify.** `python3 ml_pipeline/scripts/data_governance.py --data-dir data data-repo --data-repo ../siamsil-data --require-quarantined` must pass (it fails today, by design); `MANIFEST.sha256` still verifies; a normal build is unchanged.
6. **Lock the destination.** Owner-only access, Actions disabled, forks disabled, secret scanning on, no artifacts.
7. **Keep the guard.** The path fragment `zomibethelchurch` stays in `data/governance.json`, so re-adding the files to any manifest, pin or bundle fails the checks. After this migration, switch the private archive's workflow to `--require-quarantined`.

**Rollback:** steps 3 and 4 are reversible: the files are unchanged in history and in the destination; reverting the step 4 commit restores them.

## 6. What stays true throughout

- The files remain `not_permitted` for display, training and commercial use. Moving them clears nothing.
- `data/raw/` is not touched. No source file is modified; originals are copied byte-for-byte.
- Whether to ask the church for permission is separate and is yours to decide (`rights.json` names who to ask).
