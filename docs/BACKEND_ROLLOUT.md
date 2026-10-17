# Backend rollout: Scripture, account sync, and translation review

This release adds backend contracts and storage, not a new licensed Bible edition, a production sign-in provider, or a trained translation model.

## Run locally

1. Build the existing language release as described in the repository README.
2. Configure PostgreSQL and OIDC in `.env` using `.env.example` and `docs/IDENTITY_AND_AUTHORIZATION.md`.
3. Apply migrations from `backend/` with Python 3.11 or newer: `alembic upgrade head`.
4. Start the API and check `/health/ready`, `/api/v1/bible/versions`, and `/docs`.
5. Regenerate the typed web contract after API changes: `cd frontend && npm run api:generate`.

Do not point migrations or import commands at production until a database backup and a rollback plan have been verified. The migrations are reversible, but a downgrade removes saved items, progress, and review decisions.

## Bible editions

The supplied Zomi standardized text, its source-spelling form, and the unidentified English text are listed as **text forms**, not three independently published editions. The existing `/api/v1/bible/books` and `/chapter` routes remain compatible. New version-aware routes are:

- `GET /api/v1/bible/versions`
- `GET /api/v1/bible/versions/{id}/books`
- `GET /api/v1/bible/versions/{id}/chapter?book_id=1&chapter=1`
- `GET /api/v1/bible/versions/{id}/search?q=...`

Additional editions are imported from UTF-8 JSONL, one verse per line:

```json
{"book_id":1,"chapter":1,"verse":1,"text":"Licensed verse text"}
```

The `book_id` must match one of the supplied canonical/alias IDs. Import into a new immutable ID; existing releases are never overwritten. Example draft import:

```bash
python3.11 backend/scripts/import_bible_version.py \
  --input /path/to/licensed-verses.jsonl \
  --id edition-2026-01 --name "Edition name" --abbreviation ED26 \
  --language en --attribution "Rightsholder and citation" --scope partial
```

Draft releases are hidden from the public API. A display-approved import additionally requires `--approved-for-display --rights-evidence 'permission record reference'`. That flag is a human attestation, **not** legal verification by the script. `--scope full` checks that every canonical chapter is represented; `partial` remains visibly labeled. An editor must also check verse mapping, attribution wording, license terms, and theological/editorial accuracy before making the imported release public. Do not scrape or repackage a third-party Bible app as a source.

## Account-owned data

OIDC-authenticated endpoints under `/api/v1/me` support saved Bible verse keys, dictionary IDs, translation hashes, and lesson progress. All queries are scoped to the authenticated user. Writes are idempotent and authenticated responses use `Cache-Control: no-store`.

- `GET /api/v1/me/saved`
- `PUT` or `DELETE /api/v1/me/saved/{item_type}/{item_key}`
- `GET /api/v1/me/progress`
- `PUT /api/v1/me/progress/{lesson_id}` with `{"percent": 0..100, "completed": false}`

The current web app still uses device-local saves. Enable migration/sync in the frontend only after a real OIDC provider is configured, a sign-in flow exists, and conflict handling is designed; never erase local data merely because account storage is empty.

## 100-row translation review pilot

The existing `ml_pipeline/scripts/prepare_review_pilot.py` prepares a local flagged training-split packet. Validate it without a write:

```bash
python3.11 backend/scripts/import_review_pilot.py data/exports/review_pilot_100.jsonl
```

After PostgreSQL migration, import it explicitly with `--commit`. The importer skips existing sentence IDs and does not publish or license any text. Reviewer/editor/admin-only endpoints under `/api/v1/editorial/translation-jobs` list, lease-claim, and decide jobs. A decision appends a review and audit event while preserving the machine candidate as an immutable attempt. Lease duration is 20 minutes. Approved or edited rows remain **unpublished** pending rights review, independent evaluation, and an immutable language-release build.

## Still required for production

- Hosted PostgreSQL, production OIDC credentials, object storage, TLS/domain, backup-and-restore drills, ingress rate limits, and log shipping.
- Rights evidence and source files for any additional Bible edition or Library resource.
- A reviewer style guide, qualified reviewers, and hidden gold evaluation sets before model training.
- Frontend sign-in and safe migration of device-local saved data.
- A reviewed-release builder and rollback procedure; the pilot does not mutate the deployed SQLite language database.

The API emits request-ID-linked structured access logs without request bodies or query strings. Rate limits should be enforced at the production ingress across all API instances; an in-process limiter would not provide a reliable shared limit.
