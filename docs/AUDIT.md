# Siamsil audit

## Review and governance audit, 2026-11-19

Scope: the application as it stands on `main` (cc03cc2), then in depth the parts the sole-owner governance decision ([GOVERNANCE.md](GOVERNANCE.md)) depends on: review tools, the database, the SZSF validator, the dictionary pipeline and the evaluation tools. Each item was checked in the code, not taken from the docs. The 2026-08-18 audit is kept below.

### Application, in brief

| Area | What is there | State |
|---|---|---|
| API | FastAPI under `/api/v1`: ai, bible, dictionary, learning, search, translate, words, identity | Works; 503 passed + 41 skipped tests before this change |
| Language data | SQLite FTS5 language database (dictionary, 1,775,043 corpus pairs), Bible versions database | Works; the corpus is hidden by default (blocked in `data/rights.json`) |
| Application data | PostgreSQL with Alembic: users, sessions, roles, corpus review records, dictionary editorial tables, speech consent | Works; review and dictionary records are append-only with audit events |
| Identity | OIDC (optional), roles learner, contributor, reviewer, editor, moderator, administrator | Works; no `owner` web role yet |
| Frontend | Next.js: home, dictionary, translate, Bible, chat (Siamsil AI), learning, library, resources, profile, help, about | Works; **no review pages on `main`**. Draft PRs #68 (Review Center RBAC) and #72 (dictionary review form) are not merged |
| Deploy | Railway / VPS guides, data bundle from private storage | Data-release workflow paused (by design) |
| Rights | `data/rights.json`, per-use policy in draft PR #96 | Separate from review; unchanged here |

### Review and standardization tools that already work

| Need | Existing tool | Notes |
|---|---|---|
| Corpus review queues | `filter_szsf_corpus.py` (quarantine, soft-flag review queue, re-audit sample), `review_sample.py export-queue` | Queues in a given order, 100 at a time |
| Review in Excel | `worksheets.py ratings-sheet` / `ratings-import` with dropdowns | Meaning and fluency 0–2, corrected Zomi column |
| Decisions and history | `corpus_reviews.py`, `corpus_revisions.py`: append-only JSONL, latest decision wins, approvals lapse when reviews change; imported to PostgreSQL unchanged | Versioned and reversible by a new decision |
| Applying decisions | `build_language_db.py --reviews`: approved pairs verified, rejected pairs hidden and never exported, corrections applied only where the text still matches, original kept in `raw_target_text` | Never overwrites the original |
| Exact deduplication | `build_language_db.py`, `filter_szsf_corpus.py` (within a split; train copies of held-out pairs dropped) | Exact only |
| Automatic checks | Length ratio, number mismatch, language mismatch, HTML, repeats, identical sides (`quality_flags`) | Heuristics, no semantic alignment |
| Generator quality | `GENERATOR_REVIEW.md` spot checks per model with 95% intervals; silver tier needs the lower bound to pass | Works |
| SZSF rules | `zolai_standard.py`: adopted rules (`standard.json`, v1.1.0, ZS-001–ZS-018, creator-adopted), proposals with preview on the corpus, versioned application at export with the original kept | Rule propagation with preview exists for spelling rules |
| Spelling evidence | `spelling_variants.py`: word forms per source, variant families | Evidence only |
| SZSF files | `szsf.py` validate and manifest (rights snapshot), `szsf_convert.py`, `sop_quality_gate.py` | Works |
| Dictionary | Editorial dictionary in PostgreSQL (`dictionary_review.py`): batch sheets per reviewer, approval and corrections sheets, `apply`, `status`; `dictionary_terms.py` terminology drafts | 50K Master is primary; 0 senses reviewed |
| Evaluation | `eval_set.py` (schema, leakage check, fingerprints, owner-only mode), `mt_eval.py` (translate, score, gate), held-out pairs excluded from every split | Works |

### Where a second person was required (fixed in PR 1, this change)

| Place | Rule | Now |
|---|---|---|
| `corpus_reviews.decide` | an approval by one of the pair's reviewers was ignored | counts when marked `owner_sole` (owner only) |
| `corpus_revisions.validate` | "a lead editor cannot approve their own correction" | the owner may (edit and approve), marked `owner_sole` |
| `dictionary_reviews.validate` / `decide`, `dictionary_review.py approve` / `revise` | same two rules for dictionary senses | same change |
| `szsf.py` | "the approver must not also be a reviewer" | allowed with `review.approval: owner_sole`; the roster check confirms the owner |
| Roster | roles reviewer and lead_editor only; one role per code | adds one `owner` role that acts as both |
| `review_sample.py approve` / `revise` | refused the approver's own rows | the owner may approve their own rows |
| Messages in `zolai_standard.py`, `dictionary_terms.py`, `localize_names.py` | said a second person is needed | say a second confirmation is optional |
| Standard-form rules | already creator-adoptable since 2026-11-13 | unchanged |
| Evaluation sets | owner-only mode since 2026-11-18 (`independently_reviewed: false`) | unchanged |

