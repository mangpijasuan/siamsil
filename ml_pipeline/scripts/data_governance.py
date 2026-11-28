#!/usr/bin/env python3
"""Data-governance checks: what a releasable Siamsil data release must prove, enforced by code (docs/DATA_GOVERNANCE.md).

The release contract (backend/scripts/release_contract.py, docs/DATA_RELEASES.md) says what a bundle must declare.
These checks look at the data and the registers around it:

  registry   public-safe, runs in the app repo's CI: the rights register is consistent; every source the committed
             configuration names has a rights entry; no source that must never be served, exported, trained on or
             evaluated on is referenced; committed release manifests are well formed.
  data-repo  the private siamsil-data archive: every file in MANIFEST.sha256 exists and matches; every pinned original
             in data/source_files.json matches; files the manifest does not declare; restricted material present.
  exports    each export manifest (export_datasets.py): no uncleared or forbidden source admitted, counts match the
             files, and no exact, normalised or template duplicate across train, validation and test.
  release    a release.json against the release contract and the denylist, optionally against the evaluation sets
             and rights register it declares.
  leakage    evaluation items against training text (an export's files or a language database): exact, normalised,
             template (numbers and names masked) and near-duplicate matches.

Rules of the output: only counts, ids, file paths and hashes. Never the text of a sentence, headword or evaluation item,
so a log of these checks cannot leak private data. A failing check exits 1; a warning does not (use --strict).
These checks verify mechanical facts. They do not decide rights, approve language or clear any source.

  python3 ml_pipeline/scripts/data_governance.py registry
  python3 ml_pipeline/scripts/data_governance.py data-repo --data-repo ../siamsil-data
  python3 ml_pipeline/scripts/data_governance.py exports --export-dir data/datasets
  python3 ml_pipeline/scripts/data_governance.py release dist/release.json --environment production
  python3 ml_pipeline/scripts/data_governance.py leakage --eval data/evaluation/human/en-zomi-v1.jsonl --db data/processed/language/siamsil_language.sqlite
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import release_contract as contract  # noqa: E402
from services import rights_policy  # noqa: E402
from build_language_db import normalize_word, template_key  # noqa: E402

DATA = ROOT / "data"
BLOCKING = {"not_permitted", "blocked"}
USES = ("train", "display", "commercial_inference")  # commercial_inference reads the register's `commercial` column
NEAR_SHINGLE = 3


class Report:
    """Failures stop a release, warnings need a person's attention, facts are aggregate numbers worth recording."""

    def __init__(self, name: str) -> None:
        self.name, self.failures, self.warnings, self.facts = name, [], [], {}

    def fail(self, message: str) -> None:
        self.failures.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def fact(self, key: str, value: object) -> None:
        self.facts[key] = value

    def as_dict(self) -> dict:
        return {"check": self.name, "passed": not self.failures, "failures": self.failures,
                "warnings": self.warnings, "facts": self.facts}

    def show(self) -> None:
        print(f"== {self.name}: {'PASS' if not self.failures else 'FAIL'} "
              f"({len(self.failures)} failures, {len(self.warnings)} warnings)")
        for key, value in self.facts.items():
            print(f"   {key}: {value}")
        for message in self.failures:
            print(f"   FAIL  {message}")
        for message in self.warnings:
            print(f"   warn  {message}")


# ---- policy ------------------------------------------------------------------------------------------------------


def load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def forbidden(data_dir: Path, rights: dict[str, dict]) -> tuple[dict[str, str], dict[str, str]]:
    """Sources and path fragments that must never reach serving, export, training or evaluation.

    Derived from the rights register (a source blocked or not permitted for every use) plus the explicit list in
    data/governance.json. Deriving means a rights decision cannot be undone by forgetting a second list.
    """
    sources: dict[str, str] = {}
    for name, source in rights.items():
        if all(rights_policy.source_status(source, use)[0] in BLOCKING for use in USES):
            sources[name] = "rights register: blocked or not permitted for training, display and commercial use"
    fragments: dict[str, str] = {}
    governance = Path(data_dir) / "governance.json"
    if governance.is_file():
        config = load_json(governance)
        sources.update({k: v for k, v in (config.get("forbidden_sources") or {}).items()})
        fragments.update({k.lower(): v for k, v in (config.get("forbidden_path_fragments") or {}).items()})
    return sources, fragments


