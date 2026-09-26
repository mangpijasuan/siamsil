# Siamsil mobile and language-AI architecture

Status: target architecture
Supersedes the web-first assumption for new client development while preserving the current web MVP
Primary goal: a trusted digital platform for Zomi translation, dictionary, learning, communication, and cultural resources

## 1. Product principles

Siamsil should be designed for the conditions in which Zomi people will actually use it:

- iOS and Android are the primary consumer clients.
- Core dictionary and learning experiences work with slow or unavailable internet.
- English, Zomi, and Burmese are first-class interface and content languages.
- Language data always shows provenance and verification status.
- Machine output can propose content but cannot declare itself authoritative.
- One public API serves mobile, web, and future clients.
- The 1.78M sentence corpus is an asset to curate, not automatically trusted gold data.
- The platform starts as a modular monolith and separates services only when operational evidence requires it.

## 2. Target system

```text
                         SIAMSIL CLIENTS
       +--------------------+--------------------+
       |                    |                    |
 Expo mobile           Next.js web        Next.js editor
 iOS + Android         public/PWA          review/admin
 offline SQLite        responsive          desktop-first
       +--------------------+--------------------+
                            |
                   HTTPS / WebSocket API
                            |
                 FastAPI modular application
       +--------------------+--------------------------+
       |          |           |          |             |
   Language    Learning    Community   Library     AI orchestration
   retrieval   & testing   & chat      content     & citations
       |          |           |          |             |
       +----------+-----------+----------+-------------+
                            |
       +--------------------+---------------------------+
       |                    |                           |
 PostgreSQL          language releases           object storage
 mutable state       SQLite/Parquet               media/releases
       |                    |                           |
       +------------- background workers --------------+
                            |
                    model inference service
                            |
                 versioned model registry

                  OFFLINE LANGUAGE FACTORY
 raw -> curate -> review -> train -> evaluate -> release
```

## 3. Repository design

Move toward a workspace without forcing an immediate rewrite:

```text
siamsil/
  apps/
    mobile/                 # Expo + React Native + Expo Router
    web/                    # current Next.js public web application
    editor/                 # editorial and moderation console
  services/
    api/                    # FastAPI modular monolith
    worker/                 # asynchronous jobs
    inference/              # translation-model serving
  packages/
    api-client/             # generated TypeScript client from OpenAPI
    design-tokens/          # color, type, spacing, icon contracts
    i18n/                   # English/Zomi/Burmese UI messages
    domain-types/           # client-safe shared schemas
  ml/
    data/                   # corpus transformations and data cards
    training/               # reproducible experiments
    evaluation/             # permanent human and automatic benchmarks
    dictionary/             # candidate extraction and editorial drafts
  data/
    raw/                    # immutable originals; never committed when large
    processed/              # reproducible intermediate artifacts
    versions/               # manifests and checksums
    exports/                # Parquet and mobile release packs
  infra/                    # containers and deployment definitions
  docs/                     # architecture, ADRs, operations, model/data cards
```

The existing `frontend`, `backend`, and `ml_pipeline` folders can move gradually. Do not pause product development for a cosmetic repository rename.

## 4. Mobile application

### Technology choice

Use Expo and React Native with TypeScript for the consumer mobile app. This provides one iOS/Android codebase, matches the existing TypeScript experience, and still allows native modules when needed. Keep Next.js for the public website and the editor console; do not try to make one UI tree serve every screen on web and mobile.

Share these across clients:

- API schemas and generated client
- design tokens, icons, and content-language definitions
- validation rules that are safe to run on clients
- analytics event names

Do not share platform-specific navigation or complex UI components merely to maximize reuse.

### Mobile navigation

Use five stable primary destinations:

1. **Home** — continue learning, word of the day, community highlights.
2. **Translate** — text, saved translations, history, and later voice/camera.
3. **Dictionary** — headwords, examples, pronunciation, related forms.
4. **Learn** — courses, citizenship practice, review queue, progress.
5. **Community** — conversations, groups, cultural and language content.

