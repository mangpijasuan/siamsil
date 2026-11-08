from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml_pipeline" / "scripts"))

import localize_names as ln  # type: ignore  # noqa: E402

# English names here are invented words (Zorbo, Mirla, ...) and every Zomi name is a placeholder: no Zomi is invented.
POOLS = {
    "young_adult": {"female": [f"ZF{n}" for n in range(1, 5)], "male": [f"ZM{n}" for n in range(1, 5)]},
}


def table(**changes) -> dict:
    data = {"version": "9.0.0", "decided_by": "project owner", "decided_on": "2026-11-08",
            "confirmed_by": None, "default_stage": "young_adult", "pools": POOLS}
    data.update(changes)
    return data


def localizer(people=None, pools=None, **kwargs) -> ln.Localizer:
    names = ln.Names(table(pools=pools or POOLS))
    return ln.Localizer(names, people or {"Zorbo": "male", "Mirla": "female"}, **kwargs)


def pair(english: str, zomi: str, id: str = "p1") -> dict:
    return {"id": id, "english": english, "zomi": zomi}


class NamesTests(unittest.TestCase):
    def test_the_owners_table_loads_with_their_names(self) -> None:
        names = ln.load_names()
        self.assertEqual(names.default_stage, "young_adult")
        self.assertEqual(names.pool("female"), ["Cing Khup"])
        self.assertEqual(names.pool("male"), ["Ngam Bawm"])
        self.assertEqual(names.pool("female", "child"), ["Cingno"])
        self.assertEqual(names.pool("male", "married"), ["Pa Pa Thang"])  # recorded as the owner wrote it
        self.assertEqual(names.pool("female", "older"), ["Pi Cing Khup"])
        self.assertFalse(names.confirmed)
        self.assertTrue(json.loads(ln.DEFAULT_NAMES.read_text(encoding="utf-8"))["to_confirm"])

    def test_a_bad_table_is_refused(self) -> None:
        for change, message in (
            ({"default_stage": "teen"}, "default_stage"),
            ({"decided_by": ""}, "decided_by"),
            ({"pools": {"toddler": {"female": ["X"]}}}, "unknown stage"),
            ({"pools": {"young_adult": {"other": ["X"]}}}, "unknown gender"),
            ({"pools": {"young_adult": {"female": ["X", "X"]}}}, "twice"),
            ({"pools": {"young_adult": {"female": [" X"]}}}, "outer spaces"),
        ):
            with self.assertRaisesRegex(ValueError, message):
                ln.Names(table(**change))


