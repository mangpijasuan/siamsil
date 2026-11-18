# Siamsil Free and Pro (draft for owner decision)

Status: **proposed, not decided.** Nothing here is built, priced or announced. Until the owner signs the decision record below, the 2026-10-17 decision in [DATA_RIGHTS.md](DATA_RIGHTS.md) ("a non-profit app, offered free of charge") stands, and no paid feature may ship.

## Why Pro

Training, hosting and research cost money. Siamsil is a non-profit project. Pro is a way to recover those costs, not a way to sell language data. Fees pay for compute, hosting, support and research. Surpluses go back into the project.

## Free (always)

| Feature | Notes |
|---|---|
| Dictionary search | Everyone, no account. Entries labelled verified or unreviewed. |
| Bible reader | Cleared versions only, as the permissions allow. |
| Worship songs | As the publisher's permission allows. |
| Library and Learning | Reviewed lessons and phrases. |
| Translate (stored matches) | Retrieval of stored and reviewed pairs. Labelled. |
| Saved words and history | On the device. |

## Free with sign-in (proposed)

| Feature | Notes |
|---|---|
| Sync of saved words across devices | Sign in with Google or email. |
| Higher daily limit for translation | Anonymous visitors get a small limit; signed-in users a larger one. Limits are counted on the server and set in configuration. |
| Contributor and reviewer tools | By invitation. Reviewers are never paid-gated. |

## Pro (proposed)

| Feature | Notes |
|---|---|
| AI translation with a higher limit | Needs a model whose license, training sources and examples are all commercial-cleared. |
| Siamsil AI chat with a higher limit | Same condition. |
| Developer API keys | Metered word credits, prepaid. |
| `/v1/standardize` (spelling-rule linter) | Built from Siamsil's own rules. No corpus data involved. |
| Priority support and bulk jobs | Documents and batch files. |

Pro never gates the Bible, the songs or dictionary lookup. The paid part does not repackage restricted data.

## Conditions before any Pro feature ships

1. The owner signs the decision record below, in writing, in `DATA_RIGHTS.md`.
2. Every component of a paid route is `commercial: cleared` in `data/rights.json`: the model and its weights (NLLB-200 is CC BY-NC and cannot be used), each training source, every retrieved example and any text sent to an outside provider.
3. A second person confirms each `cleared` change.
4. A privacy policy, a consent step and account deletion exist before sign-in launches.
5. Paid output is labelled as machine translation until reviewers approve it.
6. Legal and tax advice is taken on the non-profit structure and on fees.
7. Prices are set from measured cost (see [TRANSLATION_COST_PLAN.md](TRANSLATION_COST_PLAN.md)). No price is proposed here.

## Decision record (for the owner to sign)

> **Decision (date: ______, project owner):** Siamsil remains a non-profit project. Starting on ______, it offers a paid tier, "Siamsil Pro", to recover the cost of training, hosting and research for translation and chat. Free features listed above stay free. Pro uses only components that are `commercial: cleared`. Fees are spent on the project.
>
> Signed: ______________________  Second person confirming: ______________________

Until it is signed, this section has no effect.

## Permission request for rights holders (template)

Use for the Bible Society of Myanmar, TongDot, Dr. Dal Lian Haokip and Johs. Lind / Zomi Innkuan Denmark, and any other holder of a source the paid service would use. Send only what the holder owns; fill in the names and the source.

> Subject: Request for permission: non-profit cost recovery for Siamsil's translation service
>
> Dear ______,
>
> Siamsil (siamsil.org) is a non-profit project building free tools for the Zomi (Tedim) language. You have already allowed us to ______ [display / train on] ______ [name of the work].
>
> We are planning a paid tier, "Siamsil Pro", whose fees would only cover the costs of running the AI translation and chat services and of research. The Bible reader, the dictionaries and the songs would stay free, and Pro would not sell or republish your text.
>
> We would like your written permission to ______ [use the work to train and run the paid translation service / use it as retrieval examples in that service]. We would credit you as you direct, and we would remove the work at your request. Please tell us any conditions or credit wording you would like, and whether this covers advertising on pages that do not show your text.
>
> If you prefer a different arrangement, we would be glad to discuss it.
>
> With thanks,
> ______ (Siamsil project owner)

Keep each reply in private storage, and record its date, signer and wording in `DATA_RIGHTS.md`. A second person confirms before `data/rights.json` changes.
