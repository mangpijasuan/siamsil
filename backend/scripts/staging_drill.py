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
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "ml_pipeline" / "scripts"))
import build_language_db as build  # noqa: E402
import check_release  # noqa: E402
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--work", type=Path, required=True, help="scratch folder (emptied first)")
    parser.add_argument("--json", type=Path, help="write the results here")
    args = parser.parse_args()
    drill = Drill(args.work)
    drill.run()
    failed = [r for r in drill.results if not r["passed"]]
    print(f"\n{len(drill.results) - len(failed)} of {len(drill.results)} scenarios behaved as required")
    if args.json:
        args.json.write_text(json.dumps(drill.results, indent=2), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
