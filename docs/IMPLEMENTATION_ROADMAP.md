# Siamsil implementation roadmap

Updated: 2026-09-26
Source of truth: [`MOBILE_AI_ARCHITECTURE.md`](MOBILE_AI_ARCHITECTURE.md)

## Status legend

- `[x]` Complete and present in the repository
- `[-]` Partial, prototype, local-only, or not production-ready
- `[ ]` Needed
- `[~]` Deliberately later

“Architecture documented” does not mean “feature implemented.” Completion requires working code, appropriate tests, security controls, deployment documentation, and verified data where applicable.

## Current baseline

### Architecture and repository

- [x] Next.js web application exists.
- [x] FastAPI backend exists.
- [x] `/api/v1` endpoints exist.
- [x] Dockerfiles and local Docker Compose exist.
- [x] Mobile/AI target architecture is documented.
- [x] Raw, processed, evaluation, export, and version data directories are defined.
- [-] Repository is still organized as `frontend/`, `backend/`, and `ml_pipeline/`; the target workspace structure is not implemented.
- [-] Both `/api` and `/api/v1` routes are registered; the unversioned duplicate still needs removal after compatibility review.
- [-] CI runs PostgreSQL migration rollback checks, backend tests, frontend lint, type-check, and build; data validation and secret scanning still need to be added.
- [ ] Add deployment environments for development, staging, and production.
- [-] Structured environment configuration and production database validation exist; a secrets manager is still needed.

### Current quality checks

- [x] Backend language-engine, API-contract, settings, database, schema, identity, and authorization tests pass locally and in PostgreSQL-backed container checks.
- [x] Frontend lint and TypeScript checks pass.
- [x] Upgrade Next.js to patched 16.3.6 and add a zero-high-severity production dependency audit to CI.
- [x] Fix state-in-effect errors in `DictionaryShell.tsx` and `TranslateClient.tsx`.
- [x] Fix the missing effect dependency and unused `searchTranslate` import.
- [ ] Add API integration, frontend component, accessibility, and end-to-end tests.
- [ ] Add performance budgets for mobile startup, offline search, API latency, and translation inference.

## Language data foundation

### Completed

- [x] Immutable raw-data policy is documented and implemented in the build flow.
- [x] Approximately 20,826 dictionary entries are ingested.
- [x] 1,777,002 parallel source rows are ingested.
- [x] 1,775,043 unique sentence pairs are retained after exact deduplication.
- [x] 1,959 exact duplicates are dropped.
- [x] Unicode/whitespace normalization exists.
- [x] Exact-pair hashing and English-family hashing exist.
- [x] Deterministic train/validation/test splitting exists.
- [x] Basic quality flags and scores exist.
- [x] SQLite FTS indexes dictionary entries and parallel sentences.
- [x] Concurrent API requests use independent thread-local read-only SQLite connections.
- [x] Quality report, release manifest, and evaluation samples are generated.
- [x] Production retrieval marks corpus examples as machine-translated and unverified.

### Needed

- [-] Resolve and document the complete license chain for dictionary, OPUS/Tatoeba sources, generated translations, model training, and redistribution. The register and open questions are in `DATA_RIGHTS.md`; no source is cleared yet.
- [-] Add near-duplicate detection and document/source-level grouping. Template families (learned names and numbers masked) now decide the split; MinHash-style fuzzy matching is not done.
- [ ] Add stronger language identification for English and Zomi.
- [-] Add number, entity, punctuation, truncation, alignment, and repeated-batch checks. Number mismatch, corpus-relative length-ratio outliers, and reused Zomi output are flagged; entity, punctuation, and truncation checks need Zomi conventions first.
- [-] Add dataset tiers: gold, silver, and bronze. `export_datasets.py` assigns tiers and enforces training rights from `data/rights.json`; silver needs the generator spot-check results, and nothing exports by default until rights are cleared.
- [ ] Preserve all original corpus metadata, including timestamps and batch information, in archival Parquet.
- [-] Create immutable named releases under `data/versions/` with checksums and rollback metadata. Builds write a checksummed manifest there; rollback metadata (which release a deployment replaces) is not recorded yet.
- [ ] Produce smaller signed mobile dictionary and lesson packs.
- [ ] Move Bible and reviewed phrase data into a reproducible language/content release instead of API-memory JSON loading.

