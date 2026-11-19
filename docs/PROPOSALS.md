# Proposals: attested words and AI suggestions for the owner to decide

Status: **runbook** (PR 4 of the review plan in [AUDIT.md](AUDIT.md)). `ml_pipeline/scripts/proposals.py` collects suggestions for the dictionary and the corpus. A suggestion is never a decision: every one is stored with status `ai_suggested` ([GOVERNANCE.md](GOVERNANCE.md)) until you accept, edit, reject or defer it. Accepting one records your decision; it changes no data. A later step (PR 5) applies accepted proposals with a preview and rollback.

## What a proposal claims

Each proposal says what kind of evidence it rests on, so an AI guess can never pass for an established word:

| `evidence_class` | Means |
|---|---|
| `attested` | The form occurs in a named source text; the references are listed |
| `spelling_variant` | A spelling your adopted Standard Form maps to a form the dictionary already has |
| `derived_form` | Built from an attested form by a rule you adopted (none are adopted yet) |
| `proposed_term` | A new term you or a speaker put forward |
| `ai_candidate` | A model's suggestion: unverified, whatever the model says about it |

And where it comes from (`origin`): `deterministic` (a rule in this repository), `local_model` (a model on your computer) or `provider_assisted` (an outside service). A model's output is always recorded as `ai_candidate`, with the model's name and version, a fingerprint of the prompt, and the run id. Provider-assisted proposals stay marked as such after you accept them (`provider_derived: true`), so training exports can leave them out ([QUALITY_OPERATOR_ARCHITECTURE.md](QUALITY_OPERATOR_ARCHITECTURE.md), Lane B).

## Rights come first

Before reading any text, the tool asks `data/rights.json` ([RIGHTS_POLICY.md](RIGHTS_POLICY.md)):

| Step | Use checked | Today |
|---|---|---|
| `mine-words` reads a Bible version | `train` (a word list is derived data) | Tedim Bibles TDB and TB77 are cleared |
| `generate` with a local model | `retrieval` | Only sources cleared for retrieval, such as the World English Bible |
| `generate` with an outside provider | `external_llm` | Only the World English Bible; the dictionaries and the corpus are not cleared |

If any source is not cleared, nothing is sent and the command says which. The parallel corpus is blocked for every use, so no step reads it.

## Finding attested words missing from the dictionary

```bash
python3 ml_pipeline/scripts/proposals.py mine-words \
  --bible-db data/processed/bible/bible_versions.sqlite \
  --reference-db data/processed/reference/reference_dictionaries.sqlite \
  --out ../siamsil-data/reviews/proposals/attested-words-1.jsonl
```

It counts every Zomi word form in the Bible versions it may read, leaves out forms the dictionary already has (as written or in standard form) and forms seen fewer than three times (`--min-count`), and lists the rest, most frequent first, with up to three verse references each. A form your adopted rules spell as a dictionary word becomes a `spelling_variant` of it. Forms capitalized inside sentences are marked `mostly_capitalized`, since they are probably names. Every word is quoted from a source text; the tool suggests no meanings and invents nothing.

## Asking a model

`generate` sends each item (a sense, a headword, a candidate) to a command you name. The command reads the prompt on standard input and prints JSON: a list of suggestions, or `{"suggestions": [...]}`, each with a `kind` (for example `definition`, `example`, `synonym`, `part_of_speech`), a `payload` object, and optionally an `explanation` and a `confidence` from 0 to 1.

```bash
python3 ml_pipeline/scripts/proposals.py generate --items items.jsonl --prompt prompt.txt \
  --command "ollama run MODEL" --model-name MODEL --model-version VERSION \
  --out ../siamsil-data/reviews/proposals/model-run-1.jsonl
```

Each item in `items.jsonl` names its `source` (a key in `data/rights.json`), so the rights check knows what is being sent. The prompt template must contain `{item}`. The output is treated as untrusted: malformed or unknown suggestions are dropped and counted, text is capped at 500 characters, and nothing the model says changes a proposal's evidence class or status. `--limit` (default 50) caps the items per run. For an outside service, use `--origin provider_assisted` and `--provider-terms` (a JSON file naming the product, the terms you reviewed and the date); it is refused unless every source is cleared for `external_llm`.

`--command` runs on your computer. Whether it sends text elsewhere depends on the command: use `--origin local_model` only for a model that runs locally.

## Deciding

```bash
python3 ml_pipeline/scripts/proposals.py sheet --proposals ../siamsil-data/reviews/proposals/attested-words-1.jsonl \
  --out ../siamsil-data/reviews/proposals/attested-words-1.csv \
  --decisions ../siamsil-data/reviews/proposal-decisions.jsonl
```

Open the CSV. For each row you decide, write `accept`, `edit` (with your text in **edited_text**), `reject` or `defer` in **decision**. Don't change the proposal column. Then:

```bash
python3 ml_pipeline/scripts/proposals.py record --sheet ../siamsil-data/reviews/proposals/attested-words-1.csv \
  --proposals ../siamsil-data/reviews/proposals/attested-words-1.jsonl \
  --decisions ../siamsil-data/reviews/proposal-decisions.jsonl \
  --roster ../siamsil-data/reviews/roster.csv --owner O01
```

Only the roster's owner can record decisions, each as `approval: owner_sole`, appended to the decisions file with the proposal's origin and generator. A new sheet with `--decisions` leaves out proposals you already accepted, edited or rejected; deferred ones come back.
