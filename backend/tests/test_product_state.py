from __future__ import annotations

import sys
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from identity.dependencies import get_current_user  # type: ignore  # noqa: E402
from identity.schemas import AuthenticatedUser  # type: ignore  # noqa: E402
from main import app  # type: ignore  # noqa: E402
from models.identity import User  # type: ignore  # noqa: E402
from models.product_state import LearningProgress, SavedItem  # type: ignore  # noqa: E402
from routers.product_state import get_product_session  # type: ignore  # noqa: E402


class ProductStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)
        User.__table__.create(self.engine)
        SavedItem.__table__.create(self.engine)
        LearningProgress.__table__.create(self.engine)
        self.user_id = uuid.uuid4()
        with Session(self.engine) as session:
            session.add(User(id=self.user_id))
            session.commit()

        def session_override():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_product_session] = session_override
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            user_id=self.user_id, issuer="test", subject="user", roles=frozenset({"learner"})
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_saved_item_round_trip_is_idempotent_and_user_scoped(self) -> None:
        path = "/api/v1/me/saved/bible_verse/5:18:1"
        self.assertEqual(self.client.put(path).status_code, 200)
        self.assertEqual(self.client.put(path).status_code, 200)
        listed_response = self.client.get("/api/v1/me/saved")
        self.assertEqual(listed_response.headers["Cache-Control"], "no-store")
        listed = listed_response.json()
        self.assertEqual(listed["count"], 1)
        self.assertEqual(listed["items"][0]["item_key"], "5:18:1")
        self.assertEqual(self.client.delete(path).status_code, 204)
        self.assertEqual(self.client.get("/api/v1/me/saved").json()["count"], 0)

    def test_invalid_saved_key_is_rejected(self) -> None:
        response = self.client.put("/api/v1/me/saved/bible_verse/not-a-reference")
        self.assertEqual(response.status_code, 422)

    def test_learning_progress_round_trip(self) -> None:
        path = "/api/v1/me/progress/phrases.greetings.1"
        self.assertEqual(self.client.put(path, json={"percent": 40, "completed": False}).status_code, 200)
        updated = self.client.put(path, json={"percent": 100, "completed": True})
        self.assertEqual(updated.status_code, 200)
        self.assertTrue(updated.json()["completed"])
        self.assertEqual(self.client.get("/api/v1/me/progress").json()["items"][0]["percent"], 100)

    def test_cross_user_records_are_not_visible(self) -> None:
        with Session(self.engine) as session:
            other = uuid.uuid4()
            session.add(User(id=other))
            session.add(SavedItem(user_id=other, item_type="dictionary_entry", item_key="123"))
            session.commit()
        self.assertEqual(self.client.get("/api/v1/me/saved").json()["count"], 0)


if __name__ == "__main__":
    unittest.main()