def owner_review_state(data_dir: Path) -> tuple[str, str | None]:
    """("pending" | "approved" | "invalid", detail) for data/governance.json's owner_review field.

    "approved" needs an object naming who approved and when. This only reads the field: it cannot tell whether the
    claim is true, and nothing in this code or any AI step ever writes it.
    """
    governance = Path(data_dir) / "governance.json"
    if not governance.is_file():
        return "invalid", "data/governance.json is missing"
    value = load_json(governance).get("owner_review")
    if value == "pending":
        return "pending", None
    if isinstance(value, dict) and str(value.get("approved_by") or "").strip() \
            and contract.ISO_UTC_RE.match(str(value.get("approved_at") or "")):
        return "approved", f"{value['approved_by']} on {value['approved_at']}"
    return "invalid", 'owner_review must be "pending" or {"approved_by": "<name>", "approved_at": "YYYY-MM-DDTHH:MM:SS"}'


def hit(text: str, fragments: dict[str, str]) -> list[str]:
    lowered = text.lower()
    return [fragment for fragment in fragments if fragment in lowered]


def walk_strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_strings(item)


# ---- registry ----------------------------------------------------------------------------------------------------


def check_registry(data_dir: Path = DATA) -> Report:
    report = Report("registry")
    rights = load_json(data_dir / "rights.json")["sources"]
    problems = rights_policy.validate_rights(rights)
    for problem in problems:
        report.fail(f"rights register: {problem}")
    report.fact("rights_sources", len(rights))
    by_use = {use: dict(Counter(rights_policy.source_status(s, use)[0] for s in rights.values())) for use in USES}
    report.fact("rights_status_by_use", by_use)
    never, fragments = forbidden(data_dir, rights)
    report.fact("forbidden_sources", sorted(never))
    state, detail = owner_review_state(data_dir)
    report.fact("governance_json_owner_review", state if detail is None or state == "invalid" else f"{state} ({detail})")
    if state == "invalid":
        report.fail(f"data/governance.json: {detail}")

    # Every source the committed configuration names has a rights entry.
    referenced: dict[str, list[str]] = {}
    for key in (load_json(data_dir / "bible_versions.json").get("versions") or {}):
        referenced.setdefault(f"bible_{key}", []).append("bible_versions.json")
    for key, source in (load_json(data_dir / "dictionary_sources.json").get("sources") or {}).items():
        referenced.setdefault(source.get("rights") or key, []).append("dictionary_sources.json")
    for key in (load_json(data_dir / "reference_dictionaries.json").get("sources") or {}):
        referenced.setdefault(key, []).append("reference_dictionaries.json")
    for name, where in sorted(referenced.items()):
        if name not in rights:
            report.fail(f"{', '.join(sorted(set(where)))} names source {name!r}, which has no entry in rights.json")
    report.fact("sources_referenced_by_configuration", len(referenced))
    orphans = sorted(set(rights) - set(referenced))
    report.fact("rights_sources_not_referenced_by_configuration", len(orphans))

    # Nothing forbidden is referenced by configuration or recorded in a committed release manifest.
    for name in sorted(set(referenced) & set(never)):
        report.fail(f"{name} must never be served or used ({never[name]}) but {', '.join(sorted(set(referenced[name])))} "
                    "references it")
    versions = sorted((data_dir / "versions").glob("*.json")) if (data_dir / "versions").is_dir() else []
    for path in versions:
        manifest = load_json(path)
        digest = (manifest.get("database") or {}).get("sha256", "")
        if not (manifest.get("name") and manifest.get("version") and contract.SHA256_RE.fullmatch(str(digest))):
            report.fail(f"{path.name}: needs name, version and database.sha256")
        for text in walk_strings(manifest.get("source_files") or {}):
            for fragment in hit(text, fragments):
                report.fail(f"{path.name}: a source path matches the restricted fragment {fragment!r}")
    report.fact("committed_release_manifests", len(versions))
    configured = load_json(data_dir / "source_files.json").get("sources") or {}
    for key, spec in configured.items():
        if not contract.SHA256_RE.fullmatch(str(spec.get("sha256", ""))):
            report.fail(f"source_files.json: {key} has no full SHA-256 pin")
        for fragment in hit(str(spec.get("path", "")), fragments):
            report.fail(f"source_files.json: {key} pins a path matching the restricted fragment {fragment!r}")
    report.fact("pinned_originals", len(configured))
    return report


