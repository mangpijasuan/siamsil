from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class RoleName(str, Enum):
    LEARNER = "learner"
    CONTRIBUTOR = "contributor"
    REVIEWER = "reviewer"
    EDITOR = "editor"
    MODERATOR = "moderator"
    ADMINISTRATOR = "administrator"


@dataclass(frozen=True)
class OIDCClaims:
    issuer: str
    subject: str
    expires_at: datetime
    token_id: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    locale: str = "en"


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: UUID
    issuer: str
    subject: str
    roles: frozenset[str]
    email: Optional[str] = None
    display_name: Optional[str] = None
    locale: str = "en"


class IdentityResponse(BaseModel):
    user_id: UUID
    email: Optional[str] = None
    display_name: Optional[str] = None
    locale: str
    roles: list[str]


class RoleAssignmentResponse(BaseModel):
    user_id: UUID
    roles: list[str]
