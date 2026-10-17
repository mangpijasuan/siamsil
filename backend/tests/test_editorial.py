from __future__ import annotations

import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from identity.dependencies import get_current_user  # type: ignore  # noqa: E402
from identity.schemas import AuthenticatedUser  # type: ignore  # noqa: E402
from main import app  # type: ignore  # noqa: E402
from models.identity import AuditEvent, User  # type: ignore  # noqa: E402
from models.translation_review import TranslationAttempt, TranslationJob, TranslationReview  # type: ignore  # noqa: E402
from routers.product_state import get_product_session  # type: ignore  # noqa: E402
from scripts.import_review_pilot import import_packet, read_packet  # type: ignore  # noqa: E402


class EditorialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)
        for table in (User.__table__, AuditEvent.__table__, TranslationJob.__table__,
                      TranslationAttempt.__table__, TranslationReview.__table__):
            table.create(self.engine)
        self.user_id = uuid.uuid4()
        with Session(self.engine) as session:
            session.add(User(id=self.user_id))
            job = TranslationJob(sentence_id=101, english_source="Hello", dataset_version="pilot-v1",
                                 quality_flags=["length"], license_status="needs_review", status="pending")
            session.add(job)
            session.flush()
            session.add(TranslationAttempt(job_id=job.id, attempt_number=1, zomi_text="Candidate", model="test"))
            session.commit()
            self.job_id = job.id

        def session_override():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_product_session] = session_override
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            user_id=self.user_id, issuer="test", subject="reviewer", roles=frozenset({"reviewer"})
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_claim_and_decide_does_not_publish(self) -> None:
        base = f"/api/v1/editorial/translation-jobs/{self.job_id}"
        self.assertEqual(self.client.get("/api/v1/editorial/translation-jobs").json()["count"], 1)
        claimed = self.client.post(base + "/claim")
        self.assertEqual(claimed.status_code, 200, claimed.text)
        self.assertEqual(claimed.json()["zomi_candidate"], "Candidate")
        self.assertEqual(self.client.post(base + "/claim").status_code, 409)
        decided = self.client.post(base + "/decision", json={"decision": "edit", "corrected_zomi": "Corrected"})
        self.assertEqual(decided.status_code, 200, decided.text)
        self.assertEqual(decided.json()["publication_status"], "unpublished")
        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(TranslationJob).where(TranslationJob.id == self.job_id)).status, "edited")
            self.assertEqual(session.scalar(select(TranslationReview)).corrected_zomi, "Corrected")
            self.assertEqual(session.scalar(select(TranslationAttempt)).zomi_text, "Candidate")
            self.assertEqual(session.scalar(select(AuditEvent)).action, "translation_review.decision")

    def test_non_reviewer_is_denied(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            user_id=self.user_id, issuer="test", subject="learner", roles=frozenset({"learner"})
        )
        response = self.client.get("/api/v1/editorial/translation-jobs")
        self.assertEqual(response.status_code, 403)

    def test_packet_validation_rejects_non_training_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "packet.jsonl"
            path.write_text(json.dumps({"sentence_id": 1, "english_source": "Hello",
                                        "zomi_candidate": "Candidate", "dataset_version": "v1",
                                        "dataset_split": "test", "license_status": "needs_review",
                                        "quality_flags": []}) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "training-split"):
                read_packet(path)

    def test_packet_import_keeps_original_attempt_and_skips_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "packet.jsonl"
            path.write_text(json.dumps({"sentence_id": 202, "english_source": "Good day",
                                        "zomi_candidate": "Machine candidate", "dataset_version": "pilot-v1",
                                        "dataset_split": "train", "license_status": "needs_review",
                                        "quality_flags": ["length"]}) + "\n", encoding="utf-8")
            self.assertEqual(import_packet(path), (1, 0))
            with patch("scripts.import_review_pilot.get_database_engine", return_value=self.engine):
                self.assertEqual(import_packet(path, commit=True), (1, 1))
                self.assertEqual(import_packet(path, commit=True), (1, 0))
            with Session(self.engine) as session:
                job = session.scalar(select(TranslationJob).where(TranslationJob.sentence_id == 202))
                self.assertEqual(job.license_status, "needs_review")
                self.assertEqual(session.scalar(select(TranslationAttempt).where(
                    TranslationAttempt.job_id == job.id)).zomi_text, "Machine candidate")


if __name__ == "__main__":
    unittest.main()
