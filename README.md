# Siamsil — Digital home for the Zomi language

Siamsil currently ships as a web-first, API-first language platform. Its target architecture is mobile-first with Expo apps for iOS and Android; those native clients are not built yet.

Durable product rules: [`docs/PRODUCTION_MASTER_BUILD_PROMPT.md`](docs/PRODUCTION_MASTER_BUILD_PROMPT.md)
Latest audit: [`docs/AUDIT.md`](docs/AUDIT.md)
Target architecture and migration plan: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
Mobile and language-AI target architecture: [`docs/MOBILE_AI_ARCHITECTURE.md`](docs/MOBILE_AI_ARCHITECTURE.md)
Implementation status and prioritized to-do list: [`docs/IMPLEMENTATION_ROADMAP.md`](docs/IMPLEMENTATION_ROADMAP.md)

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

### 1. Build the language database (required once)

```bash
python3 -m pip install -r ml_pipeline/requirements.txt
python3 ml_pipeline/scripts/build_language_db.py
```

This reads `data/raw/` and writes `data/processed/language/siamsil_language.sqlite` plus a real quality report. It does not modify raw files.

### 2. API

```bash
cd backend
python3 -m pip install -r requirements.txt
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
npm run lint
npm run typecheck
npm run build
```

## Ports

Siamsil uses **3002** (web) and **8001** (API) so it does not collide with other local apps on 3000/8000.
