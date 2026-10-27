"""Recognizing uploaded media and keeping it in private storage (docs/SPEECH_DATA_LAB.md, PR 2).

The type of an upload is decided from its first bytes, never from its name or the declared
content type, and only the four formats creators are asked for are accepted. Stored files sit
in a private directory, one folder per source, so deleting a source's media deletes exactly
its own files.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from uuid import UUID

SNIFF_BYTES = 16

# Brands in an MP4 container's ftyp box. M4A/M4B are audio-only; the others are ordinary MP4
# video. QuickTime ("qt  ") and anything else is refused rather than guessed at.
M4A_BRANDS = {b"M4A ", b"M4B "}
MP4_BRANDS = {b"isom", b"iso2", b"iso4", b"iso5", b"iso6", b"mp41", b"mp42", b"avc1", b"dash", b"M4V ", b"MSNV"}


@dataclass(frozen=True)
class MediaFormat:
    media_type: str
    extension: str
    demuxer: str  # FFmpeg input format, given explicitly so FFmpeg never guesses


WAV = MediaFormat("audio/wav", "wav", "wav")
MP3 = MediaFormat("audio/mpeg", "mp3", "mp3")
M4A = MediaFormat("audio/mp4", "m4a", "mov")
MP4 = MediaFormat("video/mp4", "mp4", "mov")
NORMALIZED_WAV = WAV
FORMATS = {fmt.media_type: fmt for fmt in (WAV, MP3, M4A, MP4)}


def sniff(head: bytes) -> Optional[MediaFormat]:
    """The format of a file from its first bytes, or None if it is not WAV, MP3, M4A, or MP4."""
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return WAV
    if len(head) >= 12 and head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in M4A_BRANDS:
            return M4A
        if brand in MP4_BRANDS:
            return MP4
        return None
    if head[:3] == b"ID3":
        return MP3
    # An MPEG audio frame header: 11 sync bits, a valid version, and Layer III.
    if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
        version = (head[1] >> 3) & 0b11
        layer = (head[1] >> 1) & 0b11
        if version != 0b01 and layer == 0b01:
            return MP3
    return None


SHA256 = re.compile(r"^[0-9a-f]{64}$")


class LocalMediaStore:
    """Media files in a private directory: <root>/<source id>/<kind>/<sha256>.<extension>.

    Writes are atomic (a temporary file in the same folder, then a rename), so a crash never
    leaves a half-written file under a real key. Folders are 0700 and files 0600.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    @staticmethod
    def key(source_id: UUID, kind: str, sha256: str, extension: str) -> str:
        if not SHA256.match(sha256) or kind not in {"original", "normalized_wav"} or not extension.isalnum():
            raise ValueError("invalid media key")
        return f"{source_id}/{kind}/{sha256}.{extension}"

    def path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("media key outside the media directory")
        return path

    def exists(self, key: str) -> bool:
        return self.path(key).is_file()

    def put(self, key: str, source: Path) -> None:
        """Copy a finished local file in under `key`. An existing file under the key is kept."""
        target = self.path(key)
        if target.is_file():
            return
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        for folder in (target.parent, target.parent.parent, self.root):
            os.chmod(folder, 0o700)
        handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=".incoming-")
        try:
            with os.fdopen(handle, "wb") as out, open(source, "rb") as src:
                while chunk := src.read(1024 * 1024):
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, target)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def delete(self, key: str) -> bool:
        path = self.path(key)
        if not path.exists():
            return False
        path.unlink()
        return True
