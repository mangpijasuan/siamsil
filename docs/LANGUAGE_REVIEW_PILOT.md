# Language-data review pilot

This is a **local preparation workflow**, not a dataset approval or model-training authorization. The 1.78M-pair corpus contains machine-generated Zomi text. A quality flag means “inspect this,” not “the translation is wrong,” and an unflagged row is not automatically correct.

For the representative 600-row audit, review labels, and a separate hidden human gold set, see `docs/ZOMI_TRANSLATION_REVIEW_GUIDE.md` and `docs/GOLD_TEST_WORKFLOW.md`. The 100-row packet below intentionally oversamples flagged rows and cannot estimate overall corpus quality.

## Rights gate (open)

Before redistribution, commercial training, or publication of reviewed derivatives, a responsible owner must record the actual license terms and permission evidence for each item below. Until then, keep the review packet local.

| Asset | Evidence to collect | Status |
| --- | --- | --- |
| Zomi dictionary master | Creator/rightsholder, source file, permission for app display, corrections, redistribution, and training | Needs review |
| OPUS/Tatoeba English sentences | Exact source datasets and versions, per-source licenses, attribution, commercial/training permissions | Needs review |
| Machine-generated Zomi sentences | Provider/model terms for the generation period, output rights, downstream training and redistribution permissions | Needs review |
| Bible and reviewed phrases | Source edition/contributors, quotation/display rights, translation and derivative permissions | Needs review |
| Proposed Library resources | Rights holder and per-resource upload/display/download permissions | Needs review |

No row should be promoted to a trusted public release solely because this worksheet exists.

## Prepare the 100-row packet

Run from the repository root:

```bash
./.venv/bin/python ml_pipeline/scripts/prepare_review_pilot.py
```

The script reads the existing SQLite release in read-only mode and writes `data/exports/review_pilot_100.jsonl`, which is ignored by Git. It selects flagged **training-split** rows deterministically, includes at least two examples of each available quality flag, and fills the remainder from the flagged pool. It does not touch validation/test rows or call an AI provider. The sample is diagnostic, not a statistically representative quality estimate or a hidden evaluation set.

The script will not overwrite an existing packet. Use `--output` with a new local path for another run.

The packet is immutable input for reviewers. Store decisions in a separate file keyed by `sentence_id`; do not overwrite the machine candidate or source fields. Suggested decision fields: `sentence_id`, `decision` (`approve`, `edit`, `reject`, `uncertain`), `corrected_zomi`, `reviewer_id`, `reviewed_at`, and `notes`. An approval means an identified human checked that row; it does not resolve the source license.

## Human review gate

1. Agree on spelling/dialect, names, numbers, punctuation, borrowed terms, and ambiguity guidelines with qualified Zomi reviewers.
2. Have reviewers assess meaning and naturalness without treating the model text as authoritative. Send disagreements to an adjudicator and retain both decisions.
3. Audit the results by flag type and source/model. Record error types and reviewer agreement; do not extrapolate a single quality percentage from this enriched sample.
4. Only after rights and evaluation gates are satisfied, propose corrections for a new immutable language release. Do not edit the currently deployed SQLite file in place.