# ---- data-repo ---------------------------------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    return contract.sha256_file(path)


def check_data_repo(repo: Path, data_dir: Path = DATA, require_quarantined: bool = False) -> Report:
    report = Report("data-repo")
    repo = Path(repo)
    rights = load_json(data_dir / "rights.json")["sources"]
    _, fragments = forbidden(data_dir, rights)
    manifest = repo / "MANIFEST.sha256"
    if not manifest.is_file():
        report.fail("MANIFEST.sha256 is missing")
        return report
    declared: dict[str, str] = {}
    for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        digest, _, name = line.partition("  ")
        if not (contract.SHA256_RE.fullmatch(digest) and name):
            report.fail(f"MANIFEST.sha256 line {number} is not '<sha256>  <path>'")
            continue
        declared[name] = digest
    missing = mismatched = 0
    for name, digest in sorted(declared.items()):
        path = repo / name
        if not path.is_file():
            missing += 1
            report.fail(f"declared file is missing: {name}")
        elif sha256_file(path) != digest:
            mismatched += 1
            report.fail(f"checksum mismatch: {name}")
    report.fact("declared_files", len(declared))
    report.fact("declared_missing", missing)
    report.fact("declared_mismatched", mismatched)

    pins = load_json(data_dir / "source_files.json").get("sources") or {}
    for key, spec in sorted(pins.items()):
        path = repo / spec["path"]
        if not path.is_file():
            report.fail(f"pinned original {key} is missing: {spec['path']}")
        elif sha256_file(path) != spec["sha256"]:
            report.fail(f"pinned original {key} does not match source_files.json")
    report.fact("pinned_originals_checked", len(pins))

    tracked = subprocess.run(["git", "-C", str(repo), "ls-files"], capture_output=True, text=True, check=False)
    if tracked.returncode == 0:
        files = [line for line in tracked.stdout.splitlines() if line]
        undeclared = [f for f in files if f not in declared and f not in ("MANIFEST.sha256",)]
        report.fact("tracked_files", len(files))
        report.fact("tracked_files_not_in_MANIFEST", len(undeclared))
        report.fact("undeclared_by_top_folder", dict(sorted(Counter(f.split("/")[0] for f in undeclared).items())))
        if undeclared:
            report.warn(f"{len(undeclared)} tracked files are not declared in MANIFEST.sha256 (no checksum recorded)")
        restricted = [f for f in files if hit(f, fragments)]
        report.fact("restricted_paths_present", len(restricted))
        for name in restricted:
            if name in declared or any(name == spec["path"] for spec in pins.values()):
                report.fail(f"restricted material is declared as a pinned source: {name}")
        inner = []
        # Only while restricted files remain: after a migration an upstream manifest that still lists them is expected.
        for name in files if restricted else []:
            if name.lower().endswith(".json") and "manifest" in name.lower() and name != "MANIFEST.sha256":
                path = repo / name
                if path.is_file() and path.stat().st_size < 50_000_000 and hit(path.read_text(encoding="utf-8", errors="ignore"), fragments):
                    inner.append(name)
        report.fact("manifests_listing_restricted_paths", inner)
        if inner:
            report.warn(f"{len(inner)} manifest files list restricted paths and need a quarantine notice: {', '.join(inner)}")
        if restricted and require_quarantined:
            report.fail(f"{len(restricted)} restricted files are still tracked in this archive (--require-quarantined)")
        elif restricted:
            report.warn(f"{len(restricted)} restricted files are present in the archive; keep them in a separately "
                        "access-controlled area and out of every manifest (docs/DATA_GOVERNANCE.md)")
        commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
        dirty = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True, check=False)
        report.fact("archive_commit", commit.stdout.strip())
        report.fact("archive_working_tree_clean", dirty.stdout.strip() == "")
    else:
        report.warn("the archive is not a git checkout; tracked-file checks skipped")
    return report


