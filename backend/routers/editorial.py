from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from identity.dependencies import require_roles
from identity.schemas import AuthenticatedUser
from models.identity import AuditEvent
from models.translation_review import TranslationAttempt, TranslationJob, TranslationReview
from routers.product_state import get_product_session


router = APIRouter(prefix="/editorial/translation-jobs", tags=["editorial"])
reviewer = require_roles("reviewer", "editor", "administrator")


class ReviewJobResponse(BaseModel):
    id: UUID
    sentence_id: int
    english_source: str
    zomi_candidate: str
    source_reference: str | None
    dataset_version: str
    quality_flags: list[str]
    license_status: str
    status: str
    claimed_by: UUID | None
    lease_expires_at: datetime | None


class ReviewJobsResponse(BaseModel):
    count: int
    jobs: list[ReviewJobResponse]


class ReviewDecisionRequest(BaseModel):
    decision: Literal["approve", "edit", "reject", "uncertain"]
    corrected_zomi: str | None = Field(default=None, max_length=5000)
    notes: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="after")
    def validate_edit(self) -> "ReviewDecisionRequest":
        if self.decision == "edit" and not (self.corrected_zomi or "").strip():
            raise ValueError("An edited decision requires corrected Zomi text")
        if self.decision != "edit" and self.corrected_zomi is not None:
            raise ValueError("Only edited decisions may include corrected Zomi text")
        return self


class ReviewDecisionResponse(BaseModel):
    job_id: UUID
    status: str
    review_id: UUID
    publication_status: str = "unpublished"


def job_response(session: Session, job: TranslationJob) -> ReviewJobResponse:
    attempt = session.scalar(select(TranslationAttempt).where(TranslationAttempt.job_id == job.id)
                             .order_by(TranslationAttempt.attempt_number.desc()).limit(1))
    return ReviewJobResponse(
        id=job.id, sentence_id=job.sentence_id, english_source=job.english_source,
        zomi_candidate=attempt.zomi_text if attempt else "", source_reference=job.source_reference,
        dataset_version=job.dataset_version, quality_flags=job.quality_flags,
        license_status=job.license_status, status=job.status, claimed_by=job.claimed_by,
        lease_expires_at=job.lease_expires_at,
    )


@router.get("", response_model=ReviewJobsResponse)
def list_jobs(
    job_status: Literal["pending", "claimed", "approved", "edited", "rejected", "uncertain"] = Query("pending", alias="status"),
    limit: int = Query(100, ge=1, le=100),
    user: AuthenticatedUser = Depends(reviewer),
    session: Session = Depends(get_product_session),
) -> ReviewJobsResponse:
    _ = user
    try:
        rows = session.scalars(select(TranslationJob).where(TranslationJob.status == job_status)
                               .order_by(TranslationJob.created_at, TranslationJob.id).limit(limit)).all()
        return ReviewJobsResponse(count=len(rows), jobs=[job_response(session, row) for row in rows])
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Editorial storage is unavailable.") from exc


@router.post("/{job_id}/claim", response_model=ReviewJobResponse)
def claim_job(
    job_id: UUID,
    user: AuthenticatedUser = Depends(reviewer),
    session: Session = Depends(get_product_session),
) -> ReviewJobResponse:
    now = datetime.now(timezone.utc)
    try:
        claimed_id = session.scalar(
            update(TranslationJob).where(
                TranslationJob.id == job_id,
                or_(TranslationJob.status == "pending",
                    and_(TranslationJob.status == "claimed", TranslationJob.lease_expires_at < now)),
            ).values(status="claimed", claimed_by=user.user_id,
                     lease_expires_at=now + timedelta(minutes=20), updated_at=now)
            .returning(TranslationJob.id)
        )
        if claimed_id is None:
            session.rollback()
            raise HTTPException(status_code=409, detail="Job is unavailable or already claimed.")
        session.commit()
        job = session.get(TranslationJob, job_id)
        return job_response(session, job)
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(status_code=503, detail="Editorial storage is unavailable.") from exc


@router.post("/{job_id}/decision", response_model=ReviewDecisionResponse)
def decide_job(
    job_id: UUID,
    decision: ReviewDecisionRequest,
    request: Request,
    user: AuthenticatedUser = Depends(reviewer),
    session: Session = Depends(get_product_session),
) -> ReviewDecisionResponse:
    now = datetime.now(timezone.utc)
    try:
        job = session.scalar(select(TranslationJob).where(TranslationJob.id == job_id).with_for_update())
        if job is None:
            raise HTTPException(status_code=404, detail="Review job not found.")
        lease_expiry = job.lease_expires_at
        if lease_expiry is not None and lease_expiry.tzinfo is None:
            lease_expiry = lease_expiry.replace(tzinfo=timezone.utc)
        if job.status != "claimed" or job.claimed_by != user.user_id or not lease_expiry or lease_expiry <= now:
            raise HTTPException(status_code=409, detail="Claim this job before submitting a decision.")
        review = TranslationReview(
            job_id=job.id, reviewer_id=user.user_id, decision=decision.decision,
            corrected_zomi=decision.corrected_zomi.strip() if decision.corrected_zomi else None,
            notes=decision.notes,
        )
        session.add(review)
        job.status = {"approve": "approved", "edit": "edited", "reject": "rejected", "uncertain": "uncertain"}[decision.decision]
        job.claimed_by = None
        job.lease_expires_at = None
        session.add(AuditEvent(
            actor_user_id=user.user_id, action="translation_review.decision",
            target_type="translation_job", target_id=str(job.id),
            request_id=getattr(request.state, "request_id", None),
            event_data={"decision": decision.decision, "sentence_id": job.sentence_id},
        ))
        session.commit()
        return ReviewDecisionResponse(job_id=job.id, status=job.status, review_id=review.id)
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(status_code=503, detail="Editorial storage is unavailable.") from exc
