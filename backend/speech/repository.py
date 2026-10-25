"""Database access for Speech Data Lab rights and consent records.

Every change writes an audit event in the same transaction. Callers commit or roll back.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from identity.schemas import AuthenticatedUser
from models import AuditEvent, SourcePermission, SourceSpeaker, Speaker, SpeakerConsent, SpeechSource
from models.speech import CHOICE_COLUMNS
from speech import rules
from speech.rules import PermissionStatus, Platform, SpeechUse
from speech.schemas import (
    ConsentChoices,
    ConsentCreate,
    ConsentOut,
    ConsentWithdrawal,
    EligibilityOut,
    PermissionCreate,
    PermissionDecision,
    PermissionOut,
    SourceCreate,
    SourceOut,
    SpeakerCreate,
    SpeakerOut,
    UseEligibility,
)


class SpeechNotFound(LookupError):
    pass


class SpeechConflict(ValueError):
    """The request is valid but clashes with what is stored (a duplicate, or a disallowed change)."""


class SpeechForbidden(PermissionError):
    pass


DECISION_STATUS = {
    "verify": PermissionStatus.VERIFIED,
    "reject": PermissionStatus.REJECTED,
    "revoke": PermissionStatus.REVOKED,
}


def _uses(permission: SourcePermission) -> list[SpeechUse]:
    return [use for use in SpeechUse if getattr(permission, f"allow_{use.value}")]


def _permission_out(permission: SourcePermission) -> PermissionOut:
    return PermissionOut(
        id=permission.id,
        rights_holder=permission.rights_holder,
        evidence_reference=permission.evidence_reference,
        valid_until=permission.valid_until,
        uses=_uses(permission),
        status=permission.status,
        recorded_by=permission.recorded_by,
        recorded_at=permission.recorded_at,
        decided_by=permission.decided_by,
        decided_at=permission.decided_at,
        decision_note=permission.decision_note,
    )


def _consent_out(consent: SpeakerConsent) -> ConsentOut:
    return ConsentOut(
        id=consent.id,
        form_version=consent.form_version,
        form_language=consent.form_language,
        consent_method=consent.consent_method,
        consent_date=consent.consent_date,
        collector_code=consent.collector_code,
        adult_confirmed=consent.adult_confirmed,
        choices=ConsentChoices(**{choice: getattr(consent, choice) for choice in CHOICE_COLUMNS}),
        credit=consent.credit,
        withdrawn=consent.withdrawn,
        evidence_reference=consent.evidence_reference,
        recorded_at=consent.recorded_at,
    )


class SpeechRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # Audit -----------------------------------------------------------------------------------

    def _audit(
        self, actor: AuthenticatedUser, action: str, target_type: str, target_id: Any, request_id: Optional[str], **data: Any
    ) -> None:
        self.session.add(
            AuditEvent(
                actor_user_id=actor.user_id,
                action=f"speech.{action}",
                target_type=target_type,
                target_id=str(target_id),
                request_id=request_id,
                event_data=data,
            )
        )

    # Sources ---------------------------------------------------------------------------------

    def _source(self, source_id: UUID) -> SpeechSource:
        source = self.session.get(SpeechSource, source_id)
        if source is None:
            raise SpeechNotFound("source not found")
        return source

    def _source_out(self, source: SpeechSource) -> SourceOut:
        codes = self.session.scalars(
            select(Speaker.speaker_code)
            .join(SourceSpeaker, SourceSpeaker.speaker_id == Speaker.id)
            .where(SourceSpeaker.source_id == source.id)
            .order_by(Speaker.speaker_code)
        ).all()
        permissions = self.session.scalars(
            select(SourcePermission)
            .where(SourcePermission.source_id == source.id)
            .order_by(SourcePermission.recorded_at, SourcePermission.id)
        ).all()
        return SourceOut(
            id=source.id,
            platform=Platform(source.platform),
            url=source.url,
            title=source.title,
            uploader=source.uploader,
            language=source.language,
            dialect=source.dialect,
            duration_seconds=source.duration_seconds,
            acquired_on=source.acquired_on,
            notes=source.notes,
            status=source.status,
            withdrawn_at=source.withdrawn_at,
            created_at=source.created_at,
            speaker_codes=list(codes),
            permissions=[_permission_out(permission) for permission in permissions],
        )

    def register_source(self, data: SourceCreate, *, actor: AuthenticatedUser, request_id: Optional[str]) -> SourceOut:
        try:
            url = rules.normalize_source_url(data.platform, data.url)
        except rules.InvalidSourceUrl as error:
            raise ValueError(str(error)) from None
        if url is not None and self.session.scalar(select(SpeechSource.id).where(SpeechSource.url == url)):
            raise SpeechConflict("this link is already registered")
        source = SpeechSource(
            platform=data.platform.value,
            url=url,
            title=data.title,
            uploader=data.uploader,
            dialect=data.dialect,
            duration_seconds=data.duration_seconds,
            acquired_on=data.acquired_on,
            notes=data.notes,
            registered_by=actor.user_id,
        )
        self.session.add(source)
        self._flush_or_conflict("this link is already registered")
        self._audit(actor, "source_registered", "speech_source", source.id, request_id, platform=source.platform)
        self.session.flush()
        return self._source_out(source)

    def list_sources(self, *, limit: int, offset: int) -> list[SourceOut]:
        sources = self.session.scalars(
            select(SpeechSource).order_by(SpeechSource.created_at.desc(), SpeechSource.id).limit(limit).offset(offset)
        ).all()
        return [self._source_out(source) for source in sources]

    def get_source(self, source_id: UUID) -> SourceOut:
        return self._source_out(self._source(source_id))

    def withdraw_source(
        self, source_id: UUID, reason: str, *, actor: AuthenticatedUser, request_id: Optional[str]
    ) -> SourceOut:
        source = self._source(source_id)
        if source.status == "withdrawn":
            raise SpeechConflict("the source is already withdrawn")
        source.status = "withdrawn"
        source.withdrawn_at = datetime.now(timezone.utc)
        self._audit(actor, "source_withdrawn", "speech_source", source.id, request_id, reason=reason)
        self.session.flush()
        return self._source_out(source)

    # Permissions -----------------------------------------------------------------------------

    def record_permission(
        self, source_id: UUID, data: PermissionCreate, *, actor: AuthenticatedUser, request_id: Optional[str]
    ) -> PermissionOut:
        source = self._source(source_id)
        if source.status == "withdrawn":
            raise SpeechConflict("the source is withdrawn; register it again to record new permission")
        granted = set(data.uses)
        permission = SourcePermission(
            source_id=source.id,
            rights_holder=data.rights_holder,
            evidence_reference=data.evidence_reference,
            valid_until=data.valid_until,
            recorded_by=actor.user_id,
            **{f"allow_{use.value}": use in granted for use in SpeechUse},
        )
        self.session.add(permission)
        self.session.flush()
        self._audit(
            actor,
            "permission_recorded",
            "speech_source_permission",
            permission.id,
            request_id,
            source_id=str(source.id),
            uses=sorted(use.value for use in granted),
        )
        self.session.flush()
        return _permission_out(permission)

    def decide_permission(
        self,
        source_id: UUID,
        permission_id: UUID,
        data: PermissionDecision,
        *,
        actor: AuthenticatedUser,
        request_id: Optional[str],
    ) -> PermissionOut:
        permission = self.session.get(SourcePermission, permission_id, with_for_update=True)
        if permission is None or permission.source_id != source_id:
            raise SpeechNotFound("permission not found")
        if permission.recorded_by is not None and permission.recorded_by == actor.user_id:
            raise SpeechForbidden("a permission must be verified, rejected, or revoked by someone other than its recorder")
        new_status = DECISION_STATUS[data.decision]
        current = PermissionStatus(permission.status)
        if not rules.can_transition(current, new_status):
            raise SpeechConflict(f"a {current.value} permission cannot be changed to {new_status.value}")
        permission.status = new_status.value
        permission.decided_by = actor.user_id
        permission.decided_at = datetime.now(timezone.utc)
        permission.decision_note = data.note
        self._audit(
            actor,
            f"permission_{new_status.value}",
            "speech_source_permission",
            permission.id,
            request_id,
            source_id=str(source_id),
            previous_status=current.value,
        )
        self.session.flush()
        return _permission_out(permission)

    # Speakers and consent --------------------------------------------------------------------

    def _speaker(self, speaker_code: str) -> Speaker:
        speaker = self.session.scalar(select(Speaker).where(Speaker.speaker_code == speaker_code))
        if speaker is None:
            raise SpeechNotFound("speaker not found")
        return speaker

    def _current_consent(self, speaker_id: UUID) -> Optional[SpeakerConsent]:
        return self.session.scalar(
            select(SpeakerConsent).where(SpeakerConsent.speaker_id == speaker_id).order_by(SpeakerConsent.id.desc()).limit(1)
        )

    def _speaker_out(self, speaker: Speaker) -> SpeakerOut:
        consent = self._current_consent(speaker.id)
        return SpeakerOut(
            id=speaker.id,
            speaker_code=speaker.speaker_code,
            dialect_region=speaker.dialect_region,
            age_range=speaker.age_range,
            current_consent=_consent_out(consent) if consent else None,
        )

    def create_speaker(self, data: SpeakerCreate, *, actor: AuthenticatedUser, request_id: Optional[str]) -> SpeakerOut:
        if self.session.scalar(select(Speaker.id).where(Speaker.speaker_code == data.speaker_code)):
            raise SpeechConflict("this speaker code is already in use")
        speaker = Speaker(
            speaker_code=data.speaker_code,
            dialect_region=data.dialect_region,
            age_range=data.age_range,
            created_by=actor.user_id,
        )
        self.session.add(speaker)
        self._flush_or_conflict("this speaker code is already in use")
        self._audit(actor, "speaker_created", "speaker", speaker.id, request_id, speaker_code=speaker.speaker_code)
        self.session.flush()
        return self._speaker_out(speaker)

    def list_speakers(self, *, limit: int, offset: int) -> list[SpeakerOut]:
        speakers = self.session.scalars(select(Speaker).order_by(Speaker.speaker_code).limit(limit).offset(offset)).all()
        return [self._speaker_out(speaker) for speaker in speakers]

    def record_consent(
        self, speaker_code: str, data: ConsentCreate, *, actor: AuthenticatedUser, request_id: Optional[str]
    ) -> SpeakerOut:
        speaker = self._speaker(speaker_code)
        consent = SpeakerConsent(
            speaker_id=speaker.id,
            form_version=data.form_version,
            form_language=data.form_language,
            consent_method=data.consent_method,
            consent_date=data.consent_date,
            collector_code=data.collector_code,
            adult_confirmed=data.adult_confirmed,
            credit=data.credit,
            withdrawn=False,
            evidence_reference=data.evidence_reference,
            recorded_by=actor.user_id,
            **data.choices.model_dump(),
        )
        self.session.add(consent)
        self.session.flush()
        self._audit(
            actor,
            "consent_recorded",
            "speaker",
            speaker.id,
            request_id,
            consent_id=consent.id,
            form_version=consent.form_version,
            choices=data.choices.model_dump(),
        )
        self.session.flush()
        return self._speaker_out(speaker)

    def withdraw_consent(
        self, speaker_code: str, data: ConsentWithdrawal, *, actor: AuthenticatedUser, request_id: Optional[str]
    ) -> SpeakerOut:
        """Withdrawal is a new consent record granting nothing. Earlier records stay as evidence."""
        speaker = self._speaker(speaker_code)
        current = self._current_consent(speaker.id)
        if current is None:
            raise SpeechConflict("the speaker has no consent to withdraw")
        if current.withdrawn:
            raise SpeechConflict("the speaker's consent is already withdrawn")
        withdrawal = SpeakerConsent(
            speaker_id=speaker.id,
            form_version=current.form_version,
            form_language=current.form_language,
            consent_method=current.consent_method,
            consent_date=data.withdrawn_on,
            collector_code=current.collector_code,
            adult_confirmed=current.adult_confirmed,
            credit=current.credit,
            withdrawn=True,
            evidence_reference=data.evidence_reference,
            recorded_by=actor.user_id,
            **{choice: False for choice in CHOICE_COLUMNS},
        )
        self.session.add(withdrawal)
        self.session.flush()
        self._audit(actor, "consent_withdrawn", "speaker", speaker.id, request_id, consent_id=withdrawal.id)
        self.session.flush()
        return self._speaker_out(speaker)

    def link_speaker(
        self, source_id: UUID, speaker_code: str, *, actor: AuthenticatedUser, request_id: Optional[str]
    ) -> SourceOut:
        source = self._source(source_id)
        speaker = self._speaker(speaker_code)
        if self.session.get(SourceSpeaker, (source.id, speaker.id)) is None:
            self.session.add(SourceSpeaker(source_id=source.id, speaker_id=speaker.id, added_by=actor.user_id))
            self._flush_or_conflict("the speaker is already linked to this source")
            self._audit(
                actor, "speaker_linked", "speech_source", source.id, request_id, speaker_code=speaker.speaker_code
            )
            self.session.flush()
        return self._source_out(source)

    # Eligibility -----------------------------------------------------------------------------

    def eligibility(self, source_id: UUID, *, today: date) -> EligibilityOut:
        source = self._source(source_id)
        permissions = self.session.scalars(select(SourcePermission).where(SourcePermission.source_id == source.id)).all()
        speakers = self.session.scalars(
            select(Speaker).join(SourceSpeaker, SourceSpeaker.speaker_id == Speaker.id).where(SourceSpeaker.source_id == source.id)
        ).all()
        consents = {}
        for speaker in speakers:
            consent = self._current_consent(speaker.id)
            if consent is not None:
                consents[speaker.speaker_code] = rules.ConsentFacts(
                    speaker_code=speaker.speaker_code,
                    withdrawn=consent.withdrawn,
                    adult_confirmed=consent.adult_confirmed,
                    choices={choice: getattr(consent, choice) for choice in CHOICE_COLUMNS},
                )
        facts = [
            rules.PermissionFacts(PermissionStatus(permission.status), frozenset(_uses(permission)), permission.valid_until)
            for permission in permissions
        ]
        results = [
            rules.eligibility(
                use,
                source_withdrawn=source.status == "withdrawn",
                permissions=facts,
                speaker_codes=[speaker.speaker_code for speaker in speakers],
                consents=consents,
                today=today,
            )
            for use in SpeechUse
        ]
        return EligibilityOut(
            source_id=source.id,
            checked_on=today,
            uses=[UseEligibility(use=result.use, allowed=result.allowed, reasons=list(result.reasons)) for result in results],
        )

    # ------------------------------------------------------------------------------------------

    def _flush_or_conflict(self, message: str) -> None:
        # A concurrent request can insert the same link or code between the check and the insert;
        # the unique constraint catches it, inside a savepoint so the session stays usable.
        savepoint = self.session.begin_nested()
        try:
            self.session.flush()
        except IntegrityError:
            savepoint.rollback()
            raise SpeechConflict(message) from None
        savepoint.commit()