## Existing web product

### Completed

- [x] Responsive application shell, sidebar, mobile drawer, page header, and bottom navigation exist.
- [x] Home, Dictionary, Translate, Learning, Citizenship, Library, Bible, Siamsil AI, and Profile routes exist.
- [x] Dictionary search uses the 20k-entry SQLite index.
- [x] Translation retrieval searches dictionary, reviewed phrases, Bible, and the corpus.
- [x] Unified search endpoint exists.
- [x] Bible reader and search exist.
- [x] Siamsil AI performs grounded retrieval and refuses to invent missing translations.
- [x] Saved words and search history work in browser-local storage.
- [x] Learning publishes the existing teacher-reviewed daily-use phrases.

### Partial

- [-] Profile is device-local; accounts and cloud synchronization do not exist.
- [-] Learning streak and XP are device-local and do not represent a complete learning engine.
- [-] Siamsil AI is retrieval-only and has no conversational memory or model generation.
- [-] Library has three links to existing sections and three “coming soon” placeholders; it is not a managed digital library.
- [-] Citizenship contains 10 hard-coded questions while the screen advertises 128.
- [-] Citizenship has English, Zomi, and Burmese UI content, but the translations and question version need formal editorial/source verification.
- [-] The current `/chat` route is Siamsil AI, not person-to-person community chat.
- [-] Search is not yet exposed as a complete cross-product search experience.

### Needed

- [ ] Fix frontend lint before new feature work.
- [ ] Add consistent loading, empty, offline, and retry states.
- [ ] Add keyboard, screen-reader, color-contrast, and focus-order accessibility audits.
- [x] Generate the shared TypeScript client contract from FastAPI OpenAPI and reject schema drift in CI.
- [ ] Replace hard-coded and JSON-backed editable content with APIs and editorial storage.
- [ ] Add privacy policy, terms, dataset disclosures, and content/source pages.

## Mobile application

### Needed — first release

- [ ] Create `apps/mobile` with the current stable Expo, React Native, TypeScript, and Expo Router.
- [ ] Create navigation for Home, Translate, Dictionary, Learn, and Community.
- [ ] Implement English, Zomi, and Burmese interface localization.
- [ ] Add accessibility-aware design tokens and reusable native components.
- [ ] Add secure token storage and device registration.
- [ ] Add device SQLite schema and migration management.
- [ ] Download and atomically install a signed starter dictionary pack.
- [ ] Implement fully offline dictionary search.
- [ ] Implement offline saved words, history, lessons, and citizenship content.
- [ ] Add an outbox and cursor-based synchronization protocol.
- [ ] Add network-state, sync-state, and storage-management UI.
- [ ] Add crash reporting, privacy-safe analytics, and release diagnostics.
- [ ] Set up internal iOS and Android builds before public store submission.

### Needed — later mobile capabilities

- [~] Camera/OCR translation after text translation quality is established.
- [~] Speech input, pronunciation scoring, and audio collection after consent and evaluation design.
- [~] On-device translation after a quantized model meets quality and low-cost-device performance targets.
- [~] Widgets, share extension, and system dictionary integration based on user research.

## Application backend and identity

### Existing

- [x] FastAPI application and health endpoint exist.
- [x] Dictionary, translation, search, Bible, learning, and assistant routers exist.
- [x] Inputs use Pydantic validation and parameterized SQLite queries.
- [-] Liveness and readiness report content, language-data, and PostgreSQL state; object storage, queue, and inference checks will be added with those services.

