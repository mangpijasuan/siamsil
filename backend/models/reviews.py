from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ReviewImport(Base):
    """One import of the offline review decisions file (corpus-reviews.jsonl)."""

    __tablename__ = "review_imports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    records_in_file: Mapped[int] = mapped_column(Integer, nullable=False)
    records_added: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CorpusReviewRecord(Base):
    """A reviewer rating or lead-editor approval, kept exactly as recorded and never edited.

    `position` is the record's place in the decisions file. corpus_reviews.decide() reads
    records in that order, so it is part of each decision, not just a sort key.
    """

    __tablename__ = "corpus_review_records"
    __table_args__ = (
        CheckConstraint(
            "(kind = 'review' AND meaning BETWEEN 0 AND 2 AND fluency BETWEEN 0 AND 2 AND decision IS NULL)"
            " OR (kind = 'approval' AND decision IN ('approve', 'reject') AND meaning IS NULL AND fluency IS NULL)",
            name="ck_corpus_review_records_kind_fields",
        ),
        CheckConstraint("position >= 0", name="ck_corpus_review_records_position"),
    )

    position: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    record_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    import_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_imports.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    pair_hash: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    actor_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    decided_on: Mapped[str] = mapped_column(Text, nullable=False)
    batch: Mapped[Optional[str]] = mapped_column(Text)
    meaning: Mapped[Optional[int]] = mapped_column(SmallInteger)
    fluency: Mapped[Optional[int]] = mapped_column(SmallInteger)
    decision: Mapped[Optional[str]] = mapped_column(String(16))
    record: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
