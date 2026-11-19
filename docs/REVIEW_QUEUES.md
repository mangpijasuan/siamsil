# Review queues: clusters and priority

Status: **runbook** (PR 2 of the review plan in [AUDIT.md](AUDIT.md)). Run on the computer that holds `siamsil-data`. The corpus is `blocked` in `data/rights.json`: every output stays in the private data repository.

`ml_pipeline/scripts/review_clusters.py` decides the **order** in which you review corpus pairs, so each sitting covers the pairs where one decision teaches the most. It reviews nothing, approves nothing and changes no text. You still decide every pair ([GOVERNANCE.md](GOVERNANCE.md)). It runs entirely on your computer, with no model or outside service.

## What it groups

| Cluster | What is in it | Why review them together |
|---|---|---|
| `template` | English that is the same once case, spacing, punctuation and numbers are set aside ("I am 30 years old." / "I am 45 years old.") | One correct pattern for many pairs. If they were translated several ways, that inconsistency shows at once. |
| `near` | English sentences sharing most of their words and word pairs (about one word changed in a sentence of ten words or more), among the rows you name with `--near-scope` | Similar sentences read side by side. Their Zomi is expected to differ. |

## How it orders them

Every cluster gets a priority, and the parts of it are written to `clusters.jsonl` so you can check the order:

| Part | Formula | Meaning |
|---|---|---|
| frequency | log2(1 + pairs) | How many pairs this pattern covers |
| inconsistency | (distinct Zomi − 1) / (pairs − 1), template clusters only | The same English template translated in different ways |
| uncertainty | mean of (1 − quality score) + 0.5 per soft flag + 1 for an older or unknown model | How likely the machine Zomi is wrong |
| **priority** | 2 × frequency + 3 × inconsistency + uncertainty | Highest first |

The queue is in three parts:
1. Each cluster's first `--per-cluster` pairs (default 10: the representative, then the most uncertain), cluster by cluster in priority order.
2. Pairs in no cluster, most uncertain first.
3. The rest of every cluster.

Left out: pairs that already have a review record (`--reviews`), and validation and test rows (`--include-held-out` adds them back). `export-queue` also never sends pairs held out for human evaluation.

## Running it

```bash
python3 ml_pipeline/scripts/review_clusters.py \
  --input ../siamsil-data/szsf/filtered-v1.1.0/szsf-filtered.jsonl \
  --reviews ../siamsil-data/reviews/corpus-reviews.jsonl \
  --near-scope ../siamsil-data/szsf/filtered-v1.1.0/review-queue.jsonl \
  --out-dir ../siamsil-data/reviews/clusters-v1
```

On a 300,000-row test file it took about 9 seconds and 225 MB, so the full corpus should take about a minute and a little over 1 GB of memory.

Then make sittings from it exactly as from the filter's queue ([CORPUS_FILTER_AND_REVIEW.md](CORPUS_FILTER_AND_REVIEW.md)):

```bash
python3 ml_pipeline/scripts/review_sample.py export-queue \
  ../siamsil/data/processed/language/siamsil_language.sqlite \
  --ids ../siamsil-data/reviews/clusters-v1/cluster-queue.jsonl \
  --out ../siamsil-data/reviews/queue/cluster-batch-001 --offset 0 --limit 100
```

Rate the sheet and save it with `record --owner-decides`. Re-run `review_clusters.py` with `--reviews` from time to time: pairs you have decided drop out, and the priorities are recomputed for what is left.

## Outputs

| File | What it holds |
|---|---|
| `cluster-queue.jsonl` | `{"id", "english_sha256", "cluster", "rank"}` in review order. No sentence text. |
| `clusters.jsonl` | One line per cluster: kind, size, members, representative (with its English), Zomi variants and the priority parts. |
| `summary.json` | Counts, and the parameters used |

Files are written with owner-only permissions.

## Not in this step

- **Approving a whole cluster with one decision.** Members of a cluster have different text (other numbers, a changed word), so one approval would approve sentences you did not read. That belongs with rule propagation, preview, sampling and rollback (PR 5).
- **Meaning checks with a model** (English–Zomi alignment, confidence). These come with local models in a later PR.
