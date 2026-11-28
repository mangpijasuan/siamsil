"""The data-release contract: what a Siamsil data release must declare, and how an installed bundle is checked.

Shared by release_manifest.py (builds release.json), fetch_data.py (installs a bundle on boot) and check_release.py
(on-container verification). Standard library only: fetch_data runs before the API's dependencies matter.

release.json has two schema versions:

  1  the original: bundle digest, per-file digests, creation time. Valid only for local and development bundles.
  2  version 1 plus the declarations below. Required in staging and production.

Version 2 adds, and the verifier checks:

  source                 siamsil-data commit SHA (40 hex), whether its tree was clean, and its binding: "database"
                         (read from the shipped language database) or "operator_supplied" (development only)
  rights_registry        SHA-256 of json/rights.json; must equal the file inside the bundle
  approval               status "unapproved" or "approved"; "approved" names who approved and when. A person's
                         decision recorded as data, never produced by code or by an AI
  exports                approved export counts and the export manifest's SHA-256
  protected_evaluation   evaluation sets by name and SHA-256 only (their content stays out of every release)
  derivation             how the corpus row count was reached (source rows, kept, removed by reason) and the
                         SHA-256 of the per-row removal record

What this does NOT do: it does not sign anything, grant a licence, or approve language. The manifest is pinned
by its own SHA-256 (SIAMSIL_DATA_RELEASE_MANIFEST_SHA256), exactly as the bundle is pinned. "approved" is a claim
recorded by a person; the verifier checks it is present and well formed, not that it is true.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

SCHEMA_V1 = 1
SCHEMA_V2 = 2
RIGHTS_MEMBER = "json/rights.json"
REMOVALS_NAME = "parallel-removals.jsonl"
INSTALLED_MANIFEST = ".release.json"
# Environments where a legacy (version 1) release is acceptable. Everything else is strict.
LEGACY_OK_ENVIRONMENTS = {"development", "test"}
SHA256_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
ISO_UTC_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
REMOVAL_REASONS = ("duplicate_pair", "empty_side")


class ReleaseVerificationError(Exception):
    """A release failed verification. `problems` lists every reason found, not just the first."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_hash(value: object) -> str:
    """SHA-256 of a value's canonical JSON (sorted keys, no spaces), so a list of references has one stable hash."""
    return sha256_text(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def is_strict(environment: str) -> bool:
    """Staging and production require the extended manifest; only development and test may use a legacy bundle."""
    return environment not in LEGACY_OK_ENVIRONMENTS


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def check_structure(manifest: object, *, strict: bool) -> list[str]:
    """Problems with the manifest itself, without touching any installed file."""
    if not isinstance(manifest, dict):
        return ["release manifest is not a JSON object"]
    problems: list[str] = []
    version = manifest.get("schema_version")
    if version not in (SCHEMA_V1, SCHEMA_V2):
        return [f"unsupported release manifest schema_version {version!r}"]
    bundle = manifest.get("bundle_sha256")
    if not isinstance(bundle, str) or not SHA256_RE.fullmatch(bundle):
        problems.append("bundle_sha256 is missing or not a full lowercase SHA-256")
    elif manifest.get("release_id") != f"sha256-{bundle[:16]}":
        problems.append("release_id does not match bundle_sha256")
    elif manifest.get("object_key") != f"releases/sha256-{bundle}/siamsil-data.tar.gz":
        problems.append("object_key does not match bundle_sha256")
    contents = manifest.get("contents")
    if not isinstance(contents, dict) or not contents:
        problems.append("contents is missing or empty")
    else:
        for name, record in contents.items():
            if (not isinstance(record, dict) or not isinstance(record.get("sha256"), str)
                    or not SHA256_RE.fullmatch(record["sha256"]) or not _is_int(record.get("bytes"))):
                problems.append(f"contents[{name!r}] needs bytes and a full SHA-256")

    if version == SCHEMA_V1:
        if strict:
            problems.append(
                "this is a legacy (schema 1) release manifest; staging and production require schema 2 "
                "(backend/scripts/release_manifest.py --production)")
        return problems

    problems += _check_v2(manifest, contents if isinstance(contents, dict) else {}, strict=strict)
    return problems


def _check_v2(manifest: dict, contents: dict, *, strict: bool) -> list[str]:
    problems: list[str] = []

    source = manifest.get("source")
    if not isinstance(source, dict) or not COMMIT_RE.fullmatch(str(source.get("siamsil_data_commit", ""))):
        problems.append("source.siamsil_data_commit must be a full 40-character commit SHA")
    elif strict and source.get("working_tree_clean") is not True:
        problems.append("source.working_tree_clean must be true: a release built from uncommitted data is not "
                        "tied to any commit")
    elif strict and source.get("binding") != "database":
        problems.append('source.binding must be "database": the commit has to be the one recorded inside the shipped '
                        "language database; an operator-supplied commit is a claim, not evidence (rebuild with "
                        "build_language_db.py from a siamsil-data checkout)")

    rights = manifest.get("rights_registry")
    if not isinstance(rights, dict) or rights.get("member") != RIGHTS_MEMBER \
            or not SHA256_RE.fullmatch(str(rights.get("sha256", ""))):
        problems.append(f"rights_registry must declare member {RIGHTS_MEMBER!r} and its SHA-256")
    else:
        declared = (contents.get(RIGHTS_MEMBER) or {}).get("sha256")
        if declared is None:
            problems.append(f"the bundle does not contain {RIGHTS_MEMBER}")
        elif declared != rights["sha256"]:
            problems.append("rights_registry.sha256 does not match the rights.json listed in contents")

    approval = manifest.get("approval")
    if not isinstance(approval, dict) or approval.get("status") not in ("unapproved", "approved"):
        problems.append('approval.status must be "unapproved" or "approved"')
    elif approval["status"] == "approved":
        if not str(approval.get("approved_by") or "").strip():
            problems.append("an approved release must name approval.approved_by")
        if not ISO_UTC_RE.match(str(approval.get("approved_at_utc") or "")):
            problems.append("an approved release must record approval.approved_at_utc (ISO 8601)")
    elif strict:
        problems.append("approval.status is \"unapproved\": staging and production need an approved release")

    exports = manifest.get("exports")
    if not isinstance(exports, dict) or not isinstance(exports.get("approved_counts"), dict) \
            or not all(_is_int(n) for n in exports["approved_counts"].values()):
        problems.append("exports.approved_counts must map each export split to a count")
    else:
        digest = exports.get("export_manifest_sha256")
        if exports["approved_counts"] and not SHA256_RE.fullmatch(str(digest or "")):
            problems.append("non-empty exports.approved_counts need exports.export_manifest_sha256")

    evaluation = manifest.get("protected_evaluation")
    if not isinstance(evaluation, dict) or not isinstance(evaluation.get("sets"), list):
        problems.append("protected_evaluation.sets must be a list (empty when none is frozen)")
    else:
        for entry in evaluation["sets"]:
            if not (isinstance(entry, dict) and entry.get("name") and SHA256_RE.fullmatch(str(entry.get("sha256", "")))
                    and _is_int(entry.get("items")) and isinstance(entry.get("frozen"), bool)):
                problems.append("each protected evaluation set needs name, sha256, items and frozen")
                break
        else:
            if evaluation.get("sets_sha256") != canonical_hash(evaluation["sets"]):
                problems.append("protected_evaluation.sets_sha256 does not match its sets")

    derivation = manifest.get("derivation")
    corpus = derivation.get("parallel_corpus") if isinstance(derivation, dict) else None
    if not isinstance(corpus, dict):
        problems.append("derivation.parallel_corpus is required")
    else:
        removed = corpus.get("removed")
        removals = corpus.get("removals_file")
        if not (_is_int(corpus.get("source_rows")) and _is_int(corpus.get("kept")) and isinstance(removed, dict)
                and set(removed) == set(REMOVAL_REASONS) and all(_is_int(n) for n in removed.values())):
            problems.append(f"derivation.parallel_corpus needs source_rows, kept and removed for {REMOVAL_REASONS}")
        elif corpus["source_rows"] != corpus["kept"] + sum(removed.values()):
            problems.append("derivation.parallel_corpus does not add up: source_rows must equal kept plus removed")
        if not (isinstance(removals, dict) and removals.get("name") == REMOVALS_NAME
                and SHA256_RE.fullmatch(str(removals.get("sha256", ""))) and _is_int(removals.get("records"))):
            problems.append("derivation.parallel_corpus.removals_file needs name, sha256 and records")
        elif isinstance(removed, dict) and removals["records"] != sum(removed.values()):
            problems.append("removals_file.records does not equal the number of rows removed")
    return problems


def check_installed(manifest: dict, root: Path, *, full: bool = True) -> list[str]:
    """Problems found by comparing the manifest with the files actually installed under `root`.

    full=True hashes every file (done once, when a bundle is installed). full=False checks that each file exists
    with the declared size, and hashes only the rights register: the file that decides what may be served. That is
    cheap enough for every restart.
    """
    root = Path(root)
    problems: list[str] = []
    for name, record in sorted((manifest.get("contents") or {}).items()):
        path = root / name
        if not path.is_file():
            problems.append(f"missing installed file: {name}")
            continue
        if path.stat().st_size != record.get("bytes"):
            problems.append(f"size mismatch: {name}")
            continue
        if full or name == RIGHTS_MEMBER:
            if sha256_file(path) != record.get("sha256"):
                problems.append(f"content does not match the manifest: {name}")
    rights = manifest.get("rights_registry")
    if isinstance(rights, dict) and rights.get("sha256"):
        installed = root / RIGHTS_MEMBER
        if installed.is_file() and sha256_file(installed) != rights["sha256"]:
            problems.append("installed rights.json does not match the rights register this release declares")
    return problems


def verify(manifest: object, *, environment: str, root: Path | None = None, full: bool = True,
           expected_bundle_sha256: str | None = None, expected_rights_sha256: str | None = None,
           rights_override: Path | None = None) -> None:
    """Raise ReleaseVerificationError listing every problem; return quietly when the release verifies."""
    strict = is_strict(environment)
    problems = check_structure(manifest, strict=strict)
    if isinstance(manifest, dict):
        if expected_bundle_sha256 and manifest.get("bundle_sha256") != expected_bundle_sha256:
            problems.append("manifest bundle_sha256 is not the bundle this deployment expects")
        if expected_rights_sha256:
            declared = (manifest.get("rights_registry") or {}).get("sha256") \
                or ((manifest.get("contents") or {}).get(RIGHTS_MEMBER) or {}).get("sha256")
            if declared != expected_rights_sha256:
                problems.append("the release's rights register is not the configured rights snapshot")
        if rights_override is not None and strict:
            # The API reads SIAMSIL_RIGHTS_FILE ahead of the installed register, so it must be the verified one.
            declared = (manifest.get("rights_registry") or {}).get("sha256")
            override = Path(rights_override)
            if not override.is_file() or sha256_file(override) != declared:
                problems.append("SIAMSIL_RIGHTS_FILE is not the rights register this release declares; unset it")
        if root is not None and not problems:
            problems += check_installed(manifest, root, full=full)
    if problems:
        raise ReleaseVerificationError(problems)


def check_derivation(manifest: dict, removals_path: Path, language_db: Path) -> list[str]:
    """Reproduce the duplicate-removal claim: the record file matches its hash, its counts match the manifest, and
    every removed pair is represented exactly once among the kept rows of the language database."""
    corpus = ((manifest.get("derivation") or {}).get("parallel_corpus")) or {}
    declared = corpus.get("removals_file") or {}
    problems: list[str] = []
    removals_path = Path(removals_path)
    if not removals_path.is_file():
        return [f"removal record not found: {removals_path}"]
    if sha256_file(removals_path) != declared.get("sha256"):
        problems.append("the removal record does not match the SHA-256 the manifest declares")
    counts = {reason: 0 for reason in REMOVAL_REASONS}
    duplicate_hashes: list[str] = []
    last_row = 0
    for number, line in enumerate(removals_path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            record = json.loads(line)
        except ValueError:
            problems.append(f"removal record line {number} is not JSON")
            continue
        reason = record.get("reason")
        row = record.get("source_row")
        if reason not in counts or not isinstance(row, int) or row <= last_row:
            problems.append(f"removal record line {number} has an unknown reason or is out of order")
            continue
        last_row = row
        counts[reason] += 1
        if reason == "duplicate_pair":
            duplicate_hashes.append(str(record.get("pair_hash", "")))
    if counts != corpus.get("removed"):
        problems.append("the removal record's counts do not match derivation.parallel_corpus.removed")
    if sum(counts.values()) != declared.get("records"):
        problems.append("the removal record has a different number of rows than the manifest declares")
    if not Path(language_db).is_file():
        return problems + [f"language database not found: {language_db}"]
    con = sqlite3.connect(f"file:{language_db}?mode=ro", uri=True)
    try:
        kept = con.execute("SELECT COUNT(*) FROM parallel_sentences").fetchone()[0]
        if kept != corpus.get("kept"):
            problems.append(f"the database holds {kept} corpus pairs but the manifest says {corpus.get('kept')}")
        missing = 0
        for start in range(0, len(duplicate_hashes), 500):
            chunk = duplicate_hashes[start:start + 500]
            found = {row[0] for row in con.execute(
                f"SELECT DISTINCT pair_hash FROM parallel_sentences WHERE pair_hash IN ({','.join('?' * len(chunk))})",
                chunk)}
            missing += sum(1 for value in chunk if value not in found)
        if missing:
            problems.append(f"{missing} removed duplicates have no matching kept pair in the database")
    finally:
        con.close()
    return problems
