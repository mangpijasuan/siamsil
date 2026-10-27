# Speech Data Lab

Updated: 2026-10-27
Status: **PR 2** (media storage, upload, and processing jobs) · PR 1 (rights and consent records) · Phase: [ROADMAP.md](ROADMAP.md) Phase 0 · Consent: [AUDIO_CONSENT.md](AUDIO_CONSENT.md) · Rights: [DATA_RIGHTS.md](DATA_RIGHTS.md)

The Speech Data Lab is where Siamsil collects, processes, reviews, and releases Zomi audio for future speech recognition (ASR) and speech synthesis (TTS) research. The first goal is **dataset preparation**, not production voice models. No ASR or TTS ships until there are enough human-reviewed recordings and evaluations.

This is Phase 0 work, which [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) lets run alongside Release 1, because speech data takes longest to gather. It reuses the existing stack: FastAPI under `/api/v1`, PostgreSQL with Alembic for mutable records, the existing identity, roles, and audit events, the Python pipeline, and the navy-and-gold web app. It is not a separate application.

## Ground rules

1. **Public is not permitted.** A video being public on YouTube or Facebook grants nothing. Every use needs the rights holder's permission, recorded with evidence and checked by a second administrator.
2. **No scraping, no circumvention.** Siamsil stores links; it never downloads from YouTube, Facebook, or any platform, and never bypasses DRM, access controls, or rate limits. Media enters only as a file the creator provides, or through an export the platform explicitly offers to the owner; every upload records which (PR 2).
3. **Every speaker consents to every use separately**, using the choices in [AUDIO_CONSENT.md](AUDIO_CONSENT.md). Training speech synthesis, which can produce a voice that sounds like the speaker, needs its own explicit yes.
4. **Default deny.** A recording may be used for something only when both the rights holder's verified, current permission and every speaker's current consent say yes. Anything missing means no.
5. **Withdrawal wins.** A withdrawn source or speaker drops out of every future step and release.
6. **Machines draft; people approve.** Automatic speech detection and transcription produce drafts only (PR 3). Only human reviewers and a separate lead editor can approve (PR 4).
7. **Nothing personal in git.** Speaker names and contact details live only in the private roster in `siamsil-data`. Consent and permission documents live in private storage; the database holds only a reference to them. Audio never goes into git or PostgreSQL; it goes into private media storage (PR 2). `.gitignore` blocks common media files.

## Roles

These are the existing roles in `user_roles`.

| Role | Can do |
| --- | --- |
| `administrator` | register sources; record permissions; verify, reject, or revoke a permission someone else recorded; create speakers; record consent and withdrawals; link speakers to sources; withdraw sources |
| `editor` | read sources, speakers, consent, and eligibility; approve transcripts (PR 4) |
| `reviewer` | transcribe and review clips (PR 4); no access to rights or consent records |
| others | nothing in the Speech Data Lab |

## Pipeline

```text
SOURCE REGISTERED → RIGHTS CHECK → FILE INGESTION → FILE VALIDATION → AUDIO EXTRACTION
→ SPEECH DETECTION → SEGMENTATION → DRAFT TRANSCRIPTION → HUMAN REVIEW → EDITOR APPROVAL → DATASET RELEASE
```

Each step is a resumable, idempotent job (PR 2). Before ingesting, before each job runs, before a job's result is stored, and again before any export, the pipeline checks that the use is still allowed, so a withdrawal or revocation takes effect at the next step.

## Data model

Each table arrives with the PR that first uses it, so no table exists before code that writes it.

| Model | Table | PR | Purpose |
| --- | --- | --- | --- |
| `SpeechSource` | `speech_sources` | 1 | A recording: its link (YouTube, Facebook, another https page) or a creator-provided file with no link. Title, uploader, dialect, duration, acquisition date. The language is always `ctd` (see below). Status is `registered` or `withdrawn`. |
| `SourcePermission` | `speech_source_permissions` | 1 | The rights holder's grant of each of the six uses, a reference to the evidence, an optional end date, and a status of `pending`, `verified`, `rejected`, or `revoked`. The database refuses a decision by the person who recorded it. |
| `Speaker` | `speakers` | 1 | A pseudonymous speaker code (`S0001`), with optional self-described dialect region and age range. |
| `SpeakerConsent` | `speaker_consents` | 1 | One consent record as in AUDIO_CONSENT.md: form version and language, written or oral, collector, adult confirmation, the six choices, credit, and an evidence reference. Append-only (a database trigger refuses UPDATE, DELETE, and TRUNCATE). The latest record is current, and a withdrawal is a new record that grants nothing. |
| `SourceSpeaker` | `speech_source_speakers` | 1 | Which speakers are heard in a source. Every one of them must consent. |
| `MediaAsset` | `speech_media_assets` | 2 | A private original file or a normalized WAV working copy: storage key, SHA-256, size, media type, duration, sample rate, channels, codec. An original records its provenance (`creator_provided` or `owner_platform_export`); a working copy records the original it came from. Deleting media keeps the record, marked `deleted`, without the file. |
| `AudioProcessingJob` | `speech_processing_jobs` | 2 | One pipeline step for one file: status (`pending`, `running`, `succeeded`, `failed`, `blocked`), attempts, lease, tool versions, error, and output file. Unique per file, step, and processing version, so a retry never repeats finished work. |
| `SpeechSegment` | | 3 | A clip, aiming for 5–20 seconds, cut at pauses so words and sentences stay whole: source timestamps, speaker, checksum, quality metrics, processing version. |
| `TranscriptRevision` | | 3–4 | Every transcript version, machine `DRAFT` or human, kept forever. |
| `TranscriptReview` | | 4 | A reviewer's rating and correction, then a lead editor's separate approval or rejection, mirroring the corpus review rules (SOP-07). |
| `SpeechDatasetRelease` | | 5 | An immutable release: manifest checksum, segment list, speaker-aware splits, and separate ASR and TTS eligibility. |

