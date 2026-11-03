# Siamsil Zomi Standard Form — Spelling Suggestions v1

Status: proposed implementation; no human spelling rules have yet been adopted (the current `data/zolai_standard/standard.json` has `version: 0.0.0` and `rules: []`). No suggestion may be represented as approved until the existing two-reviewer process records it.

This feature belongs to the **Siamsil** brand and targets **Zomi Standard Form (Tedim-based Zomi)**. It does not change the identity of the platform or imply that a spellchecker itself can settle standard language usage.

## Design and boundaries

- The approved rules in `data/zolai_standard/standard.json` are the only v1 authority; the existing `ml_pipeline/scripts/zolai_standard.py` remains the offline standardization tool and records provenance.
- `backend/services/zomi_spelling.py` provides deterministic spelling proposals. `POST /api/v1/words/spelling/suggest` accepts `{"text":"..."}` (experimental internal route, intentionally omitted from the stable OpenAPI schema until review) and returns `original`, `suggested`, `standard_version`, `status`, and suggestion ranges with rule IDs, rationale and `replace`/`flag` modes.
- `replace` means the user may accept a proposed approved-rule change; the API still **never edits submitted input, source data, model training, or the database**. UI should show underlines and an opt-in Accept/Undo button. A product-level auto-apply setting may be added later only for explicitly approved context-safe rules and with undo.
- `flag` means a context-dependent spelling is displayed for review **without changing** the proposed full text.
- Empty standard returns `no_approved_rules`; a missing standard returns `not_configured`; corrupted/unapproved rules fail closed.
- The existing `/api/v1/words/suggest` remains prefix completion from display-cleared Zomi Bible words, not correctness judgments. Frequency and near-edit-distance should **not** be treated as authoritative spelling.
- Do not create spelling rules from an LLM, Bible frequency, unverified corpus, or external styles without the required independent Zomi human reviewer adoption.
- If future implementation uses OpenAI for quality suggestions, keep those outputs tagged as provider-derived and outside independent model training unless expressly permitted under current provider terms.

## Follow-up milestones

1. Review and harden the experimental endpoint, then explicitly include it in the OpenAPI contract and regenerate TypeScript client types; verify CI before external clients adopt it.
2. **Implemented in this draft PR:** the Chat composer and Zomi-to-English Translate textarea use a 450 ms debounced suggestion panel with Accept / Ignore / Undo. Requests are only made from the browser when input is present; the API uses only reviewer-approved rules and no external LLM. A later UI iteration may add nonintrusive inline underlining and keyboard navigation, with mobile accessibility testing.
3. Obtain two independent native-speaker approvals for real spelling rules, including examples and context exceptions, and increase the standard version.
4. Add phrase-level and morphological suggestions, contextual disambiguation and quality measurement against a sealed independently authored human benchmark.
5. Support offline/mobile local rule caching with versioned updates and documented safeguards.

**There are intentionally no invented Zomi spelling corrections shipped in this milestone.**
