# Siamsil target architecture

> For the mobile-first product and language-model training design, use
> [`MOBILE_AI_ARCHITECTURE.md`](MOBILE_AI_ARCHITECTURE.md). This document remains
> the incremental migration reference for the current web MVP.

Status: proposed target architecture
Scope: web-first product, reusable API, language-data production, editorial review, and future mobile clients

## 1. Architectural goals

Siamsil should remain simple enough to operate now while protecting its most important asset: trustworthy Zomi language data. The design therefore separates three concerns that have different reliability and storage needs:

1. **Product delivery** — the web app and versioned API used by future mobile clients.
2. **Application state** — accounts, saved items, progress, editorial decisions, and later community data.
3. **Language-data production** — immutable sources, normalization, quality checks, model-assisted translation, human review, evaluation, and versioned releases.

The architecture is a modular monolith, not a collection of microservices. Domain boundaries are explicit inside one FastAPI application and can be extracted later only when load or team ownership justifies it.

## 2. System context

```text
                         Offline / controlled data plane
                 +------------------------------------------+
Raw source files | ingest -> normalize -> validate -> review| Editors
                 |              -> evaluate -> release      |<------+
                 +--------------------+---------------------+       |
                                      | signed/versioned assets      |
                                      v                              |
Users -> Next.js web/PWA -> FastAPI application -> PostgreSQL ------+
                         |         |            |
                         |         |            +-> job queue/worker
                         |         +-> language release (SQLite FTS)
                         +-> object storage/CDN (library and media)

Future iOS and Android clients use the same `/api/v1` contracts.
```

The API process must never ingest or rebuild the corpus at startup. It consumes a previously built, read-only language release.

## 3. Deployment units

### Web

- Next.js App Router and TypeScript.
- Server components for initial public content where practical.
- Client components only for interactive search, saved state, quizzes, and account actions.
- One typed API client with consistent timeout, error, and authentication handling.
- PWA/offline caching later for selected dictionary and learning content, not the complete corpus.

### API

- One FastAPI modular monolith under `/api/v1`.
- Domain modules own routes, services, schemas, repositories, and authorization rules.
- API responses use stable public identifiers rather than internal database row IDs where records can be republished between releases.
- OpenAPI is the contract for web and future native clients.

### Worker

- A separate Python process using the same domain packages as the API.
- Handles retranslation, imports, export preparation, notifications, and other slow jobs.
- Workers never directly publish language data. They create attempts or proposed revisions for review.

### Data pipeline

- Python command-line tools under `ml_pipeline/`.
- Deterministic and reproducible: the same inputs, configuration, and script version produce the same release.
- Produces quality reports, evaluation artifacts, hashes, and a release manifest alongside every language database.

## 4. Storage responsibilities

### Read-only language release: SQLite FTS5

Keep SQLite for the large dictionary and corpus search index. It is fast, portable, inexpensive, and already working for the 1.7M-pair corpus.

It contains:

- Published dictionary entries
- Published parallel sentences
- Search indexes
- Dataset version and provenance summaries
- Verification and quality fields required at query time

It does **not** contain:

- Accounts or sessions
- Learning progress
- Editorial drafts and review history
- Translation jobs or model credentials
- Community content

The file is an immutable release artifact. Deploy a new file for a new dataset version and retain the prior artifact for rollback.

### Transactional application database: PostgreSQL

PostgreSQL is the system of record for mutable product state:

- users, identities, roles, and sessions
- saved words and search history
- courses, lessons, enrollments, and progress
- citizenship-test question metadata and localized editorial content
- dictionary and translation revision proposals
- translation jobs, attempts, reviews, and approvals
- audit events, reports, and moderation state

Use migrations from the first PostgreSQL deployment. Store UTC timestamps and opaque public IDs. Authentication and authorization are enforced in the API, never only in the frontend.

### Object storage

Use S3-compatible object storage for:

- Library PDFs, audio, images, and downloadable resources
- Versioned data releases and Parquet exports
- Import uploads awaiting validation

PostgreSQL stores metadata and object keys, not large binary files. Public resources can be delivered through a CDN; private or draft resources require short-lived signed URLs.

### Cache and queue

Do not require Redis for the first production slice. Add it when background jobs or traffic require shared coordination. Until then, PostgreSQL can safely hold a job queue using atomic row claims and expiring leases.

