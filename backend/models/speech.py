"""Speech Data Lab records (docs/SPEECH_DATA_LAB.md): rights and consent (PR 1), media and jobs (PR 2).

Speakers are pseudonymous codes only. Names and contact details stay in the private
roster in siamsil-data (docs/AUDIO_CONSENT.md); consent documents stay in private
storage and are referenced here, never stored.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base

USE_COLUMNS = (
    "allow_transcription",
    "allow_asr_training",
    "allow_tts_training",
    "allow_playback",
    "allow_redistribution",
    "allow_commercial",
)
CHOICE_COLUMNS = (
    "keep_and_evaluate",
    "train_recognition",
    "train_synthesis",
    "play_in_app",
    "public_dataset",
    "commercial_use",
)


class SpeechSource(Base):
    """A recording Siamsil may collect: a link to where it is published, or a creator's own file."""

    __tablename__ = "speech_sources"
    __table_args__ = (
        CheckConstraint(
            "platform IN ('youtube', 'facebook', 'other', 'creator_file')", name="ck_speech_sources_platform"
        ),
        CheckConstraint("(platform = 'creator_file') = (url IS NULL)", name="ck_speech_sources_url"),
        CheckConstraint("language = 'ctd'", name="ck_speech_sources_language"),
        CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0", name="ck_speech_sources_duration"),
        CheckConstraint("status IN ('registered', 'withdrawn')", name="ck_speech_sources_status"),
        CheckConstraint("(status = 'withdrawn') = (withdrawn_at IS NOT NULL)", name="ck_speech_sources_withdrawn"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    uploader: Mapped[Optional[str]] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="ctd", server_default="ctd")
    dialect: Mapped[Optional[str]] = mapped_column(Text)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    acquired_on: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="registered", server_default="registered")
    withdrawn_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    registered_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourcePermission(Base):
    """What a source's rights holder allowed, with a pointer to the evidence, checked by a second person."""

    __tablename__ = "speech_source_permissions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'verified', 'rejected', 'revoked')", name="ck_speech_source_permissions_status"
        ),
        CheckConstraint(
            "(status = 'pending') = (decided_by IS NULL AND decided_at IS NULL)",
            name="ck_speech_source_permissions_decision",
        ),
        # Four eyes: whoever records a permission cannot also verify, reject, or revoke it.
        CheckConstraint(
            "decided_by IS NULL OR recorded_by IS NULL OR decided_by <> recorded_by",
            name="ck_speech_source_permissions_separate_decider",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("speech_sources.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rights_holder: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_reference: Mapped[str] = mapped_column(Text, nullable=False)
    valid_until: Mapped[Optional[date]] = mapped_column(Date)
    allow_transcription: Mapped[bool] = mapped_column(Boolean, nullable=False)
    allow_asr_training: Mapped[bool] = mapped_column(Boolean, nullable=False)
    allow_tts_training: Mapped[bool] = mapped_column(Boolean, nullable=False)
    allow_playback: Mapped[bool] = mapped_column(Boolean, nullable=False)
    allow_redistribution: Mapped[bool] = mapped_column(Boolean, nullable=False)
    allow_commercial: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    recorded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[Optional[str]] = mapped_column(Text)


class Speaker(Base):
    """A pseudonymous speaker. The code links to a name only in the private roster."""

    __tablename__ = "speakers"
    __table_args__ = (CheckConstraint("speaker_code ~ '^S[0-9]{4,6}$'", name="ck_speakers_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    speaker_code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    dialect_region: Mapped[Optional[str]] = mapped_column(Text)
    age_range: Mapped[Optional[str]] = mapped_column(String(16))
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SpeakerConsent(Base):
    """One consent record (docs/AUDIO_CONSENT.md). Never edited: a change or withdrawal is a new record.

    A speaker's current consent is their record with the highest `id`.
    """

    __tablename__ = "speaker_consents"
    __table_args__ = (
        CheckConstraint("consent_method IN ('written', 'oral')", name="ck_speaker_consents_method"),
        CheckConstraint("credit IN ('name', 'initials', 'none')", name="ck_speaker_consents_credit"),
        CheckConstraint("form_version ~ '^audio-consent-v[0-9]{1,3}$'", name="ck_speaker_consents_form_version"),
        CheckConstraint("collector_code ~ '^C[0-9]{2,4}$'", name="ck_speaker_consents_collector"),
        CheckConstraint(
            "NOT withdrawn OR NOT (keep_and_evaluate OR train_recognition OR train_synthesis"
            " OR play_in_app OR public_dataset OR commercial_use)",
            name="ck_speaker_consents_withdrawn_grants_nothing",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    speaker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("speakers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    form_version: Mapped[str] = mapped_column(String(32), nullable=False)
    form_language: Mapped[str] = mapped_column(String(32), nullable=False)
    consent_method: Mapped[str] = mapped_column(String(16), nullable=False)
    consent_date: Mapped[date] = mapped_column(Date, nullable=False)
    collector_code: Mapped[str] = mapped_column(String(8), nullable=False)
    adult_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    keep_and_evaluate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    train_recognition: Mapped[bool] = mapped_column(Boolean, nullable=False)
    train_synthesis: Mapped[bool] = mapped_column(Boolean, nullable=False)
    play_in_app: Mapped[bool] = mapped_column(Boolean, nullable=False)
    public_dataset: Mapped[bool] = mapped_column(Boolean, nullable=False)
    commercial_use: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credit: Mapped[str] = mapped_column(String(16), nullable=False)
    withdrawn: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    evidence_reference: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceSpeaker(Base):
    """A speaker heard in a source. Every speaker's consent counts for every use of the source."""

    __tablename__ = "speech_source_speakers"

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("speech_sources.id", ondelete="RESTRICT"), primary_key=True
    )
    speaker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("speakers.id", ondelete="RESTRICT"), primary_key=True, index=True
    )
    added_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MediaAsset(Base):
    """A stored media file for a source: the original upload, or a working copy made from it.

    The file itself is in private media storage under `storage_key`; only its facts are here.
    """

    __tablename__ = "speech_media_assets"
    __table_args__ = (
        UniqueConstraint("source_id", "kind", "sha256", name="uq_speech_media_assets_source_kind_sha256"),
        CheckConstraint("kind IN ('original', 'normalized_wav')", name="ck_speech_media_assets_kind"),
        # An original says how it reached Siamsil and comes from nothing; a working copy comes from an original.
        CheckConstraint(
            "(kind = 'original') = (derived_from_id IS NULL)", name="ck_speech_media_assets_derivation"
        ),
        CheckConstraint(
            "(kind = 'original') = (provenance IS NOT NULL)", name="ck_speech_media_assets_provenance_set"
        ),
        CheckConstraint(
            "provenance IS NULL OR provenance IN ('creator_provided', 'owner_platform_export')",
            name="ck_speech_media_assets_provenance",
        ),
        CheckConstraint(
            "media_type IN ('audio/wav', 'audio/mpeg', 'audio/mp4', 'video/mp4')", name="ck_speech_media_assets_type"
        ),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_speech_media_assets_sha256"),
        CheckConstraint("size_bytes > 0", name="ck_speech_media_assets_size"),
        CheckConstraint("status IN ('stored', 'deleted')", name="ck_speech_media_assets_status"),
        CheckConstraint("(status = 'deleted') = (deleted_at IS NOT NULL)", name="ck_speech_media_assets_deleted"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("speech_sources.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    provenance: Mapped[Optional[str]] = mapped_column(String(32))
    derived_from_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("speech_media_assets.id", ondelete="RESTRICT")
    )
    storage_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    media_type: Mapped[str] = mapped_column(String(32), nullable=False)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    sample_rate: Mapped[Optional[int]] = mapped_column(Integer)
    channels: Mapped[Optional[int]] = mapped_column(Integer)
    codec: Mapped[Optional[str]] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="stored", server_default="stored")
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deletion_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AudioProcessingJob(Base):
    """One pipeline step for one stored file.

    Unique per (asset, step, processing version), so a retry or a second worker never repeats
    finished work. A worker holds a job through a lease; an expired lease lets another take over.
    """

    __tablename__ = "speech_processing_jobs"
    __table_args__ = (
        UniqueConstraint("asset_id", "step", "processing_version", name="uq_speech_processing_jobs_step"),
        CheckConstraint("step IN ('normalize_wav')", name="ck_speech_processing_jobs_step"),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'blocked')", name="ck_speech_processing_jobs_status"
        ),
        CheckConstraint("attempts >= 0", name="ck_speech_processing_jobs_attempts"),
        CheckConstraint(
            "(status = 'running') = (lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_speech_processing_jobs_lease",
        ),
        CheckConstraint(
            "(status = 'succeeded') = (output_asset_id IS NOT NULL)", name="ck_speech_processing_jobs_output"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("speech_media_assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    step: Mapped[str] = mapped_column(String(32), nullable=False)
    processing_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    lease_owner: Mapped[Optional[str]] = mapped_column(String(128))
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    tool_versions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    error: Mapped[Optional[str]] = mapped_column(Text)
    output_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("speech_media_assets.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
