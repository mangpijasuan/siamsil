from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))

import openpyxl  # noqa: E402

from eval_set import DOMAINS, load_items, read_sources, validate_items  # type: ignore  # noqa: E402
from worksheets import main  # type: ignore  # noqa: E402

# Zomi-side strings are placeholders, never real language data.


def workbook(path: Path, sheet: str, header: list[str], rows: list[list]) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Instructions"
    data = wb.create_sheet(sheet)
    data.append(header)
    for row in rows:
        data.append(row)
    wb.save(path)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def run(*argv: str) -> str:
    out = StringIO()
    with redirect_stdout(out):
        main(list(argv))
    return out.getvalue()


WRITE_HEADER = ["ID", "Topic", "Length", "Situation", "Zomi sentence(s) you wrote", "Notes"]


class WritingSheetTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.prompts = self.dir / "prompts.csv"
        with self.prompts.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["id", "domain", "length", "situation"])
            writer.writerow(["zomi-en-0001", "health", "short", "Say that you feel dizzy."])
            writer.writerow(["zomi-en-0002", "news", "medium", "Report that a flood has damaged houses."])
            writer.writerow(["zomi-en-0003", "informal", "long", "Tell a friend about a new hobby."])

    def sheet(self, answers: list[str | None], name: str = "write.xlsx") -> Path:
        path = self.dir / name
        workbook(path, "Write", WRITE_HEADER, [
            ["zomi-en-0001", "health", "short", "Say that you feel dizzy.", answers[0], ""],
            ["zomi-en-0002", "news", "medium", "Report that a flood has damaged houses.", answers[1], ""],
            ["zomi-en-0003", "informal", "long", "Tell a friend about a new hobby.", answers[2], ""],
        ])
        return path

    def test_sheet_lists_situations_and_import_makes_a_sources_list(self) -> None:
        made = self.dir / "made.xlsx"
        self.assertIn("3 situations", run("writing-sheet", str(self.prompts), "--out", str(made)))
        wb = openpyxl.load_workbook(made)
        self.assertEqual(wb.sheetnames, ["Instructions", "Write"])
        rows = list(wb["Write"].iter_rows(values_only=True))
        self.assertEqual(list(rows[0]), WRITE_HEADER)
        self.assertEqual(rows[1][:4], ("zomi-en-0001", "health", "short", "Say that you feel dizzy."))
        self.assertEqual(rows[1][4], None)

        sources = self.dir / "zomi-en-v1.sources.csv"
        out = run("writing-import", str(self.sheet(["ZOMI_PLACEHOLDER_1", "ZOMI_PLACEHOLDER_2", None])),
                  "--writer", "W01", "--out", str(sources))
        self.assertIn("2 written, 1 not yet written", out)
        items, errors = read_sources(sources)
        self.assertEqual(errors, [])
        self.assertEqual([(i["id"], i["direction"], i["domain"], i["source_text"]) for i in items], [
            ("zomi-en-0001", "zomi-en", "health", "ZOMI_PLACEHOLDER_1"),
            ("zomi-en-0002", "zomi-en", "news", "ZOMI_PLACEHOLDER_2"),
        ])
        self.assertEqual(read_csv(sources)[0]["writer"], "W01")

        translate = self.dir / "translate.xlsx"
        self.assertIn("2 sentences", run("testset-sheet", str(sources), "--out", str(translate)))
        header = [c.value for c in openpyxl.load_workbook(translate)["Translate"][1]]
        self.assertEqual(header, ["ID", "Topic", "Zomi", "English translation", "Notes"])

    def test_append_adds_a_second_writers_rows(self) -> None:
        sources = self.dir / "zomi-en-v1.sources.csv"
        run("writing-import", str(self.sheet(["ZOMI_A", None, None])), "--writer", "W01", "--out", str(sources))
        out = run("writing-import", str(self.sheet([None, "ZOMI_B", "ZOMI_C"], "second.xlsx")),
                  "--writer", "W02", "--out", str(sources), "--append")
        self.assertIn("now has 3 sentences", out)
        rows = read_csv(sources)
        self.assertEqual([(r["id"], r["writer"]) for r in rows], [("zomi-en-0001", "W01"), ("zomi-en-0002", "W02"), ("zomi-en-0003", "W02")])

    def test_existing_sources_list_is_never_overwritten(self) -> None:
        sources = self.dir / "zomi-en-v1.sources.csv"
        run("writing-import", str(self.sheet(["ZOMI_A", None, None])), "--writer", "W01", "--out", str(sources))
        before = sources.read_text(encoding="utf-8")
        with self.assertRaises(SystemExit):
            run("writing-import", str(self.sheet(["ZOMI_B", None, None], "other.xlsx")), "--writer", "W02", "--out", str(sources))
        with self.assertRaises(SystemExit):
            run("writing-import", str(self.sheet(["ZOMI_B", None, None], "other.xlsx")), "--writer", "W02", "--out", str(sources), "--append")
        self.assertEqual(sources.read_text(encoding="utf-8"), before)

    def test_problems_stop_the_import_and_write_nothing(self) -> None:
        out = self.dir / "sources.csv"
        cases = {
            "repeats the situation": ["Say that you feel dizzy.", None, None],
            "same sentence twice": ["ZOMI_SAME", "  zomi_same ", None],
        }
        for label, answers in cases.items():
            with self.subTest(label), self.assertRaises(SystemExit):
                run("writing-import", str(self.sheet(answers)), "--writer", "W01", "--out", str(out))
            self.assertFalse(out.exists())
        bad = self.dir / "bad.xlsx"
        workbook(bad, "Write", WRITE_HEADER, [["zomi-en-0001", "sports", "short", "Say hello.", "ZOMI_X", ""]])
        with self.assertRaises(SystemExit):
            run("writing-import", str(bad), "--writer", "W01", "--out", str(out))
        self.assertFalse(out.exists())

    def test_formula_like_text_stays_text(self) -> None:
        made = self.dir / "made.xlsx"
        with self.prompts.open("a", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerow(["zomi-en-0004", "health", "short", "=HYPERLINK(\"http://x\")"])
        run("writing-sheet", str(self.prompts), "--out", str(made))
        cell = openpyxl.load_workbook(made)["Write"].cell(5, 4)
        self.assertEqual(cell.data_type, "s")

    def test_invalid_prompts_are_refused(self) -> None:
        for row in (["zomi-en-0001", "sports", "short", "x"], ["zomi-en-0001", "health", "tiny", "x"],
                    ["bad-id", "health", "short", "x"], ["zomi-en-0001", "health", "short", ""]):
            bad = self.dir / "bad.csv"
            with bad.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "domain", "length", "situation"])
                writer.writerow(row)
            with self.subTest(row), self.assertRaises(SystemExit):
                run("writing-sheet", str(bad), "--out", str(self.dir / "x.xlsx"))

    def test_shipped_prompt_list_is_balanced(self) -> None:
        shipped = PROJECT_ROOT / "data" / "evaluation_prompts" / "zomi-en-writing-prompts-v1.csv"
        rows = read_csv(shipped)
        self.assertEqual(len(rows), 140)
        self.assertEqual(len({r["id"] for r in rows}), 140)
        for domain in DOMAINS:
            lengths = [r["length"] for r in rows if r["domain"] == domain]
            self.assertEqual((lengths.count("short"), lengths.count("medium"), lengths.count("long")), (5, 10, 5), domain)
        made = self.dir / "shipped.xlsx"
        run("writing-sheet", str(shipped), "--out", str(made))


class TestSetRoundTripTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.sheet = self.dir / "translate.xlsx"
        workbook(self.sheet, "Translate", ["ID", "Topic", "English", "Zomi translation", "Notes"], [
            ["en-zomi-0001", "health", "My stomach hurts after eating the fish.", "ZOMI_PLACEHOLDER_1", ""],
            ["en-zomi-0002", "news", "No one in the family was injured.", "ZOMI_PLACEHOLDER_2", "two options"],
            ["en-zomi-0003", "informal", "Wait for me at the bus stop!", None, ""],
        ])

    def test_import_review_and_merge(self) -> None:
        draft = self.dir / "draft.jsonl"
        self.assertIn("2 translated, 1 not yet translated",
                      run("testset-import", str(self.sheet), "--translator", "T01", "--origin", "written for Siamsil", "--out", str(draft)))

        review = self.dir / "review.xlsx"
        run("review-sheet", str(draft), "--out", str(review))
        wb = openpyxl.load_workbook(review)
        ws = wb["Review"]
        self.assertEqual([c.value for c in ws[1]][:5], ["ID", "Topic", "English", "Zomi translation", "Decision"])
        ws["E2"] = "Accept"
        ws["E3"] = "Correct"
        ws["F3"] = "ZOMI_PLACEHOLDER_2_FIXED"
        wb.save(review)

        final = self.dir / "en-zomi-v1.jsonl"
        self.assertIn("2 items (1 accepted, 1 corrected)",
                      run("review-merge", str(draft), str(review), "--reviewer", "R01", "--out", str(final)))
        items, parse_errors = load_items(final)
        errors, _ = validate_items(items)
        self.assertEqual((parse_errors, errors), ([], []))
        self.assertEqual(items[1]["references"], ["ZOMI_PLACEHOLDER_2_FIXED"])
        self.assertEqual({item["reviewer"] for item in items}, {"R01"})

    def test_reviewer_must_differ_from_translator(self) -> None:
        draft = self.dir / "draft.jsonl"
        run("testset-import", str(self.sheet), "--translator", "T01", "--origin", "x", "--out", str(draft))
        review = self.dir / "review.xlsx"
        run("review-sheet", str(draft), "--out", str(review))
        wb = openpyxl.load_workbook(review)
        wb["Review"]["E2"] = "Accept"
        wb.save(review)
        with self.assertRaises(SystemExit), redirect_stdout(StringIO()):
            main(["review-merge", str(draft), str(review), "--reviewer", "T01", "--out", str(self.dir / "x.jsonl")])
        self.assertFalse((self.dir / "x.jsonl").exists())

    def test_correct_without_text_is_rejected(self) -> None:
        draft = self.dir / "draft.jsonl"
        run("testset-import", str(self.sheet), "--translator", "T01", "--origin", "x", "--out", str(draft))
        review = self.dir / "review.xlsx"
        run("review-sheet", str(draft), "--out", str(review))
        wb = openpyxl.load_workbook(review)
        wb["Review"]["E2"] = "Correct"
        wb.save(review)
        with self.assertRaises(SystemExit), redirect_stdout(StringIO()):
            main(["review-merge", str(draft), str(review), "--reviewer", "R01", "--out", str(self.dir / "x.jsonl")])


class RatingsImportTests(unittest.TestCase):
    def test_rate_sheet_becomes_review_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sheet = Path(tmp) / "rate.xlsx"
            workbook(sheet, "Rate", ["ID", "English", "Zomi (machine-made)", "Meaning (0-2)", "Fluency (0-2)", "Notes"], [
                ["R00001", "Is the shop open?", "ZOMI_PLACEHOLDER_A", 2, 1.0, ""],
                ["R00002", "It is late.", "ZOMI_PLACEHOLDER_B", None, None, "unsure"],
            ])
            out = Path(tmp) / "review.csv"
            self.assertIn("1 of 2 rows rated", run("ratings-import", str(sheet), "--out", str(out)))
            rows = list(csv.DictReader(out.open(encoding="utf-8")))
            self.assertEqual((rows[0]["sample_id"], rows[0]["meaning"], rows[0]["fluency"]), ("R00001", "2", "1"))
            self.assertEqual(rows[1]["meaning"], "")


if __name__ == "__main__":
    unittest.main()