## 5. Backend domain boundaries

```text
backend/
  app/
    api/                 # composition, dependencies, middleware
    identity/            # users, sessions, roles
    dictionary/          # entry search and editorial proposals
    translation/         # retrieval and translation requests
    learning/            # courses, lessons, progress
    citizenship/         # test banks, locales, practice sessions
    library/             # resource metadata and access
    scripture/           # Bible books, chapters, search
    assistant/           # grounded orchestration and citations
    editorial/           # review queues, approvals, audit log
    language_data/       # read-only release adapter
    jobs/                # queue and worker leases
    common/              # settings, database, errors, security
```

Rules:

- Routers validate transport concerns and call services.
- Services implement use cases and authorization.
- Repositories own persistence queries.
- The language-data adapter is read-only.
- Domains do not import router modules from one another.
- AI providers are adapters behind an internal interface; no domain depends directly on Gemini or another vendor SDK.

## 6. Language-data lifecycle

```text
data/raw (immutable)
  -> ingest and normalize
  -> deduplicate and split by sentence family
  -> automated quality checks
  -> proposed revisions / model attempts
  -> human review
  -> evaluation gates
  -> versioned release
  -> read-only production index and optional Parquet export
```

Every published record needs:

- stable source identity
- raw and normalized values
- provenance and license status
- quality flags and score
- verification status
- reviewer and review time when verified
- transformation/model/prompt versions when generated
- dataset release version

Generated output is never marked verified merely because a model call succeeded. Learning lessons and citizenship explanations may only use content with an appropriate editorial status.

## 7. Translation and review workflow

The existing 5,441 flagged corpus rows form the first bounded review queue.

```text
queued -> claimed -> generated -> validation_failed
                    |          -> awaiting_review
                    |                    |-> approved
                    |                    |-> edited_and_approved
                    |                    |-> rejected
                    +-> retry / failed
```

The application database preserves all attempts. An approved revision is included in the next language release; it does not mutate the currently deployed SQLite file.

Atomic job claiming requires a lease owner, lease expiry, attempt count, next retry time, and last error. Model output must return stable input IDs and pass count, identity, content, language, number/entity, and repetition checks before entering human review.

## 8. Public API shape

Keep `/api/v1` and remove the duplicate unversioned route registration after clients migrate.

```text
GET  /api/v1/dictionary/search
GET  /api/v1/dictionary/entries/{public_id}
GET  /api/v1/translation/search
POST /api/v1/translation/requests
GET  /api/v1/learning/courses
GET  /api/v1/learning/courses/{slug}
POST /api/v1/learning/progress
GET  /api/v1/citizenship/questions
POST /api/v1/citizenship/sessions
GET  /api/v1/library/resources
GET  /api/v1/scripture/books
GET  /api/v1/scripture/chapters/{book}/{chapter}
POST /api/v1/assistant/answers

GET  /api/v1/editorial/translation-jobs
POST /api/v1/editorial/translation-jobs/{id}/decision
GET  /api/v1/editorial/dictionary-revisions
POST /api/v1/editorial/dictionary-revisions/{id}/decision
```

List endpoints use cursor pagination. Search endpoints return provenance, verification status, quality labels, and release version. Administrative endpoints require server-enforced roles and create audit events.

## 9. Assistant architecture

Siamsil AI remains retrieval-first until generated Zomi passes a documented evaluation threshold.

```text
question
  -> intent and locale detection
  -> retrieve dictionary / reviewed examples / scripture / learning content
  -> rank by verification and relevance
  -> compose a grounded response
  -> return citations, confidence, and verification labels
```

If generation is later enabled, it must use the retrieved context, identify generated text, preserve citations, pass safety and language checks, and have an immediate retrieval-only fallback. Provider, model, prompt version, latency, and evaluation result are observable metadata.

## 10. Identity, authorization, and privacy

Initial roles:

- `learner` — personal progress and saved content
- `contributor` — submits corrections
- `reviewer` — reviews assigned language content
- `editor` — approves publication-ready content
- `admin` — manages roles and operational settings

Use an established OpenID Connect provider rather than implementing passwords. The API validates tokens and maps external identities to local users. Sensitive editorial operations require role checks and audit logging.