### Needed

- [-] PostgreSQL is integrated locally and in CI; staging and production services are not provisioned.
- [x] Add reversible Alembic migrations and automated migration testing.
- [ ] Reorganize FastAPI into explicit domain modules without changing public behavior.
- [ ] Add repository and service layers for mutable application state.
- [-] Provider-neutral OpenID Connect verification and JWKS support exist; a production identity provider and credentials are not yet configured.
- [x] Add user, external identity, device, session, role, and consent models.
- [x] Define learner, contributor, reviewer, editor, moderator, and administrator roles in the database schema.
- [-] Internal role authorization protects identity administration; future editorial, library, learning, and moderation mutations still need role enforcement.
- [x] Add request IDs and standard API error responses.
- [ ] Add production structured-log shipping, downstream timeouts, and rate limits.
- [-] User provisioning and role grants emit append-only audit events; future editorial and moderation services still need to emit events.
- [ ] Add backup, restore, migration rollback, and disaster-recovery procedures.
- [ ] Remove unversioned `/api` aliases after all clients use `/api/v1`.

## Editorial and translation-review system

### Needed

- [ ] Create PostgreSQL tables for translation jobs, attempts, validations, reviews, and audit events.
- [ ] Implement atomic job claiming with lease owner, lease expiry, retries, and dead-letter status.
- [ ] Import the 5,441 currently flagged corpus rows into the first review queue.
- [ ] Start with a representative 100-row pilot.
- [ ] Add provider-neutral translation adapters.
- [ ] Require structured outputs containing stable sentence IDs.
- [ ] Validate counts, IDs, language, entities, numbers, repetition, and length before review.
- [ ] Build protected editor queue, comparison, correction, approval, rejection, and notes screens.
- [ ] Preserve every translation attempt instead of overwriting existing text.
- [ ] Generate a v2 release from approved changes.
- [ ] Verify checksum, evaluation gates, deployment, and rollback for the release.

## Translation-model program

### Data and evaluation — must precede production training

- [ ] Publish Zomi translation and review guidelines covering spelling, dialect, borrowing, punctuation, names, and ambiguity.
- [ ] Recruit qualified translators, reviewers, and an adjudicator.
- [-] Specify the hidden test-set process, format, and validation/leakage tooling (`EVALUATION_SET.md`, `ml_pipeline/scripts/eval_set.py`).
- [ ] Build a balanced, hidden, independently reviewed English→Zomi test set.
- [ ] Build a balanced, hidden, independently reviewed Zomi→English test set.
- [ ] Cover conversation, education, government, health, religion, news, and informal language.
- [ ] Measure reviewer agreement and adjudicate disagreements.
- [ ] Ensure test families and sources cannot enter training, prompt examples, or filtering development.
- [ ] Establish translation-memory and suitable hosted/model baselines.

### Training

- [ ] Select legally compatible multilingual base-model candidates.
- [ ] Measure tokenizer coverage and unknown/fragmented Zomi forms.
- [ ] Build reproducible experiment configuration and dataset manifests.
- [ ] Train gold-only baseline models.
- [ ] Train gold plus highest-confidence silver experiments.
- [ ] Compare curriculum training, domain tags, and bidirectional direction tags.
- [ ] Consider back-translation only with independently sourced, licensed Zomi text.
- [ ] Record dataset, code, tokenizer, base-model commit, seed, hardware, and hyperparameters.
- [ ] Store checkpoints and reports in a model registry.

### Evaluation and production

- [ ] Measure SacreBLEU and chrF++ on frozen test sets.
- [ ] Validate whether any learned metric is reliable for Zomi before using it as a gate.
- [ ] Run blinded native-speaker evaluation for meaning, naturalness, grammar, terminology, omission, addition, and hallucination.
- [ ] Add named-entity, number, URL, punctuation, long-input, repetition, toxicity, and code-switching test suites.
- [ ] Define minimum quality, latency, cost, and safety promotion thresholds.
- [ ] Build a separate inference service with batching, limits, timeouts, and model metadata.
- [ ] Add translation-memory-first routing and inference fallback.
- [ ] Add shadow evaluation, canary rollout, monitoring, and instant model rollback.
- [ ] Do not enable generated Zomi in production until all gates pass.

