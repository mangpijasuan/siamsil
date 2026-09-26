from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from identity.dependencies import get_current_user, require_roles
from identity.schemas import (
    AuthenticatedUser,
    IdentityResponse,
    RoleAssignmentResponse,
    RoleName,
)
from identity.service import IdentityDatabaseUnavailableError, IdentityService, get_identity_service


router = APIRouter(prefix="/identity", tags=["identity"])


@router.get("/me", response_model=IdentityResponse)
def current_identity(user: AuthenticatedUser = Depends(get_current_user)) -> IdentityResponse:
    return IdentityResponse(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        locale=user.locale,
        roles=sorted(user.roles),
    )


@router.post("/users/{user_id}/roles/{role}", response_model=RoleAssignmentResponse)
def assign_role(
    user_id: UUID,
    role: RoleName,
    request: Request,
    actor: AuthenticatedUser = Depends(require_roles(RoleName.ADMINISTRATOR.value)),
    service: IdentityService = Depends(get_identity_service),
) -> RoleAssignmentResponse:
    try:
        roles = service.grant_role(
            actor=actor,
            target_user_id=user_id,
            role=role,
            request_id=getattr(request.state, "request_id", None),
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.") from exc
    except IdentityDatabaseUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Identity database is unavailable.",
        ) from exc
    return RoleAssignmentResponse(user_id=user_id, roles=sorted(roles))
