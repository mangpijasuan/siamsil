"""FFmpeg steps for the Speech Data Lab (docs/SPEECH_DATA_LAB.md, PR 2).

Every call names the input format explicitly (decided by `media.sniff`), reads local files
only, has a time limit, and never runs a shell. The working copy is 16 kHz mono 16-bit PCM
WAV, the usual input for speech recognition; the original upload is kept unchanged beside it.
Output is bit-exact, so the same input always gives the same file and the same checksum.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PROCESSING_VERSION = "wav-16k-mono-s16-v1"
SAMPLE_RATE = 16_000
CHANNELS = 1


class AudioError(RuntimeError):
    """The file could not be read as audio, or FFmpeg failed."""


@dataclass(frozen=True)
class Probe:
    duration_seconds: float
    sample_rate: Optional[int]
    channels: Optional[int]
    codec: Optional[str]


def _run(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError:
        raise AudioError(f"{command[0]} is not installed") from None
    except subprocess.TimeoutExpired:
        raise AudioError(f"{Path(command[0]).name} took longer than {timeout} seconds") from None
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise AudioError(f"{Path(command[0]).name} failed: {detail[-1] if detail else f'exit {result.returncode}'}")
    return result


def tool_version(binary: str) -> str:
    """The first line of `<binary> -version`, recorded with every job."""
    return _run([binary, "-version"], timeout=30).stdout.splitlines()[0].strip()


def probe(ffprobe: str, path: Path, demuxer: str, *, timeout: int = 120) -> Probe:
    """The first audio stream's facts. A file with no audio stream is refused."""
    result = _run(
        [
            ffprobe, "-v", "error", "-protocol_whitelist", "file", "-f", demuxer,
            "-select_streams", "a:0", "-show_entries", "stream=codec_name,sample_rate,channels:format=duration",
            "-of", "json", f"file:{path}",
        ],
        timeout,
    )
    data = json.loads(result.stdout or "{}")
    streams = data.get("streams") or []
    if not streams:
        raise AudioError("the file has no audio stream")
    stream = streams[0]
    try:
        duration = float((data.get("format") or {}).get("duration"))
    except (TypeError, ValueError):
        raise AudioError("the audio has no readable duration") from None
    if duration <= 0:
        raise AudioError("the audio is empty")
    return Probe(
        duration_seconds=duration,
        sample_rate=int(stream["sample_rate"]) if stream.get("sample_rate") else None,
        channels=int(stream["channels"]) if stream.get("channels") else None,
        codec=stream.get("codec_name"),
    )


def normalize(ffmpeg: str, source: Path, demuxer: str, target: Path, *, timeout: int) -> None:
    """Write the first audio stream of `source` as 16 kHz mono 16-bit PCM WAV, without metadata."""
    _run(
        [
            ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-protocol_whitelist", "file", "-f", demuxer, "-i", f"file:{source}",
            "-map", "0:a:0", "-vn", "-sn", "-dn", "-map_metadata", "-1",
            "-ac", str(CHANNELS), "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le",
            "-fflags", "+bitexact", "-flags:a", "+bitexact", "-f", "wav", f"file:{target}",
        ],
        timeout,
    )
