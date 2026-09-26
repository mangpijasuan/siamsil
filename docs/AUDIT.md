# Siamsil audit — 2026-08-18

Assessment after locating the updated 20k dictionary and ~1.7M parallel corpus. Numbers below were measured from files, not invented.

## A. Architecture audit

Current repo is a small monorepo:

- `frontend/` — Next.js 16 App Router, TypeScript, Tailwind
- `backend/` — FastAPI, in-memory JSON loader, no database, no auth
- `ml_pipeline/` — Excel/PDF importers that write JSON into `backend/data/`

Strengths: API already exists; dictionary/translate/bible/learning UIs exist; design system is distinctive.

Gaps vs the master prompt:

- Not API-versioned (`/api/...` only, no `/api/v1`)
- Business logic is thin but search was a linear scan over JSON
- No PostgreSQL/Redis/workers
- Chat, profile, and payments were UI mocks
- 1.7M sentence CSV was sitting in `backend/data/` unused
- Live dictionary was still the 508-entry A–B subset

Decision for this revision: SQLite FTS5 as the **language-data engine** (portable, no extra service). PostgreSQL remains the target for users, sessions, chat, and community when those ship.

## B. Data audit

Measured after `build_language_db.py` (2026-08-18):

| Dataset | File | Measured size | Role |
|---|---|---:|---|
| Dictionary master | `Zomi_Standard_Dictionary_AI_Cleaned.xlsx` · `Master Data` | **20,826** ingested (20,827 source rows, 1 empty headword) | Sole live dictionary |
| Parallel corpus | `zomi_english_sentences.csv` | **1,777,002** source rows | **1,775,043** unique pairs kept |
| Parallel duplicates dropped | — | **1,959** | Exact pair hash |
| Parallel verified | — | **0** | Machine-translated; do not treat as gold |
| Train / val / test | hash split on English | 1,597,938 / 88,612 / 88,493 | Isolated by English family |
| Bible | `bible_verses.json` | **30,734** | Scripture reader |
| Daily-use phrases | `daily_use_pairs.json` | **62** | Learning (reviewed) |

Parallel quality flags (not invented): possible language mismatch 3,437; identical 1,492; extremely short 759; extremely long 55; html/script 7; suspicious repeat 3.

Zomi-side models: gemini-3-flash-preview 906,543; gemini-pro 450,619; gemini-2.5-flash 403,972; gemini-3-pro-preview 7,983.

Corpus columns: `index,en,zomi,timestamp,model,worker,batch_time_sec,batch_size,batch_number`.

Unverified findings (must stay labeled):

- English side worker IDs reference `OPUS_Tatoeba_v20230412_*`
- Zomi side models include `gemini-pro`, `gemini-2.5-flash`, `gemini-3-flash-preview`, `gemini-3-pro-preview`
- This is **not** a human-verified gold bitext
- License for Tatoeba source **and** model output is `needs_review`

Dictionary master columns: `ID, Letter, Headword, POS, POS (full), Definition (Zomi), Flagged, Suggested Correction`. Flagged rows require editor review.

## C. Security audit

- CORS is localhost-only; methods GET-only except translate POST
- No authentication, rate limiting, or admin auth
- Firebase stub is disabled
- Profile “Sign in” accepted any input and showed a hardcoded person
- Chat showed a green “Online” badge in demo mode
- `.env.example` has no secrets; good
- Large corpus must not be committed; gitignore updated
- Input is interpolated into SQL via parameters (required going forward)

## D. Product gap analysis

| Area | Was | Needed for Release 1 |
|---|---|---|
| Dictionary | 508 entries, substring scan, 20-hit cap | 20k structured search, letter index, source labels |
| Translate | Tiny pair/bible scan | Corpus FTS with provenance + unverified labels |
| AI | Fake transcript + canned demo reply | Retrieval over dictionary/corpus only |
| Profile | Fake user, fake $4.99 paywall | Device-local favorites/history; no fake auth |
| Home | “2,400+ dictionary”, zomigpt.com promo | Live counts; Siamsil AI is first-party |
| Learning | 62 phrases + citizenship test | Keep; do not auto-publish corpus |
| Chat/community | Mock only | Do not launch as real-time chat |

## E. Implementation roadmap

1. Freeze raw data under `data/raw/` with provenance (this revision)
2. Build versioned SQLite language DB + quality report (this revision)
3. Wire dictionary, translate, search, grounded AI (this revision)
4. Remove production placeholders (this revision)
5. Later: Postgres, real Siamsil ID, evaluation harness, fine-tune baseline
6. Later: Learning Hub courses, moderated community, native apps

## F. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Machine Zomi presented as truth | High | Persistent `verified=false` + UI labels |
| Unclear dictionary/Tatoeba license | High | `needs_review`; no commercial-training claim |
| 1.7M-row RAM blowup | High | SQLite FTS; never load full corpus in API or browser |
| Duplicate/near-duplicate leakage into train/test | Medium | Hash split on normalized English |
| OCR/AI-cleaned dictionary noise | Medium | Keep `Flagged` and suggested corrections |
| Fake AI erodes trust | High | Retrieval-only assistant until a real model is evaluated |

## G. Proposed repository structure (adopted incrementally)

```text
siamsil/
├── apps later: web / ios / android
├── frontend/              # current web app
├── backend/               # FastAPI
├── ml_pipeline/           # ingest + quality
├── data/                  # raw / processed / datasets / evaluation
├── docs/                  # master prompt + audits
└── tests/
```

Native apps stay out until Release 5.
