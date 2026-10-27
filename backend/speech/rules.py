"""Rights and consent rules for the Speech Data Lab (docs/SPEECH_DATA_LAB.md).

Pure functions, no database, so every rule is easy to test and reuse. The default is
always "not allowed": a use is permitted only when the source's rights holder granted it
in a verified, current permission AND every speaker on the source currently consents to
it (docs/AUDIO_CONSENT.md). A public video is never treated as cleared by being public.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Iterable, Optional
from urllib.parse import urlsplit, urlunsplit


class SpeechUse(str, Enum):
    """What a recording may be used for. Each is granted or refused separately."""

    TRANSCRIPTION = "transcription"  # keep, transcribe, and evaluate internally
    ASR_TRAINING = "asr_training"  # train speech recognition
    TTS_TRAINING = "tts_training"  # train speech synthesis: can produce speech that sounds like the speaker
    PLAYBACK = "playback"  # play the recording itself in the app
    REDISTRIBUTION = "redistribution"  # publish in a dataset for others
    COMMERCIAL = "commercial"  # use in paid services


# Each use and the speaker's consent choice that must also say yes (AUDIO_CONSENT.md, questions 1-6).
CONSENT_CHOICE = {
    SpeechUse.TRANSCRIPTION: "keep_and_evaluate",
    SpeechUse.ASR_TRAINING: "train_recognition",
    SpeechUse.TTS_TRAINING: "train_synthesis",
    SpeechUse.PLAYBACK: "play_in_app",
    SpeechUse.REDISTRIBUTION: "public_dataset",
    SpeechUse.COMMERCIAL: "commercial_use",
}
CONSENT_CHOICES = tuple(CONSENT_CHOICE.values())


class Platform(str, Enum):
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    OTHER = "other"  # any other https page that identifies the work
    CREATOR_FILE = "creator_file"  # no public link: the creator gave Siamsil the file


PLATFORM_HOSTS = {
    Platform.YOUTUBE: {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"},
    Platform.FACEBOOK: {"facebook.com", "www.facebook.com", "m.facebook.com", "web.facebook.com", "fb.watch"},
}


class PermissionStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    REVOKED = "revoked"


# Allowed status changes. Anything else is refused; a rejected or revoked permission is final
# (record a new permission instead), so the history of what was allowed when stays intact.
PERMISSION_TRANSITIONS = {
    PermissionStatus.PENDING: {PermissionStatus.VERIFIED, PermissionStatus.REJECTED},
    PermissionStatus.VERIFIED: {PermissionStatus.REVOKED},
    PermissionStatus.REJECTED: set(),
    PermissionStatus.REVOKED: set(),
}

SPEAKER_CODE = re.compile(r"^S[0-9]{4,6}$")
COLLECTOR_CODE = re.compile(r"^C[0-9]{2,4}$")
CONSENT_FORM_VERSION = re.compile(r"^audio-consent-v[0-9]{1,3}$")
CONSENT_METHODS = ("written", "oral")
CREDIT_CHOICES = ("name", "initials", "none")


class InvalidSourceUrl(ValueError):
    pass


def normalize_source_url(platform: Platform, url: Optional[str]) -> Optional[str]:
    """Check and normalize a source link. Siamsil stores links; it never fetches them.

    https only, no embedded credentials, host must match the platform, fragment dropped.
    A creator-provided file has no link.
    """
    if platform is Platform.CREATOR_FILE:
        if url:
            raise InvalidSourceUrl("a creator-provided file has no link; choose the platform the link is on")
        return None
    if not url or not url.strip():
        raise InvalidSourceUrl("a link is required for this platform")
    parts = urlsplit(url.strip())
    if parts.scheme.lower() != "https":
        raise InvalidSourceUrl("links must start with https://")
    if parts.username or parts.password:
        raise InvalidSourceUrl("links must not contain a user name or password")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host or "." not in host:
        raise InvalidSourceUrl("the link has no valid host")
    allowed = PLATFORM_HOSTS.get(platform)
    if allowed is not None and host not in allowed:
        raise InvalidSourceUrl(f"{host} is not a {platform.value} address")
    if platform is Platform.OTHER and any(host in hosts for hosts in PLATFORM_HOSTS.values()):
        raise InvalidSourceUrl(f"{host} belongs to a listed platform; choose that platform")
    port = f":{parts.port}" if parts.port and parts.port != 443 else ""
    return urlunsplit(("https", host + port, parts.path or "/", parts.query, ""))


def can_transition(current: PermissionStatus, new: PermissionStatus) -> bool:
    return new in PERMISSION_TRANSITIONS[current]


@dataclass(frozen=True)
class PermissionFacts:
    status: PermissionStatus
    uses: frozenset[SpeechUse]
    valid_until: Optional[date] = None


@dataclass(frozen=True)
class ConsentFacts:
    """A speaker's current consent: their latest consent record."""

    speaker_code: str
    withdrawn: bool
    adult_confirmed: bool
    choices: dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class Eligibility:
    use: SpeechUse
    allowed: bool
    reasons: tuple[str, ...]


def eligibility(
    use: SpeechUse,
    *,
    source_withdrawn: bool,
    permissions: Iterable[PermissionFacts],
    speaker_codes: Iterable[str],
    consents: dict[str, ConsentFacts],
    today: date,
) -> Eligibility:
    """Whether a source's recordings may be used for `use` today, and if not, every reason why."""
    reasons: list[str] = []
    if source_withdrawn:
        reasons.append("the source has been withdrawn")

    granted = [
        permission
        for permission in permissions
        if permission.status is PermissionStatus.VERIFIED
        and use in permission.uses
        and (permission.valid_until is None or permission.valid_until >= today)
    ]
    if not granted:
        reasons.append(f"no verified, current permission from the rights holder grants {use.value}")

    speakers = sorted(set(speaker_codes))
    if not speakers:
        reasons.append("no speakers are recorded for this source, so no speaker consent can be checked")
    choice = CONSENT_CHOICE[use]
    for code in speakers:
        consent = consents.get(code)
        if consent is None:
            reasons.append(f"{code} has no consent record")
        elif consent.withdrawn:
            reasons.append(f"{code} has withdrawn consent")
        elif not consent.adult_confirmed:
            reasons.append(f"{code} is not confirmed as an adult")
        elif consent.choices.get(choice) is not True:
            reasons.append(f"{code} has not consented to {use.value} ({choice})")

    return Eligibility(use, not reasons, tuple(reasons))
