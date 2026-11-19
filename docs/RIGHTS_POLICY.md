# Siamsil rights policy: three clearance paths, per source and per use

Status: in force from 2026-11-19, on the project owner's instruction. Revised the same day to replace the universal second-verifier rule with three proportionate paths. Nothing here is legal advice. The register is [DATA_RIGHTS.md](DATA_RIGHTS.md) and `data/rights.json`; the checker is `backend/services/rights_policy.py` (command line: `ml_pipeline/scripts/rights_policy.py`).

The policy exists to make legitimate use of data possible, with a record that shows why each use is allowed. It asks for the evidence a use actually needs: an owner-written dictionary entry does not need the same process as machine-generated text under a provider's terms.

## Three separate questions

Siamsil keeps three kinds of approval apart. One never stands in for another.

| Question | Who answers | Where it is recorded |
|---|---|---|
| **Legal rights**: may Siamsil use this text for this purpose? | The owner, on the path below | `data/rights.json` (`uses`), this policy |
| **Linguistic quality**: is the Zomi correct? | Zomi reviewers and editors ([SOP_QUALITY_GATE.md](SOP_QUALITY_GATE.md)) | review records, tiers |
| **Engineering**: does the code enforce the decision? | Code review | this repository |

A rights clearance never changes a record's review status or training tier (Essential 3000 stays `bronze` when cleared for training), and the checker rejects review fields in a rights decision. A reviewed, accurate sentence is not thereby cleared, and a cleared one is not thereby accurate.

## The three paths

| Path | For | Who decides | Second reviewer |
|---|---|---|---|
| **A, `owner_original`** | Data the project owner created: dictionary entries, sentences, lists the owner wrote | The owner (owner roster code, `O01`…) | Optional |
| **B, `open_license`** | Third-party data under a verified open license or public-domain dedication, or a **written** grant whose recorded scope names the use | The owner, citing the evidence | Optional |
| **C, `restricted`** | Disputed, flagged, provider-derived, combined or otherwise uncertain data, and anything resting on a verbal report or a publisher's claim | The owner | **Required**: `verified_by` names someone other than the decider |

### Path A: owner-original data

The source (or subset) carries `origin: "owner_original"` and a `provenance` record. Before any use can clear, the checker confirms automatically, every time it runs:

- `attestations` include `sole_author` and `no_third_party_content` (the owner states they wrote it and copied nothing from others);
- `ai_assistance` says whether an AI tool drafted text (`none`, or what). It is a disclosure, not a bar;
- `sha256` pins the exact file the attestation covers;
- the decision is dated on or after `attested_on`, and `decided_by` is an owner roster code;
- the source has no Path C trait (below).

### Path B: verified open license or written grant

- `license` is one the checker knows (`public-domain`, `CC0-1.0`, `CC-BY-2.0-FR`, `CC-BY-3.0`, `CC-BY-4.0`, `CC-BY-SA-4.0`, `CC-BY-NC-4.0`, `MIT`) and permits the use: CC BY-NC cannot clear `commercial_inference` or `redistribute`. A license not on the list (NoDerivatives, custom terms, "see website") goes through Path C.
- Attribution is recorded where the license or source requires it (CC BY permits commercial use, with attribution); obligations such as share-alike are recorded.
- `underlying_rights_checked: true`: the licensor or grantor holds the rights it grants. A re-upload's license, or a CC0 label on someone else's sentences (CC0 section 4(c)), does not.
- A written grant records `grant.grantor`, `grant.date`, `grant.wording`, `grant.kept_at` (private storage, by pointer) and `grant.scope`; only the uses in `scope` clear. A verbal permission is not a grant: it stays a lead until it is in writing.

### Path C: restricted or uncertain

A decision is escalated to Path C automatically, and an A or B decision on it authorizes nothing, when:

- the text is `provider_derived` (for example the Gemini-generated Zomi side of the parallel corpus): the provider terms in force when it was generated are recorded per use (`provider_terms`), and provider-derived output stays out of competitive-model training unless those terms explicitly permit it;
- the source is `disputed`, or has `risk_flags` (for example the 50K Translation Master, whose authorship record was corrected on 2026-11-17);
- the source combines `components` with separate rights (the combined corpus pairs);
- the evidence is an `owner_report` (a verbal permission) or a `publisher_permission` that needs confirming.

Path C needs evidence, `underlying_rights_checked` where the evidence is someone else's grant or license, and an independent verifier.

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

Each use is decided separately. A use with no explicit decision and no legacy column is `needs_review`: not allowed. Sending private-corpus text to an external provider still needs scoped rights, consent, access controls and an authorized purpose. The Quality Operator (OpenAI-assisted lane) stays separate from Siamsil's independent model training.

## The four states

| State | Meaning for a use |
|---|---|
| `cleared` | Allowed, on a decision that is valid on its path. |
| `needs_review` | Not allowed. The rights are unknown or being checked. |
| `blocked` | Not allowed. The owner has stopped it until it is cleared. A verified subset may still be cleared on its own evidence. |
| `not_permitted` | Not allowed. The rights holder refused or no permission exists. A subset cannot override it. |

Existing live behavior on `needs_review` sources (for example the dictionary shown with an unreviewed label) is kept as it is until that source is reviewed. It is not extended to any new use.

## What a `cleared` decision records

In `uses.<use>` on a source, or on a subset:

- `status: "cleared"`, `path`, `evidence` (what it is and where it is kept; private material by pointer only), `evidence_type`, `decided_on`, `decided_by` (a roster code, never a name).
- Path-specific fields above (`license`, `attribution`, `grant`, `underlying_rights_checked`, `provider_terms`, `verified_by`).
- If the use has a legacy column, it changes in the same decision; `decide` does this, and `validate` rejects a mismatch.

