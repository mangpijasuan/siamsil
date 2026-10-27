from __future__ import annotations

import asyncio
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_database_engine  # noqa: E402
from identity.dependencies import get_current_user  # noqa: E402
from main import app  # noqa: E402
from models import AudioProcessingJob, AuditEvent, MediaAsset, User  # noqa: E402
from settings import get_settings  # noqa: E402
from speech import audio, media  # noqa: E402
from speech.ingest import MediaTooLarge, UnsupportedMedia, receive  # noqa: E402
from speech.jobs import JobRunner, WorkerSettings  # noqa: E402
from speech.media import LocalMediaStore  # noqa: E402
from speech.router import get_media_store, get_speech_session, get_speech_transactions  # noqa: E402
from tests.test_speech_api import CONSENT, person  # noqa: E402

HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def make_media(folder: Path) -> dict[str, Path]:
    """Synthetic test tones (no speech) in every accepted format, plus a video with no audio."""
    def ffmpeg(*args: str) -> None:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args], check=True)

    files = {name: folder / name for name in ("tone.wav", "tone.mp3", "tone.m4a", "tone.mp4", "silent-video.mp4")}
    ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-ar", "44100", "-ac", "2", str(files["tone.wav"]))
    ffmpeg("-i", str(files["tone.wav"]), str(files["tone.mp3"]))
    ffmpeg("-i", str(files["tone.wav"]), "-c:a", "aac", str(files["tone.m4a"]))
    ffmpeg("-f", "lavfi", "-i", "color=size=64x64:duration=2", "-i", str(files["tone.wav"]), "-shortest",
           "-c:v", "libx264", "-c:a", "aac", str(files["tone.mp4"]))
    ffmpeg("-f", "lavfi", "-i", "color=size=64x64:duration=1", "-c:v", "libx264", str(files["silent-video.mp4"]))
    return files


async def chunks(data: bytes, size: int = 7):
    for start in range(0, len(data), size):
        yield data[start : start + size]


class SniffTests(unittest.TestCase):
    def test_accepted_formats_are_recognized_from_their_bytes(self) -> None:
        self.assertIs(media.sniff(b"RIFF\x24\x00\x00\x00WAVEfmt "), media.WAV)
        self.assertIs(media.sniff(b"ID3\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"), media.MP3)
        self.assertIs(media.sniff(b"\xff\xfb\x90\x64" + b"\x00" * 12), media.MP3)  # MPEG-1 Layer III frame
        self.assertIs(media.sniff(b"\x00\x00\x00\x20ftypM4A \x00\x00\x00\x00"), media.M4A)
        self.assertIs(media.sniff(b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00"), media.MP4)

    def test_anything_else_is_refused(self) -> None:
        for head in (
            b"",
            b"just some text....",
            b"\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00",  # QuickTime
            b"\xff\xfd\x90\x64" + b"\x00" * 12,  # MPEG Layer II, not MP3
            b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
            b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n\n\n\n",
            b"#EXTM3U\nhttp://x/\n",
        ):
            with self.subTest(head=head):
                self.assertIsNone(media.sniff(head))


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder)
        self.store = LocalMediaStore(self.folder / "media")
        self.source = uuid.uuid4()

    def test_files_are_private_and_written_once(self) -> None:
        original = self.folder / "in.wav"
        original.write_bytes(b"first")
        key = self.store.key(self.source, "original", "a" * 64, "wav")
        self.assertEqual(key, f"{self.source}/original/{'a' * 64}.wav")
        self.store.put(key, original)
        path = self.store.path(key)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.store.root.stat().st_mode), 0o700)
        original.write_bytes(b"second")
        self.store.put(key, original)  # same key: the stored file is kept
        self.assertEqual(path.read_bytes(), b"first")
        self.assertEqual([p.name for p in path.parent.iterdir()], [path.name])  # no temporary files left
        self.assertTrue(self.store.delete(key))
        self.assertFalse(self.store.delete(key))

    def test_keys_cannot_escape_the_media_folder(self) -> None:
        for args in (("original", "../" * 3, "wav"), ("original", "a" * 64, "wav/../x"), ("other", "a" * 64, "wav")):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.store.key(self.source, *args)
        with self.assertRaises(ValueError):
            self.store.path("../outside.wav")


class ReceiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder)

    def receive(self, data: bytes, max_bytes: int = 10_000):
        return asyncio.run(receive(chunks(data), folder=self.folder, max_bytes=max_bytes))

    def test_a_valid_upload_is_hashed_and_kept(self) -> None:
        data = b"RIFF\x24\x00\x00\x00WAVEfmt " + bytes(range(200))
        received = self.receive(data)
        self.assertEqual(received.format, media.WAV)
        self.assertEqual(received.size_bytes, len(data))
        self.assertEqual(received.sha256, __import__("hashlib").sha256(data).hexdigest())
        self.assertEqual(received.path.read_bytes(), data)

    def test_refused_uploads_leave_nothing_behind(self) -> None:
        cases = [
            (b"RIFF\x24\x00\x00\x00WAVEfmt " + b"x" * 500, 100, MediaTooLarge),
            (b"<html>not audio at all</html>", 10_000, UnsupportedMedia),
            (b"RIFF", 10_000, UnsupportedMedia),
            (b"", 10_000, UnsupportedMedia),
        ]
        for data, limit, error in cases:
            with self.subTest(data=data[:12]), self.assertRaises(error):
                self.receive(data, limit)
        self.assertEqual(list(self.folder.iterdir()), [])


@unittest.skipUnless(HAVE_FFMPEG, "FFmpeg is not installed")
class AudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.folder = Path(tempfile.mkdtemp())
        cls.files = make_media(cls.folder)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.folder)

    def test_every_format_becomes_the_same_kind_of_working_copy_every_time(self) -> None:
        for name in ("tone.wav", "tone.mp3", "tone.m4a", "tone.mp4"):
            with self.subTest(name=name):
                fmt = media.sniff(self.files[name].read_bytes()[:16])
                self.assertIsNotNone(fmt)
                outputs = []
                for run in range(2):
                    target = self.folder / f"{name}.{run}.wav"
                    audio.normalize("ffmpeg", self.files[name], fmt.demuxer, target, timeout=60)
                    outputs.append(target.read_bytes())
                self.assertEqual(outputs[0], outputs[1])
                probe = audio.probe("ffprobe", self.folder / f"{name}.0.wav", "wav")
                self.assertEqual((probe.sample_rate, probe.channels, probe.codec), (16000, 1, "pcm_s16le"))
                self.assertAlmostEqual(probe.duration_seconds, 2.0, delta=0.1)

    def test_a_file_without_audio_is_refused(self) -> None:
        with self.assertRaisesRegex(audio.AudioError, "no audio stream"):
            audio.probe("ffprobe", self.files["silent-video.mp4"], "mov")

    def test_the_declared_format_is_enforced(self) -> None:
        with self.assertRaises(audio.AudioError):
            audio.probe("ffprobe", self.files["tone.mp3"], "wav")


class MediaAccessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_media_endpoints_require_sign_in_and_the_right_role(self) -> None:
        source = uuid.uuid4()
        upload = f"/api/v1/speech/sources/{source}/media?provenance=creator_provided"
        listing = f"/api/v1/speech/sources/{source}/media"
        deletion = f"/api/v1/speech/sources/{source}/media/delete"
        self.assertEqual(self.client.post(upload, content=b"RIFF").status_code, 401)
        self.assertEqual(self.client.get(listing).status_code, 401)
        self.assertEqual(self.client.post(deletion, json={"reason": "test"}).status_code, 401)
        app.dependency_overrides[get_speech_session] = lambda: iter([None])
        app.dependency_overrides[get_speech_transactions] = lambda: None
        for roles in (("editor",), ("reviewer",), ("contributor",)):
            with self.subTest(roles=roles):
                app.dependency_overrides[get_current_user] = lambda roles=roles: person(*roles)
                self.assertEqual(self.client.post(upload, content=b"RIFF").status_code, 403)
                self.assertEqual(self.client.post(deletion, json={"reason": "test"}).status_code, 403)
        app.dependency_overrides[get_current_user] = lambda: person("reviewer")
        self.assertEqual(self.client.get(listing).status_code, 403)

    def test_provenance_must_be_stated(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: person("administrator")
        app.dependency_overrides[get_speech_transactions] = lambda: None
        source = uuid.uuid4()
        for query in ("", "?provenance=downloaded", "?provenance=scraped"):
            with self.subTest(query=query):
                response = self.client.post(f"/api/v1/speech/sources/{source}/media{query}", content=b"RIFF")
                self.assertEqual(response.status_code, 422)


@unittest.skipUnless(HAVE_FFMPEG, "FFmpeg is not installed")
@unittest.skipUnless(os.getenv("SIAMSIL_DATABASE_URL"), "application database is not configured")
class MediaWorkflowTests(unittest.TestCase):
    """Upload, processing, withdrawal, and deletion against PostgreSQL, rolled back afterwards."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = Path(tempfile.mkdtemp())
        cls.files = make_media(cls.fixtures)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.fixtures)

    def setUp(self) -> None:
        engine = get_database_engine()
        if engine is None:
            self.skipTest("application database is not configured")
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.session = Session(bind=self.connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
        admins = [User(display_name=f"Admin {n}") for n in (1, 2)]
        self.session.add_all(admins)
        self.session.flush()
        self.admin, self.second_admin = (person("administrator", user_id=admin.id) for admin in admins)
        self.media_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.media_dir)
        self.store = LocalMediaStore(self.media_dir / "media")

        def session_for_request():
            yield self.session
            self.session.flush()

        app.dependency_overrides[get_speech_session] = session_for_request
        app.dependency_overrides[get_speech_transactions] = lambda: self.transactions
        app.dependency_overrides[get_media_store] = lambda: self.store
        self.client = TestClient(app)
        self.as_user(self.admin)
        self.runner = self.worker()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.session.close()
        self.transaction.rollback()
        self.connection.close()

    @contextmanager
    def transactions(self):
        yield self.session
        self.session.flush()

    def worker(self, name: str = "worker-a") -> JobRunner:
        return JobRunner(
            self.transactions,
            self.store,
            WorkerSettings(ffmpeg="ffmpeg", ffprobe="ffprobe", lease_seconds=600, max_attempts=3),
            worker_id=name,
        )

    def as_user(self, user) -> None:
        app.dependency_overrides[get_current_user] = lambda: user

    def post(self, path: str, body: dict) -> dict:
        response = self.client.post(path, json=body)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def cleared_source(self, speaker: str = "S0001") -> str:
        """A creator's file with a verified permission and a consenting speaker: transcription allowed."""
        source = self.post("/api/v1/speech/sources", {"platform": "creator_file", "title": f"Pilot {speaker}"})["id"]
        permission = self.post(
            f"/api/v1/speech/sources/{source}/permissions",
            {"rights_holder": "The creator", "evidence_reference": "siamsil-data/permissions/p1", "uses": ["transcription"]},
        )
        self.as_user(self.second_admin)
        self.post(f"/api/v1/speech/sources/{source}/permissions/{permission['id']}/decision", {"decision": "verify"})
        self.as_user(self.admin)
        self.post("/api/v1/speech/speakers", {"speaker_code": speaker})
        self.post(f"/api/v1/speech/speakers/{speaker}/consents", CONSENT)
        self.post(f"/api/v1/speech/sources/{source}/speakers/{speaker}", {})
        return source

    def upload(self, source: str, name: str, provenance: str = "creator_provided"):
        return self.client.post(
            f"/api/v1/speech/sources/{source}/media?provenance={provenance}", content=self.files[name].read_bytes()
        )

    def test_upload_process_withdraw_and_delete(self) -> None:
        # Nothing is accepted for a source that is not cleared, and nothing is written.
        uncleared = self.post("/api/v1/speech/sources", {"platform": "creator_file", "title": "Not cleared"})["id"]
        refused = self.upload(uncleared, "tone.wav")
        self.assertEqual(refused.status_code, 409)
        self.assertIn("no verified, current permission", refused.json()["error"]["message"])
        self.assertFalse((self.store.root / uncleared).exists())

        source = self.cleared_source()
        response = self.upload(source, "tone.mp3")
        self.assertEqual(response.status_code, 200, response.text)
        original = response.json()
        self.assertEqual((original["kind"], original["media_type"], original["provenance"]), ("original", "audio/mpeg", "creator_provided"))
        self.assertEqual([job["status"] for job in original["jobs"]], ["pending"])
        stored = self.store.path(f"{source}/original/{original['sha256']}.mp3")
        self.assertEqual(stored.read_bytes(), self.files["tone.mp3"].read_bytes())

        # The same file again is the same record, with no second job.
        again = self.upload(source, "tone.mp3").json()
        self.assertEqual(again["id"], original["id"])
        self.assertEqual(self.session.scalar(select(func.count()).select_from(AudioProcessingJob)), 1)

        # Refused files: not audio, no audio stream, or too large.
        self.assertEqual(
            self.client.post(f"/api/v1/speech/sources/{source}/media?provenance=creator_provided", content=b"<html></html>" * 4).status_code,
            415,
        )
        self.assertEqual(self.upload(source, "silent-video.mp4").status_code, 415)
        with patch.object(get_settings(), "speech_max_upload_bytes", 1024):
            self.assertEqual(self.upload(source, "tone.wav").status_code, 413)

        # The worker makes the 16 kHz mono working copy, once.
        self.assertEqual(self.runner.run_all(), {"succeeded": 1})
        self.assertEqual(self.runner.run_all(), {})
        listing = self.client.get(f"/api/v1/speech/sources/{source}/media").json()
        self.assertTrue(listing["transcription_allowed"])
        copy = next(asset for asset in listing["assets"] if asset["kind"] == "normalized_wav")
        self.assertEqual((copy["sample_rate"], copy["channels"], copy["derived_from_id"]), (16000, 1, original["id"]))
        job = next(asset for asset in listing["assets"] if asset["kind"] == "original")["jobs"][0]
        self.assertEqual((job["status"], job["attempts"], job["output_asset_id"]), ("succeeded", 1, copy["id"]))
        self.assertTrue(job["tool_versions"]["ffmpeg"].startswith("ffmpeg version"))
        self.assertTrue(self.store.exists(f"{source}/normalized_wav/{copy['sha256']}.wav"))

        # After the speaker withdraws, waiting work is blocked and no new file is accepted.
        self.assertEqual(self.upload(source, "tone.m4a", "owner_platform_export").status_code, 200)
        self.post("/api/v1/speech/speakers/S0001/withdrawal", {"withdrawn_on": "2026-10-27", "evidence_reference": "siamsil-data/consent/S0001-withdrawal"})
        self.assertEqual(self.upload(source, "tone.wav").status_code, 409)
        self.assertEqual(self.runner.run_all(), {"blocked": 1})
        self.assertEqual(self.runner.retry_blocked(), 1)
        self.assertEqual(self.runner.run_all(), {"blocked": 1})  # still not allowed
        listing = self.client.get(f"/api/v1/speech/sources/{source}/media").json()
        self.assertFalse(listing["transcription_allowed"])
        self.assertEqual(listing["reasons"], ["S0001 has withdrawn consent"])

        # Deleting removes every file; the records stay, marked deleted.
        deleted = self.post(f"/api/v1/speech/sources/{source}/media/delete", {"reason": "S0001 withdrew consent"})
        self.assertEqual((deleted["deleted_assets"], deleted["deleted_files"]), (3, 3))
        self.assertEqual([p for p in (self.store.root / source).rglob("*") if p.is_file()], [])
        statuses = self.session.scalars(select(MediaAsset.status).where(MediaAsset.source_id == uuid.UUID(source))).all()
        self.assertEqual(set(statuses), {"deleted"})
        self.assertEqual(self.runner.retry_blocked(), 0)  # deleted media is never requeued

        actions = set(self.session.scalars(select(AuditEvent.action).where(AuditEvent.action.like("speech.%"))))
        self.assertTrue({"speech.media_uploaded", "speech.media_normalized", "speech.job_succeeded",
                         "speech.job_blocked", "speech.media_deleted"} <= actions)

    def test_a_stopped_worker_is_taken_over_and_cannot_overwrite(self) -> None:
        source = self.cleared_source("S0002")
        self.assertEqual(self.upload(source, "tone.wav").status_code, 200)
        stopped = self.worker("worker-stopped")
        claimed = stopped.claim()
        self.assertIsNotNone(claimed)
        self.assertIsNone(self.worker("worker-b").claim())  # the lease is held

        job = self.session.get(AudioProcessingJob, claimed.job_id)
        job.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.session.flush()
        self.assertEqual(self.worker("worker-b").run_one(), "succeeded")
        self.assertEqual((job.status, job.attempts), ("succeeded", 2))
        # The first worker comes back: its lease is gone, so its result is discarded.
        self.assertEqual(stopped._stop(claimed.job_id, "failed", "late"), "abandoned")
        self.assertEqual(job.status, "succeeded")

    def test_jobs_fail_for_good_after_their_attempts(self) -> None:
        source = self.cleared_source("S0003")
        self.assertEqual(self.upload(source, "tone.wav").status_code, 200)
        broken = JobRunner(
            self.transactions,
            self.store,
            WorkerSettings(ffmpeg="ffmpeg-missing", ffprobe="ffprobe", lease_seconds=600, max_attempts=2),
            worker_id="broken",
        )
        self.assertEqual(broken.run_all(), {"failed": 2})
        job = self.session.scalar(select(AudioProcessingJob))
        self.assertEqual((job.status, job.attempts), ("failed", 2))
        self.assertIn("ffmpeg-missing is not installed", job.error)
        self.assertEqual(broken.run_all(), {})