Library, Bible, profile, downloads, settings, and contributor tools live one level below the primary navigation. A central search action can search across dictionary, reviewed sentences, lessons, scripture, and Library metadata.

### Local-first data

Use device SQLite for:

- a curated dictionary pack
- downloaded lessons and citizenship questions
- saved words and translation history
- pending learning progress and contribution drafts
- sync cursor and content-release metadata

Do not ship all 1.78M sentence pairs in the initial app. Offer optional downloadable language packs partitioned by purpose or frequency. Each pack is immutable, versioned, checksummed, and replaced atomically.

Local changes use an outbox:

```text
local write -> outbox -> background sync -> server accepted/rejected
```

The UI displays sync state and remains usable when disconnected. Authentication tokens belong in platform secure storage, not SQLite or ordinary key/value storage.

### Internationalization

Separate interface locale from learning language and translation direction:

```text
interface_locale: en | zom | my
source_language:  en | zom | my
target_language:  en | zom | my
```

Content uses a localized-value model instead of fixed `english`, `zomi`, and `burmese` columns:

```text
content_item
  id, type, status, version

content_localization
  content_id, locale, title, body, reviewer_id, verification_status
```

This permits additional Chin languages or dialects without redesigning every table.

## 5. Backend: modular monolith first

The FastAPI application owns clear domain modules:

```text
identity       accounts, devices, roles, consent
language       dictionary and sentence retrieval
translation    translation requests, history, feedback
learning       courses, lessons, progress, spaced review
citizenship    question banks, practice sessions, scores
community      profiles, posts, groups, reports
messaging      conversations, messages, presence, attachments
library        books, PDFs, audio, metadata, access rules
scripture      Bible navigation and search
editorial      proposals, reviews, approvals, release candidates
assistant      grounded answers, citations, policy
jobs           durable background work and retry policy
audit          security and editorial events
```

Inside each domain:

```text
router -> service/use case -> repository -> database or external adapter
```

Domain services never import another domain's HTTP router. Cross-domain calls use explicit service interfaces and transactions where appropriate.

### When to separate a service

Keep domains in one deployment until one of these is true:

- independent GPU scaling is required — separate inference first;
- long-lived chat connections interfere with API deployment — separate realtime gateway;
- a team owns an independent lifecycle;
- measured load or security isolation justifies the operational cost.

The inference service is the first intentional separation because GPU serving has different dependencies and scaling behavior from ordinary API traffic.

## 6. Data platform

### PostgreSQL: mutable source of truth

PostgreSQL stores:

- users, roles, devices, sessions, consent
- saved content and learning progress
- courses, questions, localizations, and publication state
- conversations, messages, memberships, reports, and moderation actions
- translation requests and feedback
- editorial proposals, reviews, and audit events
- model jobs, attempts, evaluation runs, and release approvals
- resource metadata and object-storage keys

Use row-level constraints, migrations, UTC timestamps, and opaque public IDs. Partition high-volume message or event tables only after their size warrants it.

### Language release: read optimized

Continue producing an immutable SQLite FTS release for dictionary and sentence retrieval. It is mounted read-only by the API and can also produce smaller mobile packs.

The production API switches releases by manifest rather than editing records in place:

```text
siamsil-language-v1.sqlite
siamsil-language-v2.sqlite
current-language-release.json
```

Every release has checksums, schema version, source versions, counts, quality report, license status, evaluation result, and rollback target.

### Object storage and CDN

Store Library documents, audio pronunciations, lesson media, chat attachments, corpus snapshots, model artifacts, and exports in S3-compatible storage. Use signed upload/download URLs for protected content and malware/media processing before publication.

### Redis: optional, not authoritative

Add Redis when needed for presence, WebSocket fan-out, rate-limit counters, and hot caches. Messages and jobs remain durable in PostgreSQL; losing Redis must not lose user data.

## 7. Translation product

Translation uses a quality-aware cascade rather than sending every request directly to a model:

```text
input
  -> language/direction detection
  -> exact reviewed dictionary or sentence match
  -> high-confidence translation memory
  -> trained translation model
  -> quality checks and confidence
  -> result with provenance and feedback action
```

