from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from speech.rules import (
    COLLECTOR_CODE,
    CONSENT_FORM_VERSION,
    SPEAKER_CODE,
    Platform,
    SpeechUse,
)

# A pointer to evidence kept in private storage (a siamsil-data path, a ticket, a file ID), never the
# evidence itself: consent and permission documents identify people and stay out of this database.
EvidenceReference = Field(min_length=3, max_length=500, pattern=r"^[^\r\n]+$")
ShortText = Field(min_length=1, max_length=500)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceCreate(Strict):
    platform: Platform
    url: Optional[str] = Field(default=None, max_length=2000)
    title: str = ShortText
    uploader: Optional[str] = Field(default=None, max_length=500)
    dialect: Optional[str] = Field(default=None, max_length=200)
    duration_seconds: Optional[int] = Field(default=None, ge=0, le=86_400)
    acquired_on: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=4000)


class PermissionCreate(Strict):
    rights_holder: str = ShortText
    evidence_reference: str = EvidenceReference
    valid_until: Optional[date] = None
    uses: list[SpeechUse] = Field(max_length=len(SpeechUse))

    @field_validator("uses")
    @classmethod
    def no_repeats(cls, uses: list[SpeechUse]) -> list[SpeechUse]:
        if len(set(uses)) != len(uses):
            raise ValueError("each use may be listed once")
        return uses


class PermissionDecision(Strict):
    decision: Literal["verify", "reject", "revoke"]
    note: Optional[str] = Field(default=None, max_length=2000)


class PermissionOut(BaseModel):
    id: UUID
    rights_holder: str
    evidence_reference: str
    valid_until: Optional[date]
    uses: list[SpeechUse]
    status: str
    recorded_by: Optional[UUID]
    recorded_at: datetime
    decided_by: Optional[UUID]
    decided_at: Optional[datetime]
    decision_note: Optional[str]


class SourceOut(BaseModel):
    id: UUID
    platform: Platform
    url: Optional[str]
    title: str
    uploader: Optional[str]
    language: str
    dialect: Optional[str]
    duration_seconds: Optional[int]
    acquired_on: Optional[date]
    notes: Optional[str]
    status: str
    withdrawn_at: Optional[datetime]
    created_at: datetime
    speaker_codes: list[str]
    permissions: list[PermissionOut]


class SourceList(BaseModel):
    sources: list[SourceOut]


class SourceWithdrawal(Strict):
    reason: str = Field(min_length=3, max_length=2000)


class SpeakerCreate(Strict):
    speaker_code: str = Field(pattern=SPEAKER_CODE.pattern)
    dialect_region: Optional[str] = Field(default=None, max_length=200)
    age_range: Optional[str] = Field(default=None, pattern=r"^[0-9]{2}-[0-9]{2}$|^[0-9]{2}\+$")


class ConsentChoices(Strict):
    """The six separate answers on the consent form. Each must be given; none defaults to yes."""

    keep_and_evaluate: bool
    train_recognition: bool
    train_synthesis: bool
    play_in_app: bool
    public_dataset: bool
    commercial_use: bool


class ConsentCreate(Strict):
    form_version: str = Field(pattern=CONSENT_FORM_VERSION.pattern)
    form_language: str = Field(min_length=2, max_length=32)
    consent_method: Literal["written", "oral"]
    consent_date: date
    collector_code: str = Field(pattern=COLLECTOR_CODE.pattern)
    adult_confirmed: bool
    choices: ConsentChoices
    credit: Literal["name", "initials", "none"]
    evidence_reference: str = EvidenceReference

    @field_validator("adult_confirmed")
    @classmethod
    def adults_only(cls, confirmed: bool) -> bool:
        # docs/AUDIO_CONSENT.md: no recordings of anyone under 18 until a guardian process is reviewed.
        if not confirmed:
            raise ValueError("Siamsil records adults only; the speaker must be confirmed as 18 or older")
        return confirmed


class ConsentWithdrawal(Strict):
    withdrawn_on: date
    evidence_reference: str = EvidenceReference


class ConsentOut(BaseModel):
    id: int
    form_version: str
    form_language: str
    consent_method: str
    consent_date: date
    collector_code: str
    adult_confirmed: bool
    choices: ConsentChoices
    credit: str
    withdrawn: bool
    evidence_reference: str
    recorded_at: datetime


class SpeakerOut(BaseModel):
    id: UUID
    speaker_code: str
    dialect_region: Optional[str]
    age_range: Optional[str]
    current_consent: Optional[ConsentOut]


class SpeakerList(BaseModel):
    speakers: list[SpeakerOut]


class UseEligibility(BaseModel):
    use: SpeechUse
    allowed: bool
    reasons: list[str]


class EligibilityOut(BaseModel):
    source_id: UUID
    checked_on: date
    uses: list[UseEligibility]
