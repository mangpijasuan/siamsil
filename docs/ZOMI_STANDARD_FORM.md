# Siamsil Zomi Standard Form

Updated: 2026-11-13
Status: **evidence and suggestions** (steps 1–3); the tool that applies adopted rules (step 5) is built. Version 0.1.0 holds eleven rules (ZS-001 to ZS-011) **adopted by the creator alone** on 2026-11-13 (see [Rules adopted by the creator](#rules-adopted-by-the-creator-alone)). No rule has been confirmed by two reviewers yet.

Siamsil's dictionary, Translate, and Siamsil AI need one consistent way to write Zomi (Zolai), so that spellings match, search finds every form, and models learn one form. Zomi writers do not all spell alike: for example, the *Zolai Standard Format* writes `uhhi` where ZCLS's guide and the Bibles write `uh hi`. Siamsil does not choose between them on its own. It gathers the evidence, Zomi language reviewers decide, and Siamsil applies their decisions.

**Creator.** The project owner is the original creator of the Siamsil Zomi Standard Form (SZSF), which they built after reviewing the corpus and the 50K dictionary (the owner's statement, 2026-11-13). That is the owner's account of how the standard came about. It is not a pair-by-pair review: a corpus pair counts as reviewed only through recorded SOP-07 review records.

The name is Siamsil's own, so it is not confused with Lian Than Tuang's *Zolai Standard Format*, one of the guides it draws on. A **standard form** is the spelling Siamsil uses for a word; it is stored beside the original text, never in place of it.

## Steps

1. **Evidence (built).** `ml_pipeline/scripts/spelling_variants.py` counts every word form in each source and finds:
   - spellings that differ only by inner apostrophes, hyphens, or doubled vowels (`gen` / `geen`), with a final possessive apostrophe counted with its word;
   - words written both joined and split (`theilo` / `thei lo` / `thei-lo`);
   - the points the style guides address, from `data/zomi_standard_form/rule_checks.json`.
2. **The guides side by side (built).** `rule_checks.json` records, for each point, what each guide says, with a page or section reference. Only explicit statements count; where a guide is silent the file says so, and its own text shows its practice in the counts. The guides:
   - Lian Than Tuang, *Zolai Standard Format* (2018);
   - Khoi Lam Thang, *Zokam le Zolai*, chapter 6 *Laigelhzia* (Zomi Christian Literature Society, 2013);
   - Lia Cingsen, *Paunam Khenna Leh Kampau Luanzia* (grammar primer).
3. **Suggestions (built).** To save the reviewers time, every row of the workbook carries a "Siamsil suggestion (AI)", always labelled as a draft:
   - **Style-guide points:** proposals in `rule_checks.json` that weigh the guides and the counts. They favour the spelling of the 2011 Tedim Bible, which is most of the translation training data, and one written word per English meaning where the guides allow it (`nulepa` = parents).
   - **Joins and families:** worked out from the counts. Each source that uses the word at least 3 times votes for its most frequent spelling, and the first source (`--reference`) breaks ties. A suggestion is "strong" when every voting source agrees.
   - **No suggestion:** where a source that uses a word 20 or more times writes it two ways at least 20% of the time, the row says "check meaning" (`tu` / `tuu`, `thugen` / `thu gen`). They may be different words, and only a Zomi speaker can tell.

   Reviewers confirm or overrule each suggestion; a suggestion is never applied on its own.
   **Tie-break (project owner, 2026-10-27).** Where the sources disagree, the suggestions follow the Bibles and common published usage, the spelling most readers already see. The *Zolai Standard Format* decides only where that usage is itself split. A spelling the owner proposed for a specific point (as for `le-leh`) is weighed as that proposal. This is recorded as `owner_policy` in `rule_checks.json`. It shapes the drafts only: reviewers still decide every rule.

   One check, `locative-ah-noun` (`gam ah` / `gamah` / `khua-ah`), was added from counts in public copies of the 1932 Tedim Bible and two Zomi news sites. The 1932 Bible joins or hyphenates `ah` after a noun, while the news sites are mixed, so the draft follows the *Zolai Standard Format* until the TDB and TB77 counts are in. Position words (`tungah`, `kiangah`) are the separate `locative-ah` check, and all those sources join them.
4. **Decisions (next).** Zomi language reviewers fill in the review workbook. Where the guides agree, a rule is quick to confirm; where they differ, the counts show what writers actually do. A rule is adopted only when two reviewers agree, like corpus reviews (SOP-07). Each adopted rule gets an ID, the chosen spelling, the reason, and examples, and becomes part of a versioned Siamsil Zomi Standard Form.
5. **Applying it (tool built, no rules yet).** Original texts are never edited. A standard form is stored beside each original, with the rules that changed it. The dictionary lists one standard headword with its variant spellings, so a search for any spelling finds it. Translate and Siamsil AI read any spelling and write the standard one; training uses the standard form.
6. **One dataset.** Every sentence and entry carries its source, rights, review status, and standard form. Only sources cleared for training reach a model.

## Running the evidence report

The sources are copyrighted and private, so the report is written to `siamsil-data`, never to this repository.

```text
python3 ml_pipeline/scripts/spelling_variants.py --out ../siamsil-data/standard/derived \
  --bible tdb=data/processed/bible/bible_versions.sqlite:tdb \
  --bible tb77=data/processed/bible/bible_versions.sqlite:tb77 \
  --text zokam=../siamsil-data/books/derived/zokam-le-zolai.txt \
  --text primer=../siamsil-data/grammar/Paunam_Khenna_Leh_Kampau_Luanzia.pdf \
  --text zsf=../siamsil-data/standard/Zolai_Standard_Format_2018.pdf \
  --xlsx "dictionary=../siamsil-data/dictionary/Zomi_Standard_Dictionary_AI_Cleaned.xlsx:Definition (Zomi)"
```

It writes `forms.csv`, `variant_families.csv`, `joins.csv`, `rule_checks.csv`, `summary.md`, and `Siamsil_Zomi_Standard_Form_Review.xlsx`. The workbook has a sheet for the guide points, for joined and split words, and for spelling families, each with yellow decision columns. Reviewers sign with their codes (R01, E01), never their names.

## Applying adopted rules

Adopted rules go in `data/zomi_standard_form/standard.json`, which starts empty (version `0.0.0`). Each rule records:

| Field | Meaning |
|---|---|
| `id` | `ZS-001`, `ZS-002`, … never reused |
| `standard` | the adopted spelling |
| `variants` | the other spellings it replaces or flags |
| `mode` | `replace` (the standard form uses the adopted spelling) or `flag` (text unchanged, match listed; for spellings whose meaning depends on context, such as the "check meaning" rows) |
| `check` | the `rule_checks.json` point it settles, if any |
| `approved_by` | at least two different reviewer codes (`R01`, `E01`) |
| `approved_on`, `reason` | the date and why |

`ml_pipeline/scripts/zolai_standard.py` refuses a file that breaks these rules. It rejects a rule with fewer than two reviewers, an unknown check, a variant listed in two rules, or a variant that is another rule's standard spelling.

```text
python3 ml_pipeline/scripts/zolai_standard.py validate
python3 ml_pipeline/scripts/zolai_standard.py apply --input pairs.jsonl --field zomi --out pairs.standard.jsonl
python3 ml_pipeline/scripts/zolai_standard.py variants
```

`apply` copies every record and adds `zomi_standard`, `zomi_standard_rules` (the rules that changed it), `zomi_standard_flags`, and `standard_version`. The original field is untouched, and the output cannot overwrite the input. Matching ignores case and apostrophe style (`'` or `’`) and only matches whole words, so a variant inside a longer word is never changed. For dictionary search, `search_forms()` returns a word's standard spelling and all its variants, so a search for any spelling finds the entry.

Bump the version when rules change: minor for added rules, major for a changed or removed rule. The language database, dictionary search, and dataset exports should record the standard version they used. Wiring them to this tool is the next step, once the first rules are adopted.

## Rules adopted by the creator alone

**Decision (project owner, 2026-11-13).** The owner is the original creator of the Siamsil Zomi Standard Form and said: "use the rule, because this is my reviewed and my ownership even though it changed many and it will get better quality sentence paired." Until then every rule needed two reviewer codes. `standard.json` now carries a `governance` block recording this decision, and a rule may use `adopted_by: "creator"` (no reviewer codes) only while that block is there. The tool refuses a creator rule without it, and refuses one that also lists reviewer codes.

What this does **not** do:

- It is not a Language Review Team approval. Rules show `adopted_by: "creator"`, so anyone reading `standard.json` sees which rules one person adopted. A second reviewer can still confirm a rule later; the owner can change or remove a rule by the same kind of decision.
- It does not review sentences. A pair changed by a rule keeps its own review status (SOP-07). The original Zomi stays in `zomi`; the standard form goes in `zomi_standard`, with `zomi_standard_rules` naming the rules.
- It does not make the corpus cleared for training (`data/rights.json` is unchanged).

The eleven rules came from these proposals (kept in full in `proposed_rules.json` under `adopted_by_creator`). `zolai_standard.py preview` still works on any new proposals.

| Rule (was) | Owner's words (2026-11-13) | Change | Evidence |
| --- | --- | --- | --- |
| ZS-001 (P-001) | "I want to use as the Bible uh hi"; reason: "uh is plural and hi is verb, for example: they will go. Amaute pai ding uh hi." | `uhi`, `uhhi` → `uh hi` | The Tedim Bibles write `uh hi` as two words 21,496 times and never `uhi` or `uhhi`. The corpus already writes `uh hi` 142,392 times, against about 32,500 for `uhi` and 473 for `uhhi` (the *Zolai Standard Format* spelling). |
| ZS-002 (P-002) | "if you see "thil", replace with "na", etc" | `thil` → `na` | `thil` is used about 14,000 times in the corpus, never in the Tedim Bibles, but in the Falam and Hakha Bibles. Aligned with the English Bible, the Tedim word most tied to "thing(s)" is `nate`, which is `na` with the plural `te`. |
| ZS-003 (P-003) | "yes, that is the correct one" (to the question whether `uh hiam` should be a second proposal) | `uhiam`, `uhhiam` → `uh hiam` | The question form, by the same reasoning as P-001. `uh hiam` as two words is already the main form in the corpus (10,911 times), against `uhiam` 947 and `uhhiam` 9. |
| ZS-004 (P-004) | "Yes, I want a rule for that." (the patterns in the owner's own corrections) | `chih` → `cih` | 4,753 words in 4,594 pairs (corrections 1, 2); counted by `preview` |
| ZS-005 (P-005) | "Yes, I want a rule for that." (the patterns in the owner's own corrections) | `harsa` → `haksa` | 415 words in 414 pairs (corrections 19, 20); counted by `preview` |
| ZS-006 (P-006) | "Yes, I want a rule for that." (the patterns in the owner's own corrections) | `cu` → `pen` | 814 words in 774 pairs (corrections 5, 6); counted by `preview` |
| ZS-007 (P-007) | "Yes, I want a rule for that." (the patterns in the owner's own corrections) | `tlai` → `ziakai` | 463 words in 462 pairs (corrections 17, 18); counted by `preview` |
| ZS-008 (P-008) | "Yes, I want a rule for that." (the patterns in the owner's own corrections) | `zinglam` → `zingsang` | 858 words in 852 pairs (correction 13); counted by `preview` |
| ZS-009 (P-009) | "Yes, I want a rule for that." (the patterns in the owner's own corrections) | `ii` → `i` | 1,042 words in 1,017 pairs (corrections 22, 26); counted by `preview` |
| ZS-010 (P-010) | "Yes, I want a rule for that." (the patterns in the owner's own corrections) | `ong` → `hong` | 829 words in 795 pairs (corrections 27, 28); counted by `preview` |
| ZS-011 (P-011) | "Yes, I want a rule for that." (the patterns in the owner's own corrections) | `ke'` → `keia` | 375 words in 374 pairs (corrections 31, 32); counted by `preview` |

- **Caution for ZS-002.** `na` is also a very common word with other meanings in the Tedim Bibles, so a Zomi reviewer should check sentences in context. A reviewer may adopt it first as mode `flag`, which lists each match and changes nothing.
- **Why ZS-001.** The owner's reason: `uh` is the plural and `hi` is the verb, as in *Amaute pai ding uh hi* ("They will go"). The two-word form is already the main spelling in the corpus, so this rule mostly tidies the joined forms.
- **Marked as a Zomi speaker review.** The owner is a Zomi speaker, and each proposal records the owner's decision as a human review (`reviews`: reviewer, kind "Zomi speaker review", date). That is one reviewer, and the owner then adopted the rule as its creator. The mark belongs to the **rule decision**, not to the sentences it would change: a spelling rule is not a review of a sentence, so the pairs a rule touches keep their own review status (`UNREVIEWED` unless reviewers and a lead editor approved that pair, SOP-07). An SZSF record shows `zomi_standard_rules: ["ZS-nnn"]`, and the rule in `standard.json` says who adopted it.
- **From the owner's corrections.** The owner corrected 40 corpus sentences by hand (2026-11-13, batches 1 and 2, kept in `siamsil-data`, `reviews/owner-corrections/`). Where both corrections of a word agree, the owner asked for a rule (P-004 to P-011). Words the owner corrected differently each time (`chi`, `ti`, `tih`, `poimawh`, `tlawm`, `sami`, `lungleng`, `thit`, `tengteng`, `hmel`) are listed as not one-to-one in the proposals file: they are corrected sentence by sentence. The owner **kept** `minit` and `me`, so they are accepted words, not errors, even though they are not in the Tedim Bibles or the dictionary: `minit` is "minute", borrowed from English, and may be written in English too; `me` is "vote" or "ballot", borrowed from Burmese, and "vote" or "ballot" may be used in Zomi text as well.
- **Effect.** 55,169 of the 1,775,043 corpus pairs (3.1%) get a different standard form, by `zolai_standard.py preview`. The original Zomi stays as it is. `na`, `pen`, `ziakai`, `zingsang`, `i` and `hong` are short common words, so a Zomi reviewer should look at examples in context; the owner's choice to adopt them alone does not remove that advice.
- **Not decided.** `thilte` → `nate` would follow from P-002 and `nate` is the Tedim Bible's word for "things", but the owner has not decided it (`suggested_not_decided` in the file). The question form follows the same reasoning and is P-003.
- **Adopting new rules.** Either two reviewers confirm a proposal in the review workbook (two reviewer codes), or the owner adopts it as creator under the governance block. It goes into `standard.json` with an ID, the date and the reason; the version goes up by a minor number; the proposal leaves the proposals file.
- Counts in the table count words; `preview` counts matches by the tool's own rules, which skip a form joined to another word by an apostrophe or a hyphen, so the two differ slightly.

## What the evidence covers

- **Included:** the TDB and TB77 Bibles, *Zokam le Zolai*, the grammar primer, the *Zolai Standard Format* itself, and the Zomi definitions of the Zomi Standard Dictionary.
- **Not yet included:** the Haokip-Lind dictionary, the Translation Master, and Essential 3000, which are not in `siamsil-data` yet.
- **Left out on purpose:** the machine-translated corpus, which shows how Gemini writes, not how Zomi writers do.
- **Caveats:**
  - The counts are of written text. They say which spelling is common, not which is right, and a few points mix two uses of a word (each check's note says where).
  - The guides are themselves sources: the *Zolai Standard Format* uses its own rules throughout its text.
  - A final apostrophe can be a closing quotation mark as well as a possessive, so the apostrophe counts are approximate.

## Rights

The *Zolai Standard Format*'s author has not yet given permission, so it is private reference only (`zolai_standard_format_2018` in `data/rights.json`: every use `not_permitted`). The other sources' rights are in [DATA_RIGHTS.md](DATA_RIGHTS.md). Counting spellings in a private source does not publish it; the review workbook quotes only the short example words the guides themselves give.