## Dictionary generation and improvement

### Existing

- [x] A 20k-entry structured dictionary source is ingested.
- [x] Dictionary source, confidence, flagged state, and suggested correction fields exist.
- [x] Corpus example retrieval exists.
- [-] Dictionary entries are predominantly unreviewed; verified entry count is currently zero.

### Needed

- [ ] Define the Zomi lexicographic style guide and dialect policy.
- [ ] Add word-form frequency and concordance extraction.
- [ ] Add spelling-variant and morphology candidate generation.
- [ ] Add bilingual word/phrase alignment experiments.
- [ ] Generate POS, sense, and English-gloss drafts with full provenance.
- [ ] Build dictionary candidate merge, split, edit, approve, and reject tools.
- [ ] Add pronunciation, inflection, dialect, domain, and safe-example fields.
- [ ] Require lexicographer approval before generated entries become searchable as authoritative.
- [ ] Publish dictionary revisions through versioned language releases.

## Learning and citizenship

### Existing

- [x] Reviewed daily-use phrase endpoint and web presentation exist.
- [x] Citizenship study and practice interactions exist for a 10-question prototype.
- [x] English, Zomi, and Burmese display modes exist in that prototype.

### Needed

- [ ] Create course, unit, lesson, activity, localization, publication, enrollment, attempt, and mastery models.
- [ ] Build editor APIs and authoring screens.
- [ ] Import the complete applicable USCIS question bank from an authoritative, versioned source.
- [ ] Verify every Zomi and Burmese citizenship translation with qualified reviewers.
- [ ] Model time-sensitive accepted answers separately and update them from authoritative sources.
- [ ] Remove hard-coded question-count/pass-rule claims and derive them from the selected test version.
- [ ] Add lesson downloads and offline attempt storage.
- [ ] Add synchronized progress, streaks, mastery, and spaced review.
- [ ] Add audio only after recording rights and pronunciation review are established.
- [ ] Prevent unreviewed corpus or model output from auto-publishing as lessons.

## Library and cultural content

### Existing

- [x] Library discovery page and basic category filtering exist.
- [x] Bible, dictionary, and learning sections are linked as available collections.

### Needed

- [ ] Create resource, creator, collection, localization, rights, file, and publication models.
- [ ] Add S3-compatible object storage and signed upload/download flows.
- [ ] Add malware scanning and media validation before publication.
- [ ] Add editor upload, metadata, rights, preview, publish, archive, and takedown workflows.
- [ ] Add real PDF/e-book/audio readers or safe downloads based on format.
- [ ] Add search across resource metadata and permitted full text.
- [ ] Resolve copyright and contributor permission for proverbs, hymns, recordings, and archives.
- [ ] Add optional mobile downloads with storage controls and checksums.

## Community and chat

### Existing

- [ ] Person-to-person chat is not implemented.
- [ ] Community profiles, posts, groups, and moderation are not implemented.

### Needed before public launch

- [ ] Define community rules, privacy policy, age policy, enforcement process, and moderator roles.
- [ ] Add user profiles with privacy controls.
- [ ] Add groups/posts only with reporting, blocking, muting, and moderation queues.
- [ ] Add durable conversations, memberships, messages, receipts, and client-generated idempotency IDs.
- [ ] Add WebSocket live delivery plus REST history and reconnection cursors.
- [ ] Add signed attachment upload, scanning, quotas, and deletion.
- [ ] Add spam/abuse rate limits and moderator audit trails.
- [ ] Add Redis only when needed for presence and multi-instance event fan-out.
- [ ] Make chat translation opt-in and visibly machine generated.
- [ ] Exclude private messages from training unless users provide explicit informed consent.
- [~] Consider end-to-end encryption only as a separately designed and reviewed security project.

