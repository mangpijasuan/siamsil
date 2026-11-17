from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from speech.rules import (  # noqa: E402
    ConsentFacts,
    InvalidSourceUrl,
    PermissionFacts,
    PermissionStatus,
    Platform,
    SpeechUse,
    can_transition,
    eligibility,
    normalize_source_url,
)

TODAY = date(2026, 10, 25)
ALL_USES = frozenset(SpeechUse)
YES = {
    "keep_and_evaluate": True,
    "train_recognition": True,
    "train_synthesis": True,
    "play_in_app": True,
    "public_dataset": True,
    "commercial_use": True,
}


def consent(code: str = "S0001", **overrides: object) -> ConsentFacts:
    choices = {**YES, **{key: value for key, value in overrides.items() if key in YES}}
    return ConsentFacts(
        speaker_code=code,
        withdrawn=bool(overrides.get("withdrawn", False)),
        adult_confirmed=bool(overrides.get("adult_confirmed", True)),
        choices=choices,
    )


def verified(uses=ALL_USES, valid_until=None) -> PermissionFacts:
    return PermissionFacts(PermissionStatus.VERIFIED, frozenset(uses), valid_until)


def check(use, *, permissions=(verified(),), speakers=("S0001",), consents=None, withdrawn=False):
    return eligibility(
        use,
        source_withdrawn=withdrawn,
        permissions=permissions,
        speaker_codes=speakers,
        consents={"S0001": consent()} if consents is None else consents,
        today=TODAY,
    )


class SourceUrlTests(unittest.TestCase):
    def test_platform_links_are_normalized(self) -> None:
        self.assertEqual(
            normalize_source_url(Platform.YOUTUBE, " https://WWW.YouTube.com/watch?v=abc123#t=30 "),
            "https://www.youtube.com/watch?v=abc123",
        )
        self.assertEqual(normalize_source_url(Platform.YOUTUBE, "https://youtu.be/abc123"), "https://youtu.be/abc123")
        self.assertEqual(
            normalize_source_url(Platform.FACEBOOK, "https://fb.watch/xyz/"), "https://fb.watch/xyz/"
        )
        self.assertEqual(normalize_source_url(Platform.OTHER, "https://example.org"), "https://example.org/")

    def test_unsafe_or_mismatched_links_are_refused(self) -> None:
        cases = [
            (Platform.YOUTUBE, "http://www.youtube.com/watch?v=abc", "https://"),
            (Platform.YOUTUBE, "javascript:alert(1)", "https://"),
            (Platform.YOUTUBE, "https://user:secret@www.youtube.com/watch?v=abc", "user name or password"),
            (Platform.YOUTUBE, "https://www.youtube.com.example.net/watch?v=abc", "is not a youtube address"),
            (Platform.FACEBOOK, "https://www.youtube.com/watch?v=abc", "is not a facebook address"),
            (Platform.OTHER, "https://youtu.be/abc", "choose that platform"),
            (Platform.OTHER, "https://localhost/file", "no valid host"),
            (Platform.YOUTUBE, "", "required"),
            (Platform.CREATOR_FILE, "https://example.org/file.mp3", "has no link"),
        ]
        for platform, url, message in cases:
            with self.subTest(platform=platform, url=url), self.assertRaisesRegex(InvalidSourceUrl, message):
                normalize_source_url(platform, url)

    def test_creator_file_has_no_link(self) -> None:
        self.assertIsNone(normalize_source_url(Platform.CREATOR_FILE, None))


class PermissionTransitionTests(unittest.TestCase):
    def test_only_forward_decisions_are_allowed(self) -> None:
        allowed = {
            (PermissionStatus.PENDING, PermissionStatus.VERIFIED),
            (PermissionStatus.PENDING, PermissionStatus.REJECTED),
            (PermissionStatus.VERIFIED, PermissionStatus.REVOKED),
        }
        for current in PermissionStatus:
            for new in PermissionStatus:
                with self.subTest(current=current, new=new):
                    self.assertEqual(can_transition(current, new), (current, new) in allowed)


class EligibilityTests(unittest.TestCase):
    def test_every_use_is_allowed_only_with_verified_rights_and_consent(self) -> None:
        for use in SpeechUse:
            with self.subTest(use=use):
                result = check(use)
                self.assertTrue(result.allowed, result.reasons)

    def test_nothing_is_allowed_without_a_verified_permission(self) -> None:
        for permissions in ((), (PermissionFacts(PermissionStatus.PENDING, ALL_USES),),
                            (PermissionFacts(PermissionStatus.REJECTED, ALL_USES),),
                            (PermissionFacts(PermissionStatus.REVOKED, ALL_USES),)):
            for use in SpeechUse:
                with self.subTest(permissions=permissions, use=use):
                    result = check(use, permissions=permissions)
                    self.assertFalse(result.allowed)
                    self.assertIn(f"no verified, current permission from the rights holder grants {use.value}", result.reasons)

    def test_a_permission_covers_only_the_uses_it_names(self) -> None:
        permissions = (verified({SpeechUse.TRANSCRIPTION, SpeechUse.ASR_TRAINING}),)
        allowed = {use for use in SpeechUse if check(use, permissions=permissions).allowed}
        self.assertEqual(allowed, {SpeechUse.TRANSCRIPTION, SpeechUse.ASR_TRAINING})

    def test_an_expired_permission_grants_nothing(self) -> None:
        self.assertFalse(check(SpeechUse.ASR_TRAINING, permissions=(verified(valid_until=date(2026, 10, 24)),)).allowed)
        self.assertTrue(check(SpeechUse.ASR_TRAINING, permissions=(verified(valid_until=TODAY),)).allowed)

    def test_voice_synthesis_needs_its_own_yes(self) -> None:
        consents = {"S0001": consent(train_synthesis=False)}
        self.assertTrue(check(SpeechUse.ASR_TRAINING, consents=consents).allowed)
        result = check(SpeechUse.TTS_TRAINING, consents=consents)
        self.assertFalse(result.allowed)
        self.assertEqual(result.reasons, ("S0001 has not consented to tts_training (train_synthesis)",))

    def test_withdrawn_consent_blocks_every_use(self) -> None:
        consents = {"S0001": consent(withdrawn=True)}
        for use in SpeechUse:
            with self.subTest(use=use):
                self.assertIn("S0001 has withdrawn consent", check(use, consents=consents).reasons)

    def test_every_speaker_on_the_source_must_consent(self) -> None:
        result = check(SpeechUse.ASR_TRAINING, speakers=("S0001", "S0002"))
        self.assertFalse(result.allowed)
        self.assertEqual(result.reasons, ("S0002 has no consent record",))

    def test_a_source_without_speakers_is_not_eligible(self) -> None:
        self.assertFalse(check(SpeechUse.TRANSCRIPTION, speakers=()).allowed)

    def test_an_unconfirmed_adult_is_not_eligible(self) -> None:
        result = check(SpeechUse.TRANSCRIPTION, consents={"S0001": consent(adult_confirmed=False)})
        self.assertEqual(result.reasons, ("S0001 is not confirmed as an adult",))

    def test_a_withdrawn_source_is_not_eligible(self) -> None:
        result = check(SpeechUse.TRANSCRIPTION, withdrawn=True)
        self.assertEqual(result.reasons, ("the source has been withdrawn",))

    def test_every_reason_is_reported(self) -> None:
        result = check(SpeechUse.TTS_TRAINING, permissions=(), consents={}, withdrawn=True)
        self.assertEqual(len(result.reasons), 3)


if __name__ == "__main__":
    unittest.main()
