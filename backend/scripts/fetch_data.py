"""Download and unpack the data bundle into the persistent volume on boot (docs/DEPLOY.md).

The bundle comes from one of:
- a private S3-compatible bucket such as Cloudflare R2, with a read-only key
  (SIAMSIL_DATA_BUNDLE_S3_ENDPOINT, _S3_BUCKET, _S3_ACCESS_KEY_ID, _S3_SECRET_ACCESS_KEY,
  and optionally _S3_KEY and _S3_REGION); a short-lived signed link is made at each download;
- or a plain link, SIAMSIL_DATA_BUNDLE_URL.

Skips work when the volume already holds the bundle matching
SIAMSIL_DATA_BUNDLE_SHA256, so restarts are instant.

Release manifest (docs/DATA_RELEASES.md, release_contract.py). Beside the bundle sits release.json, which declares
what the bundle is: its files, the rights register it carries, its source commit, its approval and its derivation.
Its address is SIAMSIL_DATA_RELEASE_MANIFEST_KEY or SIAMSIL_DATA_RELEASE_MANIFEST_URL, else beside the bundle's key,
and it is pinned by SIAMSIL_DATA_RELEASE_MANIFEST_SHA256 just as the bundle is pinned. The bundle is installed only
if every file matches the manifest and the manifest verifies. In development and test a bundle with no manifest is
still accepted (with a warning); in staging and production a schema 2, approved manifest is required, and an
already-installed bundle is re-checked from its stored copy (.release.json) on every start.
Optional: SIAMSIL_RIGHTS_SHA256 pins the rights register this deployment expects the release to carry.
"""
from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_contract as contract  # noqa: E402

DEFAULT_OBJECT_KEY = "siamsil-data.tar.gz"
MANIFEST_NAME = "release.json"
MAX_MANIFEST_BYTES = 2_000_000


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


def manifest_key(bundle_key: str) -> str:
    """Where release.json sits for a bucket key. A folder per release (releases/sha256-<digest>/siamsil-data.tar.gz)
    holds release.json beside the bundle; a flat dated name (siamsil-data-2026-11-30.tar.gz) gets its own
    siamsil-data-2026-11-30.release.json, so two releases never share one manifest."""
    folder, _, name = bundle_key.rpartition("/")
    if folder:
        return f"{folder}/{MANIFEST_NAME}"
    return (name[: -len(".tar.gz")] if name.endswith(".tar.gz") else name) + ".release.json"


def manifest_url(env: dict[str, str]) -> str:
    """Where release.json is, or "" when none is configured. Bucket mode: SIAMSIL_DATA_RELEASE_MANIFEST_KEY, else
    beside the bundle's key (see manifest_key)."""
    endpoint = env.get("SIAMSIL_DATA_BUNDLE_S3_ENDPOINT", "").strip()
    if endpoint:
        bundle_key = env.get("SIAMSIL_DATA_BUNDLE_S3_KEY", "").strip() or DEFAULT_OBJECT_KEY
        return presigned_url(
            endpoint, env["SIAMSIL_DATA_BUNDLE_S3_BUCKET"].strip(),
            env.get("SIAMSIL_DATA_RELEASE_MANIFEST_KEY", "").strip() or manifest_key(bundle_key),
            env["SIAMSIL_DATA_BUNDLE_S3_ACCESS_KEY_ID"].strip(), env["SIAMSIL_DATA_BUNDLE_S3_SECRET_ACCESS_KEY"].strip(),
            region=env.get("SIAMSIL_DATA_BUNDLE_S3_REGION", "").strip() or "auto")
    return env.get("SIAMSIL_DATA_RELEASE_MANIFEST_URL", "").strip()


def parse_manifest(raw: bytes, pinned_sha256: str) -> dict:
    """The manifest from its bytes, checked against the pinned digest when one is set."""
    if pinned_sha256 and hashlib.sha256(raw).hexdigest() != pinned_sha256:
        sys.exit("fetch_data: release manifest does not match SIAMSIL_DATA_RELEASE_MANIFEST_SHA256")
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:
        sys.exit("fetch_data: release manifest is not valid JSON")


