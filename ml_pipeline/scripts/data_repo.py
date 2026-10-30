"""Read originals directly from the private siamsil-data repository, the primary source of Siamsil data.

The clone is found at $SIAMSIL_DATA_REPO, or else beside this repository (../siamsil-data).
Every file is checked against the SHA-256 pinned in data/source_files.json before it is used;
a changed or missing file raises SourceError and nothing is built from it. Nothing here writes
to siamsil-data.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "data" / "source_files.json"
ENV_VAR = "SIAMSIL_DATA_REPO"


class SourceError(RuntimeError):
    """An original is missing or differs from its pinned checksum."""


def default_data_repo() -> Path:
    configured = os.environ.get(ENV_VAR, "").strip()
    return Path(configured).expanduser() if configured else ROOT.parent / "siamsil-data"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(repo: Path, path: Path, sha256: str | None = None) -> dict:
    """Release-manifest record for a file in siamsil-data (path shown relative to the repository)."""
    return {
        "path": f"siamsil-data/{path.relative_to(repo).as_posix()}",
        "bytes": path.stat().st_size,
        "sha256": sha256 or sha256_file(path),
    }


class DataRepo:
    def __init__(self, root: Path | None = None, config: Path = DEFAULT_CONFIG) -> None:
        self.root = (root or default_data_repo()).expanduser()
        self.sources: dict[str, dict] = json.loads(config.read_text(encoding="utf-8"))["sources"]
        if not self.root.is_dir():
            raise SourceError(
                f"siamsil-data not found at {self.root}. Clone it beside this repository "
                f"or set {ENV_VAR} (data/README.md)."
            )

    def verified(self, key: str) -> Path:
        """Path of a pinned original, after checking its checksum."""
        spec = self.sources[key]
        path = self.root / spec["path"]
        if not path.is_file():
            raise SourceError(f"{key}: {path} is missing")
        actual = sha256_file(path)
        if actual != spec["sha256"]:
            raise SourceError(
                f"{key}: {spec['path']} has SHA-256 {actual}, expected {spec['sha256']} "
                "(data/source_files.json). Update the pin only on purpose."
            )
        return path

    def parallel(self) -> "ParallelParts":
        manifest_path = self.verified("parallel_manifest")
        return ParallelParts(self.root, manifest_path)

    @contextmanager
    def unzipped(self, keys: list[str]) -> Iterator[Path]:
        """Extract pinned zips into a temporary folder (each under its unzip_to name); removed afterwards."""
        with tempfile.TemporaryDirectory(prefix="siamsil-sources-") as tmp:
            base = Path(tmp)
            for key in keys:
                archive = self.verified(key)
                safe_extract(archive, base / self.sources[key]["unzip_to"])
            yield base


class ParallelParts:
    """The parallel corpus, read from its checksummed gzip parts as the original CSV's text.

    The parts were written with CRLF line endings and repeat the header; reading them back with
    LF endings and one header gives the original CSV byte for byte, which `finish()` confirms
    against the SHA-256 the manifest records for it.
    """

    def __init__(self, repo: Path, manifest_path: Path) -> None:
        self.repo = repo
        self.manifest_path = manifest_path
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.parts: list[Path] = []
        for part in self.manifest["parts"]:
            path = manifest_path.parent / part["file"]
            if not path.is_file():
                raise SourceError(f"parallel part missing: {path}")
            if sha256_file(path) != part["sha256"]:
                raise SourceError(f"parallel part {part['file']} differs from parallel/manifest.json")
            self.parts.append(path)
        self._digest = hashlib.sha256()
        self._bytes = 0

    def lines(self) -> Iterator[str]:
        """The original CSV as text lines (one header), hashed as they are read."""
        self._digest = hashlib.sha256()
        self._bytes = 0
        for index, part in enumerate(self.parts):
            with gzip.open(part, "rb") as handle:
                for number, raw in enumerate(handle):
                    if number == 0 and index > 0:
                        continue
                    if raw.endswith(b"\r\n"):
                        raw = raw[:-2] + b"\n"
                    self._digest.update(raw)
                    self._bytes += len(raw)
                    yield raw.decode("utf-8", errors="replace")

    def finish(self) -> dict:
        """After every line was read: check the original's checksum and return its manifest record."""
        actual = self._digest.hexdigest()
        if actual != self.manifest["source_sha256"]:
            raise SourceError(
                f"the joined parallel parts give SHA-256 {actual}, not the original CSV's "
                f"{self.manifest['source_sha256']} (parallel/manifest.json)"
            )
        return {
            "path": f"siamsil-data/{self.manifest_path.parent.relative_to(self.repo).as_posix()} "
            f"({len(self.parts)} parts, joined)",
            "bytes": self._bytes,
            "sha256": actual,
        }


def safe_extract(archive: Path, target: Path) -> int:
    """Extract a zip, refusing entries that would land outside the target folder."""
    target.mkdir(parents=True, exist_ok=True)
    root = target.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            destination = (target / member.filename).resolve()
            if root != destination and root not in destination.parents:
                raise SourceError(f"{archive.name}: unsafe path {member.filename!r}")
        bundle.extractall(target)
        return len(bundle.infolist())
