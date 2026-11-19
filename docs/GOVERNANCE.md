# Siamsil Zomi language governance

**Decision (2026-11-19, project owner):** Siamsil has one human linguistic authority, the project owner. The owner created the Siamsil Zomi Standard Form (SZSF) and makes Siamsil's final linguistic decisions. No other human editor, reviewer, committee or independent approver is required. This extends the working-phase decisions of 2026-11-13 (the creator adopts standard-form rules alone, [ZOMI_STANDARD_FORM.md](ZOMI_STANDARD_FORM.md)) and 2026-11-18 (owner-approved records, [SZSF.md](SZSF.md)) to every Zomi record Siamsil keeps.

The guiding rule: **AI does the repetitive analysis and preparation; the owner makes the authoritative linguistic decisions.**

## What the owner decides

Within Siamsil, only the owner:

- approves Zomi spelling, grammar, terminology and orthographic conventions;
- creates, changes and adopts SZSF rules ([ZOMI_STANDARD_FORM.md](ZOMI_STANDARD_FORM.md));
- accepts, corrects or rejects dictionary entries;
- approves sentence translations and linguistic examples;
- approves groups of records through an explicit batch procedure (a sheet or queue the owner decided row by row, or a rule applied to records the owner previewed);
- publishes new versions of the Siamsil Zomi Standard.

Claude, Codex, Gemini and other AI agents are assistants. They analyse, propose and explain. They never approve anything, and their output is never recorded as human-verified.

Other people may still help: a second Zomi speaker may review or confirm a record, and their review is kept. Their confirmation is optional, and it does not override the owner.

## Three separate questions

| Question | Who decides | Where it is recorded |
|---|---|---|
| **Linguistic authority**: is this Zomi correct and standard? | The owner | review and revision records (below) |
| **Original intellectual property**: who created this text? | Facts, recorded as provenance | `data/rights.json` provenance, the source records |
| **Third-party rights**: may Siamsil use this text for this purpose? | Licenses, grants and provider terms, recorded by the owner | `data/rights.json`, [DATA_RIGHTS.md](DATA_RIGHTS.md) |

An owner's linguistic approval is not legal clearance. Reviewing, correcting or approving someone else's sentence does not transfer its copyright, and it does not change the terms under which machine-generated text was produced. A pair the owner approves from the blocked parallel corpus stays blocked for display, training and every other use until its rights are cleared. Where a law, license, contract or consent form needs another person's authorization, that requirement stands.

## Statuses

Every reviewed record has one linguistic status. The stored SOP names stay as they are. `corpus_reviews.linguistic_status` reports them under these names, and `corpus_revisions.linguistic_statuses` also counts approved corrections:

| Status | Meaning | Stored as |
|---|---|---|
| `unreviewed` | No person has decided anything. Bulk AI or automatic processing leaves a record here. | no review record (`UNREVIEWED` in SZSF) |
| `ai_suggested` | An AI agent proposed a change that no person has decided on yet. | a proposal file, never a review record (future PRs) |
| `owner_reviewed` | The owner rated it acceptable; no approval yet | `READY_FOR_APPROVAL` |
| `owner_approved` | The owner approved it, or approved a correction to it ("edit and approve") | `HUMAN_APPROVED`, or an approved revision |
| `rejected` | The owner rejected it; it is never shown or exported | `REJECTED` |
| `needs_recheck` | Reviewed but open: a fix is wanted, the owner deferred it, or the text changed after an approval | `NEEDS_CORRECTION` |

An approval counts only for the text it was given. If the text or a later review changes, the approval lapses and the record returns to `owner_reviewed` or `needs_recheck`.

## How an owner-only decision is recorded

- **Roster.** The private roster (`siamsil-data/reviews/roster.csv`) may list one code with the role `owner`, for example `O01,owner`. The owner's code may act as reviewer and as lead editor. A second `owner` line is refused.
- **Marked approvals.** When the owner approves their own review or correction, the approval or revision carries `"approval": "owner_sole"`. Anyone reading the record can see that one person reviewed and approved it. Only the roster's owner may make such a record; the roster check (`roster_problems`, run when records are saved and imported) refuses anyone else. Everyone else still needs a different person to approve.
- **Append-only history.** Decisions are appended to the decisions files (`corpus-reviews.jsonl`, `corpus-revisions.jsonl`, `dictionary-reviews.jsonl`, `dictionary-revisions.jsonl`) and are never edited or deleted. The PostgreSQL copy refuses edits and deletes. A later decision supersedes an earlier one, so any change can be traced and reversed by recording a new decision.
- **Originals are kept.** A correction never overwrites the source. The corpus keeps the original Zomi in `raw_target_text`, SZSF keeps `zomi` beside `zomi_standard`, and `siamsil-data` originals are never edited.
- **Evaluation sets** keep their own label: a set the owner translated and reviewed is marked `independently_reviewed: false` ([EVALUATION_SET.md](EVALUATION_SET.md)). That is an accurate description, not an extra approval step.

## Doing it

Corpus pairs, in one pass: rate the batch sheet (meaning, fluency, and a corrected Zomi where needed), then save it with `--owner-decides`:

```bash
python3 ml_pipeline/scripts/review_sample.py record review.csv key.csv --reviewer O01 --owner-decides
```

| What you wrote on a row | What is recorded |
|---|---|
| meaning 2, fluency 1 or 2, no correction | approved (`owner_sole`) |
| meaning 0, no correction | rejected |
| meaning 1 or 2 and a corrected Zomi | edit and approve: the correction is approved (`owner_sole`) and applied at the next rebuild |
| meaning 0 and a corrected Zomi | refused: 0 rejects the pair, so the correction would never apply |
| anything else (for example meaning 1, no correction) | deferred: stays `needs_recheck` |

Without `--owner-decides`, only the ratings are saved, and the approval sheet and corrections sheet (`approval-sheet`, `approve`, `corrections-sheet`, `revise`) work as before. The owner may approve their own rows there too.

Dictionary senses: `backend/scripts/dictionary_review.py approve` and `revise` accept the owner as approver of their own reviews and corrections, and mark them `owner_sole`.

Standard-form rules: the owner adopts a rule in `data/zomi_standard_form/standard.json` with `adopted_by: "creator"` ([ZOMI_STANDARD_FORM.md](ZOMI_STANDARD_FORM.md)).

## AI agents

Agents are modules of the existing pipeline, not a new platform. They write proposals with the model, version and prompt that made them, and the owner decides each one. The plan is in [AUDIT.md](AUDIT.md) ("Review and governance audit, 2026-11-19"). Restricted data stays on local models unless an external provider is authorized for that use in `data/rights.json` (`external_llm`). The parallel corpus is not authorized for any external provider.
