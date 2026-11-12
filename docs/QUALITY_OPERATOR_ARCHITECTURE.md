# Siamsil Quality Operator — Architecture and Operating Contract

Status: **proposed**, documentation only. Not an implemented agent, not an authorized automatic reviewer, and not a license clearance.
Updated: 2026-11-03.
Audience: Siamsil maintainers, Claude Code, future OpenAI/API integrations, Zomi language reviewers.

> Read with [ARCHITECTURE.md](ARCHITECTURE.md), [MOBILE_AI_ARCHITECTURE.md](MOBILE_AI_ARCHITECTURE.md), [DATA_RIGHTS.md](DATA_RIGHTS.md), [EVALUATION_SET.md](EVALUATION_SET.md), [MODEL_EVALUATION.md](MODEL_EVALUATION.md), and [DATA_RELEASES.md](DATA_RELEASES.md). This document does **not** override their protections.

## 1. Decision

Use OpenAI or other eligible language-model providers as **optional application-quality and orchestration adapters**, never as an authority to approve Zomi. Keep the independent model-training pipeline, permissioned source archive, and protected human benchmark separate from provider-assisted product evaluation.

Goals:
- Improve Siamsil Chat's meaning accuracy, conversation relevance, clarity, naturalness, terminology adherence, safety, and citation quality.
- Detect issues in product outputs and help route them to **native Zomi** reviewers.
- Audit deterministic data problems (duplicates, broken rows, missing provenance, rights flags, format errors) without treating machine judgments as speaker validation.
- Provide repeatable, versioned quality reports, cost traces, and safe release recommendations.
- Maintain a low-cost, community-first path to paid AI Chat and future commercial language API **only where data and model licenses allow**.

Non-goals: autonomous training-data generation, bulk upload of the private corpus to a third-party provider, self-approved translations, silent dataset modifications, automatic rights upgrades, model retraining, public data publishing, production merges or deployment.

## 2. Boundaries and ownership

```text
  Users (web/mobile/developer API)
          |
          v
  Siamsil FastAPI / identity / usage meter
          |
          +--> Siamsil Chat orchestrator --> AI provider adapter (OpenAI or eligible alternative)
          |                |                        (minimal scoped context only)
          |                +--> approved glossary, retrieval and citation adapters
          |                +--> quality telemetry (privacy-safe)
          |
          +--> Quality Operator (worker; restricted scope)
                       |
                       +--> deterministic data checks and benchmark runner
                       +--> Chat quality evaluator (application outputs only)
                       +--> issue and correction proposals (unverified)
                       +--> reviewer work queue / audit trail (PostgreSQL)
                                      |
                        authorized native-speaker editor
                                      |
                             human-approved decisions
                                      |
  PRIVATE siamsil-data originals / rights / approved review exports
                                      |
                        independent training + eval pipeline
                                      |
                         versioned SQLite/model release
                                      |
                        manually approved release gate
```

- `siamsil-data` remains the **private source-of-truth archive** for originals, rights evidence references, consent, authorized reviewer exports, and protected evaluation assets. Privacy of the repo does not imply copyrights or commercial permission.
- PostgreSQL remains the system of record for **mutable** requests, Chat sessions, correction proposals, reviewer decisions, scopes, evidence links, audit events, and billing usage.
- The published language database remains **immutable, read-only SQLite** with release hashes. A correction is not reflected in the deployed database until a new validated release is deliberately promoted. A separately approved glossary service may deliver a faster non-training terminology correction.
- Third-party model providers own their base models; Siamsil controls its application, private storage, independent original data, approved editorial decisions, and its own permitted checkpoints **subject to source/base-model/provider licenses**.
- Never store API keys in Git, frontend bundles, logs, or unencrypted reviewer exports.

## 3. Operator modules (proposed)

| Module | Allowed operations | Must not do |
| --- | --- | --- |
| Data Auditor | Structural validation, exact/near dedup candidate detection, format/PII/rights flags, source hash checks, language-code anomalies | Invent Zomi translations, approve rights, rewrite originals |
| Terminology QA | Compare application translation output with approved glossary, identify context-dependent mismatches | Blind string replacements or mark AI suggestions as verified |
| Chat Evaluator | Run product-specific prompts against a **permitted, scoped** benchmark; flag unsupported facts, missing citations, awkwardness, refusal quality and consistency | Use OpenAI-generated labels/outputs to train a separate competing model without required authorization |
| Review Coordinator | Prepare reviewer queues and side-by-side comparisons; record identity, votes, timestamps, context and final editor signoff | Approve a record by model vote, skip reviewer trust rules |
| Release Evaluator | Report factual pass/fail gates, hashes, regression diffs, model/source versions and blockers | Publish or deploy without human approval and licensing gates |
| Cost Controller | Measure per-model token use, costs, quotas, premium requests, timeouts, and provider fallback | Leak data, override user budgets, silently enable expensive fallbacks |

