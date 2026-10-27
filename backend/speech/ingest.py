"""Taking in media files for a source, listing them, and deleting them (docs/SPEECH_DATA_LAB.md, PR 2).

A file is accepted only while the source may be kept and transcribed (the `transcription` use:
the rights holder's verified permission AND every speaker's current consent). The check runs
before any bytes are read and again when the file is recorded. Every change writes an audit
event in the same transaction; callers commit or roll back.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from identity.schemas import AuthenticatedUser
from models import AudioProcessingJob, AuditEvent, MediaAsset, SpeechSource
from speech import audio, media
from speech.media import LocalMediaStore, MediaFormat
from speech.repository import SpeechConflict, SpeechNotFound, SpeechRepository
from speech.rules import SpeechUse
from speech.schemas import JobOut, MediaAssetOut, MediaDeletionOut, MediaList

NORMALIZE_STEP = "normalize_wav"


class MediaTooLarge(ValueError):
    pass


class UnsupportedMedia(ValueError):
    pass


@dataclass(frozen=True)
class ReceivedFile:
    """An upload written to a private temporary file, with what was learned while reading it."""

    path: Path
    sha256: str
    size_bytes: int
    format: MediaFormat


async def receive(chunks: AsyncIterator[bytes], *, folder: Path, max_bytes: int) -> ReceivedFile:
    """Stream an upload to a private temporary file, hashing it and refusing it as soon as it
    is too large or its first bytes are not WAV, MP3, M4A, or MP4. The caller deletes the file."""
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(folder, 0o700)
    handle, name = tempfile.mkstemp(dir=folder, prefix=".upload-")
    path = Path(name)
    digest = hashlib.sha256()
    size = 0
    head = b""
    fmt: Optional[MediaFormat] = None
    try:
        with os.fdopen(handle, "wb") as out:
            async for chunk in chunks:
                if not chunk:
                    continue
                size += len(chunk)
                if size > max_bytes:
                    raise MediaTooLarge(f"the file is larger than the {max_bytes:,}-byte limit")
                if fmt is None:
                    head = (head + chunk)[: media.SNIFF_BYTES]
                    if len(head) >= media.SNIFF_BYTES:
                        fmt = media.sniff(head)
                        if fmt is None:
                            raise UnsupportedMedia("only WAV, MP3, M4A, and MP4 files are accepted")
                digest.update(chunk)
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        if fmt is None:
            fmt = media.sniff(head) if size else None
            if fmt is None:
                raise UnsupportedMedia("only WAV, MP3, M4A, and MP4 files are accepted")
        return ReceivedFile(path, digest.hexdigest(), size, fmt)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _job_out(job: AudioProcessingJob) -> JobOut:
    return JobOut(
        id=job.id,
        step=job.step,
        processing_version=job.processing_version,
        status=job.status,
        attempts=job.attempts,
        error=job.error,
        tool_versions=dict(job.tool_versions or {}),
        output_asset_id=job.output_asset_id,
        created_at=job.created_at,
        finished_at=job.finished_at,
    )


class MediaRepository:
    def __init__(self, session: Session, store: LocalMediaStore) -> None:
        self.session = session
        self.store = store

    def _audit(self, actor: Optional[AuthenticatedUser], action: str, target_id: object, request_id: Optional[str], **data) -> None:
        self.session.add(
            AuditEvent(
                actor_user_id=actor.user_id if actor else None,
                action=f"speech.{action}",
                target_type="speech_media_asset",
                target_id=str(target_id),
                request_id=request_id,
                event_data=data,
            )
        )

    def transcription_reasons(self, source_id: UUID, *, today: Optional[date] = None) -> list[str]:
        """Why the source may not be kept and transcribed today; empty when it may."""
        result = SpeechRepository(self.session).eligibility(source_id, today=today or date.today())
        return next(use.reasons for use in result.uses if use.use is SpeechUse.TRANSCRIPTION)

    def require_transcription(self, source_id: UUID) -> None:
        reasons = self.transcription_reasons(source_id)
        if reasons:
            raise SpeechConflict("media cannot be collected for this source: " + "; ".join(reasons))

    def _asset_out(self, asset: MediaAsset) -> MediaAssetOut:
        jobs = self.session.scalars(
            select(AudioProcessingJob).where(AudioProcessingJob.asset_id == asset.id).order_by(AudioProcessingJob.id)
        ).all()
        return MediaAssetOut(
            id=asset.id,
            source_id=asset.source_id,
            kind=asset.kind,
            provenance=asset.provenance,
            derived_from_id=asset.derived_from_id,
            sha256=asset.sha256,
            size_bytes=asset.size_bytes,
            media_type=asset.media_type,
            duration_seconds=asset.duration_seconds,
            sample_rate=asset.sample_rate,
            channels=asset.channels,
            codec=asset.codec,
            status=asset.status,
            deleted_at=asset.deleted_at,
            created_at=asset.created_at,
            jobs=[_job_out(job) for job in jobs],
        )

    def _original(self, source_id: UUID, sha256: str) -> Optional[MediaAsset]:
        return self.session.scalar(
            select(MediaAsset).where(MediaAsset.source_id == source_id, MediaAsset.kind == "original", MediaAsset.sha256 == sha256)
        )

    def record_original(
        self,
        source_id: UUID,
        received: ReceivedFile,
        probe: audio.Probe,
        provenance: str,
        *,
        actor: AuthenticatedUser,
        request_id: Optional[str],
    ) -> MediaAssetOut:
        """Store an upload as the source's original and queue its working copy. Uploading the same
        file again returns the existing record unchanged."""
        source = self.session.get(SpeechSource, source_id, with_for_update=True)
        if source is None:
            raise SpeechNotFound("source not found")
        # Checked again here, with the source locked: a withdrawal may have landed during the upload.
        self.require_transcription(source_id)
        existing = self._original(source_id, received.sha256)
        if existing is not None:
            if existing.status == "deleted":
                raise SpeechConflict("this file was deleted from this source; register a new source to collect it again")
            return self._asset_out(existing)
        key = self.store.key(source_id, "original", received.sha256, received.format.extension)
        self.store.put(key, received.path)
        asset = MediaAsset(
            source_id=source_id,
            kind="original",
            provenance=provenance,
            storage_key=key,
            sha256=received.sha256,
            size_bytes=received.size_bytes,
            media_type=received.format.media_type,
            duration_seconds=probe.duration_seconds,
            sample_rate=probe.sample_rate,
            channels=probe.channels,
            codec=probe.codec,
            created_by=actor.user_id,
        )
        # Two identical uploads at once: the second finds the first's record instead of failing.
        savepoint = self.session.begin_nested()
        try:
            self.session.add(asset)
            self.session.flush()
        except IntegrityError:
            savepoint.rollback()
            return self._asset_out(self._original(source_id, received.sha256))
        savepoint.commit()
        self.session.add(
            AudioProcessingJob(asset_id=asset.id, step=NORMALIZE_STEP, processing_version=audio.PROCESSING_VERSION)
        )
        self._audit(
            actor,
            "media_uploaded",
            asset.id,
            request_id,
            source_id=str(source_id),
            sha256=asset.sha256,
            size_bytes=asset.size_bytes,
            media_type=asset.media_type,
            provenance=provenance,
        )
        self.session.flush()
        return self._asset_out(asset)

    def list_media(self, source_id: UUID) -> MediaList:
        if self.session.get(SpeechSource, source_id) is None:
            raise SpeechNotFound("source not found")
        assets = self.session.scalars(
            select(MediaAsset).where(MediaAsset.source_id == source_id).order_by(MediaAsset.created_at, MediaAsset.id)
        ).all()
        reasons = self.transcription_reasons(source_id)
        return MediaList(
            source_id=source_id,
            transcription_allowed=not reasons,
            reasons=reasons,
            assets=[self._asset_out(asset) for asset in assets],
        )

    def delete_media(
        self, source_id: UUID, reason: str, *, actor: AuthenticatedUser, request_id: Optional[str]
    ) -> MediaDeletionOut:
        """Delete every stored file of a source and stop its unfinished jobs. The records stay, marked
        deleted, so the history of what was collected and removed is kept without the audio.

        Files are removed before the transaction commits: if the commit then fails, the audio is
        still gone (the safe side) and a later job on it fails with "the stored file is missing"."""
        if self.session.get(SpeechSource, source_id, with_for_update=True) is None:
            raise SpeechNotFound("source not found")
        assets = self.session.scalars(
            select(MediaAsset).where(MediaAsset.source_id == source_id, MediaAsset.status == "stored").with_for_update()
        ).all()
        now = datetime.now(timezone.utc)
        files = 0
        for asset in assets:
            files += self.store.delete(asset.storage_key)
            asset.status = "deleted"
            asset.deleted_at = now
            asset.deletion_reason = reason
            for job in self.session.scalars(
                select(AudioProcessingJob)
                .where(AudioProcessingJob.asset_id == asset.id, AudioProcessingJob.status.in_(("pending", "running", "failed")))
                .with_for_update()
            ):
                job.status = "blocked"
                job.error = "the media was deleted"
                job.lease_owner = None
                job.lease_expires_at = None
            self._audit(actor, "media_deleted", asset.id, request_id, source_id=str(source_id), reason=reason)
        self.session.flush()
        return MediaDeletionOut(source_id=source_id, deleted_assets=len(assets), deleted_files=files)
