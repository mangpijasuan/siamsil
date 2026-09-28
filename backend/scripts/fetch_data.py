"""Download and unpack the data bundle into the persistent volume on boot.

Skips work when the volume already holds the bundle matching
SIAMSIL_DATA_BUNDLE_SHA256, so restarts are instant.
"""
from __future__ import annotations

import hashlib
import os
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path


def main() -> None:
    url = os.environ.get("SIAMSIL_DATA_BUNDLE_URL", "").strip()
    expected = os.environ.get("SIAMSIL_DATA_BUNDLE_SHA256", "").strip().lower()
    root = Path(os.environ.get("SIAMSIL_DATA_ROOT", "/data"))

    if not url:
        print("fetch_data: SIAMSIL_DATA_BUNDLE_URL not set; skipping")
        return
    if not expected:
        sys.exit("fetch_data: SIAMSIL_DATA_BUNDLE_SHA256 is required with a bundle URL")

    marker = root / f".bundle-{expected}"
    if marker.exists():
        print("fetch_data: bundle already present")
        return

    root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=root, suffix=".tar.gz", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        digest = hashlib.sha256()
        print("fetch_data: downloading bundle")
        with urllib.request.urlopen(url, timeout=60) as response:
            for chunk in iter(lambda: response.read(1 << 20), b""):
                digest.update(chunk)
                tmp.write(chunk)

    try:
        if digest.hexdigest() != expected:
            sys.exit(f"fetch_data: checksum mismatch (got {digest.hexdigest()})")
        with tarfile.open(tmp_path, "r:gz") as tar:
            members = tar.getmembers()
            resolved_root = root.resolve()
            for member in members:
                target = (root / member.name).resolve()
                if not (member.isfile() or member.isdir()) or resolved_root not in target.parents:
                    sys.exit(f"fetch_data: refusing unsafe bundle entry {member.name!r}")
            tar.extractall(root, members=members)
    finally:
        tmp_path.unlink(missing_ok=True)

    for old in root.glob(".bundle-*"):
        old.unlink()
    marker.touch()
    print("fetch_data: bundle installed")


if __name__ == "__main__":
    main()
