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
