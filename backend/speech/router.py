"""Speech Data Lab API (docs/SPEECH_DATA_LAB.md): sources, rights, speakers, and consent (PR 1);
media files (PR 2).

Only administrators register sources, record permissions and consent, upload or delete media,
and withdraw. Administrators and editors can read. A permission is decided by a different
administrator from the one who recorded it. Nothing here downloads media or fetches a link:
media arrives only as a file an administrator uploads.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from database import get_session_factory
from identity.dependencies import require_roles
from identity.schemas import AuthenticatedUser, RoleName
from settings import get_settings
from speech import audio
from speech.ingest import MediaRepository, MediaTooLarge, UnsupportedMedia, receive
from speech.media import LocalMediaStore
from speech.repository import SpeechConflict, SpeechForbidden, SpeechNotFound, SpeechRepository
from speech.schemas import (
    ConsentCreate,
    ConsentWithdrawal,
    EligibilityOut,
    MediaAssetOut,
    MediaDeletion,
    MediaDeletionOut,
    MediaList,
    PermissionCreate,
    PermissionDecision,
    PermissionOut,
    Provenance,
    SourceCreate,
    SourceList,
    SourceOut,
    SourceWithdrawal,
    SpeakerCreate,
    SpeakerList,
    SpeakerOut,
)

router = APIRouter(prefix="/speech", tags=["speech"])

administrator = require_roles(RoleName.ADMINISTRATOR.value)
reader = require_roles(RoleName.ADMINISTRATOR.value, RoleName.EDITOR.value)


def get_speech_session() -> Iterator[Session]:
    """One transaction per request: committed when the handler returns, rolled back on any error."""
    factory = get_session_factory()
    if factory is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Application database is unavailable.")
    with factory.begin() as session:
        yield session


def get_speech_transactions() -> Callable[[], AbstractContextManager[Session]]:
    """Short transactions on demand, for requests that must not hold one open while a file streams in."""
    factory = get_session_factory()
    if factory is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Application database is unavailable.")
    return factory.begin


def get_media_store() -> LocalMediaStore:
    return LocalMediaStore(get_settings().speech_media_dir)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


ERROR_STATUS = (
    (SpeechNotFound, status.HTTP_404_NOT_FOUND),
    (SpeechForbidden, status.HTTP_403_FORBIDDEN),
    (SpeechConflict, status.HTTP_409_CONFLICT),
    (MediaTooLarge, status.HTTP_413_CONTENT_TOO_LARGE),
    (UnsupportedMedia, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE),
    (ValueError, status.HTTP_422_UNPROCESSABLE_CONTENT),
)


def _http_error(error: Exception) -> HTTPException:
    code = next(code for kind, code in ERROR_STATUS if isinstance(error, kind))
    return HTTPException(status_code=code, detail=str(error))


def _run(action):
    try:
        return action()
    except (SpeechNotFound, SpeechForbidden, ValueError) as error:
        raise _http_error(error) from None


@router.post("/sources", response_model=SourceOut)
def register_source(
    data: SourceCreate,
    request: Request,
    actor: AuthenticatedUser = Depends(administrator),
    session: Session = Depends(get_speech_session),
) -> SourceOut:
    return _run(lambda: SpeechRepository(session).register_source(data, actor=actor, request_id=_request_id(request)))


@router.get("/sources", response_model=SourceList)
def list_sources(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: AuthenticatedUser = Depends(reader),
    session: Session = Depends(get_speech_session),
) -> SourceList:
    return SourceList(sources=SpeechRepository(session).list_sources(limit=limit, offset=offset))


@router.get("/sources/{source_id}", response_model=SourceOut)
def get_source(
    source_id: UUID,
    _: AuthenticatedUser = Depends(reader),
    session: Session = Depends(get_speech_session),
) -> SourceOut:
    return _run(lambda: SpeechRepository(session).get_source(source_id))


@router.post("/sources/{source_id}/withdraw", response_model=SourceOut)
def withdraw_source(
    source_id: UUID,
    data: SourceWithdrawal,
    request: Request,
    actor: AuthenticatedUser = Depends(administrator),
    session: Session = Depends(get_speech_session),
) -> SourceOut:
    return _run(
        lambda: SpeechRepository(session).withdraw_source(source_id, data.reason, actor=actor, request_id=_request_id(request))
    )


@router.post("/sources/{source_id}/permissions", response_model=PermissionOut)
def record_permission(
    source_id: UUID,
    data: PermissionCreate,
    request: Request,
    actor: AuthenticatedUser = Depends(administrator),
    session: Session = Depends(get_speech_session),
) -> PermissionOut:
    return _run(
        lambda: SpeechRepository(session).record_permission(source_id, data, actor=actor, request_id=_request_id(request))
    )


@router.post("/sources/{source_id}/permissions/{permission_id}/decision", response_model=PermissionOut)
def decide_permission(
    source_id: UUID,
    permission_id: UUID,
    data: PermissionDecision,
    request: Request,
    actor: AuthenticatedUser = Depends(administrator),
    session: Session = Depends(get_speech_session),
) -> PermissionOut:
    return _run(
        lambda: SpeechRepository(session).decide_permission(
            source_id, permission_id, data, actor=actor, request_id=_request_id(request)
        )
    )


@router.post("/sources/{source_id}/speakers/{speaker_code}", response_model=SourceOut)
def link_speaker(
    source_id: UUID,
    speaker_code: str,
    request: Request,
    actor: AuthenticatedUser = Depends(administrator),
    session: Session = Depends(get_speech_session),
) -> SourceOut:
    return _run(
        lambda: SpeechRepository(session).link_speaker(source_id, speaker_code, actor=actor, request_id=_request_id(request))
    )


@router.get("/sources/{source_id}/eligibility", response_model=EligibilityOut)
def source_eligibility(
    source_id: UUID,
    _: AuthenticatedUser = Depends(reader),
    session: Session = Depends(get_speech_session),
) -> EligibilityOut:
    return _run(lambda: SpeechRepository(session).eligibility(source_id, today=date.today()))


@router.post("/speakers", response_model=SpeakerOut)
def create_speaker(
    data: SpeakerCreate,
    request: Request,
    actor: AuthenticatedUser = Depends(administrator),
    session: Session = Depends(get_speech_session),
) -> SpeakerOut:
    return _run(lambda: SpeechRepository(session).create_speaker(data, actor=actor, request_id=_request_id(request)))


@router.get("/speakers", response_model=SpeakerList)
def list_speakers(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: AuthenticatedUser = Depends(reader),
    session: Session = Depends(get_speech_session),
) -> SpeakerList:
    return SpeakerList(speakers=SpeechRepository(session).list_speakers(limit=limit, offset=offset))


@router.post("/speakers/{speaker_code}/consents", response_model=SpeakerOut)
def record_consent(
    speaker_code: str,
    data: ConsentCreate,
    request: Request,
    actor: AuthenticatedUser = Depends(administrator),
    session: Session = Depends(get_speech_session),
) -> SpeakerOut:
    return _run(
        lambda: SpeechRepository(session).record_consent(speaker_code, data, actor=actor, request_id=_request_id(request))
    )


@router.post("/speakers/{speaker_code}/withdrawal", response_model=SpeakerOut)
def withdraw_consent(
    speaker_code: str,
    data: ConsentWithdrawal,
    request: Request,
    actor: AuthenticatedUser = Depends(administrator),
    session: Session = Depends(get_speech_session),
) -> SpeakerOut:
    return _run(
        lambda: SpeechRepository(session).withdraw_consent(speaker_code, data, actor=actor, request_id=_request_id(request))
    )


# Media (PR 2) -----------------------------------------------------------------------------------

UPLOAD_BODY = {
    "requestBody": {
        "required": True,
        "description": "The file itself as the raw request body: WAV, MP3, M4A, or MP4. Its type is read from its bytes.",
        "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
    }
}


@router.post("/sources/{source_id}/media", response_model=MediaAssetOut, openapi_extra=UPLOAD_BODY)
async def upload_media(
    source_id: UUID,
    request: Request,
    provenance: Provenance = Query(description="How the file reached Siamsil: from the creator, or the owner's own platform export."),
    actor: AuthenticatedUser = Depends(administrator),
    transactions: Callable[[], AbstractContextManager[Session]] = Depends(get_speech_transactions),
    store: LocalMediaStore = Depends(get_media_store),
) -> MediaAssetOut:
    """Upload a source's original file. Refused before any bytes are read unless the source may be
    kept and transcribed. The same file uploaded twice returns the first record."""
    settings = get_settings()

    def check() -> None:
        with transactions() as session:
            MediaRepository(session, store).require_transcription(source_id)

    await run_in_threadpool(_run, check)
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > settings.speech_max_upload_bytes:
        raise _http_error(MediaTooLarge(f"the file is larger than the {settings.speech_max_upload_bytes:,}-byte limit"))
    try:
        received = await receive(request.stream(), folder=store.root / ".uploads", max_bytes=settings.speech_max_upload_bytes)
    except (MediaTooLarge, UnsupportedMedia) as error:
        raise _http_error(error) from None
    try:

        def record() -> MediaAssetOut:
            try:
                probe = audio.probe(settings.speech_ffprobe, received.path, received.format.demuxer)
            except audio.AudioError as error:
                raise UnsupportedMedia(f"the file could not be read as audio: {error}") from None
            if probe.duration_seconds > settings.speech_max_duration_seconds:
                raise MediaTooLarge(f"the audio is longer than {settings.speech_max_duration_seconds:,} seconds")
            with transactions() as session:
                return MediaRepository(session, store).record_original(
                    source_id, received, probe, provenance, actor=actor, request_id=_request_id(request)
                )

        return await run_in_threadpool(_run, record)
    finally:
        received.path.unlink(missing_ok=True)


@router.get("/sources/{source_id}/media", response_model=MediaList)
def list_media(
    source_id: UUID,
    _: AuthenticatedUser = Depends(reader),
    session: Session = Depends(get_speech_session),
    store: LocalMediaStore = Depends(get_media_store),
) -> MediaList:
    return _run(lambda: MediaRepository(session, store).list_media(source_id))


@router.post("/sources/{source_id}/media/delete", response_model=MediaDeletionOut)
def delete_media(
    source_id: UUID,
    data: MediaDeletion,
    request: Request,
    actor: AuthenticatedUser = Depends(administrator),
    session: Session = Depends(get_speech_session),
    store: LocalMediaStore = Depends(get_media_store),
) -> MediaDeletionOut:
    """Delete every stored file of the source, as promised on withdrawal (docs/AUDIO_CONSENT.md)."""
    return _run(
        lambda: MediaRepository(session, store).delete_media(source_id, data.reason, actor=actor, request_id=_request_id(request))
    )
