# Immutable Siamsil data releases (operator runbook)

> **SAFETY HOLD: do not run the data-release workflow.** PR #64 exposed restricted source-derived data through public workflow artifacts and left out the rights, review and holdout gates. `.github/workflows/data-release.yml` is now a stub that fails on purpose (`release_safety_hold`). Do not unpause it, and never upload a private bundle as a workflow artifact in this public repository. It stays paused until the hardening under [Future hardening](#future-hardening) is built and the owner approves in writing. Releases to the private bucket follow the manual route in [DEPLOY.md](DEPLOY.md) for now. This page keeps the topology, the verification checks and the rollback procedure for bundles that were already approved.

This workflow connects the private **siamsil-data** source archive to reproducible build artifacts, not to live GitHub requests from the website. It supplements [DEPLOY.md](DEPLOY.md). **Never put restricted originals, R2 credentials, or bundles in the public application repository.**

## Release topology

Private `siamsil-data` clone → pinned SHA-256 sources (`data/source_files.json`) → build SQLite language/Bible databases → package an API data bundle → integrity checks → SHA-256-specific private R2 key → Railway deployment by selecting a known key+digest → API health check and in-container installed-release verification.

A new source commit, including terminology corrections, does **not** imply permission to publish it. Human review and rights gates remain separate; a release must be explicitly initiated. The live application does not hot-read the source repo.

## The release manifest contract (release.json, schema 2)

`release.json` says what a bundle is. Schema 1 (bundle digest, per-file digests, creation time) is kept as it was; **schema 2 extends it** and is what the code in `backend/scripts/release_contract.py` checks. Schema 1 is accepted only when `SIAMSIL_ENVIRONMENT` is `development` or `test`; staging and production require schema 2.

| Field | What it declares | Checked |
|---|---|---|
| `source.siamsil_data_commit`, `source.working_tree_clean` | the `siamsil-data` commit the bundle was built from, and that no uncommitted change was in the tree | 40-hex SHA; production needs a clean tree |
| `rights_registry.sha256` | digest of `json/rights.json` | equals the digest in `contents` and the installed file; optionally equals `SIAMSIL_RIGHTS_SHA256` |
| `approval.status`, `approved_by`, `approved_at_utc` | `unapproved` or `approved`, and by whom and when | production needs `approved` with a name and a time. **Only a person supplies these** (`--approved-by`, `--approved-at`); no tool or AI approves a release |
| `exports.approved_counts`, `export_manifest_sha256` | export counts per split, from an `export_datasets.py` manifest | refused if that manifest admitted any uncleared source |
| `protected_evaluation.sets`, `sets_sha256` | evaluation sets by name, SHA-256, item count and `frozen`; never their text | structure and the combined hash |
| `derivation.parallel_corpus` | source rows, rows kept, rows removed by reason, and the SHA-256 of the per-row removal record | `source_rows = kept + removed`; the record is checked against the kept pairs |

### Where the 1,777,002 → 1,775,043 difference comes from

`build_language_db.py` writes `parallel-removals.jsonl` beside the database: one line per row left out, `{"source_row": N, "reason": "duplicate_pair" | "empty_side", "pair_hash": ...}`, with the row's position in the source stream and, for duplicates, the pair hash. It holds no text. `release_contract.check_derivation` re-derives the claim: the file matches its SHA-256, its counts match the manifest, every removed duplicate's hash is present among the kept pairs, and the database holds `kept` pairs. Keep the file beside `release.json` in the private bucket.

### Building and installing

```bash
# development bundle, schema 1
python backend/scripts/release_manifest.py dist/siamsil-data.tar.gz --output dist/release.json
# production release, schema 2 (see the script's docstring for every option)
python backend/scripts/release_manifest.py dist/siamsil-data.tar.gz --output dist/release.json --production \
  --data-repo ../siamsil-data --no-exports --quality-report data/processed/language/quality_report.json \
  --removals data/processed/language/parallel-removals.jsonl --eval-set data/evaluation/human/en-zomi-v1.jsonl \
  --approved-by "<name>" --approved-at 2026-11-30T09:00:00
```

The command prints the manifest's own digest. Upload `release.json` beside the bundle (a folder per release holds `release.json`; a flat dated name `siamsil-data-2026-11-30.tar.gz` gets `siamsil-data-2026-11-30.release.json`; `SIAMSIL_DATA_RELEASE_MANIFEST_KEY` overrides) and set `SIAMSIL_DATA_RELEASE_MANIFEST_SHA256` with the bundle's digest. On boot `fetch_data.py` verifies the manifest against its pin, every unpacked file against the manifest, and the rights register against its declared digest, **before** it replaces anything live; any failure installs nothing. A restart re-checks the stored copy (`/data/.release.json`): file sizes and the rights register's digest. `check_release.py --data-root /data --sha256 <bundle>` hashes every installed file.

