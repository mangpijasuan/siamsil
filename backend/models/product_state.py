from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class SavedItem(Base):
    __tablename__ = "saved_items"
    __table_args__ = (
        CheckConstraint("item_type IN ('bible_verse', 'dictionary_entry', 'translation')", name="ck_saved_items_type"),
        UniqueConstraint("user_id", "item_type", "item_key", name="uq_saved_items_user_type_key"),
        Index("ix_saved_items_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)
    item_key: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LearningProgress(Base):
    __tablename__ = "learning_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_learning_progress_user_lesson"),
        CheckConstraint("percent >= 0 AND percent <= 100", name="ck_learning_progress_percent"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_id: Mapped[str] = mapped_column(String(160), nullable=False)
    percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