# ---- leakage -----------------------------------------------------------------------------------------------------


def tokens(text: str) -> list[str]:
    return normalize_word(text).split()


def shingles(text: str) -> frozenset:
    words = tokens(text)
    if len(words) < NEAR_SHINGLE:
        return frozenset([tuple(words)]) if words else frozenset()
    return frozenset(tuple(words[i:i + NEAR_SHINGLE]) for i in range(len(words) - NEAR_SHINGLE + 1))


class EvalIndex:
    """Evaluation items indexed for exact, template and near matching. Holds ids and hashes, reports ids only."""

    def __init__(self, items: list[tuple[str, list[str], list[str]]]) -> None:
        self.exact: dict[tuple[str, str], set[str]] = {}
        self.template: dict[tuple[str, str], set[str]] = {}
        self.shingles: dict[str, list[tuple[str, str, frozenset]]] = {}
        self.inverted: dict[tuple[str, tuple], list[int]] = {}
        self.entries: list[tuple[str, str, frozenset]] = []
        for item_id, english, zomi in items:
            for side, texts in (("en", english), ("zomi", zomi)):
                for text in texts:
                    key = normalize_word(text)
                    if not key:
                        continue
                    self.exact.setdefault((side, key), set()).add(item_id)
                    self.template.setdefault((side, template_key(text, set())), set()).add(item_id)
                    grams = shingles(text)
                    position = len(self.entries)
                    self.entries.append((item_id, side, grams))
                    for gram in grams:
                        self.inverted.setdefault((side, gram), []).append(position)

    def scan(self, side: str, text: str, threshold: float, hits: dict[str, set[str]]) -> None:
        key = normalize_word(text)
        if not key:
            return
        for item_id in self.exact.get((side, key), ()):
            hits.setdefault(item_id, set()).add("exact")
        for item_id in self.template.get((side, template_key(text, set())), ()):
            hits.setdefault(item_id, set()).add("template")
        grams = shingles(text)
        if not grams:
            return
        counts: Counter[int] = Counter()
        for gram in grams:
            for position in self.inverted.get((side, gram), ()):
                counts[position] += 1
        for position, shared in counts.items():
            item_id, entry_side, entry_grams = self.entries[position]
            if shared / len(grams | entry_grams) >= threshold:
                hits.setdefault(item_id, set()).add("near")


def eval_items(paths: list[Path]) -> list[tuple[str, list[str], list[str]]]:
    import eval_set

    items: list[tuple[str, list[str], list[str]]] = []
    for path in paths:
        loaded, errors = eval_set.load_items(Path(path))
        if errors:
            raise ValueError(f"{path}: {errors[0]}")
        for item in loaded:
            english, zomi = eval_set.item_texts(item)
            items.append((str(item.get("id") or f"{Path(path).name}:{item['_line']}"), english, zomi))
    return items


def pairs_from_db(db: Path):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        for english, zomi in con.execute("SELECT raw_source_text, raw_target_text FROM parallel_sentences"):
            yield english, zomi
    finally:
        con.close()


