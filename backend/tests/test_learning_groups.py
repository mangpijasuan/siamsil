from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.data_loader import DataStore  # noqa: E402


class LearningGroupsTests(unittest.TestCase):
    def test_only_verified_phrases_are_published(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DataStore(Path(tmp))
            store.daily_use_pairs = [
                {"id": 1, "category": "Time", "english": "today", "verified": True},
                {"id": 2, "category": "Time", "english": "tomorrow", "verified": False},
                {"id": 3, "category": "Draft", "english": "draft", "verified": None},
            ]
            self.assertEqual(store.learning_groups(), {"Time": [store.daily_use_pairs[0]]})


if __name__ == "__main__":
    unittest.main()
