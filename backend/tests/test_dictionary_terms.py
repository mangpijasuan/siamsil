from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT.parent / "ml_pipeline" / "scripts"))

import dictionary_terms  # type: ignore  # noqa: E402

# Zomi-side strings are placeholders, never real language data.
TERMS = {"terms": {"qazz": {
    "english": ["qazz", "qazzes"],
    "zomi": [{"word": "ZQNEW", "meaning": "qazz"}, {"word": "ZQOTHER", "meaning": "qazz, in another context"}],
    "note": "Placeholder decision.",
    "headword": "ZQNEW",
    "suggest": [{"from": "zqold mi", "to": "ZQNEW"}, {"from": "zqold", "to": "ZQNEWISH"}],
    "decided_by": "project owner", "decided_on": "2026-10-31", "confirmed_by": None,
}}}


class TermTests(unittest.TestCase):
    def load(self, data: dict) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "terms.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return dictionary_terms.load_terms(path)

    def test_headwords_that_use_the_term(self) -> None:
        term = self.load(TERMS)["qazz"]
        self.assertTrue(term.matches("border qazz camp"))
        self.assertTrue(term.matches("Qazzes"))
        self.assertFalse(term.matches("qazzism"))

    def test_suggestion_replaces_longest_forms_first_as_whole_words(self) -> None:
        term = self.load(TERMS)["qazz"]
        self.assertEqual(term.suggestion("qazz aid", "zqold mite huhna"), "ZQNEWte huhna")
        self.assertEqual(term.suggestion("qazz aid", "Zqold pawl ; xzqold"), "ZQNEWISH pawl ; xzqold")
        self.assertEqual(term.suggestion("qazz aid", "nothing to change"), "")
        # The headword itself gets the term's main word.
        self.assertEqual(term.suggestion("qazz", "anything else"), "ZQNEW")
        self.assertEqual(term.suggestion("qazz", "ZQNEW"), "")

    def test_choices_say_whether_a_second_person_confirmed_it(self) -> None:
        choices = self.load(TERMS)["qazz"].choices()
        self.assertIn("ZQNEW (qazz); ZQOTHER (qazz, in another context)", choices)
        self.assertIn("not yet confirmed by a second person", choices)

    def test_a_term_must_say_who_decided_it(self) -> None:
        data = json.loads(json.dumps(TERMS))
        del data["terms"]["qazz"]["decided_by"]
        with self.assertRaisesRegex(ValueError, "who decided"):
            self.load(data)

    def test_the_repository_terms_file_loads(self) -> None:
        terms = dictionary_terms.load_terms()
        self.assertTrue(terms)
        for term in terms.values():
            self.assertTrue(term.english and term.zomi)


if __name__ == "__main__":
    unittest.main()