def download_manifest(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:
        raw = response.read(MAX_MANIFEST_BYTES + 1)
    if len(raw) > MAX_MANIFEST_BYTES:
        sys.exit("fetch_data: release manifest is unexpectedly large")
    return raw


def check_release(manifest: object, env: dict[str, str], *, root: Path | None, full: bool, expected: str) -> None:
    """Verify, or stop with every reason. `root` is where the files to check are (staging or the live volume)."""
    environment = env.get("SIAMSIL_ENVIRONMENT", "development").strip() or "development"
    try:
        override = env.get("SIAMSIL_RIGHTS_FILE", "").strip()
        contract.verify(manifest, environment=environment, root=root, full=full, expected_bundle_sha256=expected,
                        expected_rights_sha256=env.get("SIAMSIL_RIGHTS_SHA256", "").strip().lower() or None,
                        rights_override=Path(override) if override else None)
    except contract.ReleaseVerificationError as error:
        sys.exit("fetch_data: release verification failed:\n  - " + "\n  - ".join(error.problems))


def install(archive: Path, root: Path, expected: str, manifest: dict | None = None, manifest_raw: bytes | None = None,
            env: dict[str, str] | None = None) -> None:
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
        if manifest is not None:
            # Before anything live is touched: a bundle that disagrees with its manifest installs nothing.
            check_release(manifest, env if env is not None else dict(os.environ), root=staging, full=True,
                          expected=expected)
        for old in root.iterdir():
            if not old.name.startswith(".") and old.name != "lost+found":
                shutil.rmtree(old) if old.is_dir() and not old.is_symlink() else old.unlink()
        for new in staging.iterdir():
            os.replace(new, root / new.name)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    for old_marker in root.glob(".bundle-*"):
        old_marker.unlink()
    (root / contract.INSTALLED_MANIFEST).unlink(missing_ok=True)
    if manifest_raw is not None:
        (root / contract.INSTALLED_MANIFEST).write_bytes(manifest_raw)
    (root / f".bundle-{expected}").touch()


def already_installed(root: Path, expected: str, env: dict[str, str], pinned: str) -> bool:
    """True when the volume already holds this bundle, after re-checking its stored release manifest.

    The stored manifest is checked cheaply (sizes, and the rights register's digest) so a changed rights.json cannot
    ride along on a restart. Called before the download and again once the install lock is held: a second process
    that finds the bundle another process just installed gets the same verification, not a free pass.
    """
    if not (expected and (root / f".bundle-{expected}").exists()):
        return False
    environment = env.get("SIAMSIL_ENVIRONMENT", "development").strip() or "development"
    stored = root / contract.INSTALLED_MANIFEST
    if stored.is_file():
        check_release(parse_manifest(stored.read_bytes(), pinned), env, root=root, full=False, expected=expected)
    elif contract.is_strict(environment):
        sys.exit(f"fetch_data: {environment} needs the installed release manifest ({contract.INSTALLED_MANIFEST}); "
                 "reinstall the bundle with its release.json")
    else:
        print("fetch_data: WARNING installed bundle has no release manifest (allowed in development and test)")
    print("fetch_data: bundle already present")
    return True


def main() -> None:
    env = dict(os.environ)
    expected = env.get("SIAMSIL_DATA_BUNDLE_SHA256", "").strip().lower()
    root = Path(env.get("SIAMSIL_DATA_ROOT", "/data"))
    environment = env.get("SIAMSIL_ENVIRONMENT", "development").strip() or "development"
    strict = contract.is_strict(environment)
    pinned = env.get("SIAMSIL_DATA_RELEASE_MANIFEST_SHA256", "").strip().lower()
    if strict and not contract.SHA256_RE.fullmatch(pinned):
        sys.exit(f"fetch_data: {environment} requires SIAMSIL_DATA_RELEASE_MANIFEST_SHA256 (the release.json digest)")
    # An installed bundle needs no download, so no credentials either.
    if already_installed(root, expected, env, pinned):
        return
    try:
        url = bundle_url(dict(os.environ))
    except ValueError as error:
        sys.exit(f"fetch_data: {error}")
    if not url:
        if strict:
            # No verified bundle is installed (the check above returned) and none can be fetched: starting the API now
            # would serve with no verified release, so a strict environment stops here.
            sys.exit(f"fetch_data: {environment} has no verified data bundle installed and none configured "
                     "(SIAMSIL_DATA_BUNDLE_S3_ENDPOINT or SIAMSIL_DATA_BUNDLE_URL, with SIAMSIL_DATA_BUNDLE_SHA256)")
        print("fetch_data: no data bundle configured (SIAMSIL_DATA_BUNDLE_S3_ENDPOINT or _URL); skipping "
              "(allowed in development and test only)")
        return
    if not expected:
        sys.exit("fetch_data: SIAMSIL_DATA_BUNDLE_SHA256 is required with a data bundle")

    manifest = manifest_raw = None
    release_url = manifest_url(env)
    if release_url:
        manifest_raw = download_manifest(release_url)
        manifest = parse_manifest(manifest_raw, pinned)
        check_release(manifest, env, root=None, full=False, expected=expected)  # the manifest alone, before downloading
    elif strict:
        sys.exit(f"fetch_data: {environment} requires a release manifest (SIAMSIL_DATA_RELEASE_MANIFEST_URL, or a "
                 "bucket key whose folder holds release.json)")
    else:
        print("fetch_data: WARNING no release manifest configured; allowed in development and test only")

    root.mkdir(parents=True, exist_ok=True)
    with (root / ".fetch.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)  # one install at a time on this volume
        if already_installed(root, expected, env, pinned):
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
            install(archive, root, expected, manifest, manifest_raw, env)
        finally:
            archive.unlink(missing_ok=True)
    print("fetch_data: bundle installed")


if __name__ == "__main__":
    main()