### Uses and consent choices

| Use (`SpeechUse`) | Rights holder grants | Speaker's consent choice |
| --- | --- | --- |
| `transcription`: keep, transcribe, evaluate internally | `allow_transcription` | `keep_and_evaluate` |
| `asr_training`: train speech recognition | `allow_asr_training` | `train_recognition` |
| `tts_training`: train speech synthesis | `allow_tts_training` | `train_synthesis` |
| `playback`: play the recording in the app | `allow_playback` | `play_in_app` |
| `redistribution`: publish in a dataset | `allow_redistribution` | `public_dataset` |
| `commercial`: use in paid services | `allow_commercial` | `commercial_use` |

`GET /api/v1/speech/sources/{id}/eligibility` reports, for each use, whether it is allowed today and every reason it is not (`backend/speech/rules.py`). ASR and TTS eligibility are separate by construction.

### Language code

Sources are labeled `ctd`, the ISO 639-3 code for Tedim, which Siamsil uses for Zomi ([DATA_RIGHTS.md](DATA_RIGHTS.md), decision of 2026-10-27). Published speech dataset and model cards declare `language: [ctd]` and name the language "Zomi (Zolai), Tedim-based". Dialect is recorded separately, as the speaker or collector describes it.

## API (PR 1)

All endpoints require sign-in.

| Method | Path | Role |
| --- | --- | --- |
| POST | `/api/v1/speech/sources` | administrator |
| GET | `/api/v1/speech/sources`, `/api/v1/speech/sources/{id}` | administrator, editor |
| POST | `/api/v1/speech/sources/{id}/withdraw` | administrator |
| POST | `/api/v1/speech/sources/{id}/permissions` | administrator |
| POST | `/api/v1/speech/sources/{id}/permissions/{permission_id}/decision` (`verify`, `reject`, `revoke`) | a different administrator from the recorder |
| POST | `/api/v1/speech/sources/{id}/speakers/{speaker_code}` | administrator |
| GET | `/api/v1/speech/sources/{id}/eligibility` | administrator, editor |
| POST | `/api/v1/speech/speakers` | administrator |
| GET | `/api/v1/speech/speakers` | administrator, editor |
| POST | `/api/v1/speech/speakers/{code}/consents` | administrator |
| POST | `/api/v1/speech/speakers/{code}/withdrawal` | administrator |

- Every change writes an `audit_events` row (`speech.*`).
- Requests with unknown fields are refused.
- A consent must answer all six choices; none defaults to yes.
- A consent that does not confirm the speaker is an adult is refused.
- Permission status moves only forward: `pending` → `verified` or `rejected`, then `verified` → `revoked`. A rejected or revoked permission is final; record a new one.

## Media and jobs (PR 2)

### Upload

An administrator uploads a source's original file as the raw request body:

```text
POST /api/v1/speech/sources/{id}/media?provenance=creator_provided|owner_platform_export
Content-Type: application/octet-stream
```

- **Refused before any bytes are read** unless `transcription` is allowed for the source today. It is checked again, with the source locked, when the file is recorded, so a withdrawal during an upload wins.
- **Type from the bytes.** WAV, MP3, M4A, and MP4 are recognized from the file's first bytes; the name and declared type are ignored. Anything else is refused (415) as soon as the first bytes arrive. FFprobe then must find an audio stream, or the file is refused (415).
- **Limits.** `SIAMSIL_SPEECH_MAX_UPLOAD_BYTES` (default 1 GiB) is enforced while streaming (413), and `SIAMSIL_SPEECH_MAX_DURATION_SECONDS` (default 6 hours) after probing. A reverse proxy in front of the API may need its own body limit raised.
- **Checksums.** SHA-256 is computed while streaming. The same file uploaded again to the same source returns the first record; a file deleted from a source cannot be uploaded to it again (register a new source).
- No file names are stored: they often contain people's names.