Allow independent deterministic checks to run without any AI provider. Provider failures must degrade gracefully.

## 4. Separation of use cases — important contractual gate

**Lane A: OpenAI-powered Siamsil product / application QA**
- Use an approved API integration to help compose responses, detect product regressions, evaluate the *OpenAI-powered application*, summarize operational QA, and triage incidents.
- Limit provider inputs to the minimum necessary; apply consent, retention, redaction, access controls and source-use permissions.
- Store provider and prompt versions; distinguish provider suggestions from native-speaker decisions.

**Lane B: independent Siamsil model training**
- Use human-authored, explicitly licensed or independently reviewed Zomi sources and a separate human-grounded evaluation program.
- Do **not** feed OpenAI outputs, judgments, rewritten examples, ranking labels or derived corrections into the training/curation of a separate competing model unless the applicable provider terms and any required exception explicitly permit it.
- Do **not** treat ownership of API output as proof that every downstream model-training use is permitted.
- Keep collection and review provenance so a training export can **exclude provider-derived records by default**.
- Re-check the **current** provider terms and base-model licenses before implementing or changing use. Specific commercial and competitive-training restrictions may change; consult legal counsel where necessary.
- Do not assume the present experimental NLLB checkpoint is commercially usable.

**Lane C: native-speaker editorial corrections**
- Original speaker-contributed corrections may be eligible for the independent data pipeline when their consent, rights, use scope, and provenance allow it.
- Separate genuine human-authored revisions from provider-proposed examples. A reviewer agreeing with a model proposal does not automatically erase provider-derived provenance or license obligations.

## 5. Reviewer decision contract

Canonical status progression (map to existing SOP statuses, do not invent conflicting production enums):

```text
DRAFT -> NEEDS_CORRECTION -> READY_FOR_APPROVAL -> HUMAN_APPROVED
       \-> REJECTED
HUMAN_APPROVED -> eligible for explicitly approved release -> RELEASED
```

Suggested metadata per case: stable record ID; source ID and SHA; domain; en/zomi text; locale/dialect; original model output; proposed replacement; origin category (`human_authored`, `provider_assisted`, `deterministic_flag`); provider/model/prompt/version when applicable; source license and allowed uses; reviewer identity; approval identity/time; evidence; final verdict; audit history; release eligibility flags.

Rules:
1. AI scores are *signals*, never proof of language correctness. Zomi Standard (Tedim-based) native-speaker editors are final authorities.
2. A native speaker can report `election` → `kiteelna` for a defined governmental context. Preserve `teelna` where it carries a different context-specific meaning; no global blind replacement.
3. Distinguish immediate **approved glossary/lookup** behavior from changes that require a new training or SQLite release.
4. Keep the sealed human evaluation holdout independent of training, prompt-tuning, retrieval corpus, and reviewer example generation.
5. Track reviewer trust and conflicts of interest; begin with one qualified reviewer and escalate contentious or high-risk decisions as SOP requires.
6. Never auto-approve, auto-train, auto-merge, auto-publish, auto-license, or auto-bill.

## 6. Quality measurements

Start with a speaker-authored, independently protected **300–500** conversational benchmark (pilot), then expand with domain and demographic/dialect coverage. Score:
- Meaning / factual correctness
- Natural Zomi phrasing and grammaticality (native-speaker rubric)
- Approved terminology accuracy and appropriate contextual use
- Clarity, answer usefulness, grounded citations and abstention
- Robustness to unsafe or unsupported requests
- Latency and cost per successful answer
- Human reviewer agreement and regressions against baseline

Keep **training split, product QA set, and protected final holdout** distinct. Do not report BLEU/chrF against synthetic references as equivalent to native-speaker correctness. Release reports must show sample counts, languages/dialects, confidence/uncertainty and model versions.

### Recommended initial acceptance gates (targets, not claimed results)
- 100% reviewer signoff for records labeled `HUMAN_APPROVED`.
- 0 unlicensed, unapproved or provider-disallowed records in commercial training exports.
- 0 protected holdout examples in training and prompt-tuning inputs (family/near-duplicate screening).
- 0 secret/token leakage in logs or reports.
- Every quality run traceable to input hash, model and prompt revision.
- Chat quality thresholds chosen after a measured baseline; **do not fabricate an accuracy percentage**.

## 7. Security, data minimization and financial controls

