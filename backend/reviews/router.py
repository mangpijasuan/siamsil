"""Review Center MVP: role-gated metadata only, no private source-text delivery."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_session_factory
from identity.dependencies import require_roles
from identity.schemas import AuthenticatedUser
from models.review_center import ReviewCase, ReviewCenterAssignment
from reviews.center import assign_reviewer, create_case, finalize_admin, propose_editor, submit_review

router = APIRouter(prefix="/editorial/review-center", tags=["editorial-review-center"])


def session():
    factory = get_session_factory()
    if factory is None:
        raise HTTPException(status_code=503, detail="Review Center database is unavailable")
    with factory() as db:
        yield db


class NewCase(BaseModel):
    case_type: str = Field(pattern=r"^(spelling|sentence|term|bible_context)$")
    source_ref: str = Field(min_length=1, max_length=255)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    rights_status: str = Field(min_length=1, max_length=32)


class Assignment(BaseModel):
    reviewer_id: UUID
    revision: int = Field(ge=1)


class ReviewDecision(BaseModel):
    revision: int = Field(ge=1)
    decision: str = Field(pattern=r"^(accept|needs_changes|reject)$")
    reason: str = Field(min_length=5, max_length=4000)


class EditorProposal(BaseModel):
    revision: int = Field(ge=1)
    proposed_form: str = Field(min_length=1, max_length=4000)
    reason: str = Field(min_length=5, max_length=4000)


class AdminFinalization(BaseModel):
    revision: int = Field(ge=1)
    decision: str = Field(pattern=r"^(approve|return|reject)$")
    reason: str = Field(min_length=5, max_length=4000)


def snapshot(case: ReviewCase):
    return {
        "id": str(case.id), "case_type": case.case_type, "source_ref": case.source_ref,
        "rights_status": case.rights_status, "status": case.status,
        "revision": case.revision, "has_editor_proposal": bool(case.editor_id),
        "admin_finalized": case.status in ("admin_approved", "rejected"),
        "rewards_enabled": False, "release_enabled": False,
    }


@router.get("/cases", include_in_schema=False)
def list_cases(
    db: Session = Depends(session),
    actor: AuthenticatedUser = Depends(require_roles("reviewer", "editor", "administrator")),
):
    stmt = select(ReviewCase)
    if "administrator" not in actor.roles and "editor" not in actor.roles:
        stmt = stmt.join(ReviewCenterAssignment, ReviewCenterAssignment.case_id == ReviewCase.id).where(
            ReviewCenterAssignment.reviewer_id == actor.user_id,
            ReviewCenterAssignment.revision == ReviewCase.revision,
        )
    cases = db.scalars(stmt.order_by(ReviewCase.created_at.desc()).limit(100)).all()
    return {"cases": [snapshot(case) for case in cases]}


@router.post("/cases", include_in_schema=False)
def add_case(
    body: NewCase,
    db: Session = Depends(session),
    actor: AuthenticatedUser = Depends(require_roles("administrator")),
):
    return snapshot(create_case(db, actor, **body.model_dump()))


@router.post("/cases/{case_id}/assign", include_in_schema=False)
def assign_case(
    case_id: UUID, body: Assignment,
    db: Session = Depends(session),
    actor: AuthenticatedUser = Depends(require_roles("administrator")),
):
    return snapshot(assign_reviewer(db, actor, case_id=case_id, **body.model_dump()))


@router.post("/cases/{case_id}/reviews", include_in_schema=False)
def review_case(
    case_id: UUID, body: ReviewDecision,
    db: Session = Depends(session),
    actor: AuthenticatedUser = Depends(require_roles("reviewer")),
):
    return snapshot(submit_review(db, actor, case_id=case_id, **body.model_dump()))


@router.post("/cases/{case_id}/editor-proposal", include_in_schema=False)
def editor_case(
    case_id: UUID, body: EditorProposal,
    db: Session = Depends(session),
    actor: AuthenticatedUser = Depends(require_roles("editor")),
):
    return snapshot(propose_editor(db, actor, case_id=case_id, **body.model_dump()))


@router.post("/cases/{case_id}/admin-finalize", include_in_schema=False)
def admin_finalize(
    case_id: UUID, body: AdminFinalization,
    db: Session = Depends(session),
    actor: AuthenticatedUser = Depends(require_roles("administrator")),
):
    return snapshot(finalize_admin(db, actor, case_id=case_id, **body.model_dump()))
