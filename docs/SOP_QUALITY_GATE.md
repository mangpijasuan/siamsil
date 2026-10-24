# Siamsil SOP Quality Gate v1

This is an incremental implementation of the **draft** Zomi AI/SI Language
Development SOP Manual, specifically SOP-07 (human review) and SOP-08 (dataset
preparation). It does not replace the manual or grant editorial authority.

## Use

```bash
python -m unittest discover -s backend/tests -p 'test_sop_quality_gate.py'
python ml_pipeline/scripts/sop_quality_gate.py candidate.jsonl --report quality-report.json
```

The gate exits nonzero on failure. Each JSONL candidate record requires:
`id`, `english`, `zomi`, `origin_language` (`en` or `zom`),
`split` (`train`/`validation`/`test`), `split_family_id`,
`review_status=HUMAN_APPROVED`, `contributor_id`, `reviewer_id`,
`approver_id`, `approval_version`, `source_id`, and
`rights: {"train": true}`.

This is a proposed **internal controlled-export schema**, not a migration of the
existing 1.775M-row corpus. Existing machine-generated/unverified pairs must
not be relabeled human-approved or training-rights-cleared. The script has no
authority to verify the authenticity of signatures, source contracts, or reviewer
identity; it checks declared metadata and rejects missing authorizations.

## Manual mapping

- **SOP-07:** Require human approval, distinguish contributor from reviewer
  and approver, preserve provenance and version IDs.
- **SOP-08:** Validate schema, IDs, UTF-8 input, duplicate bilingual pairs,
  the same English or Zomi sentence in more than one split, split-family
  isolation, and explicit training permission. Reviewer IDs are compared
  without case or surrounding spaces.
- **SOP-09/11:** This is a pre-training gate, **not** a trained-model
  performance evaluation or evidence of language accuracy.

## Before production integration

1. Build authenticated server-side editorial decisions with role checks and
   immutable audit logs. Do not trust user-submitted `HUMAN_APPROVED` flags.
2. Bind approved decisions to exact text hashes and reviewer identities.
3. Resolve licenses using the rights registry with source-specific permissions;
   do not trust arbitrary `rights` JSON for production admission.
4. Add near-duplicate and source/document-family leakage checks.
5. Maintain the SOP-02 60-original / 20-per-batch process in a future review
   workflow. This CLI intentionally does not enforce it because other sources
   use different contribution workflows.
6. Require a separate final release authorization for publication; passing
   this quality gate is necessary but **not sufficient**.
