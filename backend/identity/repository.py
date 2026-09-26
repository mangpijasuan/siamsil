from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from identity.schemas import AuthenticatedUser, OIDCClaims, RoleName
from models import AuditEvent, ExternalIdentity, User, UserRole, UserSession


def token_id_hash(issuer: str, token_id: str) -> str:
    return sha256(f"{issuer}\0{token_id}".encode("utf-8")).hexdigest()


class IdentityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def synchronize_identity(
        self,
        claims: OIDCClaims,
        *,
        request_id: str | None,
        bootstrap_admin_subjects: set[str],
    ) -> AuthenticatedUser:
        now = datetime.now(timezone.utc)
        external = self.session.scalar(
            select(ExternalIdentity).where(
                ExternalIdentity.issuer == claims.issuer,
                ExternalIdentity.subject == claims.subject,
            )
        )

        if external is None:
            user = User(
                display_name=claims.display_name,
                preferred_locale=claims.locale,
            )
            self.session.add(user)
            self.session.flush()
            external = ExternalIdentity(
                user_id=user.id,
                issuer=claims.issuer,
                subject=claims.subject,
                email=claims.email,
                last_login_at=now,
            )
            self.session.add(external)
            self.session.add(UserRole(user_id=user.id, role=RoleName.LEARNER.value))
            if claims.subject in bootstrap_admin_subjects:
                self.session.add(UserRole(user_id=user.id, role=RoleName.ADMINISTRATOR.value))
            self.session.add(
                AuditEvent(
                    actor_user_id=user.id,
                    action="identity.user_provisioned",
                    target_type="user",
                    target_id=str(user.id),
                    request_id=request_id,
                    event_data={"issuer": claims.issuer},
                )
            )
        else:
            user = self.session.get(User, external.user_id)
            if user is None:
                raise RuntimeError("external identity references a missing user")
            external.email = claims.email
            external.last_login_at = now

        if user.status != "active":
            raise PermissionError("user account is not active")

        if claims.token_id:
            digest = token_id_hash(claims.issuer, claims.token_id)
            tracked = self.session.scalar(select(UserSession).where(UserSession.token_id_hash == digest))
            if tracked is None:
                self.session.add(
                    UserSession(
                        user_id=user.id,
                        token_id_hash=digest,
                        expires_at=claims.expires_at,
                        last_seen_at=now,
                    )
                )
            else:
                if tracked.user_id != user.id:
                    raise PermissionError("token session belongs to a different user")
                if tracked.status == "revoked":
                    raise PermissionError("token session has been revoked")
                tracked.last_seen_at = now
                tracked.expires_at = claims.expires_at
                tracked.status = "active"

        self.session.flush()
        roles = frozenset(
            self.session.scalars(select(UserRole.role).where(UserRole.user_id == user.id)).all()
        )
        return AuthenticatedUser(
            user_id=user.id,
            issuer=claims.issuer,
            subject=claims.subject,
            email=external.email,
            display_name=user.display_name,
            locale=user.preferred_locale,
            roles=roles,
        )

    def grant_role(
        self,
        *,
        actor: AuthenticatedUser,
        target_user_id: UUID,
        role: RoleName,
        request_id: str | None,
    ) -> frozenset[str]:
        target = self.session.get(User, target_user_id)
        if target is None:
            raise LookupError("user not found")

        existing = self.session.get(UserRole, (target_user_id, role.value))
        if existing is None:
            self.session.add(
                UserRole(user_id=target_user_id, role=role.value, granted_by=actor.user_id)
            )
            self.session.add(
                AuditEvent(
                    actor_user_id=actor.user_id,
                    action="identity.role_granted",
                    target_type="user",
                    target_id=str(target_user_id),
                    request_id=request_id,
                    event_data={"role": role.value},
                )
            )
            self.session.flush()

        return frozenset(
            self.session.scalars(select(UserRole.role).where(UserRole.user_id == target_user_id)).all()
        )
