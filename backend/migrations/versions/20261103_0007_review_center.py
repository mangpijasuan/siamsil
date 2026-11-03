"""Review Center admin finalization foundation.

Revision ID: 20261103_0007
Revises: 20261027_0006
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261103_0007"
down_revision = "20261027_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "review_center_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_type", sa.String(24), nullable=False),
        sa.Column("source_ref", sa.String(255), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("rights_status", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("editor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("proposed_form", sa.Text()),
        sa.Column("editor_reason", sa.Text()),
        sa.Column("finalized_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued','reviewing','editor_pending','admin_pending','admin_approved','returned','rejected')",
            name="ck_review_center_cases_status",
        ),
        sa.CheckConstraint("case_type IN ('spelling','sentence','term','bible_context')",
                           name="ck_review_center_cases_type"),
        sa.CheckConstraint("revision >= 1", name="ck_review_center_cases_revision"),
    )
    op.create_index("ix_review_center_cases_status", "review_center_cases", ["status"])
    op.create_table(
        "review_center_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("review_center_cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("decision IN ('accept','needs_changes','reject')",
                           name="ck_review_center_submissions_decision"),
        sa.UniqueConstraint("case_id", "revision", "reviewer_id", name="uq_review_center_reviewer_once"),
    )
    op.create_index("ix_review_center_submissions_case_id", "review_center_submissions", ["case_id"])
    op.create_table(
        "review_center_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("review_center_cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("case_id", "revision", "reviewer_id", name="uq_review_center_assignment"),
    )
    op.create_index("ix_review_center_assignments_case_id", "review_center_assignments", ["case_id"])
    op.create_table(
        "review_center_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("review_center_cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_review_center_events_case_id", "review_center_events", ["case_id"])


def downgrade():
    op.drop_index("ix_review_center_assignments_case_id", table_name="review_center_assignments")
    op.drop_table("review_center_assignments")
    op.drop_index("ix_review_center_events_case_id", table_name="review_center_events")
    op.drop_table("review_center_events")
    op.drop_index("ix_review_center_submissions_case_id", table_name="review_center_submissions")
    op.drop_table("review_center_submissions")
    op.drop_index("ix_review_center_cases_status", table_name="review_center_cases")
    op.drop_table("review_center_cases")
