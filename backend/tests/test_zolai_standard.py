from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ml_pipeline" / "scripts" / "zolai_standard.py"
sys.path.insert(0, str(SCRIPT.parent))

import spelling_variants as sv  # noqa: E402
import zolai_standard as zs  # noqa: E402

# Placeholder words only: these tests check the mechanics, not Zomi.


def rule(rule_id: str, standard: str, variants: list[str], **extra) -> dict:
    data = {
        "id": rule_id, "standard": standard, "variants": variants, "mode": "replace",
        "approved_by": ["R01", "E01"], "approved_on": "2026-11-01", "reason": "test",
    }
    data.update(extra)
    return data


def build(*rules: dict, version: str = "1.0.0") -> zs.Standard:
    return zs.parse({"version": version, "rules": list(rules)}, check_ids={"join", "possessive"})


class ValidationTests(unittest.TestCase):
    def test_repository_standard_is_valid(self) -> None:
        standard = zs.load()
        self.assertTrue(zs.VERSION.match(standard.version))

    def test_needs_two_different_reviewers(self) -> None:
        for codes in (["R01"], ["R01", "R01"], ["R01", "reviewer"], []):
            with self.subTest(codes=codes), self.assertRaisesRegex(zs.StandardError, "two different reviewer"):
                build(rule("ZS-001", "qaqo", ["qa qo"], approved_by=codes))

    def test_rejects_bad_fields(self) -> None:
        cases = {
            "id must": rule("Z1", "qaqo", ["qa qo"]),
            "variants must": rule("ZS-001", "qaqo", []),
            "is the standard spelling itself": rule("ZS-001", "qaqo", ["QaQo"]),
            "mode must": rule("ZS-001", "qaqo", ["qa qo"], mode="auto"),
            "approved_on": rule("ZS-001", "qaqo", ["qa qo"], approved_on="soon"),
            "not in rule_checks": rule("ZS-001", "qaqo", ["qa qo"], check="nope"),
        }
        for message, bad in cases.items():
            with self.subTest(message=message), self.assertRaisesRegex(zs.StandardError, message):
                build(bad)

    def test_rejects_duplicates_and_chains(self) -> None:
        with self.assertRaisesRegex(zs.StandardError, "id used twice"):
            build(rule("ZS-001", "qaqo", ["qa qo"]), rule("ZS-001", "vu", ["vuu"]))
        with self.assertRaisesRegex(zs.StandardError, "also in ZS-001"):
            build(rule("ZS-001", "qaqo", ["qa qo"]), rule("ZS-002", "qa-qo", ["qa qo"]))
        with self.assertRaisesRegex(zs.StandardError, "standard spelling of ZS-001"):
            build(rule("ZS-001", "qaqo", ["qa qo"]), rule("ZS-002", "vu", ["qaqo"]))

    def test_rejects_bad_version(self) -> None:
        with self.assertRaisesRegex(zs.StandardError, "version"):
            build(version="draft")


class StandardizeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.standard = build(
            rule("ZS-001", "qa qo", ["qaqo"], check="join"),
            rule("ZS-002", "mi'", ["mi ii"], check="possessive"),
            rule("ZS-003", "ve-ri", ["veri", "ve ri"]),
            rule("ZS-004", "tuu", ["tu"], mode="flag"),
        )

    def test_no_rules_changes_nothing(self) -> None:
        result = zs.standardize("Qaqo veri tu.", build())
        self.assertEqual((result.text, result.rules, result.flags), ("Qaqo veri tu.", [], []))

    def test_replaces_whole_words_and_phrases_and_keeps_case(self) -> None:
        result = zs.standardize("Qaqo zu qaqo. QAQO veri, ve  ri.", self.standard)
        self.assertEqual(result.text, "Qa qo zu qa qo. QA QO ve-ri, ve-ri.")
        self.assertEqual(result.rules, ["ZS-001", "ZS-003"])

    def test_does_not_touch_parts_of_longer_words(self) -> None:
        result = zs.standardize("zuqaqo qaqozu xqaqo-zu ve-ri-zu", self.standard)
        self.assertEqual(result.text, "zuqaqo qaqozu xqaqo-zu ve-ri-zu")
        self.assertEqual(result.rules, [])

    def test_apostrophe_forms_match_each_other(self) -> None:
        self.assertEqual(zs.standardize("mi ii laibu", self.standard).text, "mi' laibu")
        standard = build(rule("ZS-001", "zo ah", ["zo’ah"]))
        self.assertEqual(zs.standardize("zo'ah zo’ah", standard).text, "zo ah zo ah")

    def test_flag_rules_list_but_do_not_change(self) -> None:
        result = zs.standardize("tu zu Tu", self.standard)
        self.assertEqual(result.text, "tu zu Tu")
        self.assertEqual(result.rules, [])
        self.assertEqual([(f["rule"], f["text"], f["start"]) for f in result.flags],
                         [("ZS-004", "tu", 0), ("ZS-004", "Tu", 6)])

    def test_variant_index_and_search_forms(self) -> None:
        index = zs.variant_index(self.standard)
        self.assertEqual(index["veri"], "ve-ri")
        self.assertEqual(index["ve-ri"], "ve-ri")
        self.assertEqual(zs.search_forms("VERI", self.standard), ["ve-ri", "veri", "ve ri"])
        self.assertEqual(zs.search_forms("zu", self.standard), ["zu"])


