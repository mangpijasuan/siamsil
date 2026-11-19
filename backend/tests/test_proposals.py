"""Proposals: attested words, spelling variants and model suggestions, all `ai_suggested` until the owner decides.

Zomi-side strings are placeholders, except the two spellings of rule ZS-001, which the owner adopted, read from
data/zomi_standard_form/standard.json at test time. The "model" is a small script: no model or network is used.
"""
from __future__ import annotations

import csv
import io
import json
import sqlite3
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))

import proposals as pr  # type: ignore  # noqa: E402
import zolai_standard  # type: ignore  # noqa: E402
from import_reference_dictionaries import SCHEMA as REFERENCE_SCHEMA  # type: ignore  # noqa: E402

STANDARD = zolai_standard.load()
RULE = next(r for r in STANDARD.rules if r.id == "ZS-001")
VARIANT, STANDARD_FORM = RULE.variants[0], RULE.standard
ROSTER = {"O01": "owner", "R01": "reviewer"}
SOURCES = {
    "bible_cleared": {"train": "cleared", "display": "cleared"},
    "bible_blocked": {"train": "blocked", "display": "blocked"},
    "notes_local": {"uses": {"retrieval": {"status": "cleared", "path": "owner_original",
                                           "evidence": "fixture", "evidence_type": "owner_authorship",
                                           "decided_on": "2026-11-19", "decided_by": "O01"}},
                    "origin": "owner_original",
                    "provenance": {"attestations": ["sole_author", "no_third_party_content"],
                                   "attested_on": "2026-11-19", "ai_assistance": "none", "sha256": "a" * 64}},
}


def bible_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE versions (id TEXT PRIMARY KEY, rights_source TEXT, language_iso TEXT, sort_order INTEGER);
        CREATE TABLE verses (version_id TEXT, book_id INTEGER, chapter INTEGER, verse INTEGER, label TEXT, text TEXT);
    """)
    con.executemany("INSERT INTO versions VALUES (?,?,?,?)", [
        ("tdbx", "bible_cleared", "ctd", 1), ("blk", "bible_blocked", "ctd", 2), ("web", "bible_cleared", "eng", 3)])
    verses = [
        ("tdbx", 1, 1, 1, f"Qaword known {VARIANT} Qaword"),
        ("tdbx", 1, 1, 2, f"Qaword qanew qanew {VARIANT} mid Qaname"),
        ("tdbx", 1, 1, 3, f"Qaword qanew {VARIANT} and Qaname"),
        ("tdbx", 1, 1, 4, "x Qaname qaonce"),
        ("blk", 1, 1, 1, "qablocked qablocked qablocked qablocked"),
        ("web", 1, 1, 1, "english english english english"),
    ]
    con.executemany("INSERT INTO verses VALUES (?,?,?,?,'',?)", verses)
    con.commit()
    con.close()


def reference_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript(REFERENCE_SCHEMA)
    con.execute("INSERT INTO entries VALUES ('e1','m',1,'w','w','n.',NULL)")
    con.execute("INSERT INTO senses VALUES ('s1','e1',1,NULL,NULL,?,NULL,NULL,NULL,NULL,NULL,NULL,'[]','unreviewed')",
                (f"known; {STANDARD_FORM}",))
    con.commit()
    con.close()


class MineWordsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        bible_db(root / "bible.sqlite")
        reference_db(root / "ref.sqlite")
        bible, ref = sqlite3.connect(root / "bible.sqlite"), sqlite3.connect(root / "ref.sqlite")
        cls.found, cls.report = pr.mine_words(bible, ref, SOURCES, STANDARD, min_count=3, run_id="r1")
        bible.close()
        ref.close()
        cls.by_word = {p["payload"]["zomi"]: p for p in cls.found}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_only_cleared_zomi_texts_are_read(self) -> None:
        self.assertEqual(self.report["versions_read"], ["tdbx"])
        self.assertIn("blk", self.report["versions_skipped"])
        self.assertNotIn("qablocked", self.by_word)
        self.assertNotIn("english", self.by_word)  # English versions are not Zomi text

    def test_words_already_in_the_dictionary_and_rare_words_are_left_out(self) -> None:
        self.assertNotIn("known", self.by_word)
        self.assertNotIn("qaonce", self.by_word)
        self.assertEqual(self.by_word["qaword"]["payload"]["occurrences"], 4)

    def test_attested_candidates_quote_their_references(self) -> None:
        candidate = self.by_word["qanew"]
        self.assertEqual((candidate["kind"], candidate["evidence_class"]), ("headword_candidate", "attested"))
        self.assertEqual(candidate["evidence"][0], {"source": "bible_cleared", "ref": "tdbx:1:1:2"})
        self.assertEqual(pr.validate(candidate), [])
        self.assertEqual(candidate["status"], "ai_suggested")

    def test_a_form_the_standard_maps_to_a_dictionary_word_is_a_spelling_variant(self) -> None:
        variant = self.by_word[zolai_standard.norm(VARIANT)]
        self.assertEqual((variant["kind"], variant["evidence_class"]), ("alternative_form", "spelling_variant"))
        self.assertEqual(variant["payload"]["standard_form"], zolai_standard.norm(STANDARD_FORM))

    def test_words_capitalized_inside_sentences_are_marked_as_probable_names(self) -> None:
        self.assertTrue(self.by_word["qaname"]["payload"].get("mostly_capitalized"))
        self.assertNotIn("mostly_capitalized", self.by_word["qanew"]["payload"])


FAKE_MODEL = textwrap.dedent("""
    import json, sys
    item = json.loads(sys.stdin.read().split("ITEM:", 1)[1])
    if item["id"] == "fail":
        sys.exit(3)
    print(json.dumps({"suggestions": [
        {"kind": "definition", "payload": {"english": "a placeholder meaning"}, "explanation": "because",
         "confidence": 0.7, "evidence_class": "attested"},
        {"kind": "not_a_kind", "payload": {"x": "y"}},
        {"kind": "synonym", "payload": "not an object"},
        {"kind": "example", "payload": {"zomi": "Q" * 900}}
    ]}))
