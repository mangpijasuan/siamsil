# Zomi names for training data

Updated 2026-11-08 · Status: tool built, **names list incomplete and not yet confirmed**

The English side of the parallel corpus is full of English names, and the Zomi side keeps them. On 2026-11-08 the project owner
decided that, **for training data first**, Siamsil swaps English personal names for Zomi names, in English and Zomi alike, with
**young adult** as the default stage. Using the names at translation time comes later.

## Why

Measured on the 1,777,002-pair corpus (2026-11-08):

- 784,462 pairs (44%) contain a name the build learns from the English side. **Tom is in about 1 pair in 4**; Mary is in about 1 in 11.
- In 99% of the pairs with a name, the Zomi side uses the same English name. A model trained on this writes "Tom" inside Zomi.
- The learned list is not only people: 14 of the 25 most common are places, languages, days or words (Boston, Algeria, French,
  Monday, God, OK). A person has to say which are people.
- Age and marriage are almost never stated: only 2,456 pairs (0.14%) have Mr, Mrs, Miss, Dr, Uncle or Aunt before a name.
- Pronouns alone cannot tell who is who when a sentence has two names, but in sentences with one name they are a useful hint
  (Tom: "he" in 67,006 sentences, "she" in 615).

## The project owner's scheme

Recorded in `data/zomi_names.json`, in the owner's words, with what is still to be confirmed:

| Stage | Girls and women | Boys and men |
| --- | --- | --- |
| `child` (to confirm) | Cingno | Thangno |
| **`young_adult` (default)** | Cing Khup | Ngam Bawm |
| `married` | Nu Cing | Pa Pa Thang (may be "Pa Thang") |
| `older` | Pi Cing Khup | Pu Ngam Bawm |

The owner ended with "etc.": more names are coming. **Nobody adds a name here unless a Zomi speaker supplied it.** A second
person confirms the list, as for every adopted rule.

## What the tool does

`ml_pipeline/scripts/localize_names.py`

1. **`sheet`** lists the capitalized words the build treats as names (324 appear in 100 or more pairs), with a pronoun hint from
   sentences that have only that name. The owner marks each row `Person?` yes or no, and `Gender` female, male or either.
2. **`apply`** writes a **new** copy of a pairs file. For each name marked as a person with a gender, it picks a Zomi name from the
   default stage's list for that gender, the same way for the English and the Zomi side. The pick is repeatable (a hash of the
   pair's ID), spreads over the list, and never gives two people in one pair the same name.

A pair is **left exactly as it was** when:

- the name comes after a title (Mr, Mrs, Miss, Ms, Dr, Professor, Uncle, Aunt, Grandpa, Grandma, Sir, Madam, Father, Mother, ...);
- the Zomi side does not use the marked names as many times as the English side;
- the name is unmarked, or marked "either";
- the list has run out of names for that pair.

A swapped pair keeps `english_original`, `zomi_original`, `names_localized` (which name became which) and `names_version`. Every
other column of the input (`model`, `worker`, `timestamp`, ...) is kept, so provider-made pairs can still be told apart. Labels
that vouch for the text (`review`, `tier`, `split`, `status`, `quality_score`, ...) are removed from a changed pair and kept
under `labels_before_localization`: changed text is not reviewed, gold or test data.

Safeguards on files: the output must be a new file (not the pairs, names or people file, nor a link to one); it is written to a
temporary file and put in place only when complete, under a lock so two runs cannot mix; a titled name is skipped whether the
title is on the English or the Zomi side, in any letter case; a name inside a hyphenated word is left alone; a sheet row marked
as a person without a name is refused; an input folder with no `.csv.gz` parts is refused; and `--min-pool` below 10 needs `--limit`.

**A run is refused unless the list has at least 10 names per gender** (`--min-pool`). With one name per group, every Tom in a quarter
of the corpus would become the same man, and a model would learn that one Zomi name is every man. `--min-pool 1` is for reading
a small sample only.

## What a swapped pair is

- **Altered training data, not original data.** The original pair stays in the corpus and in SZSF (`docs/SZSF.md`).
- It has the **same rights as the pair it came from** (`parallel_corpus` in `data/rights.json`: Tatoeba English, Gemini Zomi,
  `needs_review`). Swapping a name clears nothing.
- It is **never reviewed, never gold, and never in a test set** unless a person reviews that exact pair. Human evaluation items are
  written fresh and never altered (`docs/EVALUATION_SET.md`).

## Steps

1. The owner marks the names sheet and sends more Zomi names for every group they want used.
2. A second person confirms the names list.
3. Run `apply` on a sample; the owner reads it.
4. The swapped file may join training only when **both** hold: the owner agrees, and the source's training rights are cleared and
   recorded (`train` for `parallel_corpus` in `data/rights.json`, with the record in `docs/DATA_RIGHTS.md`). The corpus is
   `needs_review` today, so the swapped file is **not** cleared for training. When cleared, it joins as a labelled addition next
   to the original pairs, not instead of them. `apply` prints a reminder of this on every run.

## Not built yet

- Stages other than the default. A name after a title is left alone, and the other stages are in the table for when the owner
  says how the cues should work (for example what "Mr", "Uncle" or "old man" mean for the stage).
- Names at translation time.
- Reading the swapped file in `export_datasets.py`.
