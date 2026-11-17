"""Inspect a built Siamsil bundle and write a non-sensitive, immutable release manifest.

Usage:
  python backend/scripts/release_manifest.py dist/siamsil-data.tar.gz --output dist/release.json

Fails closed if either required SQLite database is absent, corrupt, or the tar has
unsafe names. It does NOT confer licensing clearance on included sources.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REQUIRED = {"siamsil_language.sqlite", "bible_versions.sqlite"}
SAFE_NAME = re.compile(r"^(?:siamsil_language\.sqlite|bible_versions\.sqlite|json/[A-Za-z0-9_.-]+\.json)$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(bundle: Path, *, created_at: str | None = None) -> dict:
    bundle = Path(bundle)
    if not bundle.is_file():
        raise ValueError(f"Missing bundle: {bundle}")
    members: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as directory, tarfile.open(bundle, "r:gz") as archive:
        infos = archive.getmembers()
        names = [member.name for member in infos]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate tar member")
        for member in infos:
            if not member.isfile() or not SAFE_NAME.fullmatch(member.name):
                raise ValueError(f"Unexpected or unsafe bundle member: {member.name}")
            target = Path(directory) / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open("wb") as out:
                if source is None:
                    raise ValueError("Cannot read bundle member")
                import shutil
                shutil.copyfileobj(source, out)
            members[member.name] = {"bytes": target.stat().st_size, "sha256": sha256(target)}
            if member.name in REQUIRED:
                con = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
                try:
                    if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise ValueError(f"SQLite integrity check failed: {member.name}")
                finally:
                    con.close()
        missing = REQUIRED - set(members)
        if missing:
            raise ValueError(f"Required database missing: {sorted(missing)}")
    checksum = sha256(bundle)
    return {
        "schema_version": 1,
        "release_id": f"sha256-{checksum[:16]}",
        "bundle_sha256": checksum,
        "bundle_bytes": bundle.stat().st_size,
        "object_key": f"releases/sha256-{checksum}/siamsil-data.tar.gz",
        "created_at_utc": created_at or datetime.now(timezone.utc).isoformat(),
        "contents": members,
        "note": "Build integrity verified; source rights and content approvals are separate gates.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = validate(args.bundle)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"release_id": manifest["release_id"], "object_key": manifest["object_key"],
                      "sha256": manifest["bundle_sha256"]}))


if __name__ == "__main__":
    main()
