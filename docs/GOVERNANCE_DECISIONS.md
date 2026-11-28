# Decisions needed from the owner: `data/governance.json`

This page is a **request for decisions, not a record of any**. `data/governance.json` is marked `"owner_review": "pending"`. Engineering wrote it; it takes effect as an enforcement list but is not approved. The project owner is the sole human reviewer and final approver of Siamsil's language and data standards; no AI agent can approve it for you.

## What the file does, in plain words

The governance checks (`ml_pipeline/scripts/data_governance.py`) refuse to let certain things appear in a serving, export, training, evaluation or release manifest. The "forbidden" list has two parts:

1. **Automatic** (you do not have to do anything): any source that `rights.json` marks `blocked` or `not_permitted` for training, display **and** commercial use.
2. **Explicit** (`data/governance.json`): extra source ids and path fragments that are forbidden whatever their status elsewhere.

A check that finds a forbidden thing in the wrong place **fails** (for example a CI run, or a release that is about to be published). The checks decide nothing about rights; they stop an accident.

## Decision 1: the explicit entries (what you are approving)

| Entry | What it blocks | If you approve | If you remove it |
|---|---|---|---|
| source `zomi_bethel_church_web` | any config, export or release that names this source | keeps a second guard in case its rights status is ever changed by mistake | nothing changes today: it is already forbidden automatically while `rights.json` says `not_permitted` for all uses |
| path fragment `zomibethelchurch` | any pin, bundle member, manifest field or tracked file path containing that text; and **fails** `data-repo --require-quarantined` while the two capture files are tracked in `siamsil-data` | a re-added capture file is caught by name even if nobody updates a rights entry | such files would be caught only if declared as a source |

Please decide: approve as written, edit the wording, or tell me to add or remove entries. Possible additions are your call: engineering is **not** proposing any other source today.

## Decision 2: the automatic list (for your information; derived, not editable here)

| Source | Why it is forbidden today | Effect | Note |
|---|---|---|---|
| `parallel_corpus` | blocked for all uses (rights.json, owner's instruction 2026-11-18) | an export or configuration naming it fails | if you later clear part of the corpus under a subset decision, say so: the automatic rule stops applying once any use is no longer blocked |
| `zolai_standard_format_2018` | `not_permitted` for all uses | any configuration or export naming it fails | nothing in the committed configuration names it today |
| `zomi_bethel_church_web` | `not_permitted` for all uses | as above | covered twice (here and in decision 1) |

## How to record your approval

Edit `data/governance.json` yourself and replace the `owner_review` value with who and when:

```json
"owner_review": {"approved_by": "<your name>", "approved_at": "2026-12-01T09:00:00"}
```

The registry check validates the shape and reports the state (`governance_json_owner_review`); it cannot tell whether the claim is true, and **no code or AI step writes this field**. Until you do, it stays `pending`, the checks still run, and CI stays green.

## Related decisions (separate documents)

- Moving the church-capture files: [RESTRICTED_SOURCE_MIGRATION.md](RESTRICTED_SOURCE_MIGRATION.md).
- Enabling the checks in the private archive: [PRIVATE_REPO_GOVERNANCE_SETUP.md](PRIVATE_REPO_GOVERNANCE_SETUP.md).
- Aligning the older two-person review wording in the roadmap and data documents with your sole-reviewer authority is the next planned change; nothing in this PR rewrites those documents.
