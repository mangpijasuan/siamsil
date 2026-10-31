"""Download and unpack the data bundle into the persistent volume on boot (docs/DEPLOY.md).

The bundle comes from one of:
- a private S3-compatible bucket such as Cloudflare R2, with a read-only key
  (SIAMSIL_DATA_BUNDLE_S3_ENDPOINT, _S3_BUCKET, _S3_ACCESS_KEY_ID, _S3_SECRET_ACCESS_KEY,
  and optionally _S3_KEY and _S3_REGION); a short-lived signed link is made at each download;
- or a plain link, SIAMSIL_DATA_BUNDLE_URL.

Skips work when the volume already holds the bundle matching
SIAMSIL_DATA_BUNDLE_SHA256, so restarts are instant.
"""
from __future__ import annotations

import fcntl
import hashlib
import hmac
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_OBJECT_KEY = "siamsil-data.tar.gz"


def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def presigned_url(endpoint: str, bucket: str, key: str, access_key_id: str, secret_access_key: str, *,
                  region: str = "auto", expires: int = 3600, now: datetime | None = None,
                  path_style: bool = True) -> str:
    """A GET link signed with AWS Signature Version 4 query parameters, as R2 and S3 accept.

    Path style (https://host/bucket/key) is what R2 uses; virtual-hosted style puts the bucket
    in the host and is kept for checking against AWS's published example.
    """
    parsed = urllib.parse.urlsplit(endpoint.rstrip("/"))
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("the bucket endpoint must be an https:// address")
    when = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    day = when[:8]
    host = parsed.netloc if path_style else f"{bucket}.{parsed.netloc}"
    path = "/" + (f"{bucket}/" if path_style else "") + urllib.parse.quote(key, safe="/~")
    scope = f"{day}/{region}/s3/aws4_request"
    query = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": f"{access_key_id}/{scope}",
        "X-Amz-Date": when,
        "X-Amz-Expires": str(expires),
        "X-Amz-SignedHeaders": "host",
    }
    canonical_query = "&".join(
        f"{urllib.parse.quote(name, safe='~')}={urllib.parse.quote(value, safe='~')}"
        for name, value in sorted(query.items())
    )
    canonical_request = "\n".join(["GET", path, canonical_query, f"host:{host}\n", "host", "UNSIGNED-PAYLOAD"])
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256", when, scope, hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])
    signing_key = _hmac(_hmac(_hmac(_hmac(f"AWS4{secret_access_key}".encode("utf-8"), day), region), "s3"),
                        "aws4_request")
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"https://{host}{path}?{canonical_query}&X-Amz-Signature={signature}"


def bundle_url(env: dict[str, str]) -> str:
    """Where to download the bundle from, or "" when no source is configured."""
    endpoint = env.get("SIAMSIL_DATA_BUNDLE_S3_ENDPOINT", "").strip()
    if endpoint:
        needed = ("SIAMSIL_DATA_BUNDLE_S3_BUCKET", "SIAMSIL_DATA_BUNDLE_S3_ACCESS_KEY_ID",
                  "SIAMSIL_DATA_BUNDLE_S3_SECRET_ACCESS_KEY")
        missing = [name for name in needed if not env.get(name, "").strip()]
        if missing:
            raise ValueError(f"set {', '.join(missing)} with SIAMSIL_DATA_BUNDLE_S3_ENDPOINT")
        return presigned_url(
            endpoint,
            env["SIAMSIL_DATA_BUNDLE_S3_BUCKET"].strip(),
            env.get("SIAMSIL_DATA_BUNDLE_S3_KEY", "").strip() or DEFAULT_OBJECT_KEY,
            env["SIAMSIL_DATA_BUNDLE_S3_ACCESS_KEY_ID"].strip(),
            env["SIAMSIL_DATA_BUNDLE_S3_SECRET_ACCESS_KEY"].strip(),
            region=env.get("SIAMSIL_DATA_BUNDLE_S3_REGION", "").strip() or "auto",
        )
    return env.get("SIAMSIL_DATA_BUNDLE_URL", "").strip()


def install(archive: Path, root: Path, expected: str) -> None:
    """Unpack a checked bundle beside the live files and, only once all of it is unpacked, replace them.

    Files from an earlier bundle that this one leaves out are removed, so data dropped from a
    bundle (for example a source no longer cleared for display) stops being served. The API starts
    only after this script finishes (backend/Dockerfile), so it never reads a half-replaced tree.
    """
    staging = root / f".staging-{expected}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir()
    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            resolved = staging.resolve()
            for member in members:
                target = (staging / member.name).resolve()
                if not (member.isfile() or member.isdir()) or resolved not in target.parents:
                    sys.exit(f"fetch_data: refusing unsafe bundle entry {member.name!r}")
            tar.extractall(staging, members=members)
        for old in root.iterdir():
            if not old.name.startswith(".") and old.name != "lost+found":
                shutil.rmtree(old) if old.is_dir() and not old.is_symlink() else old.unlink()
        for new in staging.iterdir():
            os.replace(new, root / new.name)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    for old_marker in root.glob(".bundle-*"):
        old_marker.unlink()
    (root / f".bundle-{expected}").touch()


def main() -> None:
    expected = os.environ.get("SIAMSIL_DATA_BUNDLE_SHA256", "").strip().lower()
    root = Path(os.environ.get("SIAMSIL_DATA_ROOT", "/data"))
    # An installed bundle needs no download, so no credentials either.
    if expected and (root / f".bundle-{expected}").exists():
        print("fetch_data: bundle already present")
        return
    try:
        url = bundle_url(dict(os.environ))
    except ValueError as error:
        sys.exit(f"fetch_data: {error}")
    if not url:
        print("fetch_data: no data bundle configured (SIAMSIL_DATA_BUNDLE_S3_ENDPOINT or _URL); skipping")
        return
    if not expected:
        sys.exit("fetch_data: SIAMSIL_DATA_BUNDLE_SHA256 is required with a data bundle")

    root.mkdir(parents=True, exist_ok=True)
    with (root / ".fetch.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)  # one install at a time on this volume
        if (root / f".bundle-{expected}").exists():
            print("fetch_data: bundle already present")
            return
        handle, name = tempfile.mkstemp(dir=root, prefix=".download-", suffix=".tar.gz")
        archive = Path(name)
        try:
            digest = hashlib.sha256()
            print("fetch_data: downloading bundle")
            with os.fdopen(handle, "wb") as out, urllib.request.urlopen(url, timeout=60) as response:
                for chunk in iter(lambda: response.read(1 << 20), b""):
                    digest.update(chunk)
                    out.write(chunk)
            if digest.hexdigest() != expected:
                sys.exit(f"fetch_data: checksum mismatch (got {digest.hexdigest()})")
            install(archive, root, expected)
        finally:
            archive.unlink(missing_ok=True)
    print("fetch_data: bundle installed")


if __name__ == "__main__":
    main()