Not changed, on purpose: rights clearance ([RIGHTS_POLICY.md](RIGHTS_POLICY.md) in PR #96) still needs an independent verifier on its Path C, because that is a legal question, not a linguistic one. Speech consent records still need what their consent forms say.

### Gaps against the governance plan

| Requested | Today | Planned PR |
|---|---|---|
| Owner-only approval with audit trail | **Built in PR 1** | 1 |
| One-pass approve / edit-and-approve / reject / defer | **Built in PR 1** for corpus sheets | 1 |
| Six linguistic statuses | **Reported in PR 1** (`linguistic_status`); stored values unchanged | 1 |
| Near-duplicate clustering | **Built in PR 2**: template and near-duplicate clusters ([REVIEW_QUEUES.md](REVIEW_QUEUES.md)) | 2 |
| Priority queues by impact, uncertainty, frequency, reusable pattern | **Built in PR 2**: cluster priority (frequency, inconsistency, uncertainty), queue for `export-queue` | 2 |
| Batch approval by cluster, with sampling | per-row sheets; cluster members are adjacent since PR 2. One decision for a whole cluster would approve unread text, so it waits for preview, sampling and rollback | 5 |
| English–Zomi semantic alignment, confidence | heuristic flags and `quality_score` only | 2 (local model) |
| Terminology conflict, translation consistency | `dictionary_terms.py` drafts per term; PR 2 flags one English template translated several ways | 2, 3 |
| Dictionary: headword normalization, duplicates, variants, inflected forms | sources read as written; spelling-variant evidence exists separately | 3 |
| AI correction suggestions with explanation, stored as `ai_suggested` | none; Quality Operator proposed, not deployed | 4 |
| Candidate headwords toward 100K+, classified (attested, variant, derived, proposed, AI candidate) | none | 4 |
| Rule propagation with preview and rollback beyond spelling rules | spelling rules only (versioned, original kept) | 5 |
| Progress dashboard | `status` counts on the command line | 5 |
| Web review screen with side-by-side text, keyboard shortcuts, provenance and rights panel | not on `main`; drafts #68, #72 | after 2, built on #72 rather than a new app |

### Constraints the next PRs must respect

- The 1,775,043-pair corpus is `blocked` for every use in `data/rights.json`, and its Zomi side is Gemini output. Review work stays private, uses local models only, and cannot send corpus text to any external provider (`external_llm` is not cleared). Owner approval of a pair does not clear it for display or training.
- AI output is stored as a proposal with model, version and prompt, never as a review record. Nothing approves without an owner decision.
- Every bulk operation (cluster approval, rule propagation) is previewed, recorded as one batch decision naming its members, and spot-checked by random sampling against the frozen evaluation set; held-out items never enter review queues used for training.
- No new services: SQLite and the existing PostgreSQL tables, JSONL decision files, the existing sheets and, later, the review form from #72.

### Proposed PRs

1. **Owner-only review permissions and governance** (this change): roster `owner` role, `owner_sole` approvals across corpus, dictionary and SZSF, one-pass `record --owner-decides`, linguistic statuses, [GOVERNANCE.md](GOVERNANCE.md).
2. **Sentence-review queues and clustering:** near-duplicate clusters (normalized text and character n-gram similarity, local), a priority score (frequency of the pattern, flag severity, uncertainty, reuse across the corpus), queues ordered by it, and "approve this cluster" as one recorded batch decision.
3. **Dictionary review improvements:** headword normalization, duplicate and spelling-variant detection using the adopted standard, inflected-form candidates kept apart from headwords, owner sheets with the same one-pass decisions.
4. **AI candidate generation:** proposal files from local models (and external providers only for data cleared for `external_llm`), each with model, prompt and explanation, status `ai_suggested`; classified headword candidates toward 100K+.
5. **Batch automation and quality monitoring:** rule-based propagation beyond spelling with preview and rollback, random-sample audits of bulk decisions, an evaluation run per release, and a status dashboard.

---

## Siamsil audit — 2026-08-18

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