def pairs_from_jsonl(path: Path):
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                yield record.get("english") or "", record.get("zomi") or ""


def check_leakage(eval_paths: list[Path], db: Path | None, train: list[Path], threshold: float = 0.8) -> Report:
    report = Report("leakage")
    index = EvalIndex(eval_items(eval_paths))
    items = {entry[0] for entry in index.entries}
    report.fact("evaluation_items", len(items))
    sources = ([pairs_from_db(db)] if db else []) + [pairs_from_jsonl(p) for p in train]
    if not sources:
        report.fail("no training text given (--db or --train)")
        return report
    hits: dict[str, set[str]] = {}
    scanned = 0
    for source in sources:
        for english, zomi in source:
            scanned += 1
            index.scan("en", english, threshold, hits)
            index.scan("zomi", zomi, threshold, hits)
    report.fact("training_pairs_scanned", scanned)
    by_kind = Counter(kind for kinds in hits.values() for kind in kinds)
    report.fact("evaluation_items_with_exact_match", by_kind.get("exact", 0))
    report.fact("evaluation_items_with_near_duplicate", by_kind.get("near", 0))
    report.fact("evaluation_items_with_template_variant", by_kind.get("template", 0))
    for kind, label in (("exact", "an exact (normalised)"), ("near", "a near-duplicate")):
        ids = sorted(item for item, kinds in hits.items() if kind in kinds)
        if ids:
            report.fail(f"{len(ids)} evaluation items have {label} match in training text: {', '.join(ids[:20])}"
                        + (" ..." if len(ids) > 20 else ""))
    template_only = sorted(item for item, kinds in hits.items() if "template" in kinds and not kinds & {"exact", "near"})
    if template_only:
        report.warn(f"{len(template_only)} evaluation items share a template (numbers or names masked) with training "
                    f"text: {', '.join(template_only[:20])}")
    return report


# ---- exports -----------------------------------------------------------------------------------------------------


def check_exports(export_dir: Path, data_dir: Path = DATA) -> Report:
    report = Report("exports")
    rights = load_json(data_dir / "rights.json")["sources"]
    never, _ = forbidden(data_dir, rights)
    manifests = sorted(Path(export_dir).rglob("manifest.json"))
    report.fact("export_manifests", len(manifests))
    if not manifests:
        report.warn("no export manifest found")
    for path in manifests:
        folder = path.parent
        manifest = load_json(path)
        where = str(path.relative_to(export_dir)) if path != export_dir else path.name
        if manifest.get("uncleared_sources_included"):
            report.fail(f"{where}: admits uncleared sources {', '.join(manifest['uncleared_sources_included'])}")
        for name, info in sorted((manifest.get("sources") or {}).items()):
            if not info.get("exported"):
                continue
            if name in never:
                report.fail(f"{where}: exports {name}, which must never be used ({never[name]})")
            current = rights_policy.source_status(rights.get(name, {}), "train")[0]
            if current != "cleared":
                report.fail(f"{where}: exports {name}, whose training right is now {current}")
        seen: dict[str, str] = {}
        template_seen: dict[str, str] = {}
        for split in ("train", "validation", "test"):
            file = folder / f"{split}.jsonl"
            if not file.is_file():
                continue
            rows = 0
            for english, zomi in pairs_from_jsonl(file):
                rows += 1
                key = hashlib.sha1(f"{normalize_word(english)}\t{normalize_word(zomi)}".encode()).hexdigest()
                family = template_key(english, set())
                if key in seen and seen[key] != split:
                    report.fail(f"{where}: exact duplicate pair across {seen[key]} and {split}")
                if family in template_seen and template_seen[family] != split:
                    report.warn(f"{where}: template variants straddle {template_seen[family]} and {split}")
                seen.setdefault(key, split)
                template_seen.setdefault(family, split)
            declared = ((manifest.get("splits") or {}).get(split) or {}).get("total")
            if declared is not None and declared != rows:
                report.fail(f"{where}: {split}.jsonl has {rows} rows but the manifest says {declared}")
    return report


