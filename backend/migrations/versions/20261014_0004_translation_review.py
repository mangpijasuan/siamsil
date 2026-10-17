"""Add bounded editorial translation review queue.

Revision ID: 20261014_0004
Revises: 20261014_0003
Create Date: 2026-10-14
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261014_0004"
down_revision: str | None = "20261014_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "translation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sentence_id", sa.Integer(), nullable=False),
        sa.Column("english_source", sa.Text(), nullable=False),
        sa.Column("source_reference", sa.String(500)),
        sa.Column("dataset_version", sa.String(100), nullable=False),
        sa.Column("quality_flags", sa.JSON(), nullable=False),
        sa.Column("license_status", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("claimed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'claimed', 'approved', 'edited', 'rejected', 'uncertain')", name="ck_translation_jobs_status"),
        sa.UniqueConstraint("dataset_version", "sentence_id", name="uq_translation_jobs_version_sentence"),
    )
    op.create_index("ix_translation_jobs_queue", "translation_jobs", ["status", "lease_expires_at"])
    op.create_table(
        "translation_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("translation_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("zomi_text", sa.Text(), nullable=False),
        sa.Column("model", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_translation_attempts_job_number"),
    )
    op.create_index("ix_translation_attempts_job_id", "translation_attempts", ["job_id"])
    op.create_table(
        "translation_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("translation_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("corrected_zomi", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("decision IN ('approve', 'edit', 'reject', 'uncertain')", name="ck_translation_reviews_decision"),
    )
    op.create_index("ix_translation_reviews_job_id", "translation_reviews", ["job_id"])
    op.create_index("ix_translation_reviews_reviewer_id", "translation_reviews", ["reviewer_id"])


def downgrade() -> None:
    op.drop_index("ix_translation_reviews_reviewer_id", table_name="translation_reviews")
    op.drop_index("ix_translation_reviews_job_id", table_name="translation_reviews")
    op.drop_table("translation_reviews")
    op.drop_index("ix_translation_attempts_job_id", table_name="translation_attempts")
    op.drop_table("translation_attempts")
    op.drop_index("ix_translation_jobs_queue", table_name="translation_jobs")
    op.drop_table("translation_jobs")
