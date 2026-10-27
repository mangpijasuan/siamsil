"""The Speech Data Lab job worker (docs/SPEECH_DATA_LAB.md, PR 2).

A job is claimed under a lease in a short transaction, the work runs outside any transaction,
and the result is recorded in another short transaction only if this worker still holds the
lease. Whether the source may still be kept and transcribed is checked before the work and
again before the result is stored, so a withdrawal or revocation stops the job at the next step.

Jobs are unique per (file, step, processing version), and output files are stored by checksum,
so running a job twice, or two workers racing, never produces a second copy.
"""

from __future__ import annotations

import hashlib
import os
import socket
import tempfile
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from models import AudioProcessingJob, AuditEvent, MediaAsset
from speech import audio, media
from speech.ingest import MediaRepository
from speech.media import LocalMediaStore

Transactions = Callable[[], AbstractContextManager[Session]]


@dataclass(frozen=True)
class Claimed:
    job_id: int
    asset_id: UUID
    source_id: UUID
    storage_key: str
    media_type: str


@dataclass(frozen=True)
class WorkerSettings:
    ffmpeg: str
    ffprobe: str
    lease_seconds: int
    max_attempts: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class JobRunner:
    def __init__(
        self, transactions: Transactions, store: LocalMediaStore, settings: WorkerSettings, worker_id: Optional[str] = None
    ) -> None:
        self.transactions = transactions
        self.store = store
        self.settings = settings
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"

    def _audit(self, session: Session, action: str, job: AudioProcessingJob, **data) -> None:
        session.add(
            AuditEvent(
                actor_user_id=None,
                action=f"speech.{action}",
                target_type="speech_processing_job",
                target_id=str(job.id),
                event_data={"worker": self.worker_id, **data},
            )
        )

    # Claiming ---------------------------------------------------------------------------------

    def claim(self) -> Optional[Claimed]:
        """Take the oldest job that is waiting, failed but retryable, or abandoned by an expired lease."""
        now = datetime.now(timezone.utc)
        retryable = AudioProcessingJob.attempts < self.settings.max_attempts
        with self.transactions() as session:
            # An abandoned job that has used all its attempts fails for good instead of running again.
            session.execute(
                update(AudioProcessingJob)
                .where(
                    AudioProcessingJob.status == "running",
                    AudioProcessingJob.lease_expires_at < now,
                    AudioProcessingJob.attempts >= self.settings.max_attempts,
                )
                .values(
                    status="failed",
                    lease_owner=None,
                    lease_expires_at=None,
                    error="the worker stopped before finishing, and no attempts are left",
                    finished_at=now,
                )
            )
            job = session.scalar(
                select(AudioProcessingJob)
                .where(
                    or_(
                        AudioProcessingJob.status == "pending",
                        and_(AudioProcessingJob.status == "failed", retryable),
                        and_(AudioProcessingJob.status == "running", AudioProcessingJob.lease_expires_at < now, retryable),
                    )
                )
                .order_by(AudioProcessingJob.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if job is None:
                return None
            asset = session.get(MediaAsset, job.asset_id)
            job.status = "running"
            job.attempts += 1
            job.lease_owner = self.worker_id
            job.lease_expires_at = now + timedelta(seconds=self.settings.lease_seconds)
            job.error = None
            job.finished_at = None
            session.flush()
            return Claimed(job.id, asset.id, asset.source_id, asset.storage_key, asset.media_type)

    # Finishing --------------------------------------------------------------------------------

    def _held(self, session: Session, job_id: int) -> Optional[AudioProcessingJob]:
        """The job, locked, if this worker still holds its lease; otherwise None (someone took over)."""
        job = session.get(AudioProcessingJob, job_id, with_for_update=True)
        if job is None or job.status != "running" or job.lease_owner != self.worker_id:
            return None
        return job

    def _finish(self, session: Session, job: AudioProcessingJob, status: str, error: Optional[str] = None) -> None:
        job.status = status
        job.error = error
        job.lease_owner = None
        job.lease_expires_at = None
        job.finished_at = datetime.now(timezone.utc)
        self._audit(session, f"job_{status}", job, step=job.step, error=error)

    def _stop(self, job_id: int, status: str, error: str) -> str:
        with self.transactions() as session:
            job = self._held(session, job_id)
            if job is None:
                return "abandoned"
            self._finish(session, job, status, error)
        return status

    def _blocked_reason(self, session: Session, claimed: Claimed) -> Optional[str]:
        asset = session.get(MediaAsset, claimed.asset_id)
        if asset is None or asset.status != "stored":
            return "the media was deleted"
        reasons = MediaRepository(session, self.store).transcription_reasons(claimed.source_id)
        return "; ".join(reasons) if reasons else None

    def run_one(self) -> Optional[str]:
        """Claim and run one job. Returns its new status, or None when no job is waiting."""
        claimed = self.claim()
        if claimed is None:
            return None
        with self.transactions() as session:
            reason = self._blocked_reason(session, claimed)
        if reason:
            return self._stop(claimed.job_id, "blocked", reason)
        if not self.store.exists(claimed.storage_key):
            return self._stop(claimed.job_id, "failed", "the stored file is missing")

        fmt = media.FORMATS[claimed.media_type]
        work = self.store.root / ".work"
        work.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(dir=work) as folder:
            output = Path(folder) / "normalized.wav"
            try:
                # Stop before the lease runs out, so no other worker takes over a job still running here.
                timeout = max(60, self.settings.lease_seconds - 60)
                audio.normalize(self.settings.ffmpeg, self.store.path(claimed.storage_key), fmt.demuxer, output, timeout=timeout)
                result = audio.probe(self.settings.ffprobe, output, media.NORMALIZED_WAV.demuxer)
                versions = {"ffmpeg": audio.tool_version(self.settings.ffmpeg)}
            except audio.AudioError as error:
                return self._stop(claimed.job_id, "failed", str(error))
            sha256 = _sha256(output)
            size = output.stat().st_size

            with self.transactions() as session:
                job = self._held(session, claimed.job_id)
                if job is None:
                    return "abandoned"
                reason = self._blocked_reason(session, claimed)
                if reason:
                    self._finish(session, job, "blocked", reason)
                    return "blocked"
                key = self.store.key(claimed.source_id, "normalized_wav", sha256, media.NORMALIZED_WAV.extension)
                self.store.put(key, output)
                copy = session.scalar(
                    select(MediaAsset).where(
                        MediaAsset.source_id == claimed.source_id,
                        MediaAsset.kind == "normalized_wav",
                        MediaAsset.sha256 == sha256,
                    )
                )
                if copy is None:
                    copy = MediaAsset(
                        source_id=claimed.source_id,
                        kind="normalized_wav",
                        derived_from_id=claimed.asset_id,
                        storage_key=key,
                        sha256=sha256,
                        size_bytes=size,
                        media_type=media.NORMALIZED_WAV.media_type,
                        duration_seconds=result.duration_seconds,
                        sample_rate=result.sample_rate,
                        channels=result.channels,
                        codec=result.codec,
                    )
                    session.add(copy)
                    session.flush()
                job.output_asset_id = copy.id
                job.tool_versions = versions
                self._finish(session, job, "succeeded")
                self._audit(session, "media_normalized", job, output_asset_id=str(copy.id), sha256=sha256)
        return "succeeded"

    def run_all(self, limit: Optional[int] = None) -> dict[str, int]:
        """Run jobs until none is waiting (or `limit` have run). Returns a count per outcome."""
        counts: dict[str, int] = {}
        while limit is None or sum(counts.values()) < limit:
            status = self.run_one()
            if status is None:
                break
            counts[status] = counts.get(status, 0) + 1
        return counts

    def retry_blocked(self) -> int:
        """Put blocked jobs back in the queue, for example after a permission is verified again.
        A job whose media was deleted stays blocked; any other is blocked again if still not allowed."""
        with self.transactions() as session:
            result = session.execute(
                update(AudioProcessingJob)
                .where(
                    AudioProcessingJob.status == "blocked",
                    AudioProcessingJob.asset_id.in_(select(MediaAsset.id).where(MediaAsset.status == "stored")),
                )
                .values(status="pending", error=None, finished_at=None)
            )
            return result.rowcount or 0
