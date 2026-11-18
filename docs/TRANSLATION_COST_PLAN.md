# Translation cost plan (draft, nothing built)

Status: **proposed**. No paid route exists, no corpus row is sent to any outside provider, and no price below is measured. This plan says how to measure cost and quality before choosing a provider or building a paid route. Read it with [DATA_RIGHTS.md](DATA_RIGHTS.md), [EVALUATION_SET.md](EVALUATION_SET.md) and [MODEL_EVALUATION.md](MODEL_EVALUATION.md).

## Goal

Find the lowest cost per accepted sentence that meets the quality bar, for many users, without breaking a rights rule.

## Cost levers, in order of expected effect

1. **Exact-match cache (stored translations).** Return a stored, reviewed translation with no model call. Count its hit rate on real traffic before relying on it.
2. **Response cache.** Store each model translation under a normalized key (text, direction, standard version, model). Reuse it for the next request. Expire it when the standard version or model changes.
3. **Retrieved examples (RAG).** Adds input tokens to each call. It pays off only if it lets a cheaper model reach the same quality, or if it raises quality enough to avoid review work. Measure both.
4. **Provider features.** Prompt caching for the fixed instructions, batch pricing for non-urgent jobs, and a smaller model tier.
5. **Own small model on rented GPU.** Likely the lowest cost per sentence at scale. It needs enough reviewed data and cleared training rights first.

## Rules that limit the plan

- **Examples must be reviewed.** The 1,775,043 corpus rows are bronze, machine-generated and unreviewed. Retrieve only human-reviewed pairs (owner corrections, teacher-reviewed phrases) as examples. Unreviewed rows would teach the model its own errors.
- **Rights before sending.** No corpus row or example goes to OpenAI, Google or Anthropic until its source is cleared for that use and the owner approves in writing (CLAUDE.md: scoped rights, consent, access controls, authorized purpose).
- **Provider outputs stay separate.** Provider-derived outputs and labels are not training data for Siamsil's own model unless that provider's current terms allow it.
- **Paid use.** A paid route needs every component commercial-cleared (DATA_RIGHTS.md, "Paid translation").
- **Evaluation data stays hidden.** The evaluation set never appears in the corpus, examples, prompts or caches.

## Experiment design

Use the frozen human evaluation sets. Until they exist, use a small owner-reviewed sample and say so in the result.

| Arm | Model | Examples |
|---|---|---|
| A | Provider model, plain prompt | none |
| B | Same model | reviewed pairs only (top 3 to 5 by similarity) |
| C | Cheaper tier of the same provider | reviewed pairs only |
| D | Own experimental model (if one exists) | none |

For each arm, on the same few hundred sentences, record:

- cost per 1,000 sentences (input tokens, output tokens, price at the date measured)
- reviewer acceptance rate and chrF/BLEU against the human reference
- the share of outputs the Standard Form linter changes
- latency (median and 95th percentile)

Send only evaluation-approved text to a provider, and only after the rights check above.

## Decision rule

Choose the cheapest arm whose reviewer acceptance rate is within an agreed margin of the best arm. The owner and editors set the margin. A human reviews the choice before it ships.

## Build order

1. Add the exact-match cache lookup against reviewed rows only (internal, labelled).
2. Add a response cache with the key above and a per-entry provenance record.
3. Write the evaluation harness that reports the table above.
4. Run the experiment on approved text; record dated prices.
5. Decide, then specify the paid route (separate document).
