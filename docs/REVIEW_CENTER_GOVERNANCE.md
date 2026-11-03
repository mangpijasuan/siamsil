# Siamsil Review Center — governance and contributor rewards

Status: **architecture proposal, not deployed**. Owner decision: **all editor-submitted decisions require a separate authorized admin's final approval** before any language content or spelling standard becomes final or publishable. Reviewer rewards may become available if Siamsil has a financially sustainable approved rewards program; cash and proposed `$ZOMI` tokens are alternatives, not current entitlements.

Read with [QUALITY_OPERATOR_ARCHITECTURE.md](QUALITY_OPERATOR_ARCHITECTURE.md), [ZOMI_SPELLING_CORRECTION.md](ZOMI_SPELLING_CORRECTION.md), [DATA_RIGHTS.md](DATA_RIGHTS.md) and [ZOLAI_STANDARD.md](ZOLAI_STANDARD.md).

## 1. Separation of concerns

- **Frontend** (private authenticated `/review`, proposed): contributor task inbox, evidence/context comparison, spelling and sentence review, decision form, personal quality and estimated reward metrics; editor conflict resolution; admin final-approval queue and reward budget/payout administration.
- **Backend** (FastAPI): enforce role and assignment permissions, approved source access, reviewer independence, review state machine, version checks, immutable audit log, final admin sign-off, reward eligibility calculations, payout gates, duplicate/abuse controls.
- **PostgreSQL**: transactional source of truth for assigned tasks, reviewer submissions, editor proposals, admin approvals, rewards ledger and audit events. Do not store secret API keys or unrestricted private source text in frontend payloads.
- **Private `siamsil-data`**: rights/provenance, source versions, independently permitted human-reviewed exports; signed/versioned release material. Neither a frontend button nor a model response directly modifies the private corpus.
- **Publication**: only admin-finalized, rights-cleared and release-gate-passing content can be included in a manually approved language release. Approval of a translation does not itself grant source/training/commercial rights.

## 2. Roles and workflow

```text
SOURCE OR COMMUNITY REPORT
  -> QUEUED -> ASSIGNED -> REVIEW_SUBMITTED (reviewer A)
  -> SECOND_REVIEW_SUBMITTED (reviewer B, for standard spelling rules)
  -> EDITOR_PROPOSED (editor validates evidence / reconciles disagreement)
  -> ADMIN_PENDING
          -> ADMIN_APPROVED -> RELEASE_ELIGIBLE (if rights and other gates pass)
          -> ADMIN_RETURNED -> EDITOR_PROPOSED / reassignment
          -> ADMIN_REJECTED -> closed with recorded reason
  -> release candidate -> separately authorized release/publish action
```

- **Contributor**: may propose a correction or raise a Bible contextual concern; cannot approve.
- **Reviewer**: examines independently authorized task, submits evidence and a decision. No approval authority for final publication; quality scores are advisory.
- **Editor**: verifies reviewer evidence, requests revision, reconciles conflicts, proposes the definitive language decision; **cannot finalize or publish**.
- **Admin**: independently signs off every editor proposal, with logged reason, reviewer/editor identity, source hashes and current version. Admin may return/reject; **must not skip any required two-reviewer standard-rule gate**. Admin finalization does not itself authorize payments, token issuance, data rights changes, or deployment.
- **Release operator** (may be a separately authorized admin): validates licenses, holdout isolation, signatures and release gates before manual publication. A separate release step should remain mandatory.
- An actor cannot be the sole reviewer and final admin of the **same case**. Enforce separation of duties; privileged overrides, if ever necessary, need a distinct audited emergency policy, not a routine shortcut.
- Existing `data/zolai_standard/standard.json` requires two distinct reviewer codes per rule. **Do not weaken this validation.** The newly required admin approval is an **additional gate**. Plan a versioned schema/manifest for verifiable admin evidence rather than writing an unproven admin signoff into existing rules.
- On an edit to candidate text, evidence or rights scope, prior approval must be invalidated and a new approval cycle required. Prevent approvals on stale hashes.
- For unclear Bible language, mark `needs_context_review` and show the passage in an authorized viewer; Bible usage is evidence, not automatic proof of correctness.

## 3. Reviewer rewards: conditional policy

**No payments or token grants are currently live or owed by default.** Before starting rewarded work, present contributors with clear written eligibility, rate, quality, dispute, cap, payout-timing and funding terms. Do not advertise earned cash or exchangeable tokens unless the program is approved and funded. A contributor should be able to choose volunteer participation where lawful; do not substitute tokens for legally owed wages.

Proposed units:
- **Verified word/term**: paid/rewarded by **distinct approved term review task**, not by every occurrence of a word.
- **Verified sentence**: rewarded by **distinct approved sentence task**, not repeated text length or duplicates.
- **Complex contextual review**: a separate approved rate or fixed task credit for Bible ambiguity, specialist terminology and dispute resolution.
- Optionally use per-word counts only for genuinely editorial tasks with a defined, fair scope; per-word compensation for merely clicking through tasks is easy to game.

