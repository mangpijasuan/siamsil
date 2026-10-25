# Siamsil implementation roadmap (v2)

Updated: 2026-10-25, checked against `main` at `8fa7b2f` and its CI run.
Scope: **Release 1 — Language MVP** ([`PRODUCTION_MASTER_BUILD_PROMPT.md`](PRODUCTION_MASTER_BUILD_PROMPT.md) §48).

This is the **single authoritative implementation checklist for Release 1**. Every status here comes from the code, merged pull requests, and CI on `main`, not from earlier plans. Phase gates are in [`ROADMAP.md`](ROADMAP.md); the target mobile and AI design is in [`MOBILE_AI_ARCHITECTURE.md`](MOBILE_AI_ARCHITECTURE.md). Neither of those holds item status.

Later releases are listed at the end so they stay visible. They are not Release 1 work and should not start before Release 1 ships, unless the project owner decides otherwise.

## Status legend

- `[x]` Done: working code on `main`, tested, documented
- `[-]` Partial, local-only, or not production-ready (the note says what is missing)
- `[ ]` Needed for Release 1
- `[!]` Blocked; the note names the blocker
- `[~]` Later release

An architecture document alone does not count as done. See [Definition of complete](#definition-of-complete).

## Where things stand

**CI on `main`** (`.github/workflows/ci.yml`), green at `8fa7b2f`:

- Backend: Alembic migration upgrade and rollback check, 197 backend and language tests (`unittest`), committed OpenAPI contract check.
- Frontend: `npm audit --omit=dev --audit-level=high`, generated API type check, lint, type-check, unit tests, production build.
- Sourcery review on every pull request.

**Recently merged**

| PR | What it delivered |
| --- | --- |
| #23 | Next.js 16.4.3, fixing critical and high advisories |
| #21 | Zomi Translate respects direction end to end; English ⇆ Zomi selector |
| #24 | Offline corpus review: reviewer ratings, separate lead-editor approval, applied on every rebuild (SOP-07) |
| #22 | SOP-07/08 human-review and dataset quality gates |
| #29 | `.gitignore` rules for private data kept beside the code |
| #27 | Parallel corpus source, declared license, and Gemini provenance recorded; training still `needs_review` |
| #28 | Benchmark preparation: translator sheet, source checks, automatic exclusion from training |

**Open pull requests and what happens to them**

| PR | Disposition |
| --- | --- |
| #20 Unify Home, Dictionary, Translate, Bible landscape design | Redesign; overlaps #17. **Owner decision needed** (step 7) |
| #17 Mountain and quill hero artwork (draft) | Overlaps #20; close or fold into the chosen redesign |
| #25 Dictionary Builder 10k candidate miner (draft) | Kept as a separate experimental module until the Review Center exists |
| #26 GitHub project homepage (draft) | Docs; independent of Release 1 |

## Release 1 work order

Agreed order, 2026-10-25. Each step lists what must be true before it counts as done.

1. [x] **Merge #29, #27, #28** after checking CI. All three merged 2026-10-25 on green CI.
2. [-] **Roadmap v2**: this document. Done when merged.
3. [ ] **Human-review pilot and protected benchmark.**
   - [ ] The project owner creates the private reviewer roster (`data/reviews/roster.csv`: code, role, name), with at least one reviewer and one lead editor who are different people.
   - [ ] Export the 800-pair review sample. Reviewers rate it; a lead editor approves or rejects (`docs/GENERATOR_REVIEW.md`).
   - [ ] Back up `data/reviews/corpus-reviews.jsonl` to `siamsil-data`.
   - [ ] Freeze the 300 English benchmark sentences, then have qualified translators produce the Zomi (`testset-sheet`, `docs/EVALUATION_SET.md`). Measure reviewer agreement.
   - [ ] Confirm the benchmark and its variants are excluded from training: `build_language_db.py` reports "Keeping N evaluation items out of training".
4. [ ] **Minimum PostgreSQL Review Center**, built while reviewers work offline. Its scope is [below](#review-center-minimum).
5. [!] **Training rights, then v2.** Blocked on rights. The corpus is `train: needs_review` (`data/rights.json`), and the Hugging Face dataset card is not yet verified because huggingface.co is blocked in the build environment. Train v2 only on sources marked `cleared`, plus pairs that reached `HUMAN_APPROVED`.
6. [!] **Evaluate v2 against v1 and retrieval** on the frozen human benchmark (`mt_eval.py`). Blocked on step 3 (benchmark) and step 5. Retrieval stays the production translator until a model passes the gate, and qualified Zomi speakers must approve before any deployment.
7. [ ] **Navy-and-gold redesign** as its own visual PR. The owner chooses between #20 and the alternative home page; #17 is closed or folded in.

## Release 1 checklist by area

### Platform and quality

- [x] Next.js web app, FastAPI backend, `/api/v1` only (the unversioned aliases are removed).
- [x] Typed API client generated from OpenAPI; CI rejects drift.
- [x] Request IDs, standard error responses, health and readiness endpoints.
- [x] Zero high-severity production dependency audit in CI.
- [x] Frontend unit tests in CI: translate direction and Bible preferences, references, saved data.
- [-] Browser checks: `frontend/scripts/translate.e2e.mjs` (24 checks) runs by hand against a live app; it is not yet in CI.
- [ ] Accessibility pass (keyboard, screen reader, contrast, focus order) on the Release 1 pages.
- [ ] Consistent loading, empty, offline, and retry states on the Release 1 pages.
- [ ] Secret scanning and data validation in CI.
- [-] Deployment: Dockerfiles, local Compose, and `backend/railway.toml` exist. No staging or production environment is documented as live.
- [ ] Backup and restore procedure for PostgreSQL and the language database release.
- [ ] Privacy policy, terms, and dataset/source disclosure pages.

### Auth foundation

- [x] PostgreSQL with reversible Alembic migrations (`20260926_0001`, `_0002`), checked in CI.
- [x] User, external identity, device, session, role, consent, and audit-event models.
- [x] Roles defined: learner, contributor, reviewer, editor, moderator, administrator.
- [x] Provider-neutral OIDC/JWKS verification; identity administration protected by role.
- [ ] Configure a production identity provider and credentials.
- [ ] Web sign-in flow. None exists in the frontend today, and the Review Center (step 4) is the first feature that needs it.

### Home

- [x] Home page with the navy-and-gold shell (#15/#16).
- [ ] Final home design: step 7.

### Dictionary

- [x] 20,826 entries in SQLite FTS5, with search, suggestions, letters, and entry pages.
- [x] Source, confidence, flagged, and suggested-correction fields.
- [-] Entries are unreviewed: none is verified yet. Rights are `needs_review` and the compiler and copyright holder are unknown (`DATA_RIGHTS.md`).
- [ ] Dictionary entry in `data/rights.json`. It is listed in `DATA_RIGHTS.md` but has no machine-readable record.
- [~] Candidate generation (#25) and lexicographer approval tools come after the Review Center.

### Search

- [x] Unified `/api/v1/search` endpoint.
- [-] There is no cross-product search page in the web app. Dictionary, Translate, and Bible each have their own search.
- [ ] Decide whether Release 1 needs a unified search page or whether the per-section search is enough.

### Translation

- [x] Retrieval-only translation over the dictionary, reviewed phrases, Bible, and corpus.
- [x] Direction respected end to end (#21); the UI selector uses `?dir=` and defaults to English → Zomi.
- [x] Machine-generated corpus Zomi is labeled. Pairs approved by reviewers are labeled as approved; rejected pairs are hidden, even on exact match.
- [x] Corpus review decisions survive every database rebuild (#24).
- [ ] Rank human-approved and editorial content above unreviewed corpus results everywhere results are merged.
- [~] Model-backed translation: only after step 6 passes.

### Basic Siamsil AI

- [x] Retrieval-only assistant at `/chat`, grounded in dictionary, corpus, and Bible; refuses to invent translations.
- [x] Unverified corpus material is labeled.
- [ ] Show source links and verification badges in assistant answers.
- [ ] A small retrieval evaluation set for common questions, written by Zomi speakers.

### Profile, favorites, history

- [x] Saved words, search history, and recent Bible chapters, stored in the browser (`frontend/lib/localData.ts`).
- [x] Bible bookmarks and notes stored on the device.
- [-] Profile is device-local; there is no account or sync.
- [ ] **Owner decision:** whether Release 1 ships with device-local favorites and history, or needs account sync (which depends on web sign-in).

### Language data and rights

- [x] Immutable raw data; `data/raw/` is never modified by the build.
- [x] 1,777,002 corpus rows ingested and 1,775,043 unique pairs kept. Template-family split, quality flags, and a checksummed release manifest in `data/versions/`.
- [x] Corpus provenance recorded: 1,769,117 pairs name a Gemini model; 5,926 name none.
- [x] SOP-07/08 quality gates (`sop_quality_gate.py`).
- [x] Training export enforces `data/rights.json`; nothing marked `needs_review` exports for training.
- [x] Language code decision (2026-10-04): Siamsil labels Zomi `zom`; `ctd` (Tedim) is the source reference code (`DATA_RIGHTS.md`).
- [ ] Every external dataset card, model card, and API document says that `zom` is Siamsil's label for Zomi (Tedim-based, related ISO 639-3 code `ctd`) and is not ISO 639-3 Zou.
- [!] Verify the Hugging Face dataset card for `ZomiLearner/English-Zomi-OPUS_Tatoeba_v20230412`: the declared CC0 1.0 label, plus Tatoeba attribution. Needs a screenshot or saved copy in `siamsil-data`, or huggingface.co allowed by the network policy.
- [ ] Settle training rights for the parallel corpus, Gemini output terms, the dictionary, and the daily-use phrases.

### Human review and evaluation

- [x] Offline review workflow: roster check, reviewer rating, a separate lead-editor approval, and an append-only, timestamped audit file. Nothing is approved automatically (#24).
- [x] Benchmark tooling: source checks against the corpus and English Bibles, a translator sheet, and automatic exclusion from training (#28).
- [x] Evaluation harness with chrF++/BLEU, bootstrap intervals, and a promotion gate (`mt_eval.py`).
- [ ] Zomi translation and review guidelines (spelling, dialect, borrowing, names, punctuation).
- [ ] The pilot and benchmark work in step 3.
- [ ] Zomi → English benchmark direction (the 300 sentences cover English → Zomi first).

### Review Center (minimum)

Step 4. This is what makes reviewer decisions durable and searchable before the work grows from 800 pairs to thousands.

- [ ] PostgreSQL tables for reviewers, review records, approvals, corrections, and dataset releases. Records are append-only and never edited in place.
- [ ] Importer for `corpus-reviews.jsonl` that keeps every field: reviewer and approver codes, decisions, scores, `reviewed_on`, `recorded_at`, batch, notes, and corrections. Re-running it on the same file must change nothing.
- [ ] The rules of `corpus_reviews.decide()`, reused rather than rewritten: an approval counts only if it comes after the latest review and is by someone other than the reviewers.
- [ ] Role enforcement with the existing `reviewer` and `editor` roles; requires web sign-in (Auth foundation).
- [ ] Protected screens: review queue, side-by-side comparison, rating, correction, approval, rejection, and notes.
- [ ] Export back to the decisions format, so `build_language_db.py` keeps applying approvals on every rebuild.
- [ ] Each dataset release records which review records it used.

## Later releases (visible, not Release 1)

- [~] **Release 2 — Learning:** course and lesson models, authoring, offline lessons, progress and mastery. The Citizenship prototype (10 questions) needs the full applicable USCIS bank from an authoritative, versioned source, and Zomi and Burmese translations checked by qualified reviewers.
- [~] **Library expansion:** resource and rights models, object storage, scanning, editor publishing, readers. Copyright for proverbs, hymns, recordings, and archives must be resolved first.
- [~] **Release 3 — Community:** community rules and moderation first, then profiles, groups, reporting, and durable chat. Private messages are never used for training without explicit consent.
- [~] **Release 4 — Intelligence:** model-backed translation in production (inference service, canary, rollback), Siamsil AI generation, and speech AI after audio consent (`AUDIO_CONSENT.md`) and evaluation design.
- [~] **Release 5 — Native iOS and Android:** an Expo app with an offline dictionary, signed language packs, and sync. Design in `MOBILE_AI_ARCHITECTURE.md`.

## Standing rules

- Never modify `data/raw/`. Never fabricate Zomi language data, and never add AI-generated Zomi Bible text.
- Song lyrics and non-redistributable Bible text stay out of git.
- Machine-generated Zomi is never shown as an approved translation without a human reviewer and a separate lead-editor approval.
- No work on `main` directly. Merge only on green required checks. Never bypass security checks to get CI green.

## Definition of complete

A checklist item is complete only when:

1. The implementation exists on `main` and was reviewed.
2. Automated tests appropriate to its risk pass in CI.
3. Accessibility, privacy, security, and failure states are handled.
4. Any data it needs is sourced, rights-checked, and reviewed.
5. Production changes have monitoring and a way to roll back.
6. Documentation and runbooks are updated.
