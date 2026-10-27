from __future__ import annotations

import os
import sys
import unittest
import uuid
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_database_engine  # noqa: E402
from identity.dependencies import get_current_user  # noqa: E402
from identity.schemas import AuthenticatedUser  # noqa: E402
from main import app  # noqa: E402
from models import AuditEvent, SourcePermission, SpeakerConsent, User  # noqa: E402
from speech.router import get_speech_session  # noqa: E402


def person(*roles: str, user_id: uuid.UUID | None = None) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id or uuid.uuid4(), issuer="https://issuer.example", subject=str(uuid.uuid4()), roles=frozenset(roles)
    )


CONSENT = {
    "form_version": "audio-consent-v1",
    "form_language": "zomi",
    "consent_method": "written",
    "consent_date": "2026-10-25",
    "collector_code": "C01",
    "adult_confirmed": True,
    "choices": {
        "keep_and_evaluate": True,
        "train_recognition": True,
        "train_synthesis": False,
        "play_in_app": True,
        "public_dataset": False,
        "commercial_use": False,
    },
    "credit": "initials",
    "evidence_reference": "siamsil-data/consent/S0001-v1 (private)",
}
SOURCE = {"platform": "youtube", "url": "https://www.youtube.com/watch?v=test0001", "title": "Pilot recording"}


