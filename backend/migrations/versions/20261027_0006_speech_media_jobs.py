"""Speech Data Lab media files and processing jobs (docs/SPEECH_DATA_LAB.md, PR 2).

Revision ID: 20261027_0006
Revises: 20261027_0005
Create Date: 2026-10-27
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261027_0006"
down_revision: str | None = "20261027_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('speech_media_assets',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('source_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('provenance', sa.String(length=32), nullable=True),
    sa.Column('derived_from_id', sa.UUID(), nullable=True),
    sa.Column('storage_key', sa.Text(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('media_type', sa.String(length=32), nullable=False),
    sa.Column('duration_seconds', sa.Float(), nullable=True),
    sa.Column('sample_rate', sa.Integer(), nullable=True),
    sa.Column('channels', sa.Integer(), nullable=True),
    sa.Column('codec', sa.String(length=32), nullable=True),
    sa.Column('status', sa.String(length=16), server_default='stored', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deletion_reason', sa.Text(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(kind = 'original') = (derived_from_id IS NULL)", name='ck_speech_media_assets_derivation'),
    sa.CheckConstraint("(kind = 'original') = (provenance IS NOT NULL)", name='ck_speech_media_assets_provenance_set'),
    sa.CheckConstraint("(status = 'deleted') = (deleted_at IS NOT NULL)", name='ck_speech_media_assets_deleted'),
    sa.CheckConstraint("kind IN ('original', 'normalized_wav')", name='ck_speech_media_assets_kind'),
    sa.CheckConstraint("media_type IN ('audio/wav', 'audio/mpeg', 'audio/mp4', 'video/mp4')", name='ck_speech_media_assets_type'),
    sa.CheckConstraint("provenance IS NULL OR provenance IN ('creator_provided', 'owner_platform_export')", name='ck_speech_media_assets_provenance'),
    sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name='ck_speech_media_assets_sha256'),
    sa.CheckConstraint("status IN ('stored', 'deleted')", name='ck_speech_media_assets_status'),
    sa.CheckConstraint('size_bytes > 0', name='ck_speech_media_assets_size'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['derived_from_id'], ['speech_media_assets.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['source_id'], ['speech_sources.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source_id', 'kind', 'sha256', name='uq_speech_media_assets_source_kind_sha256'),
    sa.UniqueConstraint('storage_key')
    )
    op.create_index(op.f('ix_speech_media_assets_source_id'), 'speech_media_assets', ['source_id'], unique=False)
    op.create_table('speech_processing_jobs',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
    sa.Column('asset_id', sa.UUID(), nullable=False),
    sa.Column('step', sa.String(length=32), nullable=False),
    sa.Column('processing_version', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='pending', nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('lease_owner', sa.String(length=128), nullable=True),
    sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('tool_versions', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('output_asset_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("(status = 'running') = (lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)", name='ck_speech_processing_jobs_lease'),
    sa.CheckConstraint("(status = 'succeeded') = (output_asset_id IS NOT NULL)", name='ck_speech_processing_jobs_output'),
    sa.CheckConstraint("status IN ('pending', 'running', 'succeeded', 'failed', 'blocked')", name='ck_speech_processing_jobs_status'),
    sa.CheckConstraint("step IN ('normalize_wav')", name='ck_speech_processing_jobs_step'),
    sa.CheckConstraint('attempts >= 0', name='ck_speech_processing_jobs_attempts'),
    sa.ForeignKeyConstraint(['asset_id'], ['speech_media_assets.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['output_asset_id'], ['speech_media_assets.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('asset_id', 'step', 'processing_version', name='uq_speech_processing_jobs_step')
    )
    op.create_index(op.f('ix_speech_processing_jobs_asset_id'), 'speech_processing_jobs', ['asset_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_speech_processing_jobs_asset_id'), table_name='speech_processing_jobs')
    op.drop_table('speech_processing_jobs')
    op.drop_index(op.f('ix_speech_media_assets_source_id'), table_name='speech_media_assets')
    op.drop_table('speech_media_assets')