Qualifying reward event:
1. Contributor is registered, authorized, and accepted the applicable program terms.
2. The task is unique, assigned, timestamped, properly rights-cleared, with provenance/hash and completed by the contributor.
3. Required human reviews and editor proposal are recorded.
4. **Admin explicitly finalizes** the accepted task; rejected/duplicated/abusive tasks do not qualify. Admin reward approval can be a *separate* payout gate for conflicts/fraud.
5. The configured reward program is active, has sufficient budget and any employment/contract/tax/compliance requirements are satisfied.
6. A dedicated ledger entry is issued **once** for a unique `case_id + contributor_id + reward_policy_version + contribution_role` with immutable idempotency key; adjust mistakes via reversal entries, never silent edits.

**Metrics and incentives:** show completed, pending, returned, accepted and admin-finalized tasks; reviewer accuracy/agreement, edit effort, abuse flags, and a *provisional points estimate*. Avoid pay based solely on quantity; add quality/duplicate controls, sampling, reviewer disagreement escalation and appeals. Revenue share, if used, needs a written funded formula, fiscal periods, reserve and cap; no vague automatic promise that future profits guarantee payouts.

## 4. Cash, credits and proposed $ZOMI

Recommended staged rollout:
- **Stage A:** nontransferable, noncash *contribution points* with clear statement of **no monetary value and no promise of future conversion**. These may be used as reputation and task prioritization signals; no automatic conversion to cash or tokens.
- **Stage B:** optional **cash rewards**, after revenue/funding, signed contributor terms, budget approval, payout provider integration and tax/payroll/worker-classification review. Rates configurable by task type, difficulty, country, effective date, contributor agreement and reward-policy version; never hard-code dollar values in architecture.
- **Stage C:** `$ZOMI` token rewards only after an independent legal, compliance, technical security and economic-design decision. The name `$ZOMI` is a proposal, **not evidence that a token exists**, is transferable, has a market price, represents earnings or will be issued. Review securities, money transmission, sanctions, consumer protection, tax, employment and jurisdictional implications with qualified professionals. Do not connect a wallet, mint, distribute or imply token value in the first Review Center milestone.
- Never fund rewards from user funds or a wallet without a specifically approved budget process. Keep reward ledgers separate from currency and from on-chain transaction records.

## 5. Proposed records and contracts — not yet production schemas

- `review_cases`: case ID, case type, source reference/hash, rights flags, language/dialect, original/proposed text scopes, dedup family, version, assigned roles, case status.
- `review_submissions`: append-only contributor/reviewer/editor decisions, evidence references, author, timestamps, scope/hash and policy version.
- `admin_finalizations`: actor, timestamp, case hash, decision, reason, prior editor submission, reviewer attestations; unique active finalization per content revision.
- `reward_policies`: program version, task unit, compensation type, geographic eligibility, effective window, budget caps, funded/disabled switch.
- `reward_ledger`: immutable provisional and finalized events, contribution ID, reviewer role, unique idempotency key, eligibility, payout state, reversals, immutable audit links.
- `payout_batches`: admin-approved batch, funding reference, worker/tax validation status and external provider reconciliation. **No payout endpoint in v1**.

Possible protected endpoints:
```text
GET  /api/v1/editorial/review-cases
POST /api/v1/editorial/review-cases/{id}/submissions
POST /api/v1/editorial/review-cases/{id}/editor-proposal
GET  /api/v1/admin/review-approvals
POST /api/v1/admin/review-approvals/{id}/finalize
GET  /api/v1/editorial/rewards/summary
GET  /api/v1/admin/reward-policies
```

Enforce permissions in FastAPI, not only with hidden UI controls. Never expose confidential Bible text outside approved display rights.

## 6. Implementation order and gates

1. **Review Center MVP (no rewards owed)**: authenticated task queue, reviewer/editor/admin workflows, immutable event history, admin-finalization gate, conflict resolution and sealed release export tests using synthetic data.
2. **Quality/reputation and points**: defensible accepted-task metrics, dedup, appeals, fraud checks, noncash reputation only; user-visible disclaimer.
3. **Funded compensation**: separate policy, budget, legal review, payout processor, tax and independent authorization tests; no earnings promise until active.
4. **Optional token program**: independent decision, legal classification, smart-contract audit, risk disclosure and admin-controlled treasury only if appropriate.

Tests must prove that: editor-only actions cannot finalize; no editor-pending case is exported as final; admins cannot bypass required independent reviews; stale revisions cannot be approved; two actors cannot self-approve the same case; rejected/duplicate cases are not rewarded; repeat deliveries cannot double-credit; revoked rights bar release; no payouts/tokens occur while program disabled.

## 7. Meaning of approval

**Editor submission is a proposal. Admin finalization is required for every editor submission.** Admin finalization is **necessary but not sufficient** for public release or training eligibility. A release also requires data rights, base-model license, holdout and publication gates.
