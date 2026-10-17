from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[2] / "ml_pipeline" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from prepare_review_pilot import select_rows  # noqa: E402


class ReviewPilotSelectionTests(unittest.TestCase):
    def test_selection_is_repeatable_and_covers_rare_flags(self) -> None:
        rows = [
            {"id": row_id, "quality_flags": json.dumps(["common"])}
            for row_id in range(1, 31)
        ]
        rows.extend([
            {"id": 31, "quality_flags": json.dumps(["rare"])},
            {"id": 32, "quality_flags": json.dumps(["rare"])},
        ])
        first = select_rows(rows, 10, "pilot-test")
        second = select_rows(rows, 10, "pilot-test")
        self.assertEqual([row["id"] for row in first], [row["id"] for row in second])
        self.assertEqual(len(first), 10)
        self.assertEqual({31, 32}.intersection(row["id"] for row in first), {31, 32})


if __name__ == "__main__":
    unittest.main()
