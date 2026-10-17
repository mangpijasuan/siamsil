"""Add account-owned saved items and learning progress.

Revision ID: 20261014_0003
Revises: 20260926_0002
Create Date: 2026-10-14
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261014_0003"
down_revision: str | None = "20260926_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_type", sa.String(32), nullable=False),
        sa.Column("item_key", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("item_type IN ('bible_verse', 'dictionary_entry', 'translation')", name="ck_saved_items_type"),
        sa.UniqueConstraint("user_id", "item_type", "item_key", name="uq_saved_items_user_type_key"),
    )
    op.create_index("ix_saved_items_user_created", "saved_items", ["user_id", "created_at"])
    op.create_table(
        "learning_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", sa.String(160), nullable=False),
        sa.Column("percent", sa.Integer(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("percent >= 0 AND percent <= 100", name="ck_learning_progress_percent"),
        sa.UniqueConstraint("user_id", "lesson_id", name="uq_learning_progress_user_lesson"),
    )
    op.create_index("ix_learning_progress_user_id", "learning_progress", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_learning_progress_user_id", table_name="learning_progress")
    op.drop_table("learning_progress")
    op.drop_index("ix_saved_items_user_created", table_name="saved_items")
    op.drop_table("saved_items")
