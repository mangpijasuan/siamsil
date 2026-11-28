# Release contract: deployment-level verification (PR #116)

Run: 2026-11-28 and updated 2026-11-29, on the branch head after the review fixes. This page records what was verified, how, what was **not**, and what still blocks a production release. Nothing here deployed anything, approved any data, or touched production, R2, Railway or the VPS.

## 1. CI on the latest commit

Commit `29e816e`: Backend tests and Frontend checks passed (both the push and pull-request runs, four checks in all). The PR reported a clean merge state. The Sourcery bot posted a summary only, with no findings.

## 2. The staging drill (`backend/scripts/staging_drill.py`)

A repeatable script that builds small synthetic releases (placeholder strings, never real language data) with the real build code, serves them from a local HTTP server, and runs `fetch_data.py` exactly as the container does with `SIAMSIL_ENVIRONMENT=staging`. Re-run it with `python backend/scripts/staging_drill.py --work <scratch folder>`.

**Result: 52 of 52 scenarios behaved as required** (38 install, rejection and rollback scenarios; 6 signed-bucket scenarios; 8 staging-mode API scenarios, below).

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

### 2a. Signed bucket path (local TLS mock, no credentials)

`s3_scenarios` starts a local HTTPS endpoint that behaves like a path-style S3/R2 bucket: it serves an object only for a correctly signed, unexpired SigV4 query-string request. `fetch_data.py` then runs with `SIAMSIL_DATA_BUNDLE_S3_*` exactly as in production.

| Scenario | Outcome |
|---|---|
| folder layout (`releases/sha256-<digest>/siamsil-data.tar.gz` with `release.json` beside it) | installs |
| flat dated key (`siamsil-data-2026-11-30.tar.gz` with `siamsil-data-2026-11-30.release.json`) | installs |
| wrong secret | refused: "cannot download the data bundle (HTTP 403)"; no signature or link in the log |
| bundle with no manifest beside it | refused (HTTP 404 for the manifest) |
| a manifest key from another release | refused |

Independent signature check: for 3 cases (two key shapes, odd characters in a key, a second region) the presigned URL's signature from `fetch_data.presigned_url` equals the one botocore 1.44.13 produces for the same inputs and timestamp, and the paths are equal. The existing unit test also matches AWS's published example. This proves the signing algorithm, not Cloudflare R2's acceptance of the request.

### 2b. Staging-mode API with PostgreSQL

`api_scenarios` (run with `--database-url`) starts the container's own chain, `fetch_data.py && alembic upgrade head && uvicorn`, with `SIAMSIL_ENVIRONMENT=staging` against a throwaway local PostgreSQL 16 database:

| Scenario | Outcome |
|---|---|
| verified install, migrations, API start | starts; `/health/ready` 200, status ok |
| readiness | application database reported ready |
| rights register | the API reads the verified `json/rights.json` (hash equals the manifest's) |
| `SIAMSIL_RIGHTS_FILE` points elsewhere | the container stops before serving |
| rights register tampered on the volume | `fetch_data` fails, so migrations and the API never run |
| upgrade A to B, then roll back to A | the API serves each release's own register |

Setup note: the first attempt crashed inside SQLAlchemy ("cannot use a string pattern on a bytes-like object") because my throwaway cluster was created with the container's `C` locale (`SQL_ASCII`), where psycopg returns bytes. Creating the cluster with `-E UTF8 --locale=C.UTF-8` fixed it. That was a test-environment problem, not an application bug, but a staging database must be UTF8.

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

- **No real R2, Railway or VPS staging.** I have no staging bucket or credentials and used no production ones. The signed-bucket path is exercised against a local mock and checked against botocore (section 2a), but Cloudflare R2's own behaviour (endpoint, region, permissions, object versioning) is untested.
- **The staging-mode API ran against a local PostgreSQL**, not the real staging database, and not under the real `docker-compose.yml` or Caddy.
- **The restart check is light** (file sizes and the rights register's hash). Same-size corruption of a database is detected only by full verification (`check_release.py --data-root ... --sha256 ...`). Consider scheduling it.
- **The manifest is pinned by hash, not signed**, and `approval` is a recorded claim.
- **Only the language database is bound** to a source commit. The Bible database and JSON files are not.
- **Not end-to-end:** these are script and integration tests on one machine, Linux, one Python version. No load, no concurrent real processes beyond the unit test, no network failure injection beyond 404s and corruption.

## 5. Remaining blockers before a production release

1. **A person approves the real release.** `--approved-by` and `--approved-at` must come from the owner. Nothing here approved real data.
2. **The currently installed production bundle cannot simply be wrapped in a manifest.** Its database predates source-commit recording, so its manifest would be `operator_supplied` and production refuses that. The first production release under this contract needs the language database **rebuilt** with the updated `build_language_db.py`, then packaged and manifested.
3. **Set the manifest pin before restarting any existing staging or production deployment**, or boot stops (by design). The VPS compose requires it.
4. **Run the drill's equivalent against real staging** with the owner's credentials: a staging R2 bucket and a staging API through the real compose file, including a rollback to a previously verified release. The drill's `--database-url` mode and `s3_scenarios` show what to check.
5. **Data-governance CI** (the next PR) should enforce this contract automatically; the protected `data-release.yml` workflow remains paused.
6. **Rights and review are separate gates this work does not open.** The corpus (1,775,043 pairs) is unverified machine text with training and display blocked; no human-reviewed evaluation set is frozen (the one draft has 70 sentences).
