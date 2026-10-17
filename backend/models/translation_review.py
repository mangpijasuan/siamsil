from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class TranslationJob(Base):
    __tablename__ = "translation_jobs"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'claimed', 'approved', 'edited', 'rejected', 'uncertain')", name="ck_translation_jobs_status"),
        UniqueConstraint("dataset_version", "sentence_id", name="uq_translation_jobs_version_sentence"),
        Index("ix_translation_jobs_queue", "status", "lease_expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sentence_id: Mapped[int] = mapped_column(Integer, nullable=False)
    english_source: Mapped[str] = mapped_column(Text, nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(500))
    dataset_version: Mapped[str] = mapped_column(String(100), nullable=False)
    quality_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    license_status: Mapped[str] = mapped_column(String(32), nullable=False, default="needs_review")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    claimed_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TranslationAttempt(Base):
    __tablename__ = "translation_attempts"
    __table_args__ = (UniqueConstraint("job_id", "attempt_number", name="uq_translation_attempts_job_number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("translation_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    zomi_text: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TranslationReview(Base):
    __tablename__ = "translation_reviews"
    __table_args__ = (CheckConstraint("decision IN ('approve', 'edit', 'reject', 'uncertain')", name="ck_translation_reviews_decision"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("translation_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    corrected_zomi: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
