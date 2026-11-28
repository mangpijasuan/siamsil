"""Staging drill for the data-release contract: install, rejection and rollback scenarios, run locally.

  python backend/scripts/staging_drill.py --work /tmp/drill [--json report.json]

Builds small synthetic releases (placeholder corpus strings, never real language data), serves them from a local HTTP
server and runs backend/scripts/fetch_data.py exactly as the container does, with SIAMSIL_ENVIRONMENT=staging. Each
scenario states what must happen (accept or reject, and why) and the drill reports PASS or FAIL per scenario.

What this is not: it does not touch R2, Railway, the VPS or any production setting, it uses no credentials, and it
records an approval for its synthetic releases as "STAGING-DRILL-FIXTURE (not an owner approval)". It exercises the
plain-URL path (SIAMSIL_DATA_BUNDLE_URL); the presigned R2 path is covered only by the signing unit tests.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import socket
import ssl
import threading
import urllib.parse
import time
import urllib.request
from functools import partial
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "ml_pipeline" / "scripts"))
import build_language_db as build  # noqa: E402
import check_release  # noqa: E402
import fetch_data  # noqa: E402
import release_contract as contract  # noqa: E402
import release_manifest  # noqa: E402

APPROVER = "STAGING-DRILL-FIXTURE (not an owner approval)"
APPROVED_AT = "2026-11-30T09:00:00"
ROWS = [("Hello there.", "ZOMI_ONE"), ("Good morning.", "ZOMI_TWO"), ("Hello there.", "ZOMI_ONE"), ("", "ZOMI_EMPTY"),
        ("Thank you.", "ZOMI_THREE")]


def sha(path: Path) -> str:
    return contract.sha256_file(path)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_args) -> None:  # noqa: D401
        pass


class Drill:
    def __init__(self, work: Path) -> None:
        self.work = work
        shutil.rmtree(work, ignore_errors=True)
        (work / "serve").mkdir(parents=True)
        self.serve = work / "serve"
        self.results: list[dict] = []
        self.repo = work / "siamsil-data"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "drill@example.invalid")
        git(self.repo, "config", "user.name", "Drill")
        (self.repo / "README.md").write_text("placeholder\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "placeholder")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(self.serve)))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    # ---- releases -------------------------------------------------------------------------------------------

    def release(self, name: str, *, approved: bool = True, rights_note: str = "", binding: bool = True,
                clean: bool = True) -> dict:
        """A small, real-format release: language DB built by build_language_db, bundle, schema 2 manifest."""
        folder = self.work / "build" / name
        folder.mkdir(parents=True)
        corpus = folder / "corpus.csv"
        with corpus.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["index", "en", "zomi", "model", "worker"])
            for index, (en, zomi) in enumerate(ROWS):
                writer.writerow([index, en, zomi, "drill", "drill"])
        db = folder / "siamsil_language.sqlite"
        con = build.connect(db)
        build.create_schema(con)
        stats = build.ingest_parallel(con, corpus, "2026-11-30T00:00:00+00:00")
        files: dict = {"parallel_csv": "corpus.csv"}
        if binding:
            state = build.source_state(self.repo)
            files["siamsil_data_source"] = {**state, "working_tree_clean": clean and state["working_tree_clean"]}
        con.execute("INSERT INTO dataset_versions (name, version, created_at, script_version, source_files) VALUES "
                    "(?,?,?,?,?)", ("siamsil-language", "v2", "2026-11-30T00:00:00+00:00", "drill", json.dumps(files)))
        con.commit()
        con.close()
        removals = folder / "parallel-removals.jsonl"
        record = build.write_removals(stats["removals"], removals)
        quality = folder / "quality_report.json"
        quality.write_text(json.dumps({"parallel": {
            "source_rows": stats["counts"]["source_rows"], "unique_pairs_kept": stats["counts"]["ingested"],
            "duplicates_dropped": stats["counts"].get("duplicates", 0), "empty_dropped": stats["counts"].get("empty", 0),
            "removals": record}}), encoding="utf-8")
        bible = folder / "bible_versions.sqlite"
        sqlite3.connect(bible).executescript("CREATE TABLE example (x INTEGER);")
        rights = folder / "rights.json"
        base_rights = json.loads((ROOT / "data" / "rights.json").read_text(encoding="utf-8"))
        if rights_note:
            base_rights["_drill_note"] = rights_note
        rights.write_text(json.dumps(base_rights, indent=2), encoding="utf-8")
        bundle = folder / "siamsil-data.tar.gz"
        with tarfile.open(bundle, "w:gz") as archive:
            archive.add(db, arcname="siamsil_language.sqlite")
            archive.add(bible, arcname="bible_versions.sqlite")
            archive.add(rights, arcname="json/rights.json")
        manifest = release_manifest.build_v2(
            bundle, created_at="2026-11-30T09:30:00+00:00",
            source=release_manifest.source_record(self.repo, db),
            approval=release_manifest.approval_record(APPROVER if approved else None, APPROVED_AT if approved else None),
            exports=release_manifest.exports_record(None), evaluation=release_manifest.evaluation_record([]),
            derivation=release_manifest.derivation_record(quality, removals))
        return self.publish(name, bundle, manifest)

    def publish(self, name: str, bundle: Path, manifest: dict) -> dict:
        shutil.copy(bundle, self.serve / f"{name}.tar.gz")
        raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (self.serve / f"{name}.release.json").write_bytes(raw)
        return {"name": name, "bundle_sha": sha(bundle), "manifest_sha": hashlib.sha256(raw).hexdigest(),
                "manifest": manifest, "bundle_path": bundle}

    # ---- running fetch_data exactly as the container does ------------------------------------------------------

    def env(self, rel: dict, volume: Path, **over: str) -> dict[str, str]:
        base = {"PATH": os.environ.get("PATH", ""), "SIAMSIL_ENVIRONMENT": "staging", "SIAMSIL_DATA_ROOT": str(volume),
                "SIAMSIL_DATA_BUNDLE_URL": f"{self.base}/{rel['name']}.tar.gz",
                "SIAMSIL_DATA_BUNDLE_SHA256": rel["bundle_sha"],
                "SIAMSIL_DATA_RELEASE_MANIFEST_URL": f"{self.base}/{rel['name']}.release.json",
                "SIAMSIL_DATA_RELEASE_MANIFEST_SHA256": rel["manifest_sha"]}
        base.update(over)
        return {k: v for k, v in base.items() if v is not None}

    def fetch(self, env: dict[str, str]) -> tuple[int, str, float]:
        started = time.perf_counter()
        done = subprocess.run([sys.executable, str(HERE / "fetch_data.py")], env=env, capture_output=True, text=True)
        text = (done.stdout + done.stderr).strip().replace("\n", " | ")
        return done.returncode, text[-260:], time.perf_counter() - started

    def snapshot(self, volume: Path) -> dict[str, str]:
        out = {}
        for member in ("siamsil_language.sqlite", "bible_versions.sqlite", "json/rights.json"):
            path = volume / member
            out[member] = sha(path)[:12] if path.is_file() else "(absent)"
        return out

    def expect(self, scenario: str, area: str, rc: int, text: str, *, accept: bool, contains: str = "",
               seconds: float | None = None, note: str = "") -> bool:
        ok = (rc == 0) == accept and (not contains or contains in text)
        self.results.append({"scenario": scenario, "area": area, "expected": "accept" if accept else "reject",
                             "exit": rc, "passed": ok, "message": text[-200:], "seconds": round(seconds, 2) if seconds else None,
                             "note": note})
        print(f"{'PASS' if ok else 'FAIL'}  {area:10s} {scenario}")
        if not ok:
            print(f"      exit {rc}: {text[-220:]}")
        return ok

    def volume(self, name: str) -> Path:
        path = self.work / "volumes" / name
        path.mkdir(parents=True)
        return path

    def pristine(self, rel: dict, name: str) -> Path:
        volume = self.volume(name)
        rc, text, _ = self.fetch(self.env(rel, volume))
        assert rc == 0, text
        return volume

    # ---- scenarios --------------------------------------------------------------------------------------------

    def run(self) -> None:
        a = self.release("release-a", rights_note="release A")
        b = self.release("release-b", rights_note="release B")

        # 1. a correctly configured release starts
        v = self.volume("good")
        rc, text, secs = self.fetch(self.env(a, v))
        self.expect("correct bundle + pinned manifest installs", "startup", rc, text, accept=True, seconds=secs)
        self.expect("installed files present with marker and stored manifest", "startup",
                    0 if (v / ".release.json").is_file() and (v / f".bundle-{a['bundle_sha']}").exists() and
                    (v / "json" / "rights.json").is_file() else 1, "", accept=True)
        rc, text, secs = self.fetch(self.env(a, v))
        self.expect("restart re-checks the stored manifest and starts", "startup", rc, text, accept=True,
                    contains="already present", seconds=secs)
        try:
            info = check_release.verified_manifest(v, a["bundle_sha"], None, "staging")
            self.expect("full on-container verification hashes every file", "startup", 0, json.dumps(info), accept=True)
        except Exception as error:  # noqa: BLE001
            self.expect("full on-container verification hashes every file", "startup", 1, str(error), accept=True)

        # 2. missing parts
        rc, text, _ = self.fetch(self.env(a, self.volume("m-manifest"), SIAMSIL_DATA_RELEASE_MANIFEST_URL=f"{self.base}/absent.json"))
        self.expect("release manifest missing (404)", "missing", rc, text, accept=False, contains="cannot download the release manifest (HTTP 404)")
        rc, text, _ = self.fetch(self.env(a, self.volume("m-bundle"), SIAMSIL_DATA_BUNDLE_URL=f"{self.base}/absent.tar.gz"))
        self.expect("bundle missing (404)", "missing", rc, text, accept=False, contains="cannot download the data bundle (HTTP 404)")
        rc, text, _ = self.fetch(self.env(a, self.volume("m-pin"), SIAMSIL_DATA_RELEASE_MANIFEST_SHA256=None))
        self.expect("manifest pin not configured", "missing", rc, text, accept=False, contains="RELEASE_MANIFEST_SHA256")
        rc, text, _ = self.fetch(self.env(a, self.volume("m-url"), SIAMSIL_DATA_BUNDLE_URL=None,
                                          SIAMSIL_DATA_RELEASE_MANIFEST_URL=None))
        self.expect("no bundle installed and none configured (no silent skip)", "missing", rc, text, accept=False,
                    contains="no verified data bundle")
        rc, text, _ = self.fetch(self.env(a, self.volume("m-manifest-url"), SIAMSIL_DATA_RELEASE_MANIFEST_URL=None))
        self.expect("bundle configured but no manifest address", "missing", rc, text, accept=False,
                    contains="requires a release manifest")
        marker_only = self.volume("m-stored")
        (marker_only / f".bundle-{a['bundle_sha']}").touch()
        rc, text, _ = self.fetch(self.env(a, marker_only))
        self.expect("bundle marker present but stored manifest missing", "missing", rc, text, accept=False,
                    contains="installed release manifest")

        # 3. corrupted
        bad = bytearray((self.serve / "release-a.tar.gz").read_bytes())
        bad[len(bad) // 2] ^= 0xFF
        (self.serve / "corrupt.tar.gz").write_bytes(bytes(bad))
        v = self.volume("c-bundle")
        rc, text, _ = self.fetch(self.env(a, v, SIAMSIL_DATA_BUNDLE_URL=f"{self.base}/corrupt.tar.gz"))
        self.expect("corrupted bundle download", "corrupted", rc, text, accept=False, contains="checksum mismatch")
        self.expect("a refused install leaves the volume empty", "corrupted",
                    0 if not [p for p in v.iterdir() if not p.name.startswith(".")] else 1, "", accept=True)
        edited = json.loads((self.serve / "release-a.release.json").read_text(encoding="utf-8"))
        edited["approval"]["approved_by"] = "someone else"
        (self.serve / "edited.release.json").write_text(json.dumps(edited, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rc, text, _ = self.fetch(self.env(a, self.volume("c-manifest"), SIAMSIL_DATA_RELEASE_MANIFEST_URL=f"{self.base}/edited.release.json"))
        self.expect("edited manifest no longer matches its pin", "corrupted", rc, text, accept=False, contains="does not match")
        v = self.pristine(a, "c-rights")
        (v / "json" / "rights.json").write_text(json.dumps({"sources": {}}), encoding="utf-8")
        rc, text, _ = self.fetch(self.env(a, v))
        self.expect("rights register changed after install, caught on restart", "corrupted", rc, text, accept=False,
                    contains="rights")
        v = self.pristine(a, "c-size")
        with (v / "siamsil_language.sqlite").open("ab") as handle:
            handle.write(b"x")
        rc, text, _ = self.fetch(self.env(a, v))
        self.expect("language database size changed, caught on restart", "corrupted", rc, text, accept=False,
                    contains="size mismatch")
        v = self.pristine(a, "c-flip")
        path = v / "siamsil_language.sqlite"
        data = bytearray(path.read_bytes())
        data[-1] ^= 0xFF
        path.write_bytes(bytes(data))
        rc, text, _ = self.fetch(self.env(a, v))
        self.expect("same-size content change passes the cheap restart check (known limitation)", "corrupted", rc,
                    text, accept=True, note="restart checks sizes and the rights register only")
        try:
            check_release.verified_manifest(v, a["bundle_sha"], None, "staging")
            self.expect("same-size content change caught by full verification", "corrupted", 0, "", accept=False)
        except RuntimeError as error:
            self.expect("same-size content change caught by full verification", "corrupted", 1, str(error), accept=False,
                        contains="does not match the manifest")

        # 4. mismatched
        rc, text, _ = self.fetch(self.env(a, self.volume("x-other"), SIAMSIL_DATA_RELEASE_MANIFEST_URL=f"{self.base}/release-b.release.json",
                                          SIAMSIL_DATA_RELEASE_MANIFEST_SHA256=b["manifest_sha"]))
        self.expect("manifest belongs to a different bundle", "mismatched", rc, text, accept=False,
                    contains="not the bundle this deployment expects")
        rc, text, _ = self.fetch(self.env(a, self.volume("x-pin"), SIAMSIL_DATA_RELEASE_MANIFEST_SHA256=b["manifest_sha"]))
        self.expect("wrong manifest pin (another release's)", "mismatched", rc, text, accept=False)
        mismatch = json.loads((self.serve / "release-a.release.json").read_text(encoding="utf-8"))
        mismatch["rights_registry"]["sha256"] = "0" * 64
        raw = (json.dumps(mismatch, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (self.serve / "rights-mismatch.release.json").write_bytes(raw)
        rc, text, _ = self.fetch(self.env(a, self.volume("x-rights"),
                                          SIAMSIL_DATA_RELEASE_MANIFEST_URL=f"{self.base}/rights-mismatch.release.json",
                                          SIAMSIL_DATA_RELEASE_MANIFEST_SHA256=hashlib.sha256(raw).hexdigest()))
        self.expect("manifest declares a rights hash the bundle does not carry", "mismatched", rc, text, accept=False,
                    contains="rights_registry.sha256")
        rc, text, _ = self.fetch(self.env(a, self.volume("x-snapshot"), SIAMSIL_RIGHTS_SHA256="1" * 64))
        self.expect("configured rights snapshot differs from the release", "mismatched", rc, text, accept=False,
                    contains="configured rights snapshot")
        other = self.work / "other-rights.json"
        other.write_text(json.dumps({"sources": {}}), encoding="utf-8")
        rc, text, _ = self.fetch(self.env(a, self.volume("x-override"), SIAMSIL_RIGHTS_FILE=str(other)))
        self.expect("SIAMSIL_RIGHTS_FILE points at a different register", "mismatched", rc, text, accept=False,
                    contains="SIAMSIL_RIGHTS_FILE")
        legacy = release_manifest.validate(a["bundle_path"])
        raw = (json.dumps(legacy, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (self.serve / "legacy.release.json").write_bytes(raw)
        legacy_env = {"SIAMSIL_DATA_RELEASE_MANIFEST_URL": f"{self.base}/legacy.release.json",
                      "SIAMSIL_DATA_RELEASE_MANIFEST_SHA256": hashlib.sha256(raw).hexdigest()}
        rc, text, _ = self.fetch(self.env(a, self.volume("x-legacy"), **legacy_env))
        self.expect("legacy (schema 1) manifest in staging", "mismatched", rc, text, accept=False, contains="legacy")
        rc, text, _ = self.fetch(self.env(a, self.volume("x-legacy-dev"), SIAMSIL_ENVIRONMENT="development", **legacy_env))
        self.expect("legacy manifest still accepted in development", "mismatched", rc, text, accept=True)

        # 5. unapproved or unbound
        un = self.release("release-unapproved", approved=False)
        rc, text, _ = self.fetch(self.env(un, self.volume("u-staging")))
        self.expect("unapproved release in staging", "unapproved", rc, text, accept=False, contains="unapproved")
        rc, text, _ = self.fetch(self.env(un, self.volume("u-dev"), SIAMSIL_ENVIRONMENT="development"))
        self.expect("unapproved release in development", "unapproved", rc, text, accept=True)
        dirty = self.release("release-dirty", clean=False)
        rc, text, _ = self.fetch(self.env(dirty, self.volume("u-dirty")))
        self.expect("database built from a dirty data repository", "unapproved", rc, text, accept=False,
                    contains="working_tree_clean")
        unbound = self.release("release-unbound", binding=False)
        rc, text, _ = self.fetch(self.env(unbound, self.volume("u-unbound")))
        self.expect("operator-supplied source commit (not recorded in the database)", "unapproved", rc, text,
                    accept=False, contains="binding")

        # 6. rollback
        v = self.volume("rollback")
        rc, text, _ = self.fetch(self.env(a, v))
        self.expect("install release A", "rollback", rc, text, accept=True)
        state_a = self.snapshot(v)
        rc, text, _ = self.fetch(self.env(b, v))
        self.expect("upgrade to release B", "rollback", rc, text, accept=True)
        state_b = self.snapshot(v)
        self.expect("B's files replaced A's", "rollback", 0 if state_a != state_b else 1, "", accept=True)
        c = self.release("release-c", rights_note="release C")
        (self.serve / "release-c.tar.gz").write_bytes(bytes(bytearray((self.serve / "release-c.tar.gz").read_bytes())[:-20]))
        rc, text, _ = self.fetch(self.env(c, v))
        self.expect("failed upgrade to a damaged release C", "rollback", rc, text, accept=False)
        self.expect("a failed upgrade leaves release B untouched", "rollback", 0 if self.snapshot(v) == state_b else 1, "",
                    accept=True)
        rc, text, _ = self.fetch(self.env(a, v, SIAMSIL_DATA_RELEASE_MANIFEST_SHA256=b["manifest_sha"],
                                          SIAMSIL_DATA_RELEASE_MANIFEST_URL=f"{self.base}/release-a.release.json"))
        self.expect("rollback to A with B's manifest hash left in place (the documented mistake)", "rollback", rc, text,
                    accept=False)
        self.expect("that refused rollback changes nothing", "rollback", 0 if self.snapshot(v) == state_b else 1, "",
                    accept=True)
        rc, text, secs = self.fetch(self.env(a, v))
        self.expect("rollback to A with A's bundle, manifest and hashes together", "rollback", rc, text, accept=True,
                    seconds=secs)
        self.expect("volume is exactly release A again", "rollback", 0 if self.snapshot(v) == state_a else 1, "", accept=True)
        rc, text, _ = self.fetch(self.env(a, v))
        self.expect("restart after rollback", "rollback", rc, text, accept=True, contains="already present")


ACCESS_KEY, SECRET_KEY, BUCKET = "AKIDDRILLEXAMPLE", "drill/secret+key", "siamsil-staging-bundle"


def start_bucket(objects: dict[str, bytes], work: Path) -> tuple[ThreadingHTTPServer, str, Path]:
    """A local S3-compatible HTTPS endpoint (path style) that serves `objects` only for a correctly signed,
    unexpired SigV4 query-string request, checked with the same algorithm botocore produces (see the PR notes)."""
    cert, key = work / "bucket-cert.pem", work / "bucket-key.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key), "-out", str(cert),
                    "-days", "1", "-subj", "/CN=localhost", "-addext", "subjectAltName=IP:127.0.0.1,DNS:localhost"],
                   check=True, capture_output=True)
    holder: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args) -> None:
            pass

        def do_GET(self) -> None:  # noqa: N802
            split = urllib.parse.urlsplit(self.path)
            query = dict(urllib.parse.parse_qsl(split.query))
            prefix = f"/{BUCKET}/"
            if not split.path.startswith(prefix):
                return self.send_error(404)
            name = urllib.parse.unquote(split.path[len(prefix):])
            try:
                when = datetime.strptime(query["X-Amz-Date"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                expires = int(query["X-Amz-Expires"])
                access = query["X-Amz-Credential"].split("/")[0]
            except (KeyError, ValueError):
                return self.send_error(403, "malformed signature")
            expected = fetch_data.presigned_url(holder["endpoint"], BUCKET, name, ACCESS_KEY, SECRET_KEY, expires=expires,
                                                now=when)
            expected_signature = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(expected).query))["X-Amz-Signature"]
            if access != ACCESS_KEY or query.get("X-Amz-Signature") != expected_signature:
                return self.send_error(403, "signature does not match")
            if datetime.now(timezone.utc) > when + timedelta(seconds=expires):
                return self.send_error(403, "expired")
            if name not in objects:
                return self.send_error(404)
            body = objects[name]
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    holder["endpoint"] = f"https://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, holder["endpoint"], cert


def s3_scenarios(drill: Drill) -> None:
    """The bucket path (SIAMSIL_DATA_BUNDLE_S3_*): presigned links, the manifest key beside the bundle key, and what
    a bad signature or a missing object looks like in the boot log. Needs openssl for a throwaway certificate."""
    folder_release = drill.release("s3-folder", rights_note="bucket release, folder layout")
    flat_release = drill.release("s3-flat", rights_note="bucket release, flat layout")

    def read(name: str) -> bytes:
        return (drill.serve / name).read_bytes()

    folder = f"releases/sha256-{folder_release['bundle_sha']}"
    objects = {
        f"{folder}/siamsil-data.tar.gz": read("s3-folder.tar.gz"),
        f"{folder}/release.json": read("s3-folder.release.json"),
        "siamsil-data-2026-11-30.tar.gz": read("s3-flat.tar.gz"),
        "siamsil-data-2026-11-30.release.json": read("s3-flat.release.json"),
        "orphan.tar.gz": read("s3-flat.tar.gz"),  # a bundle with no manifest beside it
    }
    server, endpoint, cert = start_bucket(objects, drill.work)

    def bucket_env(rel: dict, key: str, volume: Path, **over: str | None) -> dict[str, str]:
        env = drill.env(rel, volume, SIAMSIL_DATA_BUNDLE_URL=None, SIAMSIL_DATA_RELEASE_MANIFEST_URL=None)
        env.update({"SIAMSIL_DATA_BUNDLE_S3_ENDPOINT": endpoint, "SIAMSIL_DATA_BUNDLE_S3_BUCKET": BUCKET,
                    "SIAMSIL_DATA_BUNDLE_S3_ACCESS_KEY_ID": ACCESS_KEY, "SIAMSIL_DATA_BUNDLE_S3_SECRET_ACCESS_KEY": SECRET_KEY,
                    "SIAMSIL_DATA_BUNDLE_S3_KEY": key, "SSL_CERT_FILE": str(cert)})
        env.update({k: v for k, v in over.items() if v is not None})
        return env

    try:
        rc, text, _ = drill.fetch(bucket_env(folder_release, f"{folder}/siamsil-data.tar.gz", drill.volume("s3-1")))
        drill.expect("bucket: signed links, folder layout (release.json beside the bundle)", "bucket", rc, text, accept=True)
        rc, text, _ = drill.fetch(bucket_env(flat_release, "siamsil-data-2026-11-30.tar.gz", drill.volume("s3-2")))
        drill.expect("bucket: flat dated key (<name>.release.json)", "bucket", rc, text, accept=True)
        rc, text, _ = drill.fetch(bucket_env(flat_release, "siamsil-data-2026-11-30.tar.gz", drill.volume("s3-3"),
                                             SIAMSIL_DATA_BUNDLE_S3_SECRET_ACCESS_KEY="not-the-secret"))
        drill.expect("bucket: wrong secret is refused (HTTP 403) without printing the link", "bucket", rc, text,
                     accept=False, contains="HTTP 403")
        drill.expect("the boot log never contains a signature", "bucket", 1 if "X-Amz-Signature" in text else 0, "", accept=True)
        rc, text, _ = drill.fetch(bucket_env(flat_release, "orphan.tar.gz", drill.volume("s3-4")))
        drill.expect("bucket: bundle with no manifest beside it", "bucket", rc, text, accept=False,
                     contains="cannot download the release manifest (HTTP 404)")
        rc, text, _ = drill.fetch(bucket_env(flat_release, "siamsil-data-2026-11-30.tar.gz", drill.volume("s3-5"),
                                             SIAMSIL_DATA_RELEASE_MANIFEST_KEY=f"{folder}/release.json"))
        drill.expect("bucket: a manifest key from another release is refused", "bucket", rc, text, accept=False)
    finally:
        server.shutdown()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def api_scenarios(drill: Drill, database_url: str) -> None:
    """Start the real API the way backend/Dockerfile does (fetch_data, migrations, uvicorn) in STAGING mode against a
    PostgreSQL database the caller provides. Needs PostgreSQL, so it runs only when --database-url is given."""
    a = drill.release("api-a", rights_note="api release A")
    b = drill.release("api-b", rights_note="api release B")
    backend = ROOT / "backend"

    def start(rel: dict, volume: Path, **over: str):
        port = free_port()
        env = drill.env(rel, volume, SIAMSIL_DATABASE_URL=database_url, SIAMSIL_DATABASE_REQUIRED="true",
                        SIAMSIL_CORS_ORIGINS='["https://staging.example.invalid"]',
                        SIAMSIL_LANGUAGE_DB=str(volume / "siamsil_language.sqlite"),
                        SIAMSIL_BIBLE_VERSIONS_DB=str(volume / "bible_versions.sqlite"),
                        SIAMSIL_DATA_DIR=str(volume / "json"), SIAMSIL_RATE_LIMIT_PER_MINUTE="0", **over)
        chain = (f"{sys.executable} scripts/fetch_data.py && {sys.executable} -m alembic upgrade head && "
                 f"exec {sys.executable} -m uvicorn main:app --host 127.0.0.1 --port {port} --no-access-log")
        process = subprocess.Popen(["bash", "-c", chain], cwd=backend, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)
        return process, port

    def ready(process: subprocess.Popen, port: int) -> tuple[bool, str]:
        deadline = time.time() + 40
        while time.time() < deadline and process.poll() is None:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health/ready", timeout=2) as response:
                    return response.status == 200, response.read().decode("utf-8")
            except OSError:
                time.sleep(0.5)
        return False, (process.stdout.read() if process.poll() is not None else "timed out")[-300:]

    def stop(process: subprocess.Popen) -> str:
        if process.poll() is None:
            process.terminate()
        try:
            return (process.communicate(timeout=10)[0] or "").strip().replace("\n", " | ")[-260:]
        except subprocess.TimeoutExpired:
            process.kill()
            return ""

    volume = drill.volume("api")
    process, port = start(a, volume)
    ok, body = ready(process, port)
    state = json.loads(body) if ok else {}
    drill.expect("staging API starts after verified install, migrations and PostgreSQL", "api",
                 0 if ok and state.get("status") == "ok" else 1, body[-200:], accept=True)
    database = (state.get("checks") or {}).get("application_database") or {}
    drill.expect("readiness reports the application database as ready", "api",
                 0 if database.get("ready") or database.get("status") == "ok" else 1, json.dumps(database), accept=True)
    served = sha(volume / "json" / "rights.json")
    drill.expect("the API reads the verified rights register", "api",
                 0 if served == a["manifest"]["rights_registry"]["sha256"] else 1, "", accept=True)
    stop(process)

    # A rights override that is not the verified register: the container stops before serving anything.
    other = drill.work / "api-other-rights.json"
    other.write_text(json.dumps({"sources": {}}), encoding="utf-8")
    process, port = start(a, volume, SIAMSIL_RIGHTS_FILE=str(other))
    ok, body = ready(process, port)
    drill.expect("SIAMSIL_RIGHTS_FILE override stops the container before it serves", "api", 0 if ok else 1, body[-200:],
                 accept=False, contains="SIAMSIL_RIGHTS_FILE")
    stop(process)

    # A rights register tampered after install: fetch_data fails, so nothing after it in the start chain runs.
    (volume / "json" / "rights.json").write_text(json.dumps({"sources": {}}), encoding="utf-8")
    process, port = start(a, volume)
    ok, body = ready(process, port)
    drill.expect("tampered rights register on the volume: the API never starts", "api", 0 if ok else 1, body[-200:],
                 accept=False, contains="rights")
    stop(process)

    # Upgrade to B, roll back to A, and the API serves A's register again.
    volume = drill.volume("api-rollback")
    for rel, label in ((a, "A"), (b, "B"), (a, "A (rollback)")):
        process, port = start(rel, volume)
        ok, body = ready(process, port)
        right = sha(volume / "json" / "rights.json") == rel["manifest"]["rights_registry"]["sha256"]
        drill.expect(f"API serves release {label} with its own rights register", "api", 0 if ok and right else 1, body[-160:],
                     accept=True)
        stop(process)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--work", type=Path, required=True, help="scratch folder (emptied first)")
    parser.add_argument("--database-url", help="a PostgreSQL URL (postgresql+psycopg://...) to also run the staging-mode "
                        "API scenarios; use a throwaway database")
    parser.add_argument("--json", type=Path, help="write the results here")
    args = parser.parse_args()
    drill = Drill(args.work)
    drill.run()
    if shutil.which("openssl"):
        s3_scenarios(drill)
    else:
        print("skipped the bucket scenarios: openssl is not installed")
    if args.database_url:
        api_scenarios(drill, args.database_url)
    failed = [r for r in drill.results if not r["passed"]]
    print(f"\n{len(drill.results) - len(failed)} of {len(drill.results)} scenarios behaved as required")
    if args.json:
        args.json.write_text(json.dumps(drill.results, indent=2), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
