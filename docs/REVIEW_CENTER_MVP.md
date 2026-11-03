# Review Center admin-gate API — development milestone RC-1

Status: **development only**. This is a stacked branch based on draft spelling PR #67; it is **not on main** and is not deployed.

Read [REVIEW_CENTER_GOVERNANCE.md](REVIEW_CENTER_GOVERNANCE.md) for the full owner policy. All final editor submissions must receive independent administrator signoff.

## Implemented on this branch

- `review_center_cases`, `review_center_assignments`, `review_center_submissions`, `review_center_events` in PostgreSQL via Alembic migration `20261103_0007`.
- Backend `/api/v1/editorial/review-center/*` supports role-checked metadata queue, administrator-created cases, explicit reviewer assignment, reviewer decision, editor proposal and admin approve/return/reject.
- Real identity roles are `reviewer`, `editor`, and `administrator` (not `admin`). Requests require existing verified Siamsil OIDC bearer authentication. There is **no guest/test impersonation mode**.
- Case revisions are checked with row locks; a stale action fails rather than overriding newer work.
- A reviewer must have an explicit assignment and cannot submit twice on the same revision.
- For spelling, two distinct reviewers must submit `accept` before an independent editor may propose and an independent admin may finalize. Admin cannot be one of the case reviewers or the proposing editor.
- Append-only `review_center_events` carry audit history. Original private Bible/corpus text is **not** returned by this metadata-only API.
- No approved case is automatically released; `release_enabled=false` and `rewards_enabled=false` in responses. No reward ledger, cash payout, token minting or publishing is implemented.

## API shape (experimental, excluded from stable OpenAPI until readiness)

```text
GET  /api/v1/editorial/review-center/cases
POST /api/v1/editorial/review-center/cases
POST /api/v1/editorial/review-center/cases/{case_id}/assign
POST /api/v1/editorial/review-center/cases/{case_id}/reviews
POST /api/v1/editorial/review-center/cases/{case_id}/editor-proposal
POST /api/v1/editorial/review-center/cases/{case_id}/admin-finalize
```

This branch deliberately uses metadata references and hashes only; it does not yet import the private Bible spelling CSV into cases.

## Still needed before a functional frontend Review Center

1. **Siamsil ID frontend session integration**: the current frontend has no secure signed-in session/token exchange for protected editorial requests. Do not introduce a hardcoded token, prompt contributors to paste tokens, expose privileged bearer values in localStorage, or pretend a public page is an authenticated dashboard. Choose an approved OIDC flow and server-side session/BFF to securely call the protected APIs.
2. Reviewer-safe read-only case details service, including rights-filtered licensed Bible context. Do not expose raw private archives to browser requests.
3. Reviewer/editor/admin dashboard, task claim/assignment UI, per-case decisions, optimistic conflict handling, audit timeline and mobile accessibility.
4. Migrations and integration tests against an isolated PostgreSQL database, checking separation of duties, audit immutability, rights gates, assignment enforcement and stale revisions.
5. Import bridge from Bible review CSV and other private data queues, with provenance validation, idempotency and rights checks.
6. A separate admin-finalized dataset export gate. `admin_approved` is **not** equivalent to release or model-training clearance.
7. If reviewer rewards are pursued, begin with explicit noncash reputation accounting. Paid or transferable token rewards require independent funding and compliance decisions.

## Commands for review

```bash
cd backend
python -m unittest tests.test_review_center_admin_gate
alembic upgrade head
```

Run Alembic only against a disposable/staging database after verifying your configured `SIAMSIL_DATABASE_URL`; do not run a migration against production without explicit approval.

## Acceptance criteria

Anonymous requests return 401, insufficient roles return 403, missing assignment returns 403, stale revisions return 409, self-finalization returns 403, insufficient independent reviewer approvals return 409, successful admin approval preserves an auditable event and **does not** publish or pay.

**IMPORTANT:** these are targeted tests, not claims of full end-to-end production readiness. New functionality must pass CI and a PostgreSQL-backed integration suite before approval for deployment.
