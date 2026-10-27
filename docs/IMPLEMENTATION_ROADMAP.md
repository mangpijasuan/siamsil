# Siamsil implementation roadmap (v2)

Updated: 2026-10-25, checked against `main` at `8fa7b2f` and its CI run.
Scope: **Release 1 — Language MVP** ([`PRODUCTION_MASTER_BUILD_PROMPT.md`](PRODUCTION_MASTER_BUILD_PROMPT.md) §48).

This is the **single authoritative implementation checklist for Release 1**. Every status here comes from the code, merged pull requests, and CI on `main`, not from earlier plans. Phase gates are in [`ROADMAP.md`](ROADMAP.md); the target mobile and AI design is in [`MOBILE_AI_ARCHITECTURE.md`](MOBILE_AI_ARCHITECTURE.md). Neither of those holds item status.

Later releases are listed at the end so they stay visible. They are not Release 1 work and should not start before Release 1 ships, unless the project owner decides otherwise. The exception is Phase 0 work in [`ROADMAP.md`](ROADMAP.md), which runs continuously alongside Release 1: data rights, human evaluation sets, and consent-based audio collection ([`AUDIO_CONSENT.md`](AUDIO_CONSENT.md)), because speech data takes longest to gather.

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
| #20 Unify Home, Dictionary, Translate, Bible landscape design | **Chosen redesign** (owner decision, 2026-10-25); step 7 |
| #17 Mountain and quill hero artwork (draft) | Superseded by #20; close it, or fold any artwork the owner wants to keep into #20 |
| #25 Dictionary Builder 10k candidate miner (draft) | Kept as a separate experimental module until the Review Center exists |
| #26 GitHub project homepage (draft) | Docs; independent of Release 1 |

## Release 1 work order

Agreed order, 2026-10-25. Each step lists what must be true before it counts as done.

1. [x] **Merge #29, #27, #28** after checking CI. All three merged 2026-10-25 on green CI.
2. [-] **Roadmap v2**: this document. Done when merged.
3. [ ] **Human-review pilot and protected benchmark.**
   - [ ] The project owner creates the private reviewer roster in the `siamsil-data` repository (`reviews/roster.csv`: code, role, name), with at least one reviewer and one lead editor who are different people. Pass it to every `review_sample.py` command as `--roster ../siamsil-data/reviews/roster.csv`, as `docs/GENERATOR_REVIEW.md` does.
   - [ ] Export the 800-pair review sample. Reviewers rate it; a lead editor approves or rejects (`docs/GENERATOR_REVIEW.md`).
   - [ ] Keep the decisions in `siamsil-data` (`reviews/corpus-reviews.jsonl`, passed as `--reviews`), never in this repository.
   - [ ] Freeze the 300 English benchmark sentences, then have qualified translators produce the Zomi (`testset-sheet`, `docs/EVALUATION_SET.md`). Measure reviewer agreement.
   - [ ] Confirm the benchmark and its variants are excluded from training: `build_language_db.py` reports "Keeping N evaluation items out of training".