Collect the minimum personal data. Separate analytics identifiers from identity, provide account deletion/export paths before launching accounts, and never send private user content to an AI provider without an explicit product policy.

## 11. Reliability and observability

- Structured logs with request and job correlation IDs; never log secrets or full private prompts.
- Health checks distinguish API process, PostgreSQL, and language-release readiness.
- Metrics: request latency/error rate, search latency, empty-result rate, job queue depth, retry count, review throughput, and dataset version.
- Error tracking for frontend and API.
- Database backups plus restore tests; retain prior language releases for instant rollback.
- Rate limiting at the edge and stricter limits on authentication, AI, and write endpoints.

## 12. Repository target

Keep the current folder names during migration to avoid a disruptive rename:

```text
siamsil/
  frontend/              # Next.js web/PWA
  backend/               # FastAPI modular monolith + worker package
  ml_pipeline/           # reproducible language build and evaluation
  data/
    raw/                 # immutable, local/object-storage sources
    processed/           # reproducible intermediate outputs
    evaluation/          # permanent evaluation sets
    versions/            # immutable release manifests
    exports/             # Parquet and distribution artifacts
  migrations/            # PostgreSQL schema migrations
  docs/                  # architecture, ADRs, operations, data cards
```

Generated databases, WAL files, uploaded assets, secrets, and large raw datasets must remain outside source control.

## 13. Migration plan

### Stage 0 — stabilize the current MVP

- Keep the deployed SQLite language engine.
- Consolidate Bible and reviewed phrase data into a reproducible release instead of loading large JSON lists into process memory.
- Remove duplicate `/api` route registration after the frontend uses `/api/v1` exclusively.
- Add API error contracts, request IDs, timeouts, and broader tests.
- Fix repository hygiene so generated SQLite WAL/SHM and local editor artifacts are ignored.

Exit criterion: current features behave the same through one documented API surface.

### Stage 1 — application foundation

- Add PostgreSQL, migrations, repository interfaces, and configuration validation.
- Add OIDC authentication and roles.
- Move Library metadata, learning content, citizenship content, and user progress into PostgreSQL.
- Keep language search in the read-only SQLite release.

Exit criterion: users can sign in and retain saved items/progress; editors can manage structured content safely.

### Stage 2 — editorial and corpus quality

- Add translation jobs, attempts, reviews, and audit events.
- Import the 5,441 flagged rows as the first queue.
- Build editor APIs and a protected review UI.
- Generate a small reviewed v2 release and verify rollback.

Exit criterion: 100 records complete the full queue-to-release workflow with provenance intact.

### Stage 3 — learning and citizenship platform

- Model courses, lessons, localized content, attempts, mastery, and practice sessions.
- Treat English, Zomi, and Burmese as content locales, not hard-coded component fields.
- Publish only reviewed translations and explanations.

Exit criterion: content editors can publish a lesson or citizenship question in three locales without a code deployment.

### Stage 4 — grounded intelligence and scale

- Establish permanent Zomi evaluation sets and measurable release gates.
- Add provider-neutral generated assistance only if it beats the agreed baseline.
- Add Redis or a managed queue only when PostgreSQL queue metrics show the need.
- Add dedicated search infrastructure only when SQLite search no longer meets measured latency or deployment requirements.

## 14. Decisions to avoid

- Do not split into microservices now.
- Do not use MongoDB solely for the translation batch described in the corpus guide.
- Do not replace working SQLite FTS with a distributed search service without measurements.
- Do not store the 1.7M corpus in browser bundles or load it into API memory.
- Do not overwrite source data or a deployed release.
- Do not publish model output directly into Learning or citizenship content.
- Do not couple the product to one AI provider.

## 15. First implementation slice

The first architectural slice should be small and vertical:

1. Add PostgreSQL and migrations.
2. Create identity/role, translation-job, attempt, review, and audit tables.
3. Import 100 high-priority flagged corpus rows.
4. Add protected review-list and review-decision endpoints.
5. Add a minimal editor review screen.
6. Produce a v2 test release containing approved corrections.
7. Verify tests, provenance, and rollback before expanding the queue.

This proves the most important new boundary—immutable production language data versus mutable editorial workflow—without destabilizing dictionary, translation, Bible, Library, or Learning features.
