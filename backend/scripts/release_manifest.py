"""Inspect a built Siamsil bundle and write a non-sensitive, immutable release manifest (release.json).

Usage, development bundle (schema 1, accepted only in development and test):
  python backend/scripts/release_manifest.py dist/siamsil-data.tar.gz --output dist/release.json

Usage, production release (schema 2, required in staging and production):
  python backend/scripts/release_manifest.py dist/siamsil-data.tar.gz --output dist/release.json --production \\
    --data-repo ../siamsil-data \\
    --export-manifest data/datasets/<name>/manifest.json     (or --no-exports when nothing is exported)
    --eval-set data/evaluation/human/en-zomi-v1.jsonl        (repeatable; hashes only, content is never copied)
    --quality-report data/processed/language/quality_report.json \\
    --removals data/processed/language/parallel-removals.jsonl \\
    --approved-by "<name>" --approved-at 2026-11-30T09:00:00

Fails closed if either required SQLite database is absent, corrupt, or the tar has unsafe names. It does NOT confer
licensing clearance on included sources, and it never approves a release: --approved-by must be given by a person
(docs/DATA_RELEASES.md). Keep parallel-removals.jsonl beside release.json in the private bucket, not in public places.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_contract as contract  # noqa: E402

REQUIRED = {"siamsil_language.sqlite", "bible_versions.sqlite"}
SAFE_NAME = re.compile(r"^(?:siamsil_language\.sqlite|bible_versions\.sqlite|json/[A-Za-z0-9_.-]+\.json)$")
EXPORT_SPLITS = ("train", "validation", "test")


def sha256(path: Path) -> str:
    return contract.sha256_file(path)


def validate(bundle: Path, *, created_at: str | None = None) -> dict:
    """The schema 1 manifest: bundle digest, per-file digests, creation time. Unchanged; build_v2 extends it."""
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
        "schema_version": contract.SCHEMA_V1,
        "release_id": f"sha256-{checksum[:16]}",
        "bundle_sha256": checksum,
        "bundle_bytes": bundle.stat().st_size,
        "object_key": f"releases/sha256-{checksum}/siamsil-data.tar.gz",
        "created_at_utc": created_at or datetime.now(timezone.utc).isoformat(),
        "contents": members,
        "note": "Build integrity verified; source rights and content approvals are separate gates.",
    }


# ---- schema 2 declarations ------------------------------------------------------------------------------------


def source_record(data_repo: Path) -> dict:
    """The siamsil-data commit this release was built from, and whether its working tree had uncommitted changes."""
    def git(*args: str) -> str:
        done = subprocess.run(["git", "-C", str(data_repo), *args], capture_output=True, text=True, check=False)
        if done.returncode != 0:
            raise ValueError(f"{data_repo} is not a readable git repository: {done.stderr.strip()}")
        return done.stdout.strip()

    return {
        "siamsil_data_commit": git("rev-parse", "HEAD"),
        "working_tree_clean": git("status", "--porcelain") == "",
    }


def exports_record(export_manifest: Path | None) -> dict:
    """Approved export counts from an export_datasets.py manifest. Refused if any uncleared source was admitted."""
    if export_manifest is None:
        return {"approved_counts": {}, "export_manifest_sha256": None}
    data = json.loads(Path(export_manifest).read_text(encoding="utf-8"))
    if data.get("uncleared_sources_included"):
        raise ValueError("export manifest admits uncleared sources "
                         f"({', '.join(data['uncleared_sources_included'])}); its counts cannot be approved")
    splits = data.get("splits") or {}
    return {
        "approved_counts": {name: int((splits.get(name) or {}).get("total", 0)) for name in EXPORT_SPLITS},
        "export_manifest_sha256": sha256(export_manifest),
    }


def evaluation_record(paths: list[Path]) -> dict:
    """Protected evaluation sets by name and SHA-256 only. The text of an evaluation item never enters a release."""
    sets = []
    for path in sorted((Path(p) for p in paths), key=lambda p: p.name):
        text = path.read_text(encoding="utf-8")
        lines = [line for line in text.splitlines() if line.strip()]
        items = len(lines) if path.suffix == ".jsonl" else max(0, len(lines) - 1)
        sets.append({"name": path.name, "sha256": sha256(path), "items": items, "frozen": ".draft" not in path.name})
    return {"sets": sets, "sets_sha256": contract.canonical_hash(sets)}


def derivation_record(quality_report: Path, removals: Path) -> dict:
    """How the corpus row count was reached, from the build's quality report and its per-row removal record."""
    parallel = json.loads(Path(quality_report).read_text(encoding="utf-8"))["parallel"]
    records = sum(1 for line in Path(removals).read_text(encoding="utf-8").splitlines() if line.strip())
    return {"parallel_corpus": {
        "source_rows": parallel["source_rows"],
        "kept": parallel["unique_pairs_kept"],
        "removed": {"duplicate_pair": parallel["duplicates_dropped"], "empty_side": parallel["empty_dropped"]},
        "removals_file": {"name": contract.REMOVALS_NAME, "sha256": sha256(removals), "records": records},
    }}


