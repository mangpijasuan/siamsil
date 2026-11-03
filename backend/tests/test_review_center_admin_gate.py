"""Fail-closed approval tests using synthetic metadata only."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app
from identity.schemas import AuthenticatedUser
from reviews import center


def actor(*roles):
    return AuthenticatedUser(user_id=uuid4(), issuer="https://example.invalid",
                             subject="tester", roles=frozenset(roles))


class AdminGateTests(unittest.TestCase):
    def test_anonymous_cannot_view_or_modify_review_center(self):
        client = TestClient(app)
        case = str(uuid4())
        endpoints = [
            ("get", "/api/v1/editorial/review-center/cases"),
            ("post", "/api/v1/editorial/review-center/cases"),
            ("post", f"/api/v1/editorial/review-center/cases/{case}/reviews"),
            ("post", f"/api/v1/editorial/review-center/cases/{case}/editor-proposal"),
            ("post", f"/api/v1/editorial/review-center/cases/{case}/admin-finalize"),
        ]
        for method, url in endpoints:
            with self.subTest(url=url):
                response = getattr(client, method)(url)
                self.assertEqual(response.status_code, 401)

    def test_admin_cannot_approve_own_editor_proposal(self):
        admin = actor("administrator", "editor")
        case = SimpleNamespace(id=uuid4(), revision=1, case_type="spelling",
                               editor_id=admin.user_id, status="admin_pending")
        db = MagicMock()
        db.scalars.return_value.all.return_value = [
            SimpleNamespace(reviewer_id=uuid4(), decision="accept"),
            SimpleNamespace(reviewer_id=uuid4(), decision="accept"),
        ]
        with patch("reviews.center.locked_case", return_value=case):
            with self.assertRaises(HTTPException) as error:
                center.finalize_admin(db, admin, case_id=case.id, revision=1,
                                      decision="approve", reason="Checked evidence")
        self.assertEqual(error.exception.status_code, 403)
        db.commit.assert_not_called()

    def test_spelling_requires_two_accepted_reviews(self):
        admin = actor("administrator")
        case = SimpleNamespace(id=uuid4(), revision=1, case_type="spelling",
                               editor_id=uuid4(), status="admin_pending")
        db = MagicMock()
        db.scalars.return_value.all.return_value = [
            SimpleNamespace(reviewer_id=uuid4(), decision="accept")
        ]
        with patch("reviews.center.locked_case", return_value=case):
            with self.assertRaises(HTTPException) as error:
                center.finalize_admin(db, admin, case_id=case.id, revision=1,
                                      decision="approve", reason="Checked evidence")
        self.assertEqual(error.exception.status_code, 409)
        db.commit.assert_not_called()

    def test_unassigned_reviewer_cannot_submit(self):
        reviewer = actor("reviewer")
        case = SimpleNamespace(id=uuid4(), revision=1, status="queued")
        db = MagicMock()
        db.scalar.return_value = None
        with patch("reviews.center.locked_case", return_value=case):
            with self.assertRaises(HTTPException) as error:
                center.submit_review(db, reviewer, case_id=case.id, revision=1,
                                     decision="accept", reason="Looks accurate")
        self.assertEqual(error.exception.status_code, 403)
        db.commit.assert_not_called()

    def test_stale_revision_rejected(self):
        db = MagicMock()
        db.scalar.return_value = SimpleNamespace(revision=3)
        with self.assertRaises(HTTPException) as error:
            center.locked_case(db, uuid4(), 2)
        self.assertEqual(error.exception.status_code, 409)

    def test_admin_approval_does_not_enable_payout_or_release(self):
        admin = actor("administrator")
        case = SimpleNamespace(id=uuid4(), revision=1, case_type="spelling",
                               editor_id=uuid4(), status="admin_pending",
                               finalized_by=None)
        db = MagicMock()
        db.scalars.return_value.all.return_value = [
            SimpleNamespace(reviewer_id=uuid4(), decision="accept"),
            SimpleNamespace(reviewer_id=uuid4(), decision="accept"),
        ]
        with patch("reviews.center.locked_case", return_value=case):
            center.finalize_admin(db, admin, case_id=case.id, revision=1,
                                  decision="approve", reason="Checked evidence")
        from reviews.router import snapshot
        self.assertEqual(case.status, "admin_approved")
        self.assertFalse(snapshot(case)["release_enabled"])
        self.assertFalse(snapshot(case)["rewards_enabled"])


if __name__ == "__main__":
    unittest.main()