Results distinguish:

- editor verified
- community reviewed
- translation-memory match
- model generated
- low confidence / unable to translate safely

Cache normalized requests only when privacy policy permits. Preserve names, numbers, URLs, verse references, and formatting through protected placeholders. User feedback creates an editorial proposal; it never silently retrains or overwrites production data.

Start with server inference. Consider an on-device quantized model only after a smaller model meets quality, memory, cold-start, battery, and package-size targets on representative low-cost Android phones.

## 8. Corpus quality architecture

The existing corpus contains 1,777,002 source rows and 1,775,043 deduplicated pairs, but the Zomi side is machine-generated and currently has no human-verified pairs in the language release. Treat it as synthetic data with three quality tiers:

```text
Gold
  Human translated or independently reviewed
  Used for final test sets and highest-weight training examples

Silver
  Synthetic pairs that pass strict automatic and sampled human checks
  Used for training with lower weight

Bronze
  Raw, duplicated, suspicious, uncertain-license, or unreviewed pairs
  Retained for provenance/research; excluded from production training by default
```

### Required preparation

1. Resolve source and model-output licensing before training or publishing a commercial model.
2. Normalize Unicode, punctuation, whitespace, quotation marks, and locale-specific characters without erasing meaningful Zomi distinctions.
3. Deduplicate exact pairs and group near duplicates.
4. Detect copied English, wrong language, truncation, repetition, HTML, misalignment, and length anomalies.
5. Preserve numbers, named entities, markup, and document/source identity.
6. Split by source/document and normalized sentence family before any augmentation.
7. Freeze human test sets that are never used for prompts, tuning, filtering thresholds, or training.

The current 5,441 flagged rows are the first review queue, not the only questionable rows. Automatic `clean` means no current rule fired; it does not mean human verified.

## 9. Human data program

Model quality depends more on trustworthy evaluation and representative gold data than on adding another million synthetic rows.

Build a paid or carefully governed contributor program with:

- translator and reviewer qualifications
- independent second review for evaluation examples
- adjudication when reviewers disagree
- clear dialect, spelling, punctuation, and borrowing guidelines
- domain labels: conversation, education, government, health, religion, news, and informal chat
- privacy and consent rules for contributed conversations or audio
- measured inter-reviewer agreement

Recommended sequence:

1. Create a balanced hidden evaluation set across both directions and key domains.
2. Review high-frequency translation-memory content.
3. Review diverse training examples selected by uncertainty and coverage.
4. Continuously sample production errors and underrepresented constructions.

Do not evaluate on randomly held-out synthetic Gemini outputs alone; a model can score well by imitating the same systematic mistakes.

## 10. Translation-model training

### Baselines before training

Measure at least:

- current corpus retrieval
- a suitable multilingual translation checkpoint with compatible licensing
- a strong hosted model used only as an evaluation reference where terms permit
- fine-tuned candidate models of more than one size

Select a base model by measured English↔Zomi quality, tokenizer coverage, license, cost, latency, and deployability—not model popularity. Multilingual encoder-decoder families such as NLLB, mT5, and mBART are experiment candidates, not automatic production choices. Some available checkpoints have non-commercial restrictions and must not be adopted without license review.

### Training recipe

Use a reproducible experiment configuration containing:

- dataset and tokenizer versions
- base-model commit and license
- exact gold/silver mixture and weights
- random seed and hyperparameters
- hardware and software versions
- evaluation-set hashes
- output checkpoint and metric report

Train both directions explicitly with language/direction tags:

```text
<translate_en_zom> English source
<translate_zom_en> Zomi source
```

Initial experiments should compare:

1. Gold-only fine-tuning.
2. Gold plus highest-confidence silver.
3. Curriculum training: silver first, gold last.
4. Domain-tagged training.
5. Back-translation from independently sourced Zomi monolingual text, only when rights permit.

Avoid training from scratch. Fine-tune a licensed multilingual checkpoint first. Use parameter-efficient tuning for rapid experiments, then compare against full fine-tuning only if results justify the cost.

### Evaluation gates

