"""Store corpus review decisions (SOP-07) imported from the offline workflow.

Revision ID: 20261025_0003
Revises: 20260926_0002
Create Date: 2026-10-25
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261025_0003"
down_revision: str | None = "20260926_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("records_in_file", sa.Integer(), nullable=False),
        sa.Column("records_added", sa.Integer(), nullable=False),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "corpus_review_records",
        sa.Column("position", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("record_id", sa.String(length=64), nullable=False),
        sa.Column("import_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("pair_hash", sa.String(length=40), nullable=False),
        sa.Column("actor_code", sa.String(length=8), nullable=False),
        sa.Column("decided_on", sa.Text(), nullable=False),
        sa.Column("batch", sa.Text(), nullable=True),
        sa.Column("meaning", sa.SmallInteger(), nullable=True),
        sa.Column("fluency", sa.SmallInteger(), nullable=True),
        sa.Column("decision", sa.String(length=16), nullable=True),
        sa.Column("record", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            # IS NOT NULL is spelled out: a NULL inside BETWEEN or IN would make the check pass.
            "(kind = 'review' AND meaning IS NOT NULL AND fluency IS NOT NULL"
            " AND meaning BETWEEN 0 AND 2 AND fluency BETWEEN 0 AND 2 AND decision IS NULL)"
            " OR (kind = 'approval' AND decision IS NOT NULL AND decision IN ('approve', 'reject')"
            " AND meaning IS NULL AND fluency IS NULL)",
            name="ck_corpus_review_records_kind_fields",
        ),
        sa.CheckConstraint("position >= 0", name="ck_corpus_review_records_position"),
        sa.ForeignKeyConstraint(["import_id"], ["review_imports.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("position"),
        sa.UniqueConstraint("record_id"),
    )
    op.create_index("ix_corpus_review_records_actor_code", "corpus_review_records", ["actor_code"])
    op.create_index("ix_corpus_review_records_import_id", "corpus_review_records", ["import_id"])
    op.create_index("ix_corpus_review_records_pair_hash", "corpus_review_records", ["pair_hash"])

    # Review decisions are an audit trail: refuse edits and deletes in the database itself.
    op.execute(
        """
        CREATE FUNCTION corpus_review_records_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'corpus_review_records is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER corpus_review_records_append_only
        BEFORE UPDATE OR DELETE ON corpus_review_records
        FOR EACH ROW EXECUTE FUNCTION corpus_review_records_append_only()
        """
    )
    # Row triggers do not see TRUNCATE, so refuse it with a statement trigger.
    op.execute(
        """
        CREATE TRIGGER corpus_review_records_no_truncate
        BEFORE TRUNCATE ON corpus_review_records
        FOR EACH STATEMENT EXECUTE FUNCTION corpus_review_records_append_only()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER corpus_review_records_no_truncate ON corpus_review_records")
    op.execute("DROP TRIGGER corpus_review_records_append_only ON corpus_review_records")
    op.execute("DROP FUNCTION corpus_review_records_append_only()")
    op.drop_index("ix_corpus_review_records_pair_hash", table_name="corpus_review_records")
    op.drop_index("ix_corpus_review_records_import_id", table_name="corpus_review_records")
    op.drop_index("ix_corpus_review_records_actor_code", table_name="corpus_review_records")
    op.drop_table("corpus_review_records")
    op.drop_table("review_imports")