### Storage

Files are kept under `SIAMSIL_SPEECH_MEDIA_DIR` (default `data/speech/media/`, ignored by git) as `<source id>/<original|normalized_wav>/<sha256>.<ext>`, with folders `0700` and files `0600`. Writes are atomic. Only the API and the job worker read this directory; it must never be served by a web server or synced anywhere public, and it needs its own encrypted backup. A cloud bucket (for example Cloudflare R2) can replace it behind the same interface (`speech/media.py`) once the API's host is chosen.

### Jobs

Each upload queues one `normalize_wav` job: FFmpeg writes the first audio stream as 16 kHz mono 16-bit PCM WAV, without metadata and bit-exact, so the same input always gives the same checksum. The original is kept unchanged beside it.

```text
python backend/scripts/run_speech_jobs.py            # run every waiting job, then stop
python backend/scripts/run_speech_jobs.py --watch    # keep running
python backend/scripts/run_speech_jobs.py --retry-blocked
```

- A worker claims a job under a lease (`SIAMSIL_SPEECH_JOB_LEASE_SECONDS`, default 30 minutes) with `FOR UPDATE SKIP LOCKED`, so several workers can run at once. A stopped worker's job is taken over when the lease expires, and a worker that lost its lease cannot record a result.
- A failed job is retried up to `SIAMSIL_SPEECH_JOB_MAX_ATTEMPTS` (default 3) times, then stays `failed` with its error.
- Before running and again before storing its result, a job checks that the source may still be transcribed; if not, it becomes `blocked` with the reasons. `--retry-blocked` requeues blocked jobs after a permission is fixed; they block again if still not allowed.
- FFmpeg is called without a shell, with the input format named explicitly, local files only, and a time limit. Each job records the FFmpeg version.

### Withdrawal and deletion

`GET /api/v1/speech/sources/{id}/media` shows each file with its jobs, and whether the source may still be transcribed. When it may not (a withdrawal or revocation), an administrator deletes its media:

```text
POST /api/v1/speech/sources/{id}/media/delete   {"reason": "..."}
```

Every stored file of the source is removed and its unfinished jobs are blocked. The records stay, marked `deleted`, with the reason, so what was collected and removed remains on record without the audio. Deletion is an explicit step rather than automatic, because it cannot be undone.

| Method | Path | Role |
| --- | --- | --- |
| POST | `/api/v1/speech/sources/{id}/media` | administrator |
| GET | `/api/v1/speech/sources/{id}/media` | administrator, editor |
| POST | `/api/v1/speech/sources/{id}/media/delete` | administrator |

Every change writes an audit event: `speech.media_uploaded`, `speech.media_normalized`, `speech.job_succeeded`, `speech.job_failed`, `speech.job_blocked`, and `speech.media_deleted`. Jobs are audited with no user, naming the worker.

## Plan

| PR | Delivers |
| --- | --- |
| 1 | This document; the rights and consent tables, API, rules, and tests |
| 2 | **Built.** Private media storage; upload of creator-provided MP4, MP3, M4A, and WAV with type sniffing, size limits, and checksums; FFmpeg extraction to normalized WAV; resumable, idempotent jobs; ingestion blocked unless `transcription` is allowed; media deletion on withdrawal |
| 3 | Speech detection; segmentation into 5–20-second clips at pauses; clip manifests with stable IDs and checksums; quality metrics; draft-transcript hooks (status `DRAFT`) |
| 4 | Reviewer workspace in the web app (playback, waveform, editable transcript, flags, notes) and a separate lead-editor approval, with full revision history |
| 5 | Quality gates: duplicate audio, speaker-aware splits, benchmark-speaker isolation, rights-aware export blocking, consent-withdrawal removal; versioned, checksummed, immutable releases with provenance manifests; separate ASR and TTS eligibility |
| 6 | ASR baseline research and offline evaluation (Whisper and other open models). No model is said to support Zomi until it is measured on human-reviewed Zomi audio; if quality is too low, transcription stays human-first. |

## First pilot

The targets are 5–10 authorized recordings, about 1–3 hours of audio, 100–300 reviewed clips, and several qualified Zomi-speaking reviewers. These are targets, not promises. The first milestone is one authorized sample file, provided locally, going through the pipeline end to end.

Before the first recording, [AUDIO_CONSENT.md](AUDIO_CONSENT.md)'s checklist still applies: legal review of the form, Zomi and Burmese translations by native speakers, a staffed withdrawal contact, and collector training.