Automatic metrics include SacreBLEU and chrF++; add a learned metric only after confirming it behaves sensibly for Zomi. Automatic metrics never replace native-speaker review.

Human evaluation scores:

- meaning preservation
- grammaticality and naturalness
- terminology and dialect appropriateness
- names, numbers, and entity preservation
- omission, addition, hallucination, and toxicity
- preference versus the current production baseline

A model is promoted only when it improves both translation directions on the hidden gold set, does not regress critical domains, passes safety/entity tests, and meets latency/cost limits. Store results in a model registry with `candidate`, `staging`, `production`, and `retired` stages.

## 11. Model serving

Expose an internal inference contract:

```text
POST /internal/v1/models/translate
{
  "request_id": "...",
  "source_language": "en",
  "target_language": "zom",
  "text": "...",
  "domain": "conversation"
}
```

The inference service provides dynamic batching, maximum-length enforcement, timeouts, model/version metadata, and health metrics. The product API—not the mobile client—selects models, applies policy, redacts protected values, caches allowed results, and falls back to translation memory when inference is unavailable.

Roll out new models by shadow evaluation and small canaries. A model rollback changes a registry or deployment pointer; it never requires a mobile release.

## 12. Dictionary generation

The corpus can expand the dictionary, but it cannot directly author an authoritative dictionary.

```text
corpus and monolingual Zomi
  -> word/form frequency
  -> spelling and morphology candidates
  -> bilingual alignment and concordance examples
  -> sense/POS candidate grouping
  -> machine-authored draft
  -> lexicographer review
  -> approved dictionary revision
  -> next language release
```

Each candidate contains:

- proposed headword and normalized lookup forms
- part of speech and possible senses
- English gloss candidates
- real concordance examples with provenance
- frequency and domain distribution
- model/tool version and confidence
- reviewer decision and revision history

Generated definitions remain drafts. Reviewers can merge duplicate senses, record inflections and dialect variants, choose safe examples, add pronunciation audio, and reject hallucinated meanings.

## 13. Learning platform

Model reusable learning objects rather than hard-coded pages:

```text
course -> unit -> lesson -> activity -> localized content
                                  -> attempts -> mastery state
```

Activities can include:

- word recognition and recall
- listen-and-select
- sentence ordering
- translation with acceptable alternatives
- speaking practice with explicit confidence limits
- citizenship questions in English, Zomi, and Burmese
- spaced review generated from learner errors

Learning content must be editor-published. The translation model can propose distractors, explanations, or variants, but these remain drafts until reviewed. Progress syncs across devices while downloaded lessons remain available offline.

## 14. Chat and community

### Durable messaging

- WebSocket for live delivery; REST for history and recovery.
- PostgreSQL is the durable message store.
- Client-generated message IDs make retries idempotent.
- Per-conversation sequence/cursor supports reconnection and pagination.
- Redis may fan out presence and live events but is not the source of truth.
- Attachments upload directly to object storage through signed URLs and are scanned before delivery.

### Safety before growth

Ship blocking, muting, reporting, rate limits, moderator queues, audit trails, and age/privacy rules before public discovery. Do not claim end-to-end encryption unless message keys, backup, multi-device recovery, abuse reporting, and metadata tradeoffs have been deliberately designed and independently reviewed.

Translation inside chat is opt-in and visibly machine generated. Private messages are not added to training data without explicit, informed consent.

## 15. Search and assistant

Unified search ranks verified results above unverified ones and searches:

- dictionary entries and forms
- reviewed sentence examples
- lessons and citizenship material
- scripture
- Library metadata
- permitted public community content

Keep lexical/FTS search as the baseline. Add embeddings only after building a Zomi retrieval evaluation set and proving that semantic retrieval improves relevant results.

Siamsil AI is a grounded orchestrator:

```text
question -> intent -> retrieve trusted sources -> rank -> answer -> cite
```

Generated explanations are labeled, cite their sources, and never silently convert an unverified sentence into a verified fact.

## 16. API and sync contracts

Use `/api/v1`, cursor pagination, idempotency keys for retried writes, and a standard error envelope. Generate the TypeScript client from OpenAPI.

