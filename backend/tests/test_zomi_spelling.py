from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from main import app  # noqa: E402
from services.zomi_spelling import suggest_spelling  # noqa: E402


def approved_rule(variant="qa qo", replacement="qaqo", mode="replace"):
    return {"id": "ZS-001", "standard": replacement, "variants": [variant],
            "mode": mode, "approved_by": ["R01", "E01"],
            "approved_on": "2026-11-03", "reason": "Synthetic test example"}


class SpellingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / "standard.json"

    def standard(self, rules):
        self.file.write_text(json.dumps({"version": "1.0.0", "rules": rules}), encoding="utf-8")

    def test_no_adopted_rules_no_guessed_corrections(self):
        self.standard([])
        result = suggest_spelling("qa qo", self.file)
        self.assertEqual(result["status"], "no_approved_rules")
        self.assertEqual(result["suggested"], "qa qo")
        self.assertEqual(result["suggestions"], [])

    def test_single_approved_rule_suggests_without_editing_original(self):
        self.standard([approved_rule()])
        result = suggest_spelling("Qa qo, qa qo.", self.file)
        self.assertEqual(result["original"], "Qa qo, qa qo.")
        self.assertEqual(result["suggested"], "Qaqo, qaqo.")
        self.assertEqual(len(result["suggestions"]), 2)
        self.assertEqual(result["suggestions"][0]["rule_id"], "ZS-001")
        self.assertEqual(result["suggestions"][0]["start"], 0)

    def test_context_sensitive_rule_flags_without_replacement(self):
        self.standard([approved_rule(mode="flag")])
        result = suggest_spelling("qa qo", self.file)
        self.assertEqual(result["suggested"], "qa qo")
        self.assertEqual(result["suggestions"][0]["mode"], "flag")

    def test_never_changes_substrings_in_other_words(self):
        self.standard([approved_rule("qa", "qaa")])
        self.assertEqual(suggest_spelling("qamo qa qa-qo", self.file)["suggested"], "qamo qaa qa-qo")

    def test_missing_configuration(self):
        self.assertEqual(suggest_spelling("qamo", self.file)["status"], "not_configured")

    def test_one_reviewer_rejected(self):
        rule = approved_rule()
        rule["approved_by"] = ["R01"]
        self.standard([rule])
        with self.assertRaisesRegex(ValueError, "reviewer"):
            suggest_spelling("qa qo", self.file)

    def test_conflicting_rules_rejected(self):
        other = approved_rule(replacement="qaqoo")
        other["id"] = "ZS-002"
        self.standard([approved_rule(), other])
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            suggest_spelling("qa qo", self.file)

    def test_too_long_rejected(self):
        with self.assertRaises(ValueError):
            suggest_spelling("a" * 4001, self.file)

    def test_endpoint_returns_suggestions_only(self):
        self.standard([approved_rule()])
        client = TestClient(app)
        with patch("services.zomi_spelling.standard_path", return_value=self.file):
            response = client.post("/api/v1/words/spelling/suggest", json={"text": "qa qo"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["suggested"], "qaqo")
        self.assertEqual(response.json()["original"], "qa qo")

    def test_endpoint_rejects_long_text(self):
        client = TestClient(app)
        self.assertEqual(client.post("/api/v1/words/spelling/suggest",
                                     json={"text": "a" * 4001}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