""")


class GenerateTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        (self.dir / "model.py").write_text(FAKE_MODEL, encoding="utf-8")
        self.command = [sys.executable, str(self.dir / "model.py")]

    def run_model(self, items: list[dict], origin: str = "local_model", **kwargs):
        return pr.generate(items, prompt_template="Suggest. ITEM:{item}", command=self.command,
                           model_name="fake-model", model_version="0.1", origin=origin, sources=SOURCES,
                           run_id="run-1", **kwargs)

    def test_output_is_untrusted_checked_and_always_an_ai_candidate(self) -> None:
        found, report = self.run_model([{"id": "s1", "type": "sense", "source": "notes_local"}])
        self.assertEqual([p["kind"] for p in found], ["definition", "example"])
        self.assertTrue(all(p["evidence_class"] == "ai_candidate" for p in found))  # the model's "attested" is ignored
        self.assertEqual(len(found[1]["payload"]["zomi"]), pr.MAX_TEXT)  # capped
        self.assertEqual(report["dropped_malformed"], 2)
        self.assertEqual([pr.validate(p) for p in found], [[], []])
        self.assertEqual(found[0]["confidence_self_reported"], 0.7)
        self.assertEqual(len(found[0]["generator"]["prompt_sha256"]), 64)

    def test_nothing_is_sent_for_a_source_that_is_not_cleared(self) -> None:
        with self.assertRaises(PermissionError):
            self.run_model([{"id": "x", "source": "bible_blocked"}])
        with self.assertRaises(PermissionError):  # no external_llm clearance for any fixture source
            self.run_model([{"id": "s1", "source": "notes_local"}], origin="provider_assisted",
                           provider_terms={"product": "p", "terms_reference": "t", "reviewed_on": "2026-11-19"})
        with self.assertRaises(ValueError):
            self.run_model([{"id": "s1", "source": "notes_local"}], origin="provider_assisted")

    def test_a_failing_model_is_counted_not_fatal(self) -> None:
        found, report = self.run_model([{"id": "fail", "source": "notes_local"}, {"id": "s1", "source": "notes_local"}])
        self.assertEqual(report["model_errors"], 1)
        self.assertEqual(len(found), 2)


class ValidateTests(unittest.TestCase):
    def base(self, **changes) -> dict:
        p = pr.make("headword_candidate", {"type": "new"}, {"zomi": "qanew"}, "attested", "deterministic",
                    {"name": "mine-words", "version": "1"}, ["bible_cleared"],
                    [{"source": "bible_cleared", "ref": "v:1:1:1"}])
        p.update(changes)
        return p

    def test_rules(self) -> None:
        self.assertEqual(pr.validate(self.base()), [])
        self.assertTrue(pr.validate(self.base(status="owner_approved")))  # a proposal is never a decision
        self.assertTrue(pr.validate(self.base(evidence=[])))  # attested needs references
        self.assertTrue(pr.validate(self.base(origin="local_model")))  # a model cannot claim "attested"
        self.assertTrue(pr.validate(self.base(inputs=[])))


class RecordTests(unittest.TestCase):
    def test_owner_decides_edits_and_provenance_is_kept(self) -> None:
        found = [pr.make("definition", {"type": "sense", "id": "s1"}, {"english": "a meaning"}, "ai_candidate",
                         "provider_assisted", {"name": "m", "version": "1", "prompt_sha256": "a" * 64, "run_id": "r",
                                               "provider_terms": {"product": "p", "terms_reference": "t",
                                                                  "reviewed_on": "d"}}, ["notes_local"])]
        with tempfile.TemporaryDirectory() as tmp:
            sheet = Path(tmp) / "sheet.csv"
            pr.write_sheet(sheet, found)
            with sheet.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
        rows[0]["decision"] = "edit"
        _, errors = pr.record(rows, found, owner="O01", roster=ROSTER, decided_on="d", recorded_at="t")
        self.assertIn("edited_text", errors[0])
        rows[0]["edited_text"] = "the owner's meaning"
        out, errors = pr.record(rows, found, owner="O01", roster=ROSTER, decided_on="d", recorded_at="t")
        self.assertEqual(errors, [])
        self.assertEqual((out[0]["decision"], out[0]["edited_text"], out[0]["approval"]),
                         ("edit", "the owner's meaning", "owner_sole"))
        self.assertTrue(out[0]["provider_derived"])  # accepting it does not erase where it came from
        _, errors = pr.record(rows, found, owner="R01", roster=ROSTER, decided_on="d", recorded_at="t")
        self.assertIn("not the owner", errors[0])

    def test_cli_mine_sheet_record_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bible_db(root / "bible.sqlite")
            reference_db(root / "ref.sqlite")
            rights = root / "rights.json"
            rights.write_text(json.dumps({"sources": SOURCES}), encoding="utf-8")
            (root / "roster.csv").write_text("code,role\nO01,owner\n", encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(pr.main(["mine-words", "--bible-db", str(root / "bible.sqlite"), "--reference-db",
                                          str(root / "ref.sqlite"), "--out", str(root / "p.jsonl"),
                                          "--rights", str(rights)]), 0)
                self.assertEqual(pr.main(["sheet", "--proposals", str(root / "p.jsonl"), "--out",
                                          str(root / "s.csv")]), 0)
                with (root / "s.csv").open(encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                rows[0]["decision"] = "accept"
                with (root / "s.csv").open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=pr.SHEET_COLUMNS)
                    writer.writeheader()
                    writer.writerows(rows)
                self.assertEqual(pr.main(["record", "--sheet", str(root / "s.csv"), "--proposals",
                                          str(root / "p.jsonl"), "--decisions", str(root / "d.jsonl"),
                                          "--roster", str(root / "roster.csv"), "--owner", "O01"]), 0)
                self.assertEqual(pr.main(["sheet", "--proposals", str(root / "p.jsonl"), "--out",
                                          str(root / "s2.csv"), "--decisions", str(root / "d.jsonl")]), 0)
            self.assertEqual((root / "p.jsonl").stat().st_mode & 0o777, 0o600)
            with (root / "s2.csv").open(encoding="utf-8", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), len(rows) - 1)


if __name__ == "__main__":
    unittest.main()