class SwapTests(unittest.TestCase):
    def test_a_name_is_swapped_on_both_sides_and_the_originals_are_kept(self) -> None:
        loc = localizer()
        out = loc.localize(pair("Zorbo went home.", "ZOMI_PLACEHOLDER Zorbo hi."))
        self.assertIn(out["names_localized"]["Zorbo"], ("ZM1", "ZM2", "ZM3", "ZM4"))
        name = out["names_localized"]["Zorbo"]
        self.assertEqual((out["english"], out["zomi"]), (f"{name} went home.", f"ZOMI_PLACEHOLDER {name} hi."))
        self.assertEqual((out["english_original"], out["zomi_original"]),
                         ("Zorbo went home.", "ZOMI_PLACEHOLDER Zorbo hi."))
        self.assertEqual((out["names_version"], out["id"]), ("9.0.0", "p1"))

    def test_gender_picks_the_pool_and_two_names_in_one_pair_get_different_names(self) -> None:
        loc = localizer()
        out = loc.localize(pair("Zorbo told Mirla about Zorbo's plan.", "Zorbo in Mirla Zorbo’ plan."))
        chosen = out["names_localized"]
        self.assertTrue(chosen["Zorbo"].startswith("ZM"))
        self.assertTrue(chosen["Mirla"].startswith("ZF"))
        # The possessive endings are kept, and every use of a name is swapped the same way.
        self.assertEqual(out["english"], f"{chosen['Zorbo']} told {chosen['Mirla']} about {chosen['Zorbo']}'s plan.")
        self.assertEqual(out["zomi"], f"{chosen['Zorbo']} in {chosen['Mirla']} {chosen['Zorbo']}’ plan.")
        both = localizer(people={"Zorbo": "male", "Zim": "male"}).localize(pair("Zorbo met Zim.", "Zorbo Zim."))
        self.assertEqual(len(set(both["names_localized"].values())), 2)

    def test_the_choice_is_repeatable_and_spreads_across_the_pool(self) -> None:
        results = [localizer().localize(pair("Zorbo ran.", "Zorbo.", id=f"p{n}"))["names_localized"]["Zorbo"] for n in range(200)]
        again = [localizer().localize(pair("Zorbo ran.", "Zorbo.", id=f"p{n}"))["names_localized"]["Zorbo"] for n in range(200)]
        self.assertEqual(results, again)
        self.assertEqual(set(results), {"ZM1", "ZM2", "ZM3", "ZM4"})
        self.assertNotEqual(results, [localizer(seed="other").localize(pair("Zorbo ran.", "Zorbo.", id=f"p{n}"))["names_localized"]["Zorbo"] for n in range(200)])

    def test_pairs_that_cannot_be_swapped_safely_are_left_alone(self) -> None:
        loc = localizer()
        cases = {
            "name after a title": pair("Mr. Zorbo went home.", "Mr. Zorbo hi."),
            "Zomi side does not use the names as often": pair("Zorbo went home.", "ZOMI_PLACEHOLDER_ONLY"),
            "name pool too small for this pair": None,
        }
        self.assertIsNone(loc.localize(cases["name after a title"]))
        self.assertIsNone(loc.localize(cases["Zomi side does not use the names as often"]))
        self.assertIsNone(loc.localize(pair("Zorbo went home.", "Zorbo Zorbo hi.")))  # used twice in Zomi, once in English
        self.assertIsNone(loc.localize(pair("Nobody here.", "ZOMI_PLACEHOLDER")))
        self.assertIsNone(localizer(people={"Zorbo": "male", "Zim": "male"}, pools={"young_adult": {"male": ["ZM1"]}}).localize(
            pair("Zorbo met Zim.", "Zorbo Zim.")))
        self.assertEqual(loc.skipped["name after a title"], 1)
        self.assertEqual(loc.skipped["Zomi side does not use the names as often"], 2)
        # A word that merely contains a marked name is not a name.
        self.assertIsNone(loc.localize(pair("The Zorbons left.", "The Zorbons.")))

    def test_share_swaps_only_a_chosen_part(self) -> None:
        loc = localizer(share=0.5)
        swapped = sum(loc.localize(pair("Zorbo ran.", "Zorbo.", id=f"p{n}")) is not None for n in range(400))
        self.assertTrue(120 < swapped < 280, swapped)
        self.assertEqual(swapped + loc.skipped["not chosen (share)"], 400)


class FileTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        records = [pair("Zorbo ran.", "Zorbo.", "a"), pair("Plain sentence.", "ZOMI_PLACEHOLDER.", "b"), pair("Mirla sat.", "Mirla.", "c")]
        self.pairs = self.root / "pairs.jsonl"
        self.pairs.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
        self.names = self.root / "names.json"
        self.names.write_text(json.dumps(table()), encoding="utf-8")
        self.people = self.root / "people.csv"
        self.people.write_text("Name,Pairs,Person?,Gender\nZorbo,5,yes,male\nMirla,4,yes,female\nParis,3,no,\nKit,2,yes,either\nZed,1,,male\n",
                               encoding="utf-8")

    def run_main(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ln.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_only_rows_marked_person_with_a_gender_are_used(self) -> None:
        self.assertEqual(ln.load_people(self.people), {"Zorbo": "male", "Mirla": "female"})
        with self.assertRaises(ValueError):
            bad = self.root / "bad.csv"
            bad.write_text("Name,Notes\nZorbo,x\n", encoding="utf-8")
            ln.load_people(bad)

    def test_apply_writes_a_new_file_with_every_pair(self) -> None:
        out = self.root / "out.jsonl"
        code, shown, _ = self.run_main("apply", "--pairs", str(self.pairs), "--people", str(self.people),
                                       "--out", str(out), "--names", str(self.names), "--min-pool", "4", "--limit", "100")
        self.assertEqual(code, 0)
        rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["id"] for r in rows], ["a", "b", "c"])
        self.assertIn("english_original", rows[0])
        self.assertNotIn("english_original", rows[1])
        self.assertEqual(rows[1]["english"], "Plain sentence.")
        self.assertIn("swapped names in 2", shown)
        self.assertEqual(ln.read_pairs(self.pairs).__next__()["english"], "Zorbo ran.")  # the input is unchanged

    def test_a_small_name_pool_stops_a_run_unless_it_is_a_sample(self) -> None:
        out = self.root / "out.jsonl"
        code, _, error = self.run_main("apply", "--pairs", str(self.pairs), "--people", str(self.people),
                                       "--out", str(out), "--names", str(self.names), "--min-pool", "10")
        self.assertEqual(code, 2)
        self.assertIn("4 female, 4 male", error)
        self.assertIn("one name would stand for every person", error)
        self.assertFalse(out.exists())
        # The owner's own table has one name per group, so it also needs --min-pool 1.
        code, _, error = self.run_main("apply", "--pairs", str(self.pairs), "--people", str(self.people), "--out", str(out))
        self.assertEqual(code, 2)
        self.assertIn("1 female, 1 male", error)

    def test_the_input_is_never_overwritten_and_share_is_checked(self) -> None:
        self.assertEqual(self.run_main("apply", "--pairs", str(self.pairs), "--people", str(self.people), "--out", str(self.pairs))[0], 2)
        self.assertEqual(self.run_main("apply", "--pairs", str(self.pairs), "--people", str(self.people),
                                       "--out", str(self.root / "o.jsonl"), "--share", "0")[0], 2)

    def test_pairs_can_be_read_from_the_corpus_csv_parts(self) -> None:
        import gzip

        folder = self.root / "parts"
        folder.mkdir()
        with gzip.open(folder / "zomi_english_sentences.part-0001.csv.gz", "wt", encoding="utf-8", newline="") as handle:
            handle.write("index,en,zomi,timestamp,model\n7,Zorbo ran.,Zorbo.,1,m\n")
        rows = list(ln.read_pairs(folder))
        self.assertEqual(rows, [{"id": "corpus-7", "index": "7", "english": "Zorbo ran.", "zomi": "Zorbo.", "timestamp": "1", "model": "m"}])
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaisesRegex(ValueError, "no .csv.gz parts"):
            list(ln.read_pairs(empty))

    def test_safeguards_from_review(self) -> None:
        loc = localizer()
        # lowercase title, and a title only on the Zomi side
        self.assertIsNone(loc.localize(pair("uncle Zorbo came.", "uncle Zorbo.")))
        self.assertIsNone(loc.localize(pair("Zorbo came.", "Mr Zorbo.")))
        # a name inside a hyphenated word is not touched
        self.assertIsNone(loc.localize(pair("Zorbo-and-Mirla ran.", "Zorbo-and-Mirla.")))
        # trusted labels leave a changed pair and are kept aside; other columns stay
        out = loc.localize({"id": "x", "english": "Zorbo ran.", "zomi": "Zorbo.", "tier": "gold", "split": "test",
                            "review": {"status": "HUMAN_APPROVED"}, "model": "m"})
        for key in ("tier", "split", "review"):
            self.assertNotIn(key, out)
        self.assertEqual(out["labels_before_localization"]["tier"], "gold")
        self.assertEqual(out["model"], "m")

    def test_blank_person_names_are_refused(self) -> None:
        sheet = self.root / "blank.csv"
        sheet.write_text("Name,Person?,Gender\n,yes,male\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "no Name"):
            ln.load_people(sheet)

    def test_output_may_not_alias_an_input_and_a_failed_run_keeps_the_old_output(self) -> None:
        import os

        link = self.root / "link.jsonl"
        os.link(self.pairs, link)
        self.assertEqual(self.run_main("apply", "--pairs", str(self.pairs), "--people", str(self.people), "--out", str(link))[0], 2)
        self.assertEqual(self.run_main("apply", "--pairs", str(self.pairs), "--people", str(self.people), "--out", str(self.people))[0], 2)
        self.assertEqual(self.run_main("sheet", "--pairs", str(self.pairs), "--out", str(self.pairs))[0], 2)
        # a low --min-pool without --limit is refused
        code, _, error = self.run_main("apply", "--pairs", str(self.pairs), "--people", str(self.people),
                                       "--out", str(self.root / "o.jsonl"), "--names", str(self.names), "--min-pool", "1")
        self.assertEqual(code, 2)
        self.assertIn("--limit", error)
        # a failure part-way leaves the previous output whole and no temporary file behind
        out = self.root / "keep.jsonl"
        out.write_text("old\n", encoding="utf-8")

        def broken():
            yield pair("Zorbo ran.", "Zorbo.")
            raise OSError("disk")

        with self.assertRaises(OSError):
            ln.apply(broken(), localizer(), out)
        self.assertEqual(out.read_text(encoding="utf-8"), "old\n")
        self.assertEqual([p.name for p in self.root.glob("keep.jsonl.*.part")], [])


class SheetTests(unittest.TestCase):
    def test_the_sheet_lists_names_with_a_pronoun_hint_from_sentences_with_one_name(self) -> None:
        pairs = []
        for n in range(30):
            pairs.append(pair(f"We saw that Zorbo said he was late number {n}.", "Z.", f"z{n}"))
            pairs.append(pair(f"We saw that Mirla said she was late number {n}.", "Z.", f"m{n}"))
            pairs.append(pair(f"We saw that Quill said it was late number {n}.", "Z.", f"q{n}"))
            pronoun = "he" if n % 2 else "she"
            pairs.append(pair(f"We saw that Pip said {pronoun} was late number {n}.", "Z.", f"p{n}"))
        pairs += [pair("We saw Zorbo and Mirla, and he left.", "Z.", f"b{n}") for n in range(30)]
        rows = {r["name"]: r for r in ln.candidate_names(pairs, min_pairs=10)}
        self.assertEqual({"Zorbo", "Mirla", "Quill", "Pip"}, set(rows))
        self.assertEqual((rows["Zorbo"]["pairs"], rows["Zorbo"]["he"], rows["Zorbo"]["she"], rows["Zorbo"]["hint"]), (60, 30, 0, "he"))
        self.assertEqual(rows["Mirla"]["hint"], "she")  # the 'he' in sentences with two names does not count
        self.assertEqual(rows["Quill"]["hint"], "")  # no he or she at all: no hint
        self.assertEqual(rows["Pip"]["hint"], "unclear")  # half he, half she

    def test_a_marked_sheet_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            sheet = Path(folder) / "names.xlsx"
            ln.write_sheet([{"name": "Zorbo", "pairs": 60, "he": 30, "she": 0, "hint": "he"},
                            {"name": "Mirla", "pairs": 40, "he": 0, "she": 30, "hint": "she"}], sheet)
            import openpyxl

            book = openpyxl.load_workbook(sheet)
            names = book["Names"]
            self.assertEqual([c.value for c in names[1]], ln.SHEET_COLUMNS)
            names["F2"], names["G2"], names["F3"], names["G3"] = "yes", "male", "yes", "female"
            book.save(sheet)
            self.assertEqual(ln.load_people(sheet), {"Zorbo": "male", "Mirla": "female"})


if __name__ == "__main__":
    unittest.main()