4. [ ] **Minimum PostgreSQL Review Center**, built while reviewers work offline. Its scope is [below](#review-center-minimum).
5. [!] **Training rights, then v2.** Blocked on rights. The corpus is `train: needs_review` (`data/rights.json`), and the Hugging Face dataset card is not yet verified because huggingface.co is blocked in the build environment. A pair may enter v2 training only when its source is `train: cleared` in `data/rights.json`. Reaching `HUMAN_APPROVED` is a quality decision, not a rights decision, and never makes an uncleared source trainable. For the parallel corpus, both are required: the source cleared and the pair `HUMAN_APPROVED`.
6. [!] **Evaluate v2 against v1 and retrieval** on the frozen human benchmark (`mt_eval.py`). Blocked on step 3 (benchmark) and step 5. Retrieval stays the production translator until a model passes the gate, and qualified Zomi speakers must approve before any deployment.
7. [ ] **Navy-and-gold redesign** as its own visual PR: **#20** (owner decision, 2026-10-25). It merges on green CI after review; #17 is closed or folded into it.

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
- [-] Search engines: robots, sitemap (pages and Zomi Bible chapters), per-chapter titles, canonical links, social previews, and schema.org data, all switched on by `SIAMSIL_SITE_URL` ([`SEARCH_ENGINES.md`](SEARCH_ENGINES.md)). Still needed: the public domain, Search Console, and per-word dictionary pages, which wait on dictionary rights.

### Auth foundation

- [x] PostgreSQL with reversible Alembic migrations (`20260926_0001`, `_0002`), checked in CI.
- [x] User, external identity, device, session, role, consent, and audit-event models.
- [x] Roles defined: learner, contributor, reviewer, editor, moderator, administrator.
- [x] Provider-neutral OIDC/JWKS verification; identity administration protected by role.
- [ ] Configure a production identity provider and credentials.
- [ ] Web sign-in flow. None exists in the frontend today, and the Review Center (step 4) is the first feature that needs it.

### Home

- [x] Home page with the navy-and-gold shell (#15/#16).
- [ ] Final home design: #20 (step 7).

### Dictionary

- [x] 20,826 entries in SQLite FTS5, with search, suggestions, letters, and entry pages.
- [x] Source, confidence, flagged, and suggested-correction fields.
- [-] Entries are unreviewed: none is verified yet. Rights are `needs_review` and the compiler and copyright holder are unknown (`DATA_RIGHTS.md`).
- [ ] Dictionary entry in `data/rights.json`. It is listed in `DATA_RIGHTS.md` but has no machine-readable record.
- [~] Candidate generation (#25) and lexicographer approval tools come after the Review Center.

### Search

- [x] Unified `/api/v1/search` endpoint.
- [x] Dictionary, Translate, and Bible each have their own search page.
- [x] **Decision (2026-10-25, project owner):** Release 1 keeps separate searches in Dictionary, Translate, and Bible. There is no unified search page in Release 1.
- [~] A cross-product search page on `/api/v1/search` comes in a later release.

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
- [x] **Decision (2026-10-25, project owner):** Release 1 keeps favorites and history on the device. Account sync is not part of Release 1.
- [-] Profile is device-local; there is no account. That is expected for Release 1.
- [~] Account sync for saved words, history, and Bible notes comes after web sign-in, in a later release.

### Language data and rights

- [x] Immutable raw data; `data/raw/` is never modified by the build.
- [x] 1,777,002 corpus rows ingested and 1,775,043 unique pairs kept. Template-family split, quality flags, and a checksummed release manifest in `data/versions/`.
- [x] Corpus provenance recorded: 1,769,117 pairs name a Gemini model; 5,926 name none.
- [x] SOP-07/08 quality gates (`sop_quality_gate.py`).
- [x] Training export enforces `data/rights.json`; nothing marked `needs_review` exports for training.
- [x] Language code decision (2026-10-27, replacing 2026-10-04): Siamsil labels Zomi `ctd` (ISO 639-3, Tedim) in code, data, and APIs (`DATA_RIGHTS.md`).
- [-] Siamsil Zomi Standard Form: spelling evidence across the Bibles, books, and dictionary, and the three style guides compared, are built ([`ZOMI_STANDARD_FORM.md`](ZOMI_STANDARD_FORM.md)). Zomi reviewers' decisions are next; nothing is standardized until two agree.
- [ ] Every external dataset card and model card declares `language: [ctd]` and names the language "Zomi (Zolai), Tedim-based".
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

- [-] PostgreSQL tables for reviewers, review records, approvals, corrections, and dataset releases. Records are append-only and never edited in place. *4a:* `corpus_review_records` (reviews and approvals, with their corrections and notes) and `review_imports` exist; a database trigger refuses edits and deletes. Reviewer and dataset-release tables are not built yet.
- [x] Importer for `corpus-reviews.jsonl` (`backend/scripts/import_reviews.py`) that keeps every field of both record kinds:
  - `kind` and `pair_hash`;
  - reviews: `meaning`, `fluency`, `reviewer`, `reviewed_on`, `correction`;
  - approvals: `decision`, `approver`, `approved_on`;
  - both: `recorded_at`, `batch`, `notes`.
  Round-trip tests must show that a file of reviews and approvals exports back unchanged.
- [x] Each imported record has a stable source identity (source file and line, or a hash of the record) protected by a database uniqueness constraint. Inserts are conflict-safe inside one transaction, so re-running the import, or running two imports at once, adds nothing twice.
- [x] The original record order is stored and kept through import, storage, and export, because `corpus_reviews.decide()` uses order to find the latest review and whether an approval came after it. File order is checked on every import, and export writes records back in that order.
- [ ] The rules of `corpus_reviews.decide()`, reused rather than rewritten: an approval counts only if it comes after the latest review and is by someone other than the reviewers.
- [ ] An approval names the review records it was shown. The server checks that they are still the latest reviews and saves the approval in the same transaction; if a newer review arrived in between, the approval is refused.
- [ ] Role enforcement with the existing `reviewer` and `editor` roles; requires web sign-in (Auth foundation).
- [ ] Protected screens: review queue, side-by-side comparison, rating, correction, approval, rejection, and notes.
- [x] Export back to the decisions format, so `build_language_db.py` keeps applying approvals on every rebuild (`backend/scripts/export_reviews.py`). It never overwrites decisions the database lacks.
- [x] Each dataset release records which review records it used: the manifest's `counts.corpus_review_records` is N, meaning stored positions 0 to N-1.

## Later releases (visible, not Release 1)

- [~] **Release 2 — Learning:** course and lesson models, authoring, offline lessons, progress and mastery. The Citizenship prototype (10 questions) needs the full applicable USCIS bank from an authoritative, versioned source, and Zomi and Burmese translations checked by qualified reviewers.
- [~] **Library expansion:** resource and rights models, object storage, scanning, editor publishing, readers. Copyright for proverbs, hymns, recordings, and archives must be resolved first.
- [~] **Release 3 — Community:** community rules and moderation first, then profiles, groups, reporting, and durable chat. Private messages are never used for training without explicit consent.
- [-] **Speech Data Lab (Phase 0, runs alongside Release 1):** rights, consent, and speaker records with a default-deny eligibility check are built (PR 1, [`SPEECH_DATA_LAB.md`](SPEECH_DATA_LAB.md)). Ingestion, segmentation, the review interface, releases, and ASR baselines follow in PRs 2–6. No ASR or TTS ships before human-reviewed data and evaluations exist.
- [~] **Release 4 — Intelligence:** model-backed translation in production (inference service, canary, rollback), Siamsil AI generation, and speech AI after audio consent (`AUDIO_CONSENT.md`) and evaluation design.
- [~] **Repository restructuring:** move gradually toward the `apps/` and `packages/` workspace in `MOBILE_AI_ARCHITECTURE.md`, and split FastAPI into domain modules without changing public behavior. This is not Release 1 work; do it when a feature needs it, such as the mobile app.
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
