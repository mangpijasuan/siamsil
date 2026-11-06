# Siamsil AI Dictionary Builder — 10,000-candidate pilot

## Objective
Mine up to **10,000 English lexical candidates** from the existing read-only SQLite language release, without adding any unreviewed material to the published dictionary. This is an SOP-01 discovery tool, **not** an AI translator or a 10,000-verified-entry release.

## First working module
`ml_pipeline/scripts/dictionary_builder.py` streams English source sentences from the existing `parallel_sentences` SQLite table, counts candidate tokens, excludes existing dictionary headwords and the protected evaluation holdout, and exports deterministic JSONL.

```bash
python ml_pipeline/scripts/dictionary_builder.py --target 10000 --min-frequency 3 --out /tmp/siamsil-dictionary-candidates.jsonl
python -m unittest discover -s backend/tests -p 'test_dictionary_builder.py'
```

A language SQLite release must already exist. Result volume depends on corpus vocabulary; the target is an **upper limit, not a guaranteed count**. This first pass extracts single English words only. It intentionally does not claim POS, senses, Zomi equivalents, etymology, or validity. Source English corpus and generated Zomi permissions remain under review; therefore these are **internal candidates** and must not be redistributed or trained on.

## Target integration (incremental, not yet implemented)
1. **SQLite FTS5**: continue using the current immutable language DB as a read-only evidence source, never write draft entries into `dictionary_entries` or its public FTS index.
2. **PostgreSQL**: introduce `dictionary_candidate` with candidate ID, normalized headword, language, source/provenance, evidence IDs, model/version, rights status, and draft content; `dictionary_review` with reviewer identity, decision, feedback and revision; `dictionary_release` with immutable approved version, rights signoff, and publish manifest.
3. **FastAPI**: add authenticated `/api/v1/editorial/dictionary-candidates` listing, assigned review, corrections, editor signoff, and release operations. Enforce contributor/reviewer separation, role-based permissions and audit logging server-side.
4. **Quality**: cluster inflections and duplicate senses; distinguish headwords, senses and phrases; filter names, noise and borrowed forms; independently validate bilingual meaning and natural Standard Zomi.
5. **Rights**: resolve source permissions per use (internal display, training, redistribution, commercial). Never interpret quality scores as license clearance.
6. **Human approval**: use SOP `DRAFT -> NEEDS_CORRECTION -> READY_FOR_APPROVAL -> HUMAN_APPROVED -> RELEASED` with a distinct `REJECTED` path. A machine never marks `HUMAN_APPROVED`.
7. **Release**: only approved, rights-cleared content enters a newly built, versioned SQLite FTS5 release. Preserve prior release for rollback.

## Pilot acceptance criteria
- Deterministic output, max 10,000 candidates, and no mutation of SQLite.
- Dedup against existing English headwords.
- Every candidate has source evidence; marked DRAFT and not human verified.
- No automatic model training or publication.
- Review a stratified sample with qualified Zomi editors; report acceptance, duplicates and spelling/meaning error rates.
- Move to 10,000-candidate batch only after a smaller (e.g. 1,000) sample is reviewed.

## Implementation stages
| Stage | Deliverable |
| --- | --- |
| 1 | Read-only candidate miner and tests (this PR) |
| 2 | PostgreSQL candidate/review models, migration, authenticated FastAPI endpoints |
| 3 | Editorial UI, claims/assignments, review and audit |
| 4 | Multiword, morphology, bilingual alignment and optional model-assisted drafting |
| 5 | Rights-aware release, immutable FTS index rebuild and rollback |
| 6 | Measured pilot and scale-out |

The 10,000 figure is a candidate target, **not** 10,000 new verified Standard Zomi words. Existing 1.775M aligned pairs are machine-generated on the Zomi side and are not a human-verified dictionary.
