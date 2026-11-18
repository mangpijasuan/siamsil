# Siamsil Pro: monthly budget (planning sheet)

Status: **planning only.** Every price below is a rough estimate from memory or a labelled placeholder, not a quote. Replace each with the provider's current price on the day you decide. Nothing here is a commitment, and no Pro feature exists yet (see [PRO_PLAN.md](PRO_PLAN.md)).

## Fixed monthly costs (launch)

| Item | Low | High | Notes |
|---|---:|---:|---|
| Domain `siamsil.org` | $1 | $1 | Billed yearly. |
| Frontend (Vercel) | $0 | $20 | Free plan is for non-commercial use; Pro or ads likely need the paid plan. |
| API server (small VPS or Railway) | $5 | $15 | Railway can cost more once memory is counted. |
| Cloudflare R2 (data bundle) | $0 | $1 | Inside the free tier at our size. |
| Managed PostgreSQL (accounts, credits) | $0 | $25 | Use a plan with backups for money data. |
| Email, monitoring, error tracking | $0 | $10 | Free tiers cover a small launch. |
| **Fixed total** | **about $6** | **about $72** | |

Stripe has no monthly fee. It takes a percentage plus a fixed amount per payment, which varies by country. Price credit packs so each pack covers provider cost plus Stripe's fee.

## Variable cost: the translation provider

Formula:

```
monthly cost = sentences per month x tokens per sentence x price per million tokens / 1,000,000
```

Assumptions (change them):

- **Tokens per sentence:** 150 (instructions, the input and the output together). Prompt caching can lower the instruction share.
- **Price per million tokens:** two **hypothetical placeholders**, $1 (a small model) and $5 (a mid-priced model). They are not real quotes.

| Scenario | Sentences per month | Cost at $1 / M tokens | Cost at $5 / M tokens |
|---|---:|---:|---:|
| Pilot | 5,000 | $0.75 | $3.75 |
| Early growth | 50,000 | $7.50 | $37.50 |
| Busy | 500,000 | $75 | $375 |
| Large | 5,000,000 | $750 | $3,750 |

A response cache lowers every row by the share of requests it answers. Add the cache hit rate once it is measured.

## Putting it together

| Scenario | Fixed (low to high) | Provider ($1 to $5) | Total range |
|---|---:|---:|---:|
| Pilot | $6 to $72 | $1 to $4 | about $7 to $76 |
| Early growth | $6 to $72 | $8 to $38 | about $14 to $110 |
| Busy | $6 to $72 | $75 to $375 | about $81 to $447 |
| Large | $6 to $72 | $750 to $3,750 | about $756 to $3,822 |

## Break-even check for credit packs

For a pack of N words priced at P dollars:

```
P x (1 - Stripe fee share) >= N / words per sentence x cost per sentence
```

Use the measured cost per 1,000 sentences from the experiment in [TRANSLATION_COST_PLAN.md](TRANSLATION_COST_PLAN.md). Do not set a price from the placeholders above.

## Costs not included

- Your own model: GPU rental for training and serving, after a cleared model exists.
- Legal and accounting advice, and any non-profit registration fees.
- Staff and reviewer time.
- Rights holders' fees, if any holder asks for one.
