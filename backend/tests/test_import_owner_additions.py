"""The owner's filled candidate-headwords workbook becomes a private source file (docs/DICTIONARY.md).

Zomi text here is placeholder text only; no Zomi language data is invented.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml_pipeline" / "scripts"))

import dictionary_sources as sources  # type: ignore  # noqa: E402
import import_owner_additions as imp  # type: ignore  # noqa: E402

WORDS = ["#", "English word", "Tier", "Commonness (0 to 8)", "Used in 50K definitions", "In Haokip-Lind draft",
         "Part of speech (AI draft)", "English meaning (AI draft)", "AI note", "Decision",
         "Your meaning if you change it", "Your Zomi", "Notes"]
FORMS = ["#", "English form", "Base word in the 50K (by a simple match)", "Part of speech (AI draft)",
         "English meaning (AI draft)", "AI note", "AI suggestion", "Your decision", "Your meaning if you change it",
         "Your Zomi", "Notes"]
PHRASES = ["#", "English phrase", "Part of speech (AI draft)", "English meaning (AI draft)", "AI note", "Decision",
           "Your meaning if you change it", "Your Zomi", "Notes"]
NAMES = ["#", "Capitalised word", "Part of speech (AI draft)", "English meaning (AI draft)", "AI note", "Decision",
         "Your meaning if you change it", "Your Zomi spelling or word", "Notes"]


def word(headword, pos, draft, note, decision, own="", zomi=""):
    return [1, headword, "A common", 5.0, 1, "", pos, draft, note, decision, own, zomi, ""]


def workbook(path: Path, words=(), phrases=(), forms=(), names=()) -> Path:
    import openpyxl

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for title, header, rows in (("Words", WORDS, words), ("Phrases", PHRASES, phrases),
                                ("Forms you have", FORMS, forms), ("Names", NAMES, names)):
        sheet = wb.create_sheet(title)
        sheet.append(header)
        for row in rows:
            sheet.append(row)
    wb.save(path)
    return path


class BuildTests(unittest.TestCase):
    def build(self, rows, skip=None):
        return imp.build(rows, "t1", "E01", skip or set())

    def row(self, **kw):
        base = {"sheet": "Words", "row": 2, "headword": "word1", "decision": "Add (draft is fine)", "pos": "n.",
                "draft": "A meaning.", "note": "", "own_meaning": "", "zomi": "ZOMI_PLACEHOLDER_1"}
        base.update(kw)
        return base

    def test_a_valid_row_becomes_a_record_with_its_meaning_source(self) -> None:
        records, errors, _, counts = self.build([
            self.row(),
            self.row(headword="word2", decision="Add (I change the meaning)", own_meaning="My meaning.", zomi="ZOMI_PLACEHOLDER_2"),
            self.row(headword="word3", note="WordNet | other senses: x", zomi="ZOMI_PLACEHOLDER_3"),
        ])
        self.assertEqual(errors, [])
        self.assertEqual([r["meaning_source"] for r in records], ["ai_draft", "owner", "wordnet"])
        self.assertEqual(records[1]["definition_en"], "My meaning.")
        self.assertTrue(all(r["owner_code"] == "E01" and r["id"].startswith("OA-") for r in records))
        self.assertEqual(counts["added (owner meaning)"], 1)

    def test_rows_not_marked_to_add_are_left_out(self) -> None:
        records, errors, _, counts = self.build([
            self.row(decision="Skip"), self.row(headword="b", decision="Later"), self.row(headword="c", decision="", zomi=""),
            self.row(headword="d", decision="Discuss"),
        ])
        self.assertEqual((records, errors), ([], []))
        self.assertEqual(sum(counts.values()), 4)

    def test_problems_stop_the_whole_batch(self) -> None:
        cases = {
            "no Zomi": self.row(zomi=""),
            "Zomi copies the English": self.row(zomi="word1"),
            "own meaning missing": self.row(decision="Add (I change the meaning)", own_meaning=""),
            "no meaning at all": self.row(draft=""),
            "unknown decision": self.row(decision="Probably"),
            "line break in Zomi": self.row(zomi="ZOMI X"),
        }
        for label, row in cases.items():
            with self.subTest(label):
                records, errors, _, _ = self.build([row])
                self.assertEqual(records, [])
                self.assertTrue(errors, label)

    def test_a_headword_is_added_once_per_part_of_speech(self) -> None:
        _, errors, _, _ = self.build([self.row(), self.row(sheet="Phrases", row=9)])
        self.assertTrue(any("also added" in e for e in errors))
        records, errors, _, _ = self.build([self.row(), self.row(pos="v.", zomi="ZOMI_PLACEHOLDER_9")])
        self.assertEqual((len(records), errors), (2, []))

    def test_earlier_batches_are_not_added_again(self) -> None:
        records, errors, _, counts = self.build([self.row()], skip={("word1", "n.")})
        self.assertEqual((records, errors), ([], []))
        self.assertEqual(counts["already in an earlier batch"], 1)

    def test_phrasal_verbs_keep_their_part_of_speech(self) -> None:
        records, _, _, _ = self.build([self.row(pos="phr. v.")])
        self.assertEqual(records[0]["part_of_speech"], "phrasal v.")

    def test_a_check_source_draft_is_added_with_a_warning(self) -> None:
        records, errors, warnings, _ = self.build([self.row(note="check source")])
        self.assertEqual((len(records), errors), (1, []))
        self.assertTrue(any("check source" in w for w in warnings))

    def test_ids_do_not_depend_on_row_order(self) -> None:
        a = self.build([self.row(), self.row(headword="word2", zomi="ZOMI_PLACEHOLDER_2")])[0]
        b = self.build([self.row(headword="word2", zomi="ZOMI_PLACEHOLDER_2"), self.row()])[0]
        self.assertEqual({r["headword"]: r["id"] for r in a}, {r["headword"]: r["id"] for r in b})


class CommandTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.book = workbook(
            self.dir / "filled.xlsx",
            words=[word("alpha", "n.", "Draft one.", "", "Add (draft is fine)", zomi="ZOMI_PLACEHOLDER_1"),
                   word("beta", "n.", "Draft two.", "WordNet", "Add (I change the meaning)", own="Mine.", zomi="ZOMI_PLACEHOLDER_2"),
                   word("gamma", "n.", "Draft three.", "", "Skip")],
            phrases=[[1, "give up", "phr. v.", "To stop trying.", "", "Add (draft is fine)", "", "ZOMI_PLACEHOLDER_3", ""]],
            forms=[[1, "alphas", "alpha", "n.", "More than one alpha.", "plural of alpha", "", "Covered by the base word", "", "", ""],
                   [2, "angler", "angle", "n.", "A person who fishes.", "agent noun", "", "Add as own entry", "", "ZOMI_PLACEHOLDER_4", ""]],
            names=[[1, "Paris", "prop. n.", "A city.", "name", "Add (draft is fine)", "", "ZOMI_PLACEHOLDER_5", ""]],
        )

    def run_main(self, *args: str):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = imp.main(["--workbook", str(self.book), "--batch", "t1", "--out-dir", str(self.dir / "out"), *args])
        return code, out.getvalue(), err.getvalue()

    def test_writes_one_private_deterministic_file_and_nothing_else(self) -> None:
        code, out, err = self.run_main("--owner-code", "E01")
        self.assertEqual(code, 0, err)
        files = sorted((self.dir / "out").iterdir())
        self.assertEqual([f.name for f in files], ["owner-additions-t1.jsonl"])  # no review or approval file
        self.assertEqual(stat.S_IMODE(os.stat(files[0]).st_mode), 0o600)
        rows = [json.loads(l) for l in files[0].read_text(encoding="utf-8").splitlines()]
        self.assertEqual(sorted(r["headword"] for r in rows), ["Paris", "alpha", "angler", "beta", "give up"])
        self.assertIn("No review or approval was recorded", out)
        # Same input, same bytes.
        first = files[0].read_bytes()
        files[0].unlink()
        self.assertEqual(self.run_main("--owner-code", "E01")[0], 0)
        self.assertEqual(files[0].read_bytes(), first)

    def test_refuses_to_overwrite_and_dry_run_writes_nothing(self) -> None:
        code, out, _ = self.run_main("--dry-run")
        self.assertEqual(code, 0)
        self.assertFalse((self.dir / "out").exists())
        self.assertIn("Dry run", out)
        self.assertEqual(self.run_main()[0], 0)
        code, _, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("already exists", err)

    def test_a_problem_writes_nothing(self) -> None:
        workbook(self.book, words=[word("alpha", "n.", "Draft.", "", "Add (draft is fine)", zomi="")])
        code, _, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("Nothing was written", err)
        self.assertFalse((self.dir / "out").exists())

    def test_a_missing_sheet_is_reported(self) -> None:
        import openpyxl

        wb = openpyxl.Workbook()
        wb.active.title = "Words"
        wb.active.append(WORDS)
        wb.save(self.book)
        code, _, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("is missing", err)

    def test_register_config_adds_a_pinned_entry_once(self) -> None:
        fake = self.dir / "repo"
        (fake / "data").mkdir(parents=True)
        (fake / "data" / "dictionary_sources.json").write_text(json.dumps({"sources": {}}), encoding="utf-8")
        original = imp.ROOT
        imp.ROOT = fake
        self.addCleanup(setattr, imp, "ROOT", original)
        self.assertEqual(self.run_main("--register-config")[0], 0)
        config = json.loads((fake / "data" / "dictionary_sources.json").read_text(encoding="utf-8"))
        entry = config["sources"]["owner_additions_t1"]
        self.assertEqual((entry["format"], entry["rights"], entry["role"]), ("owner_additions_jsonl", "owner_additions", "reference"))
        written = (self.dir / "out" / "owner-additions-t1.jsonl").read_bytes()
        import hashlib

        self.assertEqual(entry["sha256"], hashlib.sha256(written).hexdigest())

    def test_the_output_is_read_by_the_importer_format(self) -> None:
        self.run_main("--owner-code", "E01")
        read = sources.READERS["owner_additions_jsonl"](self.dir / "out" / "owner-additions-t1.jsonl")
        by = {r.headword: r for r in read.records}
        self.assertEqual(len(read.records), 5)
        self.assertEqual(by["alpha"].equivalents, [("ctd", "equivalent", "ZOMI_PLACEHOLDER_1")])
        self.assertEqual([i.code for i in by["alpha"].issues], ["AI_DRAFT_MEANING"])  # AI-drafted English is flagged
        self.assertEqual(by["beta"].issues, [])  # the owner's own meaning
        self.assertEqual(by["give up"].part_of_speech, "phrasal v.")
        self.assertIsNone(by["alpha"].sense_id)  # the repository mints the ID


class RegisterTests(unittest.TestCase):
    def test_the_rights_entry_exists_and_grants_nothing(self) -> None:
        rights = json.loads((ROOT / "data" / "rights.json").read_text(encoding="utf-8"))["sources"]["owner_additions"]
        self.assertEqual({rights[k] for k in ("display", "train", "redistribute", "commercial")}, {"needs_review"})


if __name__ == "__main__":
    unittest.main()
