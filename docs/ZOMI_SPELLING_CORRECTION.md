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

## Bible-first spelling evidence and human-review queue

Bible texts are a **primary observation source**, not automatically correct Standard Zomi and not a guarantee that a phrase makes sense outside its scriptural context. Never describe a Bible variant or an archaic/figurative expression as an error solely because another spelling is common.

The repository now provides `backend/scripts/bible_spelling_review.py`, a bounded **reference-only review exporter**:

```bash
python3 backend/scripts/bible_spelling_review.py \
  --db data/processed/bible/bible_versions.sqlite \
  --out ../siamsil-data/standard/derived/bible-spelling-review.csv \
  --limit 500
```

It scans only Zomi Bible editions marked `display_status=cleared` in the existing read-only versions database, and compares tokens/phrases against *known variant families* from `data/zolai_standard/rule_checks.json`. The resulting CSV contains Bible version, book/chapter/verse IDs, style-check ID, observed spelling, alternatives, and blank reviewer fields. **No Bible verse text is exported**, no approved spelling is manufactured, and no original verse is changed. Place the file in the **private `siamsil-data` workspace**, never inside the public application repository. Existing review exports are not overwritten.

For unclear or seemingly unnatural Bible wording that variant matching cannot identify, a native speaker may create a UTF-8 CSV of references and explanations (not Bible passages):

```csv
version,book_id,chapter,verse,reason
tdb,1,1,1,Needs contextual meaning review
```

Then run the exporter with `--manual-reports ../siamsil-data/standard/manual-verse-flags.csv`. These reference IDs must exist in a display-cleared Zomi edition; each is added as `check_id=manual`. Reports are **review leads, not automatic findings or corrections**. The sample reference above is a format illustration, not a claim about that verse.

A reviewer should open the verse in its original displayed context, examine the full paragraph and translation date, compare any other permitted Bible editions, check the Zolai standard references, and distinguish (a) a genuine spelling variant, (b) biblical/archaic vocabulary, (c) a translation/semantic concern, and (d) insufficient evidence. If unresolved, **flag** rather than replace. Two separate authorized Zomi reviewers must approve any adopted *standard spelling*; a proposed alteration of Bible scripture requires a separate, rights-respecting editorial procedure and is never performed by this feature.

**Known limitations:** Automatic candidate generation does not determine if Bible wording “makes sense” and may include many legitimate variants or miss contextual problems. It is intentionally limited to known review-check alternatives; prioritization and a reviewer-facing UI are later milestones. Bible display permission is not automatically training, redistribution or commercial permission.

## Admin approval and future reviewer compensation

The [Review Center governance and contributor rewards contract](REVIEW_CENTER_GOVERNANCE.md) adds an independent **admin finalization** step after the native-speaker reviewers and editor proposal. Do not mark a spelling rule final, update the standard, or allow a release solely because an editor approves. Reviewer cash or $ZOMI rewards are only optional future funded programs; tracking task counts is not the same as creating an earning or payout obligation.
