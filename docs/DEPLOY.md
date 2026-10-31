# Deploying Siamsil

Updated: 2026-10-31

Siamsil runs as three parts:

| Part | Where | What it is |
| --- | --- | --- |
| Website | Vercel, from `frontend/` | Next.js pages at `siamsil.com` |
| API | Railway, from `backend/` | FastAPI at `api.siamsil.com`, with a PostgreSQL database and a volume at `/data` |
| Data bundle | A private Cloudflare R2 bucket | The language and Bible databases, which the API downloads into `/data` |

The domain and its DNS are at Cloudflare. Merges to `main` deploy the website and the API automatically. The data bundle changes only when you rebuild and upload it.

Estimated cost to start: about $20 a month (Vercel Hobby $0, Railway Hobby about $15–20, R2 $0 within its free 10 GB, plus the domain). Check each provider's pricing page; prices change.

## 1. Domain (Cloudflare)

Buy `siamsil.com` under **Domain Registration**. Its DNS is then managed in Cloudflare (step 5).

## 2. The data bundle (R2)

The bundle holds Bible text and dictionaries that Siamsil may show but not redistribute (`docs/DATA_RIGHTS.md`), so the bucket stays **private**.

1. **R2 → Create bucket**, for example `siamsil-data-bundle`. Do not turn on public access, and do not connect a custom domain to the bucket.
2. **R2 → Manage API tokens**, then make two tokens limited to that bucket:
   - **Read-only** (*Object Read only*), for the API. Note its Access Key ID and Secret Access Key.
   - **Read and write**, for uploading from your computer only. Never give it to Railway.
3. Note the account's S3 endpoint, `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`, shown on the R2 overview page.

Build and upload the bundle on the computer that holds `siamsil-data` (beside this repository):

```bash
python3 ml_pipeline/scripts/build_language_db.py     # dictionary, corpus, approved corrections
python3 ml_pipeline/scripts/import_usx_bibles.py     # Bible versions cleared for display
python3 backend/scripts/package_data.py              # writes dist/siamsil-data.tar.gz and prints its SHA-256
```

The bundle (about 600 MB; 1.7 GB unpacked) is too large for the dashboard's upload button. Upload it with the AWS command-line tool and the **read-and-write** token:

```bash
aws s3 cp dist/siamsil-data.tar.gz s3://siamsil-data-bundle/siamsil-data.tar.gz \
  --endpoint-url https://<ACCOUNT_ID>.r2.cloudflarestorage.com --region auto
```

The bundle contains `siamsil_language.sqlite`, `bible_versions.sqlite` and any reviewed phrase lists in `backend/data`. It leaves out `bible_verses.json`, the workbook's "ISO Improved Text" Bible, which is not cleared for display.

## 3. API (Railway)

1. **New project → Deploy from GitHub repo** → `mangpijasuan/siamsil`. In the service's settings, set the root directory to `backend`. It builds `backend/Dockerfile` and, before switching traffic to a new deployment, waits for `/health/ready`, which fails while the language database or PostgreSQL is not ready (`backend/railway.toml`).
2. **Add a PostgreSQL database** to the project.
3. **Add a volume** to the API service, mounted at `/data`. It needs room for the bundle and its unpacked files: about 5 GB.
4. **Variables** on the API service:

| Variable | Value |
| --- | --- |
| `SIAMSIL_ENVIRONMENT` | `production` |
| `SIAMSIL_DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (Railway fills it in) |
| `SIAMSIL_DATABASE_REQUIRED` | `true` |
| `SIAMSIL_CORS_ORIGINS` | `["https://siamsil.com","https://www.siamsil.com"]` |
| `SIAMSIL_DATA_BUNDLE_S3_ENDPOINT` | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` |
| `SIAMSIL_DATA_BUNDLE_S3_BUCKET` | `siamsil-data-bundle` |
| `SIAMSIL_DATA_BUNDLE_S3_ACCESS_KEY_ID` | the read-only token's Access Key ID |
| `SIAMSIL_DATA_BUNDLE_S3_SECRET_ACCESS_KEY` | the read-only token's Secret Access Key |
| `SIAMSIL_DATA_BUNDLE_SHA256` | the SHA-256 that `package_data.py` printed |

The Dockerfile already points the API at `/data` (`SIAMSIL_LANGUAGE_DB`, `SIAMSIL_BIBLE_VERSIONS_DB`, `SIAMSIL_DATA_DIR`). On its first start the API downloads the bundle into the volume. It unpacks the whole bundle before replacing anything, and removes files an earlier bundle had that the new one leaves out. That takes a few minutes, which is why the health check waits up to 10 minutes. It then applies the database migrations and starts. Later restarts skip the download while the SHA-256 is unchanged.

5. **Settings → Networking → Custom domain**: `api.siamsil.com`. Railway shows a CNAME record to add in step 5.

## 4. Website (Vercel)

1. **Add New → Project** → import `mangpijasuan/siamsil`, with the root directory `frontend`. `frontend/vercel.json` sets the build.
2. **Environment variables**:

| Variable | Value |
| --- | --- |
| `SIAMSIL_API_URL` | `https://api.siamsil.com` |
| `NEXT_PUBLIC_API_URL` | `https://api.siamsil.com` |
| `SIAMSIL_SITE_URL` | `https://siamsil.com` |

3. **Settings → Domains**: add `siamsil.com` and `www.siamsil.com`. Vercel shows the records to add in step 5.

Vercel's free Hobby plan is for non-commercial use. Move to Pro before Siamsil sells anything (Siamsil Docs, `docs/ROADMAP.md`).

## 5. DNS (Cloudflare)

Add the records that Vercel and Railway showed: `siamsil.com` and `www` for Vercel, `api` as a CNAME for Railway. Set each to **DNS only** (grey cloud). Vercel and Railway issue the HTTPS certificates themselves, and Cloudflare's proxy can interfere with that.

## 6. Check

- `https://api.siamsil.com/health` reports `"status": "ok"`, the dictionary and corpus counts, and the database check.
- On `https://siamsil.com`:
  - the Dictionary finds "water" → *tui*;
  - Translate in Zomi → English offers completions while typing;
  - the Bible shows Genesis 1 in Zomi with English;
  - Siamsil AI answers "John 3:16".

## Updating

- **Code:** merge a pull request into `main`. Vercel and Railway redeploy on their own.
- **Data** (new dictionary corrections, a new Bible version, a rebuilt corpus): rebuild and upload the bundle as in step 2, then change `SIAMSIL_DATA_BUNDLE_SHA256` in Railway. The API redeploys and downloads the new bundle.
- **Rollback:** before uploading a new bundle, keep the previous one under a dated name, for example `siamsil-data-2026-10-31.tar.gz`. To roll back, set `SIAMSIL_DATA_BUNDLE_S3_KEY` to that name and `SIAMSIL_DATA_BUNDLE_SHA256` to its checksum.

## Keep private

Tokens, the database address, and the bundle never go in this repository or in a public place. Keep them as Railway and Vercel variables and on the computer that uploads the bundle.
