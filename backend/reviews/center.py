"""Protected Review Center service. All state changes are transaction-bound and audited."""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from identity.schemas import AuthenticatedUser
from models.review_center import ReviewCase, ReviewCenterEvent, ReviewCenterSubmission, ReviewCenterAssignment
from models.identity import UserRole

REVIEWER = "reviewer"
EDITOR = "editor"
ADMIN = "administrator"


def locked_case(db: Session, case_id: UUID, expected_revision: int) -> ReviewCase:
    case = db.scalar(select(ReviewCase).where(ReviewCase.id == case_id).with_for_update())
    if case is None:
        raise HTTPException(status_code=404, detail="Review case not found")
    if case.revision != expected_revision:
        raise HTTPException(status_code=409, detail="Review case has changed; refresh before acting")
    return case


def record_event(db: Session, case: ReviewCase, actor: AuthenticatedUser, action: str, details: dict) -> None:
    db.add(ReviewCenterEvent(
        case_id=case.id, revision=case.revision,
        actor_id=actor.user_id, action=action, details=details,
    ))


def create_case(db: Session, actor: AuthenticatedUser, *, case_type: str,
                source_ref: str, source_sha256: str, rights_status: str) -> ReviewCase:
    if ADMIN not in actor.roles:
        raise HTTPException(status_code=403, detail="Administrator role required")
    case = ReviewCase(case_type=case_type, source_ref=source_ref, source_sha256=source_sha256,
                      rights_status=rights_status, status="queued", revision=1)
    db.add(case)
    db.flush()
    record_event(db, case, actor, "created", {"case_type": case_type})
    db.commit()
    db.refresh(case)
    return case


def assign_reviewer(db: Session, actor: AuthenticatedUser, *, case_id: UUID,
                    revision: int, reviewer_id: UUID) -> ReviewCase:
    if ADMIN not in actor.roles:
        raise HTTPException(status_code=403, detail="Administrator role required")
    case = locked_case(db, case_id, revision)
    if case.status not in ("queued", "reviewing"):
        raise HTTPException(status_code=409, detail="Reviewer assignments are closed")
    is_reviewer = db.scalar(select(UserRole).where(
        UserRole.user_id == reviewer_id, UserRole.role == REVIEWER
    ))
    if is_reviewer is None:
        raise HTTPException(status_code=422, detail="Assignee must have reviewer role")
    existing = db.scalar(select(ReviewCenterAssignment.id).where(
        ReviewCenterAssignment.case_id == case.id,
        ReviewCenterAssignment.revision == case.revision,
        ReviewCenterAssignment.reviewer_id == reviewer_id
    ))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Already assigned")
    db.add(ReviewCenterAssignment(
        case_id=case.id, revision=case.revision,
        reviewer_id=reviewer_id, assigned_by=actor.user_id,
    ))
    record_event(db, case, actor, "reviewer_assigned", {"reviewer_id": str(reviewer_id)})
    db.commit()
    return case


def submit_review(db: Session, actor: AuthenticatedUser, *, case_id: UUID, revision: int,
                  decision: str, reason: str) -> ReviewCase:
    if REVIEWER not in actor.roles:
        raise HTTPException(status_code=403, detail="Reviewer role required")
    case = locked_case(db, case_id, revision)
    if case.status not in ("queued", "reviewing"):
        raise HTTPException(status_code=409, detail="This case is not accepting reviewer decisions")
    assigned = db.scalar(select(ReviewCenterAssignment.id).where(
        ReviewCenterAssignment.case_id == case.id,
        ReviewCenterAssignment.revision == case.revision,
        ReviewCenterAssignment.reviewer_id == actor.user_id,
    ))
    if assigned is None:
        raise HTTPException(status_code=403, detail="Reviewer is not assigned to this case")
    already = db.scalar(select(ReviewCenterSubmission.id).where(
        ReviewCenterSubmission.case_id == case.id,
        ReviewCenterSubmission.revision == case.revision,
        ReviewCenterSubmission.reviewer_id == actor.user_id,
    ))
    if already:
        raise HTTPException(status_code=409, detail="Reviewer has already submitted on this revision")
    db.add(ReviewCenterSubmission(case_id=case.id, revision=case.revision,
                                  reviewer_id=actor.user_id, decision=decision, reason=reason))
    case.status = "reviewing"
    record_event(db, case, actor, "review_submitted", {"decision": decision})
    db.commit()
    return case


def propose_editor(db: Session, actor: AuthenticatedUser, *, case_id: UUID, revision: int,
                   proposed_form: str, reason: str) -> ReviewCase:
    if EDITOR not in actor.roles:
        raise HTTPException(status_code=403, detail="Editor role required")
    case = locked_case(db, case_id, revision)
    if case.status not in ("reviewing", "returned"):
        raise HTTPException(status_code=409, detail="Case not ready for editor proposal")
    reviews = db.scalars(select(ReviewCenterSubmission).where(
        ReviewCenterSubmission.case_id == case.id,
        ReviewCenterSubmission.revision == case.revision,
    )).all()
    minimum = 2 if case.case_type == "spelling" else 1
    accepted = {entry.reviewer_id for entry in reviews if entry.decision == "accept"}
    if len(accepted) < minimum:
        raise HTTPException(status_code=409, detail="Required independent accepting reviews are missing")
    if actor.user_id in {entry.reviewer_id for entry in reviews}:
        raise HTTPException(status_code=403, detail="Editor must be independent of this case's reviewers")
    case.editor_id = actor.user_id
    case.proposed_form = proposed_form
    case.editor_reason = reason
    case.finalized_by = None
    case.status = "admin_pending"
    record_event(db, case, actor, "editor_proposed", {"review_count": len(accepted)})
    db.commit()
    return case


def finalize_admin(db: Session, actor: AuthenticatedUser, *, case_id: UUID,
                   revision: int, decision: str, reason: str) -> ReviewCase:
    if ADMIN not in actor.roles:
        raise HTTPException(status_code=403, detail="Administrator role required")
    case = locked_case(db, case_id, revision)
    if case.status != "admin_pending":
        raise HTTPException(status_code=409, detail="Case is not pending admin finalization")
    reviews = db.scalars(select(ReviewCenterSubmission).where(
        ReviewCenterSubmission.case_id == case.id,
        ReviewCenterSubmission.revision == case.revision,
    )).all()
    if actor.user_id == case.editor_id or any(entry.reviewer_id == actor.user_id for entry in reviews):
        raise HTTPException(status_code=403, detail="Administrator must be independent of reviewers and editor")
    minimum = 2 if case.case_type == "spelling" else 1
    if len({entry.reviewer_id for entry in reviews if entry.decision == "accept"}) < minimum:
        raise HTTPException(status_code=409, detail="Required reviewer approvals are missing")
    if decision == "approve":
        case.status = "admin_approved"
        case.finalized_by = actor.user_id
    elif decision == "return":
        case.status = "returned"
        case.finalized_by = None
    else:
        case.status = "rejected"
        case.finalized_by = actor.user_id
    record_event(db, case, actor, "admin_" + decision, {"reason": reason})
    db.commit()
    return case