### Rollout note for existing production deployments

An environment that already runs a bundle has no manifest. Before restarting it in staging or production, upload a schema 2 `release.json` for that bundle and set `SIAMSIL_DATA_RELEASE_MANIFEST_SHA256`; until then `fetch_data.py` stops with a message naming what is missing. The VPS compose file now requires the variable.

### What this does not do

It is not a signature: the manifest is protected by its pinned SHA-256, as the bundle is, so someone who can change both the bucket objects and the deployment settings can still change both. `approval` is a person's recorded decision; the verifier checks it is present and well formed, not that it is true. It grants no licence and does not review any language. The protected data-release workflow stays paused.

## Required GitHub setup (one-time, performed by repo owner)

1. In GitHub Environments, create `siamsil-data-release` and configure required reviewers for production uploads. Environment protection availability varies with the GitHub plan and repository visibility.
2. Add repository/environment secret `SIAMSIL_DATA_READ_TOKEN`: short-lived or tightly scoped read-only access to the private `mangpijasuan/siamsil-data` repository. Prefer a GitHub App installation token if your runner provisioning supports it.
3. For R2 publishing only, add `SIAMSIL_R2_WRITE_KEY_ID`, `SIAMSIL_R2_WRITE_SECRET`, and `SIAMSIL_R2_ENDPOINT` as environment secrets. Set `SIAMSIL_R2_BUCKET` as an environment variable. Limit the write token to the single private bucket; rotate it according to policy.
4. Do not configure personal secrets in code or PR comments. The action's checkout of the private data repo and its upload step cannot run successfully without these settings.
5. Keep the private source repo and its large tracked assets accessible to GitHub Actions. Account for Git LFS and GitHub bandwidth quotas before running; this workflow does not download an uncommitted local `zomi-data.zip`.

## Build and release (suspended)

The workflow-based build below is **not available while the hold is in place.** The earlier procedure produced `dist/siamsil-data.tar.gz` and `dist/release.json` and saved them as a workflow artifact; that is the step that exposed data and it has been removed. Do not recreate it.

When a release is approved by the owner, the bundle is built and uploaded on the computer that holds `siamsil-data`, as in [DEPLOY.md](DEPLOY.md). Each release goes to an immutable, digest-specific key:

```text
releases/sha256-<full-bundle-sha256>/siamsil-data.tar.gz
releases/sha256-<full-bundle-sha256>/release.json
```

Each release receives an immutable, digest-specific key. Keep older keys for rollback; do not republish different bytes under the same key. To promote a release, update these Railway settings together and redeploy:

```text
SIAMSIL_DATA_BUNDLE_S3_KEY=releases/sha256-<full-bundle-sha256>/siamsil-data.tar.gz
SIAMSIL_DATA_BUNDLE_SHA256=<full-bundle-sha256>
```

R2 access remains private; the FastAPI container fetches the selected bundle via its read-only R2 credentials. Promotion is a separate owner-controlled step and is NOT performed by this GitHub workflow.

## Verify and roll back

Run:

```bash
python backend/scripts/check_release.py --url https://api.siamsil.org
```

This confirms the HTTPS API returns readiness and a language database. The health response alone **cannot** prove the specific release digest. For on-host verification within the API container (with `/data` mounted), run:

```bash
python scripts/check_release.py --url http://127.0.0.1:8000 \
  --data-root /data --sha256 <expected-full-bundle-sha256>
```

The local check validates the installed `.bundle-<sha256>` marker and required database files. It is not a remote cryptographic attestation; the bundle itself was verified against SHA-256 when installed.

Rollback is controlled by selecting the **previous immutable key and its matching SHA-256** in Railway, redeploying, and repeating both checks. Preserve a release ledger recording code commit, source-repo commit, bundle SHA, R2 key, rollout timestamp, reviewer, benchmark results, and permission approval. Database schema compatibility and application version compatibility must be checked before rollback.

## Future hardening

Before unattended production promotion: add a protected training/evaluation pipeline, rights and human-review approvals, semantic API smoke checks, explicit source commit pins, database compatibility checks, remote release-version endpoint, and an alerting monitor. Do not treat this workflow as complete autonomous production synchronization.