- Provider calls must be made server-side through a versioned adapter, with explicit allowlist of input fields; never stream raw private corpus or confidential rights documents by default.
- Redact personal information and sensitive contents before transmission; obtain consent and honor deletion obligations.
- Configure API retention and logging based on the actual connected product/provider; verify provider terms and settings rather than claiming zero retention.
- Restrict operator identity to read-only source manifests and an explicit application QA sample; allow writing proposals to PostgreSQL only.
- Require role-based approval for decisions and a separate signed authorization for release, licensing and data export.
- Set per-request token caps, max completion length, tenant quotas, and monthly provider-cost budgets; implement fail-closed cost limits.
- Keep provider QA data in a separately tagged storage namespace to prevent accidental ingestion into independent model training.
- Treat all fetched text and LLM output as untrusted; defend against prompt injection, quoted instructions and data exfiltration.
- Keep restricted dataset bundles out of artifacts in the public GitHub repo; honor the security hold introduced after PR #64 and remediated by PR #65.

## 8. Bounded implementation plan for Claude Code

**Milestone QO-0 — docs + contract (this document):** no runtime behavior change.

**Milestone QO-1 — application QA read-only pilot**
1. Add typed `QualityCase`, `QualityRun`, `QualityFinding`, and `ProviderUsage` schemas in an isolated `backend/quality_operator/` package (or equivalent existing modular structure).
2. Implement deterministic checks (glossary lookup, missing fields, duplicate detection, unsafe-text scan) against **fixtures or separately authorized scoped test data**.
3. Implement optional provider adapter behind a feature flag, disabled by default, with redacted inputs, token/expense caps and mock tests.
4. Expose authorized admin-only quality-run initiation and read-only report endpoints; do not expose private dataset contents in public responses.
5. Write unit/integration tests for RBAC, untrusted tool results, disabled-by-default behavior, record lineage, budget exhaustion and rejection of unauthorized training export.
6. Add a short runbook, config example with placeholder values only, and measured test results.

**Milestone QO-2 — human Review Center integration**
- Write only review *proposals* to PostgreSQL; use existing approval enums and migration conventions. **All editor proposals must be finalized by a separately authorized admin** as specified in [REVIEW_CENTER_GOVERNANCE.md](REVIEW_CENTER_GOVERNANCE.md). Export only admin-finalized, appropriately reviewed human records, rights-filtered and lineage-tagged.
- Build a reviewer/editor/admin UI to inspect authorized source context, corrections and provenance, with audit events, editor proposals, and admin approve/return/reject controls. Editors cannot finalize their own proposals.
- For the starter sample, use the existing 800-pair offline pilot and do not import as gold automatically.

**Milestone QO-3 — Chat quality and paid usage**
- Add versioned evaluation harness for application prompts and provider adapters; record anonymized success, errors, latency, cost and grounded-source presence.
- Introduce a free Community tier and configurable paid Starter / Pro / Max tiers only when billing, quotas and relevant commercial rights are ready. **Illustrative initial prices** are Starter $4.99, Pro $9.99 and Max $19.99 per month, but all prices, allowances and offerings may be changed by authorized administrators as business costs and community needs evolve. These are **proposals**, not fixed architectural values or guarantees; do not implement unlimited usage. Store prices, currency, effective dates and plan versions in controlled billing configuration (not hard-coded in application logic), show them transparently to customers, and handle existing subscriptions, applicable notice/consent requirements and billing-provider changes before a new price takes effect.
- Keep developer Language API subscriptions independently metered.

**Milestone QO-4 — release / training interoperability**
- Connect human-authorized, independently permissible review exports to the private `siamsil-data` release gate, keeping holdouts sealed and validating base-model licenses.
- Preserve manual release/promotion and safe rollback.
- Require explicit approval before changing any production dataset, model, billing, secrets or deployment.

## 9. Suggested internal API contracts (proposal, not current endpoints)

```text
POST /api/v1/admin/quality/runs
GET  /api/v1/admin/quality/runs/{id}
GET  /api/v1/admin/quality/findings?status=...
POST /api/v1/editorial/quality-cases/{id}/decision
GET  /api/v1/admin/quality/budgets
```

All require backend authorization; audit every mutation. API designs should be finalized against existing routers/OpenAPI before implementation.

## 10. Definition of done for a development PR

- State verified repository facts separately from architectural proposals.
- Code and tests are bounded to the selected milestone; avoid unrelated refactors.
- Tests must run with **synthetic fixtures only** by default, with no required production provider credentials.
- No change of human-review permissions, rights status, paid billing, releases or deployment.
- Documentation points to this file from `docs/ARCHITECTURE.md` and root `CLAUDE.md`.
- PR contains tested command/output, known limitations, cost/privacy notes and explicit approvals needed for next phase.
