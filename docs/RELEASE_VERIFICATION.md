# Release contract: deployment-level verification (PR #116)

Run: 2026-11-28, on the branch head after the review fixes. This page records what was verified, how, what was **not**, and what still blocks a production release. Nothing here deployed anything, approved any data, or touched production, R2, Railway or the VPS.

## 1. CI on the latest commit

Commit `29e816e`: Backend tests and Frontend checks passed (both the push and pull-request runs, four checks in all). The PR reported a clean merge state. The Sourcery bot posted a summary only, with no findings.

## 2. The staging drill (`backend/scripts/staging_drill.py`)

A repeatable script that builds small synthetic releases (placeholder strings, never real language data) with the real build code, serves them from a local HTTP server, and runs `fetch_data.py` exactly as the container does with `SIAMSIL_ENVIRONMENT=staging`. Re-run it with `python backend/scripts/staging_drill.py --work <scratch folder>`.

**Result: 38 of 38 scenarios behaved as required.**

| Area | Scenario | Outcome |
|---|---|---|
| Startup | correct bundle and pinned manifest | installs; marker and stored manifest written |
| Startup | restart | stored manifest re-checked, starts |
| Startup | full on-container verification (`check_release.py` logic) | hashes every file, passes |
| Missing | manifest missing (HTTP 404) | refused: "cannot download the release manifest (HTTP 404)" |
| Missing | bundle missing (HTTP 404) | refused: "cannot download the data bundle (HTTP 404)" |
| Missing | manifest pin not set | refused |
| Missing | no bundle installed and none configured | refused, not skipped |
| Missing | bundle configured, no manifest address | refused |
| Missing | bundle marker present, stored manifest missing | refused |
| Corrupted | altered bundle download | refused (checksum mismatch); volume left empty |
| Corrupted | edited manifest | refused (does not match its pin) |
| Corrupted | `rights.json` changed after install | refused on restart |
| Corrupted | database size changed after install | refused on restart |
| Corrupted | database changed, same size | **passes the restart check** (known limitation, below); caught by full verification |
| Mismatched | manifest of another bundle | refused |
| Mismatched | wrong manifest pin | refused |
| Mismatched | manifest declares a rights hash the bundle does not carry | refused |
| Mismatched | configured rights snapshot differs | refused |
| Mismatched | `SIAMSIL_RIGHTS_FILE` points at a different register | refused |
| Mismatched | legacy (schema 1) manifest | refused in staging, accepted in development |
| Unapproved | unapproved release | refused in staging, accepted in development |
| Unapproved | database built from a dirty data repository | refused |
| Unapproved | source commit not recorded in the database | refused |
| Rollback | install A, upgrade to B | B's files replace A's |
| Rollback | upgrade to a damaged C | refused; B untouched |
| Rollback | roll back to A leaving B's manifest hash set (the documented mistake) | refused; nothing changed |
| Rollback | roll back to A with A's bundle, manifest and hashes together | volume is exactly A again; restart passes |

The approval on the drill's synthetic releases reads `STAGING-DRILL-FIXTURE (not an owner approval)`. It only exercises the "approved" code path; it approves no data.

## 3. Real-size check (542 MB bundle, 1.6 GB database)

The bundle from a full rebuild of the language database in a scratch copy, with the real manifest built by `release_manifest.py` (originals read-only, nothing written to the repository or `data/raw`). Its release manifest is **unapproved**, as it should be.

| Check | Result |
|---|---|
| Staging policy | refused in 0.1 s, **before** the 542 MB download, because the manifest is unapproved; the volume stayed empty |
| Development policy, fresh volume | downloaded, fully verified and installed in 32.9 s (local disk and loopback) |
| Restart | 0.1 s (stored-manifest check) |
| API started on the installed volume (development settings) | live in about 3 s; `/health/ready` 200 in 0.18 s; 50,282 dictionary senses and 1,775,043 corpus pairs; a dictionary query returned results |
| Rights register | the API read the installed `json/rights.json`, whose hash equals the manifest's declared hash; `parallel_corpus` display remains denied |

## 4. What was not verified (limitations)

- **No R2 or Railway/VPS staging.** I have no staging bucket or credentials and did not use any production ones. The drill uses the plain-URL path (`SIAMSIL_DATA_BUNDLE_URL`); the presigned R2 path is covered only by the existing signing unit tests, and the manifest-key derivation by a unit test.
- **The API was not started in staging mode.** Staging and production require PostgreSQL, which this environment lacks. The settings guard (rights override) is unit tested; a Postgres-backed start under the real compose file is untested.
- **The restart check is light** (file sizes and the rights register's hash). Same-size corruption of a database is detected only by full verification (`check_release.py --data-root ... --sha256 ...`). Consider scheduling it.
- **The manifest is pinned by hash, not signed**, and `approval` is a recorded claim.
- **Only the language database is bound** to a source commit. The Bible database and JSON files are not.
- **Not end-to-end:** these are script and integration tests on one machine, Linux, one Python version. No load, no concurrent real processes beyond the unit test, no network failure injection beyond 404s and corruption.

## 5. Remaining blockers before a production release

1. **A person approves the real release.** `--approved-by` and `--approved-at` must come from the owner. Nothing here approved real data.
2. **The currently installed production bundle cannot simply be wrapped in a manifest.** Its database predates source-commit recording, so its manifest would be `operator_supplied` and production refuses that. The first production release under this contract needs the language database **rebuilt** with the updated `build_language_db.py`, then packaged and manifested.
3. **Set the manifest pin before restarting any existing staging or production deployment**, or boot stops (by design). The VPS compose requires it.
4. **Run the drill's equivalent against real staging**: a staging bucket, a Postgres-backed staging API, and a rollback to a previously verified release. This needs credentials only the owner holds.
5. **Data-governance CI** (the next PR) should enforce this contract automatically; the protected `data-release.yml` workflow remains paused.
6. **Rights and review are separate gates this work does not open.** The corpus (1,775,043 pairs) is unverified machine text with training and display blocked; no human-reviewed evaluation set is frozen (the one draft has 70 sentences).
