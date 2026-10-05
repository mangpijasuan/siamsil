# Siamsil — Digital home for the Zomi language

Siamsil currently ships as a web-first, API-first language platform. Its target architecture is mobile-first with Expo apps for iOS and Android; those native clients are not built yet.

Durable product rules: [`docs/PRODUCTION_MASTER_BUILD_PROMPT.md`](docs/PRODUCTION_MASTER_BUILD_PROMPT.md)
Latest audit: [`docs/AUDIT.md`](docs/AUDIT.md)
Target architecture and migration plan: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
Mobile and language-AI target architecture: [`docs/MOBILE_AI_ARCHITECTURE.md`](docs/MOBILE_AI_ARCHITECTURE.md)
Long-term vision: [`docs/VISION.md`](docs/VISION.md)
Phase roadmap: [`docs/ROADMAP.md`](docs/ROADMAP.md)
Data rights register: [`docs/DATA_RIGHTS.md`](docs/DATA_RIGHTS.md)
Human evaluation sets: [`docs/EVALUATION_SET.md`](docs/EVALUATION_SET.md)
Audio recording consent (draft): [`docs/AUDIO_CONSENT.md`](docs/AUDIO_CONSENT.md)
Generator spot-check: [`docs/GENERATOR_REVIEW.md`](docs/GENERATOR_REVIEW.md)
Implementation status and prioritized to-do list: [`docs/IMPLEMENTATION_ROADMAP.md`](docs/IMPLEMENTATION_ROADMAP.md)
Identity and authorization setup: [`docs/IDENTITY_AND_AUTHORIZATION.md`](docs/IDENTITY_AND_AUTHORIZATION.md)

## What is live (Release 1)

- Dictionary over the ~20k English–Zomi master
- Translation **retrieval** over dictionary, reviewed phrases, Bible, and the unverified parallel corpus
- Siamsil AI as retrieval only (no generated Zomi)
- Bible reader
- Learning phrases that were already teacher-reviewed
- Device-local saved words and search history

The parallel corpus Zomi side is machine-translated (Gemini) from Tatoeba/OPUS English. It is **not** gold data and is labeled unverified in the UI.

## Project layout

```text
siamsil/
├── frontend/          Next.js web app
├── backend/           FastAPI (`/api/v1/...`)
├── ml_pipeline/       ingest + quality
└── data/raw/          immutable originals
```

## Quick start

### Docker (recommended)

Build the language database once, then start the complete local stack:

```bash
python3 -m pip install -r ml_pipeline/requirements.txt
python3 ml_pipeline/scripts/build_language_db.py
docker compose up --build
```

Docker starts PostgreSQL on host port **55433**, applies Alembic migrations,
starts the API on **8001**, and starts the web app on **3002**. Override the
database port with `SIAMSIL_POSTGRES_PORT` if needed.

### 1. Build the language database (required once)

```bash
python3 -m pip install -r ml_pipeline/requirements.txt
python3 ml_pipeline/scripts/build_language_db.py
```

This reads `data/raw/` and writes `data/processed/language/siamsil_language.sqlite` plus a real quality report. It does not modify raw files.

### 2. API

```bash
cp .env.example .env
docker compose up -d postgres
cd backend
python3 -m pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --port 8001
```

Health: [http://127.0.0.1:8001/health](http://127.0.0.1:8001/health)

### 3. Web

```bash
cd frontend
npm install
npm run dev
```

Open [http://127.0.0.1:3002](http://127.0.0.1:3002)

## Tests

```bash
python3 -m pip install -r backend/requirements-dev.txt -r ml_pipeline/requirements.txt
python3 -m unittest discover -s backend/tests -p "test_*.py"

cd frontend
npm run api:check
npm run lint
npm run typecheck
npm run build
```

`frontend/openapi.json` and `frontend/lib/generated/api-types.ts` are generated
from FastAPI. Run `npm run api:generate` after changing API routes or schemas;
CI rejects contract drift.

## Ports

Siamsil uses **3002** (web), **8001** (API), and **55433** (PostgreSQL) so it
does not collide with common defaults.

## Data responsibilities

- PostgreSQL stores mutable application data such as users, identities,
  devices, roles, consent records, and audit events.
- SQLite stores the immutable, versioned dictionary and parallel-language
  release used for fast retrieval.
- Alembic migrations under `backend/migrations/` manage PostgreSQL only.

## Authentication

Identity endpoints use provider-neutral OpenID Connect. Public language routes
continue to work without sign-in. To enable identity, configure the OIDC issuer,
audience, and JWKS URL described in
[`docs/IDENTITY_AND_AUTHORIZATION.md`](docs/IDENTITY_AND_AUTHORIZATION.md).
