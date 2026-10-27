"""Speech Data Lab API: sources, rights, speakers, and consent (docs/SPEECH_DATA_LAB.md, PR 1).

Only administrators register sources, record permissions and consent, and withdraw.
Administrators and editors can read. A permission is decided by a different administrator
from the one who recorded it. Nothing here downloads media or fetches a link.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from database import get_session_factory
from identity.dependencies import require_roles
from identity.schemas import AuthenticatedUser, RoleName
from speech.repository import SpeechConflict, SpeechForbidden, SpeechNotFound, SpeechRepository
from speech.schemas import (
    ConsentCreate,
    ConsentWithdrawal,
    EligibilityOut,
    PermissionCreate,
    PermissionDecision,
    PermissionOut,
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


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _run(action):
    try:
        return action()
    except SpeechNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from None
    except SpeechForbidden as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from None
    except SpeechConflict as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None


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
