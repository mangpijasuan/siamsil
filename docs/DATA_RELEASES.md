# Immutable Siamsil data releases (operator runbook)

This workflow connects the private **siamsil-data** source archive to reproducible build artifacts, not to live GitHub requests from the website. It supplements [DEPLOY.md](DEPLOY.md). **Never put restricted originals, R2 credentials, or bundles in the public application repository.**

## Release topology

Private `siamsil-data` clone → pinned SHA-256 sources (`data/source_files.json`) → build SQLite language/Bible databases → package an API data bundle → integrity checks → SHA-256-specific private R2 key → Railway deployment by selecting a known key+digest → API health check and in-container installed-release verification.

A new source commit, including terminology corrections, does **not** imply permission to publish it. Human review and rights gates remain separate; a release must be explicitly initiated. The live application does not hot-read the source repo.

## Required GitHub setup (one-time, performed by repo owner)

1. In GitHub Environments, create `siamsil-data-release` and configure required reviewers for production uploads. Environment protection availability varies with the GitHub plan and repository visibility.
2. Add repository/environment secret `SIAMSIL_DATA_READ_TOKEN`: short-lived or tightly scoped read-only access to the private `mangpijasuan/siamsil-data` repository. Prefer a GitHub App installation token if your runner provisioning supports it.
3. For R2 publishing only, add `SIAMSIL_R2_WRITE_KEY_ID`, `SIAMSIL_R2_WRITE_SECRET`, and `SIAMSIL_R2_ENDPOINT` as environment secrets. Set `SIAMSIL_R2_BUCKET` as an environment variable. Limit the write token to the single private bucket; rotate it according to policy.
4. Do not configure personal secrets in code or PR comments. The action's checkout of the private data repo and its upload step cannot run successfully without these settings.
5. Keep the private source repo and its large tracked assets accessible to GitHub Actions. Account for Git LFS and GitHub bandwidth quotas before running; this workflow does not download an uncommitted local `zomi-data.zip`.

## Build and release

Open **Actions → Build and validate Siamsil data release → Run workflow** and choose `publish_to_r2=false` for a dry run. The workflow checks out the private repo, hashes its pinned originals, builds the SQLite databases, and produces `dist/siamsil-data.tar.gz` and `dist/release.json`. Both are saved as a short-retention **private workflow artifact**. Do not forward either externally. Inspect the output, license metadata and holdout exclusions before approval.

For a reviewed release, run again with `publish_to_r2=true` and approve the protected environment. The action uploads to:

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
python backend/scripts/check_release.py --url https://api.siamsil.com
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
