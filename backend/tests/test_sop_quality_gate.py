from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml_pipeline" / "scripts"))
from sop_quality_gate import check_records


def approved(**overrides):
    row = {
        "id": "sentence-001", "english": "Welcome home.", "zomi": "Test Zomi sentence.",
        "split": "train", "split_family_id": "family-001", "origin_language": "en",
        "review_status": "HUMAN_APPROVED", "contributor_id": "author-1",
        "reviewer_id": "reviewer-2", "approver_id": "editor-3",
        "approval_version": "1", "source_id": "source-001", "rights": {"train": True},
    }
    row.update(overrides)
    return row


class SopQualityGateTests(unittest.TestCase):
    def test_approved_record_passes(self):
        self.assertTrue(check_records([approved()])["passed"])

    def test_ai_generated_unreviewed_rejected(self):
        self.assertIn("not_human_approved", self.codes([approved(review_status="DRAFT")]))

    def test_self_approval_rejected(self):
        self.assertIn("self_approval", self.codes([approved(reviewer_id="author-1")]))

    def test_missing_training_rights_rejected(self):
        self.assertIn("training_rights_not_cleared", self.codes([approved(rights={"display": True})]))

    def test_family_cannot_cross_splits(self):
        rows = [approved(), approved(id="sentence-002", english="Different.",
                                  zomi="Other.", split="test")]
        self.assertIn("split_family_leakage", self.codes(rows))

    def test_duplicate_pair_across_splits_rejected(self):
        rows = [approved(), approved(id="sentence-002", split_family_id="family-002",
                                    split="test")]
        self.assertIn("duplicate_pair_across_splits", self.codes(rows))

    def test_same_english_with_different_zomi_cannot_cross_splits(self):
        rows = [approved(), approved(id="sentence-002", split_family_id="family-002",
                                    zomi="Other test Zomi.", split="test")]
        self.assertIn("english_across_splits", self.codes(rows))

    def test_same_zomi_with_different_english_cannot_cross_splits(self):
        rows = [approved(), approved(id="sentence-002", split_family_id="family-002",
                                    english="Welcome back.", split="test")]
        self.assertIn("zomi_across_splits", self.codes(rows))

    def test_duplicate_pair_within_split_rejected(self):
        rows = [approved(), approved(id="sentence-002", split_family_id="family-002")]
        self.assertIn("duplicate_pair", self.codes(rows))

    def test_self_approval_ignores_case_and_spaces(self):
        self.assertIn("self_approval", self.codes([approved(reviewer_id=" AUTHOR-1 ")]))
        self.assertIn("self_approval", self.codes([approved(approver_id="Author-1")]))

    def test_distinct_rows_in_different_splits_pass(self):
        rows = [approved(), approved(id="sentence-002", split_family_id="family-002",
                                    english="Welcome back.", zomi="Other test Zomi.", split="test")]
        self.assertTrue(check_records(rows)["passed"])

    def test_missing_provenance_rejected(self):
        self.assertIn("missing_provenance", self.codes([approved(source_id="")]))

    def test_missing_origin_rejected(self):
        self.assertIn("invalid_origin_language", self.codes([approved(origin_language="my")]))

    def test_duplicate_identifier_rejected(self):
        rows = [approved(), approved(english="Different", zomi="Other", split_family_id="other")]
        self.assertIn("duplicate_id", self.codes(rows))

    def test_empty_dataset_rejected(self):
        self.assertIn("empty_dataset", self.codes([]))

    @staticmethod
    def codes(records):
        return {error["code"] for error in check_records(records)["errors"]}


if __name__ == "__main__":
    unittest.main()
