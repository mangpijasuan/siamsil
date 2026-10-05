# Translation model evaluation

Updated: 2026-10-05
Phase: [ROADMAP.md](ROADMAP.md) Phase 2

Every translation system, whether today's retrieval, a hosted model, or a Siamsil fine-tune, is judged the same way: on the hidden human evaluation sets from [EVALUATION_SET.md](EVALUATION_SET.md), with the same metrics, against the same baselines. The parallel corpus test split is machine-generated and is never used to claim quality.

## Steps

All commands use `ml_pipeline/scripts/mt_eval.py`. Hypothesis files are written under `data/evaluation/runs/` and stay out of git (`*.jsonl`); the score files (`.json`) contain only numbers and can be committed.

1. **Run each system on each set**, one direction per set:

   ```bash
   python3 ml_pipeline/scripts/mt_eval.py translate --system retrieval \
     --eval data/evaluation/human/en-zomi-v1.jsonl --out data/evaluation/runs/en-zomi-v1/retrieval.jsonl
   ```

   Other systems (hosted model, fine-tunes) write the same format: one line per item with `id`, `hypothesis`, and `system`.

2. **Score all systems together**:

   ```bash
   python3 ml_pipeline/scripts/mt_eval.py score --eval data/evaluation/human/en-zomi-v1.jsonl \
     --hyp data/evaluation/runs/en-zomi-v1/retrieval.jsonl \
     --hyp data/evaluation/runs/en-zomi-v1/candidate.jsonl \
     --out data/evaluation/runs/en-zomi-v1/results.json
   ```

   Reports chrF++ (primary) and BLEU with 95% bootstrap intervals, chrF++ per domain, missing and empty outputs, and a paired bootstrap comparison between every pair of systems. Results record the evaluation set's SHA-256.

3. **Apply the automatic gate** across both directions:

   ```bash
   python3 ml_pipeline/scripts/mt_eval.py gate \
     --results data/evaluation/runs/en-zomi-v1/results.json \
     --results data/evaluation/runs/zomi-en-v1/results.json \
     --candidate candidate --baseline retrieval --baseline hosted-llm
   ```

   Passes only if the candidate beats every baseline on chrF++ in every file with paired-bootstrap p < 0.05.

4. **Human evaluation.** Passing the automatic gate is necessary, not sufficient. Native-speaker reviewers then rate a blinded sample for meaning, naturalness, omissions, additions, and errors before any model ships.

## Metrics

- **chrF++** is the primary metric. It works on characters and word pairs, which suits languages without large tokenizers or standard word lists.
- **BLEU** is reported for comparison with other work, not used for decisions.
- Learned metrics (COMET and similar) are not used until shown to agree with Zomi speakers' judgments.

## Baselines

| System | Status |
|---|---|
| `retrieval`: best-matching corpus pair, as the app does today, excluding held-out pairs | Implemented |
| Hosted model, untuned | Not yet: needs a provider-neutral adapter and a decision about sending the hidden sets to an outside service |
| Siamsil fine-tune | Needs cleared training data, a licensed base model, and GPU training |

## Rules

- Never tune a system, prompt, or filter on the evaluation sets. Use the corpus validation split or a separate development set for that.
- Report every system run on a set version, not only the best one.
- When an evaluation set gets a new version, rescore all baselines on it.