## Siamsil AI and search

### Existing

- [x] Retrieval-only assistant exists.
- [x] Dictionary, corpus, and Bible sources can ground responses.
- [x] Unverified corpus material is labeled.
- [-] Source citations are returned as data but the conversational UI is limited.

### Needed

- [ ] Create a retrieval evaluation set for common Zomi questions.
- [ ] Rank verified/editorial content above unverified corpus results consistently.
- [ ] Add source links, release versions, and verification badges to assistant responses.
- [ ] Add conversation storage only after identity and privacy controls exist.
- [ ] Add provider-neutral answer generation only after Zomi evaluation gates pass.
- [ ] Add prompt-injection defenses and strict source/document boundaries.
- [ ] Evaluate semantic search before adding embeddings or a vector database.
- [ ] Add transparent fallback when retrieval or inference is unavailable.

## Operations, security, and observability

### Needed

- [ ] Add staging and production infrastructure definitions.
- [ ] Add managed PostgreSQL, object storage, TLS, domain, and CDN configuration.
- [ ] Add error tracking for web, mobile, API, worker, and inference services.
- [ ] Add privacy-safe metrics and dashboards for API, sync, search, chat, jobs, and models.
- [ ] Add dependency, container, and secret vulnerability scanning.
- [ ] Add database and object-storage backups with scheduled restore tests.
- [ ] Add incident response, content takedown, model rollback, and data-release rollback runbooks.
- [ ] Add data retention and deletion jobs.
- [ ] Add staged mobile, content-pack, dataset, and model rollout procedures.

## Prioritized execution order

### P0 — stabilize what exists

- [x] Fix frontend lint.
- [x] Add CI and integration smoke tests. Local tests, browser smoke checks, and the first hosted CI run pass.
- [x] Correct the Citizenship prototype’s displayed counts/version behavior.
- [x] Remove or clearly label the current prototype-only UI.
- [x] Consolidate API errors, request IDs, and health reporting.
- [x] Confirm the first hosted CI run after the repository is pushed.

### P1 — product foundation

- [-] Add PostgreSQL, migrations, identity, roles, audit events, and object storage. The database, migrations, OIDC verification, session tracking, internal authorization, and initial audit events are complete; production provider configuration and object storage remain.
- [x] Generate the typed API client with consistent timeout, caching, and standard error handling.
- [ ] Create the Expo app, localization, device database, and offline dictionary.
- [ ] Implement saved-item and learning-progress synchronization.

### P2 — trustworthy language loop

- [ ] Resolve licensing.
- [ ] Establish reviewer guidelines and hidden gold evaluation sets.
- [ ] Build the translation review system and complete the 100-row pilot.
- [ ] Publish and roll back a test v2 language release.

### P3 — real learning and Library

- [ ] Implement localized content and publication workflows.
- [ ] Import and verify the full applicable citizenship bank.
- [ ] Implement offline learning, progress, mastery, and Library resources.

### P4 — translation model

- [ ] Build gold/silver/bronze datasets.
- [ ] Train and evaluate licensed candidate models.
- [ ] Deploy translation cascade, inference, canary, monitoring, and rollback.

### P5 — community

- [ ] Establish policies and moderation operations.
- [ ] Add profiles, groups, reporting, and durable chat.
- [ ] Add opt-in chat translation after the translation system is proven.

## Definition of complete

A checklist item is complete only when:

1. The implementation exists and is reviewed.
2. Automated tests appropriate to its risk pass.
3. Accessibility, privacy, security, and failure states are handled.
4. Required data is sourced, licensed, and reviewed.
5. Monitoring and rollback exist for production changes.
6. Documentation and runbooks are updated.