A decision that fails its path's checks does not authorize anything, and `validate` reports it.

## Verified subsets

Part of a blocked or uncleared source can be used before the whole source is cleared, if it has an entry under `subsets`:

- `members_sha256`: the SHA-256 of the sorted record ids it was cleared for (`membership_digest`). If the members change, the clearance stops applying.
- `members_file` (optional): a file of member ids, one per line, relative to `data/`. Code that reads a source record by record (`usable_ids`) serves only the ids in it, and only while it matches `members_sha256`.
- `uses`: the uses cleared for the subset. A subset may carry its own `origin`/`provenance` (for example owner-written rows inside a larger file, Path A), but inherits every Path C trait of its source.
- `component_clearances`: for a subset of a combined source, a valid clearance for the same use on **each** component.
- A subset cannot override `not_permitted`.

## Where the decisions are enforced

| Code path | Use checked | Behavior |
|---|---|---|
| Training export, `ml_pipeline/scripts/export_datasets.py` | `train` | A source is exported only if the policy clears `train` (the earlier code read the legacy column only). `--allow-uncleared` still admits `needs_review`, never `blocked`. |
| Bible import, `ml_pipeline/scripts/import_usx_bibles.py` | `display`, `train` | The statuses written into `bible_versions.sqlite`, which the API filters on, come from the policy. |
| API corpus search, `backend/services/language_engine.py` | `display`; Siamsil AI also `retrieval` | Served only when `SIAMSIL_SERVE_PARALLEL_CORPUS` is on **and** the register clears the corpus, as a whole or as verified subsets (then only their pairs). The switch alone no longer exposes the corpus. |
| Deploy bundle, `backend/scripts/package_data.py` | — | Carries `rights.json` so the running API can read the register. With none found, the API denies every gated use. |

Application code asks the register through `backend/services/rights.py`:

```python
from services import rights
rights.allowed("bible_web", "retrieval")                 # bool
rights.decision("parallel_corpus", "display").reason     # why not
rights.usable_ids("parallel_corpus", "display")          # None = whole source, else cleared subset ids
```

**Not yet enforced** (decision needed): Siamsil AI quotes Bible passages as answer context, which is `retrieval`. The World English Bible is cleared for it (Path B, 2026-11-19); the Bible Society versions (TDB, TB77, FCL, HCL06), KJV and Judson are `display`-cleared but have no `retrieval` decision, and the permission letter's wording has to be checked for it. The Bible lookup is not gated yet, so production does not change before that decision; gating it is a one-line `rights.allowed(version["rights_source"], "retrieval")` filter in `services/bible_lookup.py`.

## Using the checker

```bash
python3 ml_pipeline/scripts/rights_policy.py validate
```

```bash
python3 ml_pipeline/scripts/rights_policy.py report essential_3000
```

```bash
python3 ml_pipeline/scripts/rights_policy.py check bible_web retrieval
```

`validate` reports problems in the register (it runs in the test suite). `report` lists, for every source and use, whether it is allowed and, if not, the path it needs and what is missing. `check` prints ALLOWED or DENIED with the reason.

Recording a decision (the person deciding runs it; the tool only records what it is given and refuses a decision that does not validate):

```bash
python3 ml_pipeline/scripts/rights_policy.py attest essential_3000 no_third_party_content --by O01
```

```bash
python3 ml_pipeline/scripts/rights_policy.py decide essential_3000 train --path owner_original --by O01 \
  --evidence "Owner's authorship statements, 2026-10-25 and 2026-10-26; attestation of no third-party content"
```

```bash
python3 ml_pipeline/scripts/rights_policy.py decide bible_web retrieval --path open_license --by O01 \
  --evidence-type public_domain --license public-domain --underlying-rights-checked \
  --evidence "Public-domain dedication, copr.htm in the eBible.org engwebu download, received 2026-10-17"
```

`decide` replaces the per-use entry, changes the legacy column with it, and appends a dated `history` line that keeps the previous status. Add `--dry-run` to see the result without writing. Record the decision in DATA_RIGHTS.md in the same change; the git history is the audit log.

## Eligible now (2026-11-19)

From `report`, against the real register. 22 of 168 source-uses are allowed: the 18 legacy clearances, plus the owner's four decisions of 2026-11-19, the first made under this policy:

| Decided 2026-11-19 by O01 | Path | Effect |
|---|---|---|
| Essential 3000 (`essential_3000`, 3,000 headwords): `train` | A | Its example sentences and phrases are admitted to the training export without `--allow-uncleared`, still `bronze`. No second reviewer. Other uses not decided. |
| World English Bible (`bible_web`, 31,098 verses): `retrieval`, `local_embeddings`, `external_llm` | B | Public domain: usable as retrieval context, for local embeddings, and with outside providers. All seven uses now cleared. |

Still open:

| Source | Path | What is missing |
|---|---|---|
| Essential 3000, other uses | A | The owner's decision for display, retrieval, embeddings, external LLM, commercial inference, redistribution (`decide`). |
| Tatoeba English side (`parallel_corpus_english_tatoeba`) | B | The license of the OPUS release and of the sentences used, and the attribution text. On its own it is English only; the pairs also need the Zomi side. |
| Bible Society versions, TongDot, primer, *Zokam le Zolai*, Haokip-Lind | B | The written grant recorded (grantor, date, wording, where kept, scope). Verbal reports stay leads. |
| Gemini Zomi side, combined corpus pairs (1,775,043 pairs) | C | Provider terms per use, and an independent verifier. The corpus is not cleared, as a whole or in part. |
| 50K Translation Master, Zomi Standard Dictionary, ISO Improved Bible text | C | Sources identified (50K), compiler and copyright holder (Standard Dictionary), authorship of the changes (ISO Improved). |
