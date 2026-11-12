# Review Center web UI — Phase 1 (Claude Code review handoff)

This branch starts from `feature/review-center-admin-gate` (PR #68), **not main**, because the backend is not merged there. The initial component is intentionally **not mounted or connected to production APIs**.

## Implemented
- `frontend/components/review/DictionaryReviewForm.tsx`: a mobile-friendly, controlled human review form with English, Zomi, optional Burmese reference, quality flags, three reviewer decisions, a correction field, a required reason, and an optional evidence-only AI suggestion.
- Async submission callback and error handling. No browser credentials, no direct API calls, no auto-approval or publication.

## Claude Code: review and finish before deployment
1. Check PR #68 dependencies and merge strategy; rebase onto a safe base only after its backend is reviewed.
2. Implement a secure Siamsil ID OIDC server session and backend-for-frontend (BFF) authorization with CSRF protection. **Never** put bearer tokens in localStorage, pasted inputs, or browser source.
3. Implement dictionary-specific authenticated review queue APIs. The current experimental Review Center supports `spelling|sentence|term|bible_context`, not dictionary senses. Use the existing editorial dictionary IDs, revision fingerprints, review/lead-editor separation, and PostgreSQL audit records. Avoid parallel approval systems.
4. Connect the component to an authenticated route only after step 2. Do not expose source text to unauthorized users or expose private data in logs.
5. Add on-demand AI assistance through a server-only, rights-gated, cost-limited service. Cite actual permitted source evidence, cache by content fingerprint, and never invent Zomi or auto-decide.
6. Add reviewer assignment, skip/next, editor approval and admin screens, accessibility, loading states, tests, and a staging verification checklist.
7. Ensure proposed corrections are persisted in the correct editorial workflow; the existing generic PR #68 review endpoint accepts a decision/reason but does **not** accept `suggestedZomi`. Do not silently drop it.
8. Run `npm run lint`, `npm run typecheck`, `npm test` and relevant backend tests, and report exact results. No tests have been run by this initial GitHub-only change.
9. Keep `release_enabled=false` and `rewards_enabled=false`. Require independent human approval and source-rights clearance before any release.

## Security boundary
This component is a **UI foundation**, not a completed Review Center or AI model integration. Do not claim reviewers can use it until secure authentication, persistence, and tests are implemented.