class ApplyTests(unittest.TestCase):
    def test_apply_keeps_original_and_adds_standard(self) -> None:
        standard = build(rule("ZS-001", "qa qo", ["qaqo"]))
        out = list(zs.apply_records([{"id": 1, "zomi": "Qaqo zu"}, {"id": 2, "en": "no zomi"}], "zomi", standard))
        self.assertEqual(out[0]["zomi"], "Qaqo zu")
        self.assertEqual(out[0]["zomi_standard"], "Qa qo zu")
        self.assertEqual(out[0]["zomi_standard_rules"], ["ZS-001"])
        self.assertEqual(out[0]["standard_version"], "1.0.0")
        self.assertEqual(out[1], {"id": 2, "en": "no zomi"})

    def test_cli_apply_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            standard_path = tmp_path / "standard.json"
            standard_path.write_text(json.dumps({"version": "0.1.0", "rules": [rule("ZS-001", "qa qo", ["qaqo"])]}))
            source = tmp_path / "in.jsonl"
            source.write_text(json.dumps({"zomi": "qaqo"}) + "\n", encoding="utf-8")
            out = tmp_path / "out.jsonl"
            base = [sys.executable, str(SCRIPT), "--standard", str(standard_path)]
            subprocess.run([*base, "apply", "--input", str(source), "--field", "zomi", "--out", str(out)], check=True)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["zomi_standard"], "qa qo")
            self.assertEqual(json.loads(source.read_text(encoding="utf-8")), {"zomi": "qaqo"})
            same = subprocess.run([*base, "apply", "--input", str(source), "--field", "zomi", "--out", str(source)],
                                  capture_output=True, text=True)
            self.assertNotEqual(same.returncode, 0)
            standard_path.write_text(json.dumps({"version": "0.1.0", "rules": [rule("ZS-001", "qa qo", ["qaqo"], approved_by=["R01"])]}))
            bad = subprocess.run([*base, "validate"], capture_output=True, text=True)
            self.assertEqual(bad.returncode, 1)
            self.assertIn("two different reviewer", bad.stderr)


class RuleChecksFileTests(unittest.TestCase):
    def test_rule_checks_file_loads_and_every_check_names_each_guide(self) -> None:
        data = json.loads(zs.DEFAULT_CHECKS.read_text(encoding="utf-8"))
        ids = [check["id"] for check in data["checks"]]
        self.assertEqual(len(ids), len(set(ids)))
        for check in data["checks"]:
            with self.subTest(check=check["id"]):
                for guide in data["guides"]:
                    self.assertTrue(check.get(guide), f"{check['id']} has no '{guide}' entry")
                self.assertTrue(check["variants"] and all(check["variants"]))
        self.assertTrue(data["owner_policy"]["text"])
        # The evidence script still counts every check's variants.
        source = sv.Source("s", "test")
        source.add("qa qo")
        self.assertEqual(len({row["check"] for row in sv.rule_checks([source], data["checks"])}), len(ids))


if __name__ == "__main__":
    unittest.main()
