from __future__ import annotations

from functools import lru_cache
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from identity.repository import IdentityRepository
from identity.schemas import AuthenticatedUser, OIDCClaims, RoleName
from database import get_session_factory
from settings import Settings, get_settings


class IdentityDatabaseUnavailableError(Exception):
    pass


class IdentityService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def synchronize(self, claims: OIDCClaims, *, request_id: str | None) -> AuthenticatedUser:
        factory = get_session_factory()
        if factory is None:
            raise IdentityDatabaseUnavailableError("application database is not configured")
        try:
            with factory.begin() as session:
                return IdentityRepository(session).synchronize_identity(
                    claims,
                    request_id=request_id,
                    bootstrap_admin_subjects=set(self.settings.bootstrap_admin_subjects),
                )
        except SQLAlchemyError as exc:
            raise IdentityDatabaseUnavailableError("identity database operation failed") from exc

    def grant_role(
        self,
        *,
        actor: AuthenticatedUser,
        target_user_id: UUID,
        role: RoleName,
        request_id: str | None,
    ) -> frozenset[str]:
        factory = get_session_factory()
        if factory is None:
            raise IdentityDatabaseUnavailableError("application database is not configured")
        try:
            with factory.begin() as session:
                return IdentityRepository(session).grant_role(
                    actor=actor,
                    target_user_id=target_user_id,
                    role=role,
                    request_id=request_id,
                )
        except SQLAlchemyError as exc:
            raise IdentityDatabaseUnavailableError("identity database operation failed") from exc


@lru_cache(maxsize=1)
def get_identity_service() -> IdentityService:
    return IdentityService(get_settings())
