"""Check a deployed Siamsil API and the expected immutable data bundle release.

Example:
  python backend/scripts/check_release.py --url https://api.siamsil.com \
    --sha256 <expected-bundle-sha> --data-root /data

The HTTP check validates API readiness. The local marker check validates the
installed archive digest; use it *inside the Railway container* to prove that
the running volume has the intended release. A remote HTTP check alone cannot
verify the installed release ID until the service exposes it.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from pathlib import Path


def check_health(url: str) -> dict:
    if not url.startswith("https://") and not url.startswith("http://127.0.0.1") and not url.startswith("http://localhost"):
        raise ValueError("Use an HTTPS URL for remote health checks")
    with urllib.request.urlopen(url.rstrip("/") + "/health/ready", timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"Readiness returned HTTP {response.status}")
        result = json.load(response)
    if result.get("status") != "ok":
        raise RuntimeError(f"Service is not ready: {result.get('status')}")
    language = result.get("language") or {}
    if language.get("database") is not True:
        raise RuntimeError("Language database is not ready")
    return {"ready": True, "dictionary_entries": language.get("dictionary_entries"),
            "parallel_sentences": language.get("parallel_sentences")}


def installed_release(data_root: Path, expected_sha256: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("Provide the full lowercase SHA-256 digest")
    if not (data_root / f".bundle-{expected_sha256}").is_file():
        raise RuntimeError("Expected release marker not present")
    for filename in ("siamsil_language.sqlite", "bible_versions.sqlite"):
        if not (data_root / filename).is_file():
            raise RuntimeError(f"Required release database missing: {filename}")
    return {"release_sha256": expected_sha256, "installed": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--sha256", help="Expected archive SHA-256 for an on-container check")
    parser.add_argument("--data-root", type=Path, help="Installed data directory (Railway: /data)")
    args = parser.parse_args()
    info = check_health(args.url)
    if bool(args.sha256) != bool(args.data_root):
        parser.error("--sha256 and --data-root must be provided together")
    if args.sha256:
        info.update(installed_release(args.data_root, args.sha256))
    print(json.dumps(info, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
