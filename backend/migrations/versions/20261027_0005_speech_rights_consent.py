"""Speech Data Lab rights and consent records (docs/SPEECH_DATA_LAB.md, PR 1).

Revision ID: 20261027_0005
Revises: 20261027_0004
Create Date: 2026-10-27
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261027_0005"
down_revision: str | None = "20261027_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('speakers',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('speaker_code', sa.String(length=8), nullable=False),
    sa.Column('dialect_region', sa.Text(), nullable=True),
    sa.Column('age_range', sa.String(length=16), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("speaker_code ~ '^S[0-9]{4,6}$'", name='ck_speakers_code'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('speaker_code')
    )
    op.create_table('speech_sources',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('platform', sa.String(length=16), nullable=False),
    sa.Column('url', sa.Text(), nullable=True),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('uploader', sa.Text(), nullable=True),
    sa.Column('language', sa.String(length=8), server_default='ctd', nullable=False),
    sa.Column('dialect', sa.Text(), nullable=True),
    sa.Column('duration_seconds', sa.Integer(), nullable=True),
    sa.Column('acquired_on', sa.Date(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=16), server_default='registered', nullable=False),
    sa.Column('withdrawn_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('registered_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(platform = 'creator_file') = (url IS NULL)", name='ck_speech_sources_url'),
    sa.CheckConstraint("(status = 'withdrawn') = (withdrawn_at IS NOT NULL)", name='ck_speech_sources_withdrawn'),
    sa.CheckConstraint("language = 'ctd'", name='ck_speech_sources_language'),
    sa.CheckConstraint("platform IN ('youtube', 'facebook', 'other', 'creator_file')", name='ck_speech_sources_platform'),
    sa.CheckConstraint("status IN ('registered', 'withdrawn')", name='ck_speech_sources_status'),
    sa.CheckConstraint('duration_seconds IS NULL OR duration_seconds >= 0', name='ck_speech_sources_duration'),
    sa.ForeignKeyConstraint(['registered_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('url')
    )
    op.create_table('speaker_consents',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
    sa.Column('speaker_id', sa.UUID(), nullable=False),
    sa.Column('form_version', sa.String(length=32), nullable=False),
    sa.Column('form_language', sa.String(length=32), nullable=False),
    sa.Column('consent_method', sa.String(length=16), nullable=False),
    sa.Column('consent_date', sa.Date(), nullable=False),
    sa.Column('collector_code', sa.String(length=8), nullable=False),
    sa.Column('adult_confirmed', sa.Boolean(), nullable=False),
    sa.Column('keep_and_evaluate', sa.Boolean(), nullable=False),
    sa.Column('train_recognition', sa.Boolean(), nullable=False),
    sa.Column('train_synthesis', sa.Boolean(), nullable=False),
    sa.Column('play_in_app', sa.Boolean(), nullable=False),
    sa.Column('public_dataset', sa.Boolean(), nullable=False),
    sa.Column('commercial_use', sa.Boolean(), nullable=False),
    sa.Column('credit', sa.String(length=16), nullable=False),
    sa.Column('withdrawn', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('evidence_reference', sa.Text(), nullable=False),
    sa.Column('recorded_by', sa.UUID(), nullable=True),
    sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("collector_code ~ '^C[0-9]{2,4}$'", name='ck_speaker_consents_collector'),
    sa.CheckConstraint("consent_method IN ('written', 'oral')", name='ck_speaker_consents_method'),
    sa.CheckConstraint("credit IN ('name', 'initials', 'none')", name='ck_speaker_consents_credit'),
    sa.CheckConstraint("form_version ~ '^audio-consent-v[0-9]{1,3}$'", name='ck_speaker_consents_form_version'),
    sa.CheckConstraint('NOT withdrawn OR NOT (keep_and_evaluate OR train_recognition OR train_synthesis OR play_in_app OR public_dataset OR commercial_use)', name='ck_speaker_consents_withdrawn_grants_nothing'),
    sa.ForeignKeyConstraint(['recorded_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['speaker_id'], ['speakers.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_speaker_consents_speaker_id'), 'speaker_consents', ['speaker_id'], unique=False)
    op.create_table('speech_source_permissions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('source_id', sa.UUID(), nullable=False),
    sa.Column('rights_holder', sa.Text(), nullable=False),
    sa.Column('evidence_reference', sa.Text(), nullable=False),
    sa.Column('valid_until', sa.Date(), nullable=True),
    sa.Column('allow_transcription', sa.Boolean(), nullable=False),
    sa.Column('allow_asr_training', sa.Boolean(), nullable=False),
    sa.Column('allow_tts_training', sa.Boolean(), nullable=False),
    sa.Column('allow_playback', sa.Boolean(), nullable=False),
    sa.Column('allow_redistribution', sa.Boolean(), nullable=False),
    sa.Column('allow_commercial', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='pending', nullable=False),
    sa.Column('recorded_by', sa.UUID(), nullable=True),
    sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('decided_by', sa.UUID(), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decision_note', sa.Text(), nullable=True),
    sa.CheckConstraint("(status = 'pending') = (decided_by IS NULL AND decided_at IS NULL)", name='ck_speech_source_permissions_decision'),
    sa.CheckConstraint("status IN ('pending', 'verified', 'rejected', 'revoked')", name='ck_speech_source_permissions_status'),
    sa.CheckConstraint('decided_by IS NULL OR recorded_by IS NULL OR decided_by <> recorded_by', name='ck_speech_source_permissions_separate_decider'),
    sa.ForeignKeyConstraint(['decided_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['recorded_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['source_id'], ['speech_sources.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_speech_source_permissions_source_id'), 'speech_source_permissions', ['source_id'], unique=False)
    op.create_table('speech_source_speakers',
    sa.Column('source_id', sa.UUID(), nullable=False),
    sa.Column('speaker_id', sa.UUID(), nullable=False),
    sa.Column('added_by', sa.UUID(), nullable=True),
    sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['added_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['source_id'], ['speech_sources.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['speaker_id'], ['speakers.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('source_id', 'speaker_id')
    )
    op.create_index(op.f('ix_speech_source_speakers_speaker_id'), 'speech_source_speakers', ['speaker_id'], unique=False)

    # Consent records are evidence: a change or withdrawal is a new record, never an edit.
    op.execute(
        """
        CREATE FUNCTION speaker_consents_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'speaker_consents is append-only: record a new consent instead';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER speaker_consents_append_only
        BEFORE UPDATE OR DELETE ON speaker_consents
        FOR EACH ROW EXECUTE FUNCTION speaker_consents_append_only()
        """
    )
    op.execute(
        """
        CREATE TRIGGER speaker_consents_no_truncate
        BEFORE TRUNCATE ON speaker_consents
        FOR EACH STATEMENT EXECUTE FUNCTION speaker_consents_append_only()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER speaker_consents_no_truncate ON speaker_consents")
    op.execute("DROP TRIGGER speaker_consents_append_only ON speaker_consents")
    op.execute("DROP FUNCTION speaker_consents_append_only()")
    op.drop_index(op.f('ix_speech_source_speakers_speaker_id'), table_name='speech_source_speakers')
    op.drop_table('speech_source_speakers')
    op.drop_index(op.f('ix_speech_source_permissions_source_id'), table_name='speech_source_permissions')
    op.drop_table('speech_source_permissions')
    op.drop_index(op.f('ix_speaker_consents_speaker_id'), table_name='speaker_consents')
    op.drop_table('speaker_consents')
    op.drop_table('speech_sources')
    op.drop_table('speakers')
