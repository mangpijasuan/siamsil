# Siamsil Free and Pro (plan for the owner's decision)

Status: **proposed, not decided.** Nothing here is built, priced or announced. Paid features need the commercial-use decision in [DATA_RIGHTS.md](DATA_RIGHTS.md) ("Commercial use: draft decision") to be signed. Until then, the 2026-10-17 decision ("a non-profit app, offered free of charge") stands, and no paid feature may ship.

Updated 2026-11-19: commercial use on `siamsil.org`, the site structure, launch scope, and a source-by-source checklist. The earlier version described Pro as non-profit cost recovery; that framing is replaced by the draft decision.

## Principle

**Access to the Zomi language stays free.** Pro is paid for advanced AI features, productivity and higher limits, never for basic access to the language. Pro never gates the dictionary, the Bible, the songs or the lessons, and it never sells or republishes other people's text.

## Domain and site structure

`siamsil.org` can carry paid services. The `.org` domain is open to anyone and does not require nonprofit status. What the domain does not settle: the operator's legal status, taxes on subscription income, and every license's commercial terms (below).

| Address | What it holds | When |
|---|---|---|
| `siamsil.org` | Landing page, free dictionary, Bible, learning, stored translations | now |
| `siamsil.org/workspace` | The on-device workspace (saved words, history, progress) | now (PR #99) |
| `siamsil.org/pricing` | Plans and limits | at Pro launch |
| `app.siamsil.org` | The signed-in workspace, once accounts exist | with accounts |
| `api.siamsil.org` | Paid API with metered usage | after Pro |

The footer names the operator ("Siamsil is operated by ______") once the registered legal entity is confirmed. The name the owner has mentioned, Siamsil Technologies, Inc., is not recorded anywhere in this repository as a registered entity, so it is not used until it is confirmed.

## Free (always)

| Feature | Notes |
|---|---|
| Dictionary search | Everyone, no account. Entries labelled verified or unreviewed. |
| Bible reader | Cleared versions only, as the permissions allow. |
| Worship songs | As the publisher's permission allows. |
| Library and Learning | Reviewed lessons and phrases. |
| Translate (stored matches) | Retrieval of stored and reviewed pairs. Labelled. |
| Workspace | Saved words, history, bookmarks and progress, on the device. |

## Free with sign-in (proposed)

| Feature | Notes |
|---|---|
| Sync of the workspace across devices | Sign in with Google or email. |
| Higher daily limit for translation | Anonymous visitors get a small limit, signed-in users a larger one. Limits are counted on the server and set in configuration. |

Sign-in needs a privacy policy, a consent step and account deletion first.

## Pro (proposed)

| Feature | Needs |
|---|---|
| SZSF terminology and spelling check (`/v1/standardize`) | Only Siamsil's own rules (`data/zomi_standard_form/standard.json`, creator-adopted). No third-party text. **The most ready Pro feature.** |
| Personal glossary | The user's own words. No third-party text. |
| Extended history | Accounts. |
| AI translation with a higher limit, with explanations and alternatives | A model, prompts and examples that are all commercial-cleared, and a measured quality bar (see below). |
| Siamsil AI chat with a higher limit | Same condition, and only commercial-cleared sources as context. |
| Document translation | The same as AI translation, plus private handling of uploaded files (storage, retention, deletion). |

**Launch scope.** Start with Free and Pro only. Add Max (larger allowance, batch tools, priority), the paid API, document translation and enterprise services once real usage and cost are measured. Prices are set from measured cost ([PRO_BUDGET.md](PRO_BUDGET.md), [TRANSLATION_COST_PLAN.md](TRANSLATION_COST_PLAN.md)). The $9.99 and $19.99 figures discussed on 2026-11-19 are illustrations, not prices.

**Quality before sale.** AI translation into Zomi is sold only after it is measured on the frozen human evaluation set ([EVALUATION_SET.md](EVALUATION_SET.md)), and its output is labelled as machine translation unless the owner approved the text.

## Commercial-use checklist, by source

From `data/rights.json` on 2026-11-19. "Free lane" means it may keep serving the free service within its terms. "Paid lane" means usable by a paid feature. Nothing moves to the paid lane until its `commercial` status is `cleared` under the clearance rules in force.

| Source | Commercial now | Free lane | Paid lane needs |
|---|---|---|---|
| World English Bible (`bible_web`) | `cleared` (public domain) | yes | nothing more: usable now |
| KJV (`bible_kjv`) | `needs_review` | yes | a decision on the UK Crown patent (outside the UK it is public domain) |
| Tedim Bibles TDB and TB77, Falam FCL, Hakha HCL06 (Bible Society of Myanmar) | `not_permitted` | yes, as permitted | new written permission for paid use |
| Judson Bible (`bible_bjb`) | `not_permitted` | yes, as permitted | the edition's terms checked, then permission if needed |
| Worship songs (`zomi_worship_songs`) | `not_permitted` | yes, as permitted | new written permission from the publisher and collective |
| Essential 3000 (`essential_3000`) | `needs_review` | as decided | the owner's decision for commercial use, as the owner's own work |
| 50K Translation Master (`translation_master_50k`) | `needs_review` | shown as unreviewed | its sources identified and each cleared, or removed from the paid lane |
| Zomi Standard Dictionary (`zomi_standard_dictionary`) | `needs_review` | shown as unreviewed | its compiler and rights holder identified |
| TongDot (`tongdot`) | `not_permitted` (refused) | when its permission is in writing | TongDot changing its answer, in writing |
| Haokip-Lind 2011, primer by Lia Cingsen, *Zokam le Zolai*, Paumkim sheets | `not_permitted` | when their permissions are in writing | new written permission for paid use |
| Parallel corpus (`parallel_corpus`, 1,775,043 pairs) | `blocked` | no | Tatoeba attribution terms and the Gemini terms in force when it was generated, for paid use |
| Zolai Standard Format 2018, Zomi Bethel Church website | `not_permitted` | no | permission first, for any use |
| NLLB-200 weights (CC BY-NC 4.0) and models fine-tuned from them (`nllb-zomi-bible-v1`) | non-commercial license | yes | cannot be used: choose a commercially licensed base model |
| SZSF rules, the owner's own corrections and term decisions | the owner's | yes | the owner's decision for commercial use |

What a first Pro release can use without new permissions: the SZSF rules, the user's own glossary, the World English Bible, and an outside provider's model whose terms allow the paid use, with only cleared text in its prompts. Essential 3000 joins when the owner decides its commercial use.

## Conditions before any Pro feature ships

1. The owner signs the commercial-use decision in [DATA_RIGHTS.md](DATA_RIGHTS.md), with its date and the legal operator.
2. Every component of a paid route is `commercial: cleared` in `data/rights.json`: the model and its weights, each training source, every retrieved example and any text sent to an outside provider. Paid routes check this in code (`commercial_inference` in [RIGHTS_POLICY.md](RIGHTS_POLICY.md)), separately from the free routes' `display` check.
3. The outside provider's current terms allow the paid use, recorded with the product, terms reference and review date.
4. A privacy policy, a consent step and account deletion exist before sign-in launches. Document translation also needs a file retention and deletion policy.
5. Paid output is labelled as machine translation unless the owner approved the text.
6. The operator's legal status and the tax treatment of subscription income are confirmed with a qualified adviser.
7. Prices are set from measured cost. No price is fixed here.

## Decision record

The decision to offer paid features is in [DATA_RIGHTS.md](DATA_RIGHTS.md), "Commercial use: draft decision", so it sits with the rights decisions it changes. Sign it there. This page has no separate signature.

## Permission request for rights holders (template)

Use for the Bible Society of Myanmar, the worship-song publisher and collective, TongDot, Dr. Dal Lian Haokip and Johs. Lind / Zomi Innkuan Denmark, Lia Cingsen, Rev. Khoi Lam Thang and the Zomi Christian Literature Society, and any other holder of a source a paid feature would use. Send only what the holder owns; fill in the names and the source. Describe the paid use as it really is.

> Subject: Request for permission: use of ______ in Siamsil's paid features
>
> Dear ______,
>
> Siamsil (siamsil.org) builds free tools for the Zomi (Tedim) language, operated by ______. You have already allowed us to ______ [display / train on] ______ [name of the work] in the free service.
>
> We plan to offer paid features, "Siamsil Pro", alongside the free service: AI translation and language help with higher limits, for a subscription fee. The free dictionary, Bible reader and songs stay free. Pro would not sell or republish your text.
>
> We would like your written permission to ______ [use the work to train and run the paid translation service / use it as reference examples in the paid service / show it inside paid features]. We would credit you as you direct and remove the work at your request. Please tell us any conditions, fees or credit wording you would like.
>
> If you would rather the work stay in the free service only, we will keep it there.
>
> With thanks,
> ______ (Siamsil project owner)

Keep each reply in private storage, and record its date, signer, wording and scope in `DATA_RIGHTS.md` before `data/rights.json` changes.
