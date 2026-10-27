# Siamsil Zomi Standard Form

Updated: 2026-10-27
Status: **evidence and suggestions** (steps 1–3). No spelling rule has been decided.

Siamsil's dictionary, Translate, and Siamsil AI need one consistent way to write Zomi (Zolai), so that spellings match, search finds every form, and models learn one form. Zomi writers do not all spell alike: for example, the *Zolai Standard Format* writes `uhhi` where ZCLS's guide and the Bibles write `uh hi`. Siamsil does not choose between them on its own. It gathers the evidence, Zomi language reviewers decide, and Siamsil applies their decisions.

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
4. **Decisions (next).** Zomi language reviewers fill in the review workbook. Where the guides agree, a rule is quick to confirm; where they differ, the counts show what writers actually do. A rule is adopted only when two reviewers agree, like corpus reviews (SOP-07). Each adopted rule gets an ID, the chosen spelling, the reason, and examples, and becomes part of a versioned "Siamsil Zomi Standard Form".
5. **Applying it.** Original texts are never edited. A standard form is stored beside each original, with the rules that changed it. The dictionary lists one standard headword with its variant spellings, so a search for any spelling finds it. Translate and Siamsil AI read any spelling and write the standard one; training uses the standard form.
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
  --xlsx "dictionary=../siamsil-data/dictionary/Zomi_Dictionary_Master_Data.xlsx:Definition (Zomi)"
```

It writes `forms.csv`, `variant_families.csv`, `joins.csv`, `rule_checks.csv`, `summary.md`, and `Siamsil_Zomi_Standard_Form_Review.xlsx`. The workbook has a sheet for the guide points, for joined and split words, and for spelling families, each with yellow decision columns. Reviewers sign with their codes (R01, E01), never their names.

## What the evidence covers

- **Included:** the TDB and TB77 Bibles, *Zokam le Zolai*, the grammar primer, the *Zolai Standard Format* itself, and the Zomi definitions of the Zomi Standard Dictionary.
- **Not yet included:** the Haokip-Lind dictionary, the Translation Master, and Essential 3000, which are not in `siamsil-data` yet.
- **Left out on purpose:** the machine-translated corpus, which shows how Gemini writes, not how Zomi writers do.
- **Caveats:**
  - The counts are of written text. They say which spelling is common, not which is right, and a few points mix two uses of a word (each check's note says where).
  - The guides are themselves sources: the *Zolai Standard Format* uses its own rules throughout its text.
  - A final apostrophe can be a closing quotation mark as well as a possessive, so the apostrophe counts are approximate.

## Rights

The *Zolai Standard Format*'s author has not yet given permission, so it is private reference only. The other sources' rights are in [DATA_RIGHTS.md](DATA_RIGHTS.md). Counting spellings in a private source does not publish it; the review workbook quotes only the short example words the guides themselves give.