def approval_record(approved_by: str | None, approved_at: str | None) -> dict:
    """Recorded only when a person supplies both values. Nothing here, or in any AI step, approves a release."""
    if approved_by or approved_at:
        if not (approved_by and approved_at):
            raise ValueError("--approved-by and --approved-at go together")
        return {"status": "approved", "approved_by": approved_by, "approved_at_utc": approved_at}
    return {"status": "unapproved", "approved_by": None, "approved_at_utc": None}


def build_v2(bundle: Path, *, source: dict, approval: dict, exports: dict, evaluation: dict, derivation: dict,
             created_at: str | None = None) -> dict:
    """The schema 1 manifest plus the declarations the verifier checks. Extends release.json; does not replace it."""
    manifest = validate(bundle, created_at=created_at)
    rights = manifest["contents"].get(contract.RIGHTS_MEMBER)
    if rights is None:
        raise ValueError(f"the bundle has no {contract.RIGHTS_MEMBER}; a schema 2 release must carry its rights register")
    manifest.update({
        "schema_version": contract.SCHEMA_V2,
        "source": source,
        "rights_registry": {"member": contract.RIGHTS_MEMBER, "sha256": rights["sha256"]},
        "approval": approval,
        "exports": exports,
        "protected_evaluation": evaluation,
        "derivation": derivation,
        "note": "Build integrity verified; source rights and content approvals are separate gates. "
                "approval is a person's recorded decision, not something this tool or an AI decides.",
    })
    return manifest


def extract_language_db(bundle: Path, directory: Path) -> Path:
    target = Path(directory) / "siamsil_language.sqlite"
    with tarfile.open(bundle, "r:gz") as archive, archive.extractfile("siamsil_language.sqlite") as source:
        target.write_bytes(source.read())
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--production", action="store_true",
                        help="write a schema 2 manifest and require every declaration below; verified before writing")
    parser.add_argument("--data-repo", type=Path, help="siamsil-data clone the bundle was built from")
    parser.add_argument("--export-manifest", type=Path, help="export_datasets.py manifest.json")
    parser.add_argument("--no-exports", action="store_true", help="declare that this release approves no export")
    parser.add_argument("--eval-set", type=Path, action="append", default=[], help="evaluation set file (repeatable)")
    parser.add_argument("--quality-report", type=Path, help="build_language_db.py quality_report.json")
    parser.add_argument("--removals", type=Path, help="parallel-removals.jsonl from the same build")
    parser.add_argument("--approved-by", help="who approved this release (a person)")
    parser.add_argument("--approved-at", help="approval time, ISO 8601 UTC, e.g. 2026-11-30T09:00:00")
    args = parser.parse_args()

    extended = any((args.production, args.data_repo, args.export_manifest, args.no_exports, args.eval_set,
                    args.quality_report, args.removals, args.approved_by, args.approved_at))
    try:
        if not extended:
            manifest = validate(args.bundle)
        else:
            missing = [flag for flag, value in (
                ("--data-repo", args.data_repo), ("--quality-report", args.quality_report),
                ("--removals", args.removals)) if value is None]
            if not (args.export_manifest or args.no_exports):
                missing.append("--export-manifest or --no-exports")
            if args.production and not (args.approved_by and args.approved_at):
                missing.append("--approved-by and --approved-at")
            if missing:
                parser.error("a schema 2 release needs " + ", ".join(missing))
            manifest = build_v2(
                args.bundle,
                source=source_record(args.data_repo),
                approval=approval_record(args.approved_by, args.approved_at),
                exports=exports_record(args.export_manifest),
                evaluation=evaluation_record(args.eval_set),
                derivation=derivation_record(args.quality_report, args.removals),
            )
            with tempfile.TemporaryDirectory() as directory:
                problems = contract.check_derivation(
                    manifest, args.removals, extract_language_db(args.bundle, Path(directory)))
            problems += contract.check_structure(manifest, strict=args.production)
            if problems:
                sys.exit("release not written:\n  - " + "\n  - ".join(problems))
    except (ValueError, OSError, KeyError) as error:
        sys.exit(f"release not written: {error}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    args.output.write_text(text, encoding="utf-8")
    print(json.dumps({"release_id": manifest["release_id"], "object_key": manifest["object_key"],
                      "sha256": manifest["bundle_sha256"],
                      "release_manifest_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                      "schema_version": manifest["schema_version"]}))


if __name__ == "__main__":
    main()
