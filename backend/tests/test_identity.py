from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

try:
    import jwt as pyjwt
    from cryptography.hazmat.primitives.asymmetric import rsa
except ModuleNotFoundError:
    pyjwt = None
    rsa = None

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from database import get_database_engine  # type: ignore  # noqa: E402
from identity.dependencies import get_current_user, require_roles  # type: ignore  # noqa: E402
from identity.repository import IdentityRepository, token_id_hash  # type: ignore  # noqa: E402
from identity.schemas import AuthenticatedUser, OIDCClaims, RoleName  # type: ignore  # noqa: E402
from identity.security import OIDCVerifier  # type: ignore  # noqa: E402
from main import app  # type: ignore  # noqa: E402
from models import AuditEvent, UserSession  # type: ignore  # noqa: E402
from settings import Settings  # type: ignore  # noqa: E402


class IdentityConfigurationTests(unittest.TestCase):
    def test_enabled_oidc_requires_provider_settings(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(
                oidc_enabled=True,
                oidc_issuer=None,
                oidc_audience=None,
                oidc_jwks_url=None,
                _env_file=None,
            )

    def test_token_identifier_is_hashed_with_issuer(self) -> None:
        digest = token_id_hash("https://issuer.example", "sensitive-token-id")

        self.assertEqual(len(digest), 64)
        self.assertNotIn("sensitive-token-id", digest)
        self.assertNotEqual(
            digest,
            token_id_hash("https://different-issuer.example", "sensitive-token-id"),
        )

    def test_production_oidc_requires_https(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(
                environment="production",
                database_url="postgresql+psycopg://user:password@database/siamsil",
                oidc_enabled=True,
                oidc_issuer="http://identity.example",
                oidc_audience="https://api.siamsil.com",
                oidc_jwks_url="http://identity.example/jwks.json",
                _env_file=None,
            )


@unittest.skipUnless(pyjwt is not None and rsa is not None, "PyJWT crypto dependencies are not installed")
class OIDCTokenVerificationTests(unittest.TestCase):
    def test_verifier_checks_signature_issuer_audience_and_claims(self) -> None:
        settings = Settings(
            oidc_enabled=True,
            oidc_issuer="https://issuer.example",
            oidc_audience="https://api.siamsil.test",
            oidc_jwks_url="https://issuer.example/.well-known/jwks.json",
            _env_file=None,
        )
        verifier = OIDCVerifier(settings)
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        signing_key = MagicMock()
        signing_key.key = private_key.public_key()
        verifier._jwk_client = MagicMock()
        verifier._jwk_client.get_signing_key_from_jwt.return_value = signing_key
        now = datetime.now(timezone.utc)
        token = pyjwt.encode(
            {
                "iss": settings.oidc_issuer,
                "sub": "person-1",
                "aud": settings.oidc_audience,
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=5)).timestamp()),
                "jti": "token-1",
                "email": "verified@example.com",
                "email_verified": True,
                "locale": "zom",
            },
            private_key,
            algorithm="RS256",
        )

        claims = verifier.verify(token)

        self.assertEqual(claims.subject, "person-1")
        self.assertEqual(claims.email, "verified@example.com")
        self.assertEqual(claims.locale, "zom")


class AuthorizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_identity_endpoint_requires_bearer_token(self) -> None:
        response = self.client.get("/api/v1/identity/me")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "http_401")
        self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")

    def test_identity_endpoint_reports_disabled_provider(self) -> None:
        response = self.client.get(
            "/api/v1/identity/me",
            headers={"Authorization": "Bearer placeholder"},
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "http_503")

    def test_identity_endpoint_returns_internal_roles(self) -> None:
        user = AuthenticatedUser(
            user_id=uuid4(),
            issuer="https://issuer.example",
            subject="person-1",
            roles=frozenset({"learner", "reviewer"}),
            email="learner@example.com",
            display_name="Zomi Learner",
            locale="zom",
        )
        app.dependency_overrides[get_current_user] = lambda: user

        response = self.client.get("/api/v1/identity/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["roles"], ["learner", "reviewer"])
        self.assertNotIn("subject", response.json())

    def test_role_requirement_rejects_non_admin(self) -> None:
        dependency = require_roles(RoleName.ADMINISTRATOR.value)
        user = AuthenticatedUser(
            user_id=uuid4(),
            issuer="https://issuer.example",
            subject="person-1",
            roles=frozenset({"learner"}),
        )

        with self.assertRaises(HTTPException) as raised:
            dependency(user)

        self.assertEqual(raised.exception.status_code, 403)


@unittest.skipUnless(os.getenv("SIAMSIL_DATABASE_URL"), "application database is not configured")
class IdentityRepositoryIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = get_database_engine()
        if engine is None:
            self.skipTest("application database is not configured")
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.session = Session(bind=self.connection, expire_on_commit=False)

    def tearDown(self) -> None:
        self.session.close()
        self.transaction.rollback()
        self.connection.close()

    def test_provision_session_role_and_audit_are_atomic(self) -> None:
        claims = OIDCClaims(
            issuer="https://issuer.example",
            subject=f"integration-{uuid4()}",
            email="reviewer@example.com",
            display_name="Integration Reviewer",
            locale="zom",
            token_id=f"token-{uuid4()}",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        repository = IdentityRepository(self.session)

        user = repository.synchronize_identity(
            claims,
            request_id="identity-integration-test",
            bootstrap_admin_subjects={claims.subject},
        )
        roles = repository.grant_role(
            actor=user,
            target_user_id=user.user_id,
            role=RoleName.REVIEWER,
            request_id="identity-role-test",
        )

        self.assertEqual(user.roles, frozenset({"learner", "administrator"}))
        self.assertEqual(roles, frozenset({"learner", "administrator", "reviewer"}))
        tracked_session = self.session.scalar(
            select(UserSession).where(UserSession.user_id == user.user_id)
        )
        self.assertIsNotNone(tracked_session)
        self.assertNotEqual(tracked_session.token_id_hash, claims.token_id)
        actions = set(
            self.session.scalars(
                select(AuditEvent.action).where(AuditEvent.target_id == str(user.user_id))
            ).all()
        )
        self.assertEqual(actions, {"identity.user_provisioned", "identity.role_granted"})


if __name__ == "__main__":
    unittest.main()
