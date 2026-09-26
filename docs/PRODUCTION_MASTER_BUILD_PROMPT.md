# SIAMSIL

## PRODUCTION MASTER BUILD PROMPT

### Web-First → iOS → Android | Zomi Language + AI + Community Platform

This file is the durable copy of the production master prompt. Follow it for architecture, data, product scope, and honesty rules. Do not treat it as a request to generate the entire platform in one pass.

---

# 0. MISSION

Siamsil is a long-term technology platform designed to become:

> **The Digital Home for the Zomi Language and Community.**

The first platform is the **Web/PWA application**.

The architecture MUST be API-first so that the same backend can later power Web, iOS, and Android.

---

# 1. CORE PRODUCT

1. Zomi Dictionary
2. Zomi Translate
3. Zomi Learning Hub
4. Siamsil AI
5. Zomi Chat
6. Zomi Community
7. Siamsil Identity
8. Zomi language resources
9. Search
10. Personalized learning

# 2. MOST IMPORTANT ASSET

- Dataset A — Zomi Dictionary (~20,000 entries)
- Dataset B — Parallel Corpus (~1,000,000 English ↔ Zomi sentence pairs)

These are core intellectual/data assets. Build data infrastructure around them. Never treat them as ordinary seed data.

# 3. DATA-FIRST PRINCIPLE

```text
RAW DATA → INGESTION → NORMALIZATION → CLEANING → DEDUPLICATION
→ LANGUAGE VALIDATION → ALIGNMENT VALIDATION → QUALITY SCORING
→ HUMAN REVIEW → VERSIONED DATASET → PRODUCTION / TRAINING / EVALUATION
```

Never overwrite raw data. Preserve original source rows.

# 4. DATA STORAGE ARCHITECTURE

Use `data/raw`, `data/processed`, `data/datasets/{train,validation,test}`, `data/evaluation`, `data/exports`, and `data/versions`.

# 5. DATA PROVENANCE

Preserve source, original filename, author, license, acquisition date, transformation history, dataset version, processing script version, review status, and quality score.

Never assume data can legally be used for commercial AI training. Flag uncertain licensing for human review.

# 6–7. DATA MODELS

Dictionary entries are structured records (not key/value pairs). Parallel sentences keep raw and normalized text, quality scores, verification, and dataset split.

# 8. DATASET SPLITTING

Never train on all pairs. Isolate train / validation / test. Prevent duplicate, near-duplicate, and sentence-family leakage.

# 9. DATA QUALITY PIPELINE

Validate emptiness, duplicates, encoding, Unicode, length, alignment, language mismatch, repeated content, HTML/script, and bad metadata. Generate actual metrics. Do not invent numbers.

# 10–16. LANGUAGE ENGINE, SEARCH, DICTIONARY, TRANSLATE, AI

The Zomi Language Engine (dictionary + parallel corpus + retrieval) powers the product.

Do not hallucinate dictionary definitions when authoritative data exists. Distinguish verified information from AI-generated explanation.

Do not hard-code one AI provider. Do not train a massive model from scratch before establishing a baseline.

# 17–22. LEARNING, CHAT, COMMUNITY, IDENTITY

Do not automatically publish unreviewed corpus content as lessons.

Do not launch public community without reporting and moderation.

Siamsil Identity is independent from any cryptocurrency or financial system.

# 23–27. WEB, API, BACKEND, DATABASE

Web-first: Next.js, React, TypeScript, Tailwind. API-first: `/api/v1/...`. Backend: Python, FastAPI. PostgreSQL is the production application database; SQLite FTS is acceptable for local language-data indexing until Postgres is provisioned.

# 28–36. SECURITY, PRIVACY, AUTH, DESIGN, ACCESSIBILITY, PERFORMANCE, PWA, ANALYTICS

Never trust client-side authorization. Minimize collection. Design mobile-first. Do not load 20k dictionary entries or 1M sentence pairs into the browser.

# 37–40. TESTING, AI EVALUATION, CI/CD, MONOREPO

# 41–42. FUTURE IOS / ANDROID

Do not build native clients unless explicitly instructed. Design APIs so they can.

# 43–47. NO FRONTEND-ONLY BUSINESS LOGIC, NO PRODUCTION PLACEHOLDERS, ERROR STATES, ADMIN, LANGUAGE EDITOR WORKFLOW

# 48. RELEASE STRATEGY

- Release 1 — Language MVP: auth foundation, home, dictionary, search, translation, basic Siamsil AI, profile, favorites, history
- Release 2 — Learning
- Release 3 — Community (chat, groups, moderation)
- Release 4 — Intelligence
- Release 5 — Native iOS / Android

# 49–54. DEFINITION OF DONE, PRODUCTION CHECKLIST, PHASED DEVELOPMENT, CRITICAL DATA RULE, PRODUCT VISION

Prioritize: **Data Quality → Correctness → Security → Reliability → UX → Performance → Scalability → Maintainability**

Do not fabricate Zomi language data, translation quality, test results, or legal/security compliance. If something cannot be verified, identify it as unverified.
