"""The owner's applied dictionary changes on the live 50K dictionary (build_language_db.py --applied-dictionary).

Zomi-side strings are placeholders, except the two spellings of owner-adopted rule ZS-001 (data/zomi_standard_form).
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "services"))

import changesets as cs  # type: ignore  # noqa: E402
import zolai_standard  # type: ignore  # noqa: E402
from build_language_db import (  # type: ignore  # noqa: E402
    OWNER_HEADWORDS, apply_applied_dictionary, connect, create_schema, ingest_translation_master,
)
from import_reference_dictionaries import SCHEMA as REFERENCE_SCHEMA  # type: ignore  # noqa: E402
from language_engine import LanguageEngine  # type: ignore  # noqa: E402

STANDARD = zolai_standard.load()
RULE = next(r for r in STANDARD.rules if r.id == "ZS-001")
VARIANT, STANDARD_FORM = RULE.variants[0], RULE.standard
CREATED = "2026-11-19T00:00:00+00:00"


def live_db(root: Path) -> Path:
    import openpyxl

    wb = openpyxl.Workbook()
    records = wb.active
    records.title = "01_All_Records"
    records.append(["group header"])
    records.append(["Entry ID", "Headword", "Part of speech", "Sense number", "Simple English definition",
                    "Current Standard Zomi", "Current Burmese (reference only)", "Usage tier code", "Domain"])
    records.append(["ZD-000001", "ability", "n.", "1", "The power to do something.", f"{VARIANT}; QAZU", None, "A1", None])
    records.append(["ZD-000002", "books", "n.", "1", "More than one book.", "QABOOKS", None, "A1", None])
    records.append(["ZD-000003", "abandon", "v.", "1", "To leave.", "VOZE", None, "B1", None])
    records.append(["ZD-000004", "twin", "n.", "1", "One of two.", "QATWIN", None, "B1", None])
    records.append(["ZD-000005", "twin", "n.", "2", "One of two.", "QATWIN", None, "B1", None])  # ambiguous
    issues = wb.create_sheet("04_Open_Issue_Index")
    issues.append(["title"])
    issues.append(["Item ID", "Record ID", "Issue category", "Issue code"])
    source = root / "50k.xlsx"
    wb.save(source)
    db = root / "lang.sqlite"
    con = connect(db)
    create_schema(con)
    ingest_translation_master(con, source, CREATED)
    con.close()
    return db


def applied_db(root: Path) -> Path:
    """A reference copy holding the same senses, with an applied changeset made by the real changesets code."""
    base = root / "ref.sqlite"
    con = sqlite3.connect(base)
    con.executescript(REFERENCE_SCHEMA)
    entries = [("m:1", "ability"), ("m:2", "books"), ("m:3", "abandon"), ("m:4", "twin"), ("e:1", "able")]
    for entry_id, headword in entries:
        source = "essential_3000" if entry_id.startswith("e:") else "translation_master_50k"
        con.execute("INSERT INTO entries VALUES (?,?,1,?,?,'n.',NULL)", (entry_id, source, headword, headword))
    senses = [("m:1:1", "m:1", f"{VARIANT}; QAZU", "The power to do something."),
              ("m:3:1", "m:3", "VOZE", "To leave."), ("m:4:1", "m:4", f"QATWIN {VARIANT}", "One of two."),
              ("e:1:1", "e:1", f"{VARIANT}", "Can do.")]
    for sense_id, entry_id, zomi, definition in senses:
        con.execute("INSERT INTO senses VALUES (?,?,1,NULL,?,?,NULL,NULL,NULL,NULL,NULL,NULL,'[]','unreviewed')",
                    (sense_id, entry_id, definition, zomi))
    con.commit()
    con.close()
    base_op = {"decision": "d", "origin": "deterministic", "provider_derived": False}
    changeset = {"changeset_id": "C-test", "ops": [
        {**base_op, "op": "standardize_zomi", "sense": "m:1:1"},
        {**base_op, "op": "set_definition", "sense": "m:3:1", "text": "To leave behind (the owner's words)."},
        {**base_op, "op": "mark_inflected", "source": "translation_master_50k", "headword": "books",
         "base_headword": "book"},
        {**base_op, "op": "standardize_zomi", "sense": "m:4:1"},   # ambiguous on the live side
        {**base_op, "op": "standardize_zomi", "sense": "e:1:1"},   # Essential 3000: not in the live dictionary
        {**base_op, "op": "add_zomi_headword", "zomi": "qanew", "meaning_en": "a new thing", "variant_of": "",
         "evidence": [{"source": "bible_tdb", "ref": "tdb:1:1:1"}]},
        {**base_op, "op": "add_zomi_headword", "zomi": "qawait", "meaning_en": "", "variant_of": "", "evidence": []},
        {"decision": "p", "origin": "provider_assisted", "provider_derived": True, "op": "add_zomi_headword",
         "zomi": "qaprov", "meaning_en": "provider meaning", "variant_of": "", "evidence": []},
        {"decision": "m", "origin": "local_model", "provider_derived": False, "op": "annotate_sense",
         "sense": "m:1:1", "kind": "example", "value": "model text"},
    ]}
    out = root / "applied.sqlite"
    out.write_bytes(base.read_bytes())
    con = sqlite3.connect(out)
    cs.run_changeset(con, changeset, STANDARD)
    con.commit()
    con.close()
    return out


class AppliedDictionaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.db = live_db(root)
        con = sqlite3.connect(cls.db)
        cls.stats = apply_applied_dictionary(con, applied_db(root), CREATED)
        con.close()
        cls.engine = LanguageEngine(cls.db)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def entry(self, english: str) -> dict:
        return self.engine.search_dictionary(english)[0]

    def test_standard_form_reaches_the_live_entry_in_the_live_style(self) -> None:
        self.assertEqual(self.entry("ability")["zomi"], f"{STANDARD_FORM} ; QAZU")
        # Search follows the new text.
        self.assertEqual(self.engine.search_dictionary(STANDARD_FORM.split()[0], direction="ctd-en")[0]["english"],
                         "ability")

    def test_the_owners_definition_and_inflected_form_note(self) -> None:
        self.assertEqual(self.entry("abandon")["definition"], "To leave behind (the owner's words).")
        self.assertEqual(self.entry("books")["usage_notes"], "Inflected form of 'book'")

    def test_ambiguous_and_absent_matches_are_skipped_not_guessed(self) -> None:
        twins = self.engine.search_dictionary("twin")
        self.assertTrue(all(t["zomi"] == "QATWIN" for t in twins))
        self.assertEqual(self.stats["skipped_no_single_match"], 1)
        self.assertEqual(self.stats["not_in_the_live_dictionary"], 1)

    def test_owner_headwords_are_added_but_not_model_or_provider_text(self) -> None:
        new = self.entry("a new thing")
        self.assertEqual((new["zomi"], new["source"], new["verification_status"]), ("qanew", OWNER_HEADWORDS, "verified"))
        self.assertEqual(self.engine.search_dictionary("provider meaning"), [])
        self.assertEqual(self.stats["zomi_headwords_added"], 1)
        self.assertEqual(self.stats["zomi_headwords_waiting_for_a_meaning"], 1)
        self.assertEqual(self.stats["zomi_headwords_from_provider_not_shown"], 1)
        self.assertEqual(self.stats["annotations_not_shown"], 1)
        con = sqlite3.connect(self.db)
        text = " ".join(str(v) for row in con.execute("SELECT * FROM dictionary_entries") for v in row)
        con.close()
        self.assertNotIn("model text", text)

    def test_unchanged_rows_keep_their_status(self) -> None:
        self.assertEqual(self.entry("ability")["verification_status"], "unreviewed")


if __name__ == "__main__":
    unittest.main()
