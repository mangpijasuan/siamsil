# Siamsil

The digital home for the Zomi language and community.

- Production master prompt: `docs/PRODUCTION_MASTER_BUILD_PROMPT.md`
- Latest audit: `docs/AUDIT.md`
- Language data: `data/README.md`

Current engineering target is **Release 1 — Language MVP**. Do not generate the entire platform in one pass. Never modify `data/raw/`. Never fabricate Zomi language data.

## Mandatory architecture context for Claude Code

Before changing Siamsil AI, Chat, translation, datasets, quality control, reviews or release procedures, read:
- `docs/ARCHITECTURE.md`
- `docs/QUALITY_OPERATOR_ARCHITECTURE.md` (**OpenAI-assisted Quality Operator: design, provider-use rules, human review, cost caps and milestones**)
- `docs/DATA_RIGHTS.md`
- `docs/EVALUATION_SET.md`
- `docs/DATA_RELEASES.md`

The Quality Operator is proposed, **not deployed**. Keep the OpenAI-assisted application QA lane separate from Siamsil's independent model training; exclude provider-derived outputs/labels from competitive-model training unless explicitly permitted under current terms. Never auto-approve Zomi corrections or licenses. Never read/stream the private corpus to external APIs without scoped rights, consent, access controls and an authorized purpose. Do not unpause the protected data-release workflow, merge, publish, or deploy without explicit approval. Preserve the established Zomi Standard (Tedim-based) terminology process; human editorial decisions are final.

## Zomi Standard Form spelling corrections

Read `docs/ZOMI_SPELLING_CORRECTION.md` before changing spelling, word completion, dictionary search, Chat/Translate editors or standardization. The experimental spelling service only suggests changes derived from two-reviewer-approved rules in `data/zolai_standard/standard.json`. No rules are adopted yet, and no model-generated guess may be called a validated correction. Never silently overwrite user text; preserve original, offer Accept/Ignore/Undo, and do not merge a machine suggestion into training data. The internal POST spelling endpoint is not yet part of stable OpenAPI.

## Bible-first spelling review policy

Treat Zomi Bible spelling and usage as important *evidence*, **not** infallible Standard Zomi or proof that a passage's wording makes sense. Read `docs/ZOMI_SPELLING_CORRECTION.md` before changing spelling logic. Use `backend/scripts/bible_spelling_review.py` to create **private reference-only** candidate lists from display-cleared Zomi Bible versions and accepted review-check variant families. Human reports of confusing verse wording must be entered as references with a reason, never assumed automatically wrong. Exports are unverified, contain no verse text, and must remain outside the public repo. Two authorized Zomi language reviewers must agree before a standard spelling rule is adopted. Never silently edit scripture, overwrite a review export, or send a Bible corpus to an external API without appropriate rights.

## Review Center governance and rewards (owner decision)

Read `docs/REVIEW_CENTER_GOVERNANCE.md` before implementing contributor reviews, editorial approvals, rewards or release exports. **Every editor-submitted final proposal requires explicit independent admin finalization**; editors cannot publish and admins cannot bypass the existing two-reviewer spelling rule gate. The reward system is a **future proposal**; no cash, debt, future conversion entitlement or $ZOMI token currently exists by virtue of this plan. Track provisional contribution metrics separately from earnings and never mint/payout without funded, legally reviewed policy and explicit authorization.
