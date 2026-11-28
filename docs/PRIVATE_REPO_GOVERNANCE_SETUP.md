# Enabling the governance workflow in the private `siamsil-data` repository

Status: prepared, **not enabled**. I cannot change `siamsil-data` from this session, and enabling it is your decision after reviewing the permissions below. The workflow file is `docs/templates/siamsil-data-governance.yml`; it fails on purpose until a reviewed checker commit is set.

## What it does and what it can see

It checks out the private archive and the public app repo, then runs `data_governance.py data-repo`: every file in `MANIFEST.sha256` exists and matches, the pinned originals match `data/source_files.json`, files with no recorded checksum are counted, and restricted files are reported (or, with `--require-quarantined`, fail). Its log holds counts, paths and hashes only; a test enforces that no record text is printed.

Because it checks out the **whole** archive, anything the workflow runs can read all of it. That is why the checker is pinned to a commit you have reviewed rather than to a moving branch.

## Evidence it works

A clean `git clone` of `siamsil-data` (what a CI checkout sees, with nothing ignored or untracked) gives the same result as the working copy: 88 of 88 declared files match, 6 of 6 pins match, 1,055 tracked files have no recorded checksum, and the 2 restricted files are reported. This was run locally; the workflow itself has never run in `siamsil-data`.

## Review checklist before enabling

| # | Item | Recommended | Why |
|---|---|---|---|
| 1 | Workflow `permissions` | `contents: read` only (already set) | no write access, no tokens that can push or publish |
| 2 | Secrets in the repo | none; the workflow needs none (the app repo is public) | PR #64 exposed restricted data through public workflow artifacts; this workflow needs no credentials at all |
| 3 | Artifacts | the workflow never uploads any; do not add `actions/upload-artifact` or caches of data | uploaded artifacts in a public repo exposed restricted data before |
| 4 | Checker version | set `CHECKER_REF` to a reviewed commit SHA of `mangpijasuan/siamsil` (the step fails while it is the placeholder) | a moving `main` could change what runs against the archive without review |
| 5 | Allowed actions | Settings, Actions, General: allow only the GitHub-owned actions used (`actions/checkout`, `actions/setup-python`); consider pinning them to commit SHAs | supply-chain risk |
| 6 | Default workflow permissions | read-only | defence in depth |
| 7 | Forks and outside collaborators | require approval before workflows run; keep forks disabled for this private repo | untrusted code would otherwise run next to private data |
| 8 | Branch protection | require the `Data governance (siamsil-data)` check on `main` | the check is only useful if a failing one blocks the merge |
| 9 | Log retention | the shortest retention you accept | logs hold paths and counts, not content, but need no long life |
| 10 | Who can edit workflows | owner only (optionally a CODEOWNERS rule for `.github/` and `MANIFEST.sha256`) | the workflow is itself a control |
| 11 | Git LFS | not used today (`.gitattributes` has no LFS rules); if that changes, enable `lfs: true` in the template | otherwise large files would appear missing |

## Steps (yours; I have not done any)

1. Review this checklist and the template.
2. Choose the checker commit and set `CHECKER_REF` (after PR #116 and #117 are merged, use the merge commit).
3. Copy the template to `siamsil-data/.github/workflows/data-governance.yml` and commit it on a branch; open a pull request in that repo and read the first run's log.
4. Apply the settings in rows 5, 6, 7 and 8.
5. After the church-capture migration, switch the step to `--require-quarantined` (the template has the line commented).

## What it does not do

It does not decide rights, approve data or language, or isolate files from people who can already read the repository. The archive has no automated checks of its own today; this adds checksum and restricted-source enforcement, nothing more.