class SpeechAccessTests(unittest.TestCase):
    """Who may call what. Runs without a database: access is decided before any query."""

    def setUp(self) -> None:
        self.client = TestClient(app)
        app.dependency_overrides[get_speech_session] = lambda: iter([None])

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def as_user(self, *roles: str) -> None:
        app.dependency_overrides[get_current_user] = lambda: person(*roles)

    def test_every_speech_endpoint_requires_sign_in(self) -> None:
        app.dependency_overrides.pop(get_speech_session)
        source = uuid.uuid4()
        calls = [
            ("get", "/api/v1/speech/sources"),
            ("post", "/api/v1/speech/sources"),
            ("get", f"/api/v1/speech/sources/{source}"),
            ("get", f"/api/v1/speech/sources/{source}/eligibility"),
            ("post", f"/api/v1/speech/sources/{source}/permissions"),
            ("post", f"/api/v1/speech/sources/{source}/permissions/{uuid.uuid4()}/decision"),
            ("post", f"/api/v1/speech/sources/{source}/speakers/S0001"),
            ("post", f"/api/v1/speech/sources/{source}/withdraw"),
            ("get", "/api/v1/speech/speakers"),
            ("post", "/api/v1/speech/speakers"),
            ("post", "/api/v1/speech/speakers/S0001/consents"),
            ("post", "/api/v1/speech/speakers/S0001/withdrawal"),
        ]
        for method, path in calls:
            with self.subTest(method=method, path=path):
                response = self.client.post(path, json={}) if method == "post" else self.client.get(path)
                self.assertEqual(response.status_code, 401)

    def test_only_administrators_change_records(self) -> None:
        for roles in (("learner",), ("contributor",), ("reviewer",), ("editor",), ("moderator",)):
            with self.subTest(roles=roles):
                self.as_user(*roles)
                self.assertEqual(self.client.post("/api/v1/speech/sources", json=SOURCE).status_code, 403)
                self.assertEqual(
                    self.client.post("/api/v1/speech/speakers/S0001/consents", json=CONSENT).status_code, 403
                )

    def test_reviewers_cannot_read_rights_or_consent(self) -> None:
        self.as_user("reviewer")
        self.assertEqual(self.client.get("/api/v1/speech/speakers").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/speech/sources").status_code, 403)

    def test_invalid_consent_is_refused_before_anything_is_saved(self) -> None:
        self.as_user("administrator")
        minor = {**CONSENT, "adult_confirmed": False}
        missing_choice = {**CONSENT, "choices": {k: v for k, v in CONSENT["choices"].items() if k != "train_synthesis"}}
        multiline_evidence = {**CONSENT, "evidence_reference": "line one\nline two"}
        unknown_field = {**CONSENT, "speaker_name": "Real Name"}
        for body in (minor, missing_choice, multiline_evidence, unknown_field):
            with self.subTest(body=body):
                self.assertEqual(self.client.post("/api/v1/speech/speakers/S0001/consents", json=body).status_code, 422)

    def test_invalid_codes_and_uses_are_refused(self) -> None:
        self.as_user("administrator")
        self.assertEqual(self.client.post("/api/v1/speech/speakers", json={"speaker_code": "Mang"}).status_code, 422)
        permission = {"rights_holder": "Creator", "evidence_reference": "ref-1", "uses": ["asr_training", "asr_training"]}
        response = self.client.post(f"/api/v1/speech/sources/{uuid.uuid4()}/permissions", json=permission)
        self.assertEqual(response.status_code, 422)


@unittest.skipUnless(os.getenv("SIAMSIL_DATABASE_URL"), "application database is not configured")
class SpeechWorkflowTests(unittest.TestCase):
    """The whole PR 1 workflow against PostgreSQL, inside one transaction that is rolled back."""

    def setUp(self) -> None:
        engine = get_database_engine()
        if engine is None:
            self.skipTest("application database is not configured")
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.session = Session(bind=self.connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
        admins = [User(display_name=f"Admin {n}") for n in (1, 2)]
        self.session.add_all(admins)
        self.session.flush()
        self.admin, self.second_admin = (person("administrator", user_id=admin.id) for admin in admins)
        self.editor = person("editor")

        def session_for_request():
            yield self.session
            self.session.flush()

        app.dependency_overrides[get_speech_session] = session_for_request
        self.client = TestClient(app)
        self.as_user(self.admin)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.session.close()
        self.transaction.rollback()
        self.connection.close()

    def as_user(self, user: AuthenticatedUser) -> None:
        app.dependency_overrides[get_current_user] = lambda: user

    def eligibility(self, source_id: str) -> dict[str, dict]:
        self.as_user(self.editor)
        response = self.client.get(f"/api/v1/speech/sources/{source_id}/eligibility")
        self.as_user(self.admin)
        self.assertEqual(response.status_code, 200, response.text)
        return {item["use"]: item for item in response.json()["uses"]}

    def register(self, **overrides) -> dict:
        response = self.client.post("/api/v1/speech/sources", json={**SOURCE, **overrides})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_rights_and_consent_workflow(self) -> None:
        source = self.register(url="https://WWW.YOUTUBE.com/watch?v=test0001#t=5")
        self.assertEqual(source["url"], "https://www.youtube.com/watch?v=test0001")
        self.assertEqual(source["language"], "ctd")
        source_id = source["id"]

        # A registered public video is cleared for nothing.
        self.assertTrue(all(not item["allowed"] for item in self.eligibility(source_id).values()))

        response = self.client.post(
            f"/api/v1/speech/sources/{source_id}/permissions",
            json={
                "rights_holder": "The uploader",
                "evidence_reference": "siamsil-data/permissions/test0001 (private)",
                "uses": ["transcription", "asr_training", "tts_training"],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        permission = response.json()
        self.assertEqual(permission["status"], "pending")
        decision = f"/api/v1/speech/sources/{source_id}/permissions/{permission['id']}/decision"

        # The administrator who recorded the permission cannot verify it.
        self.assertEqual(self.client.post(decision, json={"decision": "verify"}).status_code, 403)
        self.as_user(self.second_admin)
        verified = self.client.post(decision, json={"decision": "verify", "note": "Email from the uploader checked"})
        self.assertEqual(verified.status_code, 200, verified.text)
        self.assertEqual(verified.json()["status"], "verified")
        self.assertEqual(self.client.post(decision, json={"decision": "verify"}).status_code, 409)
        self.as_user(self.admin)

        # Rights alone are not enough: no speaker has consented yet.
        self.assertFalse(self.eligibility(source_id)["asr_training"]["allowed"])

        self.assertEqual(self.client.post("/api/v1/speech/speakers", json={"speaker_code": "S0001"}).status_code, 200)
        self.assertEqual(self.client.post("/api/v1/speech/speakers", json={"speaker_code": "S0001"}).status_code, 409)
        consented = self.client.post("/api/v1/speech/speakers/S0001/consents", json=CONSENT)
        self.assertEqual(consented.status_code, 200, consented.text)
        linked = self.client.post(f"/api/v1/speech/sources/{source_id}/speakers/S0001")
        self.assertEqual(linked.json()["speaker_codes"], ["S0001"])

        uses = self.eligibility(source_id)
        self.assertTrue(uses["transcription"]["allowed"])
        self.assertTrue(uses["asr_training"]["allowed"])
        # The rights holder allowed synthesis, but the speaker did not: no voice cloning.
        self.assertEqual(uses["tts_training"]["reasons"], ["S0001 has not consented to tts_training (train_synthesis)"])
        # The speaker allowed playback, but the rights holder did not.
        self.assertFalse(uses["playback"]["allowed"])

        # Withdrawal is a new record that grants nothing; the earlier one stays as evidence.
        withdrawn = self.client.post(
            "/api/v1/speech/speakers/S0001/withdrawal",
            json={"withdrawn_on": "2026-10-26", "evidence_reference": "siamsil-data/consent/S0001-withdrawal"},
        )
        self.assertEqual(withdrawn.status_code, 200, withdrawn.text)
        self.assertTrue(withdrawn.json()["current_consent"]["withdrawn"])
        self.assertTrue(all(not item["allowed"] for item in self.eligibility(source_id).values()))
        self.assertEqual(self.session.scalar(select(func.count()).select_from(SpeakerConsent)), 2)
        self.assertEqual(
            self.client.post(
                "/api/v1/speech/speakers/S0001/withdrawal",
                json={"withdrawn_on": "2026-10-27", "evidence_reference": "again"},
            ).status_code,
            409,
        )

        # Every change is in the audit log.
        actions = set(self.session.scalars(select(AuditEvent.action).where(AuditEvent.action.like("speech.%"))))
        self.assertEqual(
            actions,
            {
                "speech.source_registered",
                "speech.permission_recorded",
                "speech.permission_verified",
                "speech.speaker_created",
                "speech.consent_recorded",
                "speech.speaker_linked",
                "speech.consent_withdrawn",
            },
        )

    def test_revoking_a_permission_ends_eligibility(self) -> None:
        source_id = self.register()["id"]
        self.client.post("/api/v1/speech/speakers", json={"speaker_code": "S0002"})
        self.client.post("/api/v1/speech/speakers/S0002/consents", json=CONSENT)
        self.client.post(f"/api/v1/speech/sources/{source_id}/speakers/S0002")
        permission = self.client.post(
            f"/api/v1/speech/sources/{source_id}/permissions",
            json={"rights_holder": "Creator", "evidence_reference": "ref-2", "uses": ["transcription"]},
        ).json()
        decision = f"/api/v1/speech/sources/{source_id}/permissions/{permission['id']}/decision"

        self.as_user(self.second_admin)
        self.assertEqual(self.client.post(decision, json={"decision": "revoke"}).status_code, 409)  # still pending
        self.assertEqual(self.client.post(decision, json={"decision": "verify"}).status_code, 200)
        self.assertTrue(self.eligibility(source_id)["transcription"]["allowed"])
        self.as_user(self.second_admin)
        self.assertEqual(self.client.post(decision, json={"decision": "revoke"}).status_code, 200)
        self.assertFalse(self.eligibility(source_id)["transcription"]["allowed"])
        self.as_user(self.second_admin)
        self.assertEqual(self.client.post(decision, json={"decision": "verify"}).status_code, 409)  # revoked is final

    def test_withdrawn_source_is_not_eligible_and_takes_no_new_permission(self) -> None:
        source_id = self.register()["id"]
        response = self.client.post(f"/api/v1/speech/sources/{source_id}/withdraw", json={"reason": "Creator asked"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "withdrawn")
        self.assertIn("the source has been withdrawn", self.eligibility(source_id)["transcription"]["reasons"])
        late = self.client.post(
            f"/api/v1/speech/sources/{source_id}/permissions",
            json={"rights_holder": "Creator", "evidence_reference": "ref-3", "uses": ["transcription"]},
        )
        self.assertEqual(late.status_code, 409)

    def test_duplicate_and_unsafe_links_are_refused(self) -> None:
        self.register()
        self.assertEqual(self.client.post("/api/v1/speech/sources", json=SOURCE).status_code, 409)
        insecure = {**SOURCE, "url": "http://www.youtube.com/watch?v=other"}
        self.assertEqual(self.client.post("/api/v1/speech/sources", json=insecure).status_code, 422)
        creator_file = self.client.post("/api/v1/speech/sources", json={"platform": "creator_file", "title": "Given file"})
        self.assertEqual(creator_file.status_code, 200, creator_file.text)
        self.assertIsNone(creator_file.json()["url"])

    def test_unknown_records_return_not_found(self) -> None:
        self.assertEqual(self.client.get(f"/api/v1/speech/sources/{uuid.uuid4()}").status_code, 404)
        self.assertEqual(self.client.post("/api/v1/speech/speakers/S0999/consents", json=CONSENT).status_code, 404)

    def test_the_database_enforces_append_only_consent_and_separate_deciders(self) -> None:
        self.client.post("/api/v1/speech/speakers", json={"speaker_code": "S0003"})
        self.client.post("/api/v1/speech/speakers/S0003/consents", json=CONSENT)
        for statement in (
            "UPDATE speaker_consents SET train_synthesis = true",
            "DELETE FROM speaker_consents",
            "TRUNCATE speaker_consents",
        ):
            with self.subTest(statement=statement):
                savepoint = self.connection.begin_nested()
                with self.assertRaisesRegex(DBAPIError, "append-only"):
                    self.connection.execute(text(statement))
                savepoint.rollback()

        source_id = self.register()["id"]
        self.client.post(
            f"/api/v1/speech/sources/{source_id}/permissions",
            json={"rights_holder": "Creator", "evidence_reference": "ref-4", "uses": ["transcription"]},
        )
        permission = self.session.scalar(select(SourcePermission).where(SourcePermission.source_id == uuid.UUID(source_id)))
        savepoint = self.connection.begin_nested()
        with self.assertRaises(IntegrityError):
            self.connection.execute(
                text(
                    "UPDATE speech_source_permissions SET status = 'verified', decided_by = recorded_by,"
                    " decided_at = now() WHERE id = :id"
                ),
                {"id": permission.id},
            )
        savepoint.rollback()

    def test_expired_permission_is_not_eligible(self) -> None:
        source_id = self.register()["id"]
        self.client.post("/api/v1/speech/speakers", json={"speaker_code": "S0004"})
        self.client.post("/api/v1/speech/speakers/S0004/consents", json=CONSENT)
        self.client.post(f"/api/v1/speech/sources/{source_id}/speakers/S0004")
        permission = self.client.post(
            f"/api/v1/speech/sources/{source_id}/permissions",
            json={
                "rights_holder": "Creator",
                "evidence_reference": "ref-5",
                "uses": ["transcription"],
                "valid_until": (date.today() - timedelta(days=1)).isoformat(),
            },
        ).json()
        self.as_user(self.second_admin)
        self.client.post(
            f"/api/v1/speech/sources/{source_id}/permissions/{permission['id']}/decision", json={"decision": "verify"}
        )
        self.assertFalse(self.eligibility(source_id)["transcription"]["allowed"])


if __name__ == "__main__":
    unittest.main()
