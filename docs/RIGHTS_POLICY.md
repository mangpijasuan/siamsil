# Siamsil rights policy: per source, per purpose

Status: in force from 2026-11-19, on the project owner's instruction. Nothing here is legal advice. The register is [DATA_RIGHTS.md](DATA_RIGHTS.md) and `data/rights.json`; the checker is `ml_pipeline/scripts/rights_policy.py`.

## What changed, and what did not

The blanket "block the whole corpus" approach is replaced by a decision for each **source**, each **use** and, where evidence supports it, each verified **subset**. Risk decides how much evidence a use needs; it never lowers the bar to "none".

Not changed:
- The four states stay: `cleared`, `needs_review`, `blocked`, `not_permitted`.
- Every earlier decision and its audit text stays. New decisions are appended (`history`), never rewritten.
- **Production behavior is unchanged.** No decision in the register has been changed to `cleared` by this policy. The parallel corpus is still blocked and hidden by default. The checker is a library and a validator; no serving, export or training path calls it yet. Wiring a path to it needs its own explicit, documented decision.
- Unknown or disputed rights are never cleared automatically. Default is deny.

## The seven uses

| Use | What it covers | Risk | Legacy column |
|---|---|---|---|
| `display` | Showing the text to users, with attribution where owed | low | `display` |
| `retrieval` | Internal retrieval and RAG context, results grounded in the text | medium | none |
| `local_embeddings` | Embeddings made with a model Siamsil runs itself | medium | none |
| `external_llm` | Sending the text to a third-party provider (including embedding or LLM APIs) | high | none |
| `commercial_inference` | Output served through a paid API or product | high | `commercial` |
| `train` | Training or fine-tuning a model | high | `train` |
| `redistribute` | Publishing the text, a dataset or derived weights | high | `redistribute` |

A use with no explicit decision and no legacy column is `needs_review`, which means not allowed. Clearing `display` does not clear `retrieval`; clearing `retrieval` does not clear `external_llm`. Sending private-corpus text to an external provider still needs scoped rights, consent, access controls and an authorized purpose.

The Quality Operator (OpenAI-assisted lane) stays separate from Siamsil's independent model training. Provider-derived outputs and labels stay out of competitive-model training unless the provider's current terms explicitly permit it.

## The four states

| State | Meaning for a use |
|---|---|
| `cleared` | Allowed, on recorded and independently verified evidence (below). |
| `needs_review` | Not allowed. The rights are unknown or being checked. |
| `blocked` | Not allowed. The owner has stopped it until it is cleared. A verified subset may still be cleared on its own evidence. |
| `not_permitted` | Not allowed. The rights holder refused or no permission exists. A subset cannot override it. |

Existing live behavior on `needs_review` sources (for example the dictionary shown with an unreviewed label) is kept as it is until that source is reviewed. It is not extended to any new use.

## Evidence, and what it does not prove

| Evidence | What it supports |
|---|---|
| `written_permission` | The rights holder's own written grant, within its stated scope. |
| `publisher_permission` | The publisher's grant; clears only once `underlying_rights_checked` is true. |
| `open_license` | An open license (for example CC BY 2.0 FR). **CC BY can permit commercial use** with the attribution and conditions it names; record the attribution text owed. Clears only once `underlying_rights_checked` is true. |
| `cc0_declaration` | The uploader waives its own rights. It does not clear other people's rights (CC0 section 4(c)) or contract terms. Clears only once `underlying_rights_checked` is true. |
| `owner_report` | The project owner's report of a permission. It is a lead, not a clearance on its own. |

CC0 declarations, publisher permissions and open licenses are evidence **supporting** a clearance, subject to the underlying rights.

## What a `cleared` decision must record

In `uses.<use>` on a source (or in a subset):

- `status: "cleared"`, `evidence` (what, where it is kept; private material by pointer only), `evidence_type`, `decided_on` (date).
- `decided_by` and `verified_by`: roster codes (for example `O01`, `R02`), never names. **The person who decided cannot be the one who verified.** At least one independent verifier is required for every use, whatever its risk.
- `underlying_rights_checked: true` when the evidence is a CC0 declaration, an open license or a publisher permission.
- `attribution` when the source has `attribution_required` (for example CC BY text).
- `provider_terms` (`product`, `terms_reference`, `reviewed_on`) when the source is `provider_derived`, such as the Gemini-generated Zomi side. Provider terms are checked per use: training another model is a different question from retrieval or commercial inference.
- If a legacy column exists for the use, change it in the same decision. The validator rejects a `cleared` use whose legacy column says otherwise.

A clearance that fails these checks does not authorize anything, and `validate` reports it.

## English and Zomi are separate

Rights in the English source (Tatoeba sentences, mostly CC BY 2.0 FR with some CC0) are separate from rights in the Gemini-derived Zomi text. A combined record (`components`) can be cleared for a use only after **every** component is. The English side may be cleared before the Zomi side; the pairs follow only when both are.

## Verified subsets

A part of a blocked or unreviewed source can be used before the whole source is cleared, if it has its own entry under `subsets`:

- `members_sha256`: the SHA-256 of the sorted record ids it was verified on (`membership_digest`). If the members change, the clearance stops applying until it is re-verified.
- `uses`: the specific uses cleared for the subset, each fully evidenced as above. Anything not listed is not cleared.
- `component_clearances`: for a subset of a combined source, a valid clearance for the same use on **each** component.
- A subset cannot override `not_permitted`.

At run time, `select_usable(records, rights, use, members={subset: ids})` returns the usable records and counts why the rest were excluded. A record that only claims a subset, without being in the supplied membership, is judged as the source alone.

Example (a fixture, not a real decision): 3,000 sentences whose English text is verified as CC BY and whose Zomi translation was written or corrected by a human reviewer, cleared for `retrieval` only. The other 1.77 million pairs stay out.

## Audit

- `history` on a source lists dated decisions in order: append, never edit.
- `validate` fails if history is out of order or undated, a `cleared` use lacks evidence, a combined record is cleared before its components, or a subset's members hash is malformed.
- Rights changes go through a reviewed change to this repository; the git history is the audit log.

## Using the checker

```
python3 ml_pipeline/scripts/rights_policy.py validate
python3 ml_pipeline/scripts/rights_policy.py check parallel_corpus retrieval
```

The first reports problems in the register (it runs in the test suite). The second prints ALLOWED or DENIED with the reason; today every corpus use is DENIED.

## Closing a use, in practice

1. Collect the evidence for **one use** of one source or subset (DATA_RIGHTS.md "Closing an item").
2. Add the entry with the fields above; leave other uses as they are.
3. A second person confirms and is recorded in `verified_by`.
4. Run `validate` and the tests; record the decision in DATA_RIGHTS.md in the same change.
5. Only then may a code path opt in to the decision. That wiring is reviewed separately.