# ---- release -----------------------------------------------------------------------------------------------------


def check_release(release: Path, environment: str, data_dir: Path = DATA, evaluation: list[Path] | None = None,
                  rights_file: Path | None = None) -> Report:
    report = Report("release")
    manifest = load_json(release)
    rights = load_json(data_dir / "rights.json")["sources"]
    _, fragments = forbidden(data_dir, rights)
    report.fact("schema_version", manifest.get("schema_version"))
    report.fact("environment_policy", environment)
    for problem in contract.check_structure(manifest, strict=contract.is_strict(environment)):
        report.fail(problem)
    for name in (manifest.get("contents") or {}):
        for fragment in hit(name, fragments):
            report.fail(f"the bundle lists {name!r}, which matches the restricted fragment {fragment!r}")
    for text in walk_strings({k: v for k, v in manifest.items() if k != "contents"}):
        for fragment in hit(text, fragments):
            report.fail(f"the manifest mentions a restricted fragment {fragment!r}")
    if rights_file is not None:
        declared = (manifest.get("rights_registry") or {}).get("sha256")
        if sha256_file(rights_file) != declared:
            report.fail("the rights register supplied is not the one this release declares")
    for path in evaluation or []:
        entry = next((s for s in (manifest.get("protected_evaluation") or {}).get("sets", []) if s.get("name") == Path(path).name), None)
        if entry is None:
            report.fail(f"evaluation set {Path(path).name} is not declared in the release")
        elif entry.get("sha256") != sha256_file(Path(path)):
            report.fail(f"evaluation set {Path(path).name} does not match the hash the release declares")
    for entry in (manifest.get("protected_evaluation") or {}).get("sets", []):
        if not entry.get("frozen"):
            report.warn(f"evaluation set {entry.get('name')} is a draft (not frozen)")
    if (manifest.get("approval") or {}).get("status") != "approved":
        report.warn("the release is unapproved")
    return report


# ---- command line ------------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", type=Path, help="write the report here (counts, ids and hashes only)")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    parser.add_argument("--data-dir", type=Path, default=DATA, help="the app repo's data folder (rights.json, ...)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("registry")
    repo = commands.add_parser("data-repo")
    repo.add_argument("--data-repo", type=Path, required=True)
    repo.add_argument("--require-quarantined", action="store_true",
                      help="fail while any restricted file is still tracked (use after the migration)")
    exports = commands.add_parser("exports")
    exports.add_argument("--export-dir", type=Path, required=True)
    release = commands.add_parser("release")
    release.add_argument("release", type=Path)
    release.add_argument("--environment", default="production")
    release.add_argument("--evaluation", type=Path, action="append", default=[])
    release.add_argument("--rights", type=Path)
    leakage = commands.add_parser("leakage")
    leakage.add_argument("--eval", type=Path, action="append", required=True, dest="eval_files")
    leakage.add_argument("--db", type=Path)
    leakage.add_argument("--train", type=Path, action="append", default=[])
    leakage.add_argument("--near-threshold", type=float, default=0.8)
    args = parser.parse_args(argv)

    if args.command == "registry":
        report = check_registry(args.data_dir)
    elif args.command == "data-repo":
        report = check_data_repo(args.data_repo, args.data_dir, args.require_quarantined)
    elif args.command == "exports":
        report = check_exports(args.export_dir, args.data_dir)
    elif args.command == "release":
        report = check_release(args.release, args.environment, args.data_dir, args.evaluation, args.rights)
    else:
        try:
            report = check_leakage(args.eval_files, args.db, args.train, args.near_threshold)
        except ValueError as error:
            print(f"leakage: {error}")
            return 1
    report.show()
    if args.json:
        args.json.write_text(json.dumps(report.as_dict(), indent=2), encoding="utf-8")
    return 1 if report.failures or (args.strict and report.warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