Key surfaces:

```text
/identity       sessions, devices, profile
/sync           release manifests, deltas, outbox acknowledgement
/dictionary     search, entries, suggestions
/translation    translate, history, feedback
/learning       catalog, lessons, progress, reviews
/citizenship    banks, sessions, results
/community      profiles, posts, groups, reports
/messaging      conversations, messages, receipts
/library        resources and downloads
/assistant      grounded questions and citations
/editorial      queues, decisions, release candidates
```

Breaking API changes require a new version or a compatibility window. Content and model releases have their own versions independent of the mobile binary.

## 17. Security, privacy, and trust

- Use OpenID Connect/passkeys or a mature identity provider; do not build password security from scratch.
- Enforce roles and resource ownership on the server.
- Encrypt transport, managed databases, backups, and object storage.
- Keep secrets in a secrets manager, never app bundles or source control.
- Apply per-user/device/IP rate limits to authentication, chat, AI, and contribution endpoints.
- Record immutable audit events for role, moderation, and editorial actions.
- Minimize personal data and define deletion/export flows before collecting it.
- Separate operational analytics from language-training consent.
- Complete provenance and license review before distributing datasets or model weights.

## 18. Observability and release safety

Track:

- API and WebSocket availability, latency, and errors
- search zero-result and correction rates
- translation latency, cache hit rate, model version, feedback, and fallback rate
- sync conflicts and stale mobile content packs
- queue depth, worker retries, and review throughput
- chat delivery delay, spam reports, and moderation response time
- model quality by direction, domain, dialect, and release

Use structured correlation IDs from mobile request through API, job, and inference. Avoid logging private text by default. Mobile releases use staged store rollout; content, language packs, and models use independent signed releases with rollback.

## 19. Delivery roadmap

### Phase A — foundation

- Stabilize the existing `/api/v1` backend and immutable language release.
- Add PostgreSQL migrations, identity, roles, audit events, and object storage.
- Generate a typed API client.
- Create the Expo mobile shell, navigation, localization, secure session storage, and device SQLite.
- Ship offline dictionary search and downloaded starter lessons.

### Phase B — trusted language product

- Create the gold/silver/bronze corpus pipeline and hidden human evaluation set.
- Build translation feedback and editorial review.
- Import the 5,441 flagged rows and complete a 100-row end-to-end release pilot.
- Build translation memory plus server-model baseline evaluation.
- Add dictionary candidate and concordance tools.

### Phase C — learning and citizenship

- Move lessons and citizenship questions to the localized content model.
- Add authoring, review, publication, downloads, progress, and spaced practice.
- Release English, Zomi, and Burmese experiences from one content system.

### Phase D — model training and serving

- Run licensed base-model experiments using gold and filtered silver data.
- Evaluate automatically and with independent native speakers.
- Deploy inference behind the quality-aware translation cascade.
- Canary, observe, and retain immediate translation-memory fallback.

### Phase E — safe community

- Add profiles, groups, posts, moderation, and reporting.
- Add durable one-to-one/group messaging and attachments.
- Introduce opt-in chat translation without using private chat as training data.

### Phase F — expansion

- Add speech collection and pronunciation only with explicit consent and evaluation.
- Investigate quantized on-device translation for offline use.
- Expand reviewed dictionary senses and domain-specific models.
- Add native capabilities only when user research demonstrates value.

## 20. First 90-day implementation target

The first target should prove the architecture without attempting every feature:

1. Mobile app opens in English, Zomi, or Burmese.
2. Curated dictionary pack works fully offline.
3. Signed-in users synchronize saved words and learning progress.
4. Translate uses reviewed matches first and clearly labels unverified/model output.
5. Editors can review correction proposals and publish a small v2 language pack.
6. A hidden, independently reviewed English↔Zomi evaluation set exists.
7. At least two licensed model baselines are evaluated; no model ships merely because it trained successfully.
8. Learning and citizenship content can be published in three locales without a code change.

This creates a strong mobile foundation and a trustworthy language improvement loop before public chat or large-scale model serving increases operational and safety risk.
