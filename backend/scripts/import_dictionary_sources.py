"""Import the dictionary sources listed in data/dictionary_sources.json into PostgreSQL.

From the repository root, with SIAMSIL_DATABASE_URL set and migrations applied:

    python backend/scripts/import_dictionary_sources.py [--data-repo ../siamsil-data] [--only SOURCE] [--dry-run]

Every file is checked against its pinned SHA-256 before anything is written, and all
selected sources are imported in one transaction: either all of them are stored or none.
Running it again adds nothing for sources already imported from the same file. Needs
poppler's pdftotext for PDF sources (brew install poppler).
"""

from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))

from dictionary_sources import READERS  # type: ignore  # noqa: E402
from database import get_session_factory  # noqa: E402
from dictionary.repository import DictionaryImportConflict, DictionaryRepository  # noqa: E402


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Import dictionary sources into the editorial dictionary.")
    parser.add_argument("--data-repo", type=Path, default=PROJECT_ROOT.parent / "siamsil-data",
                        help="the private siamsil-data checkout")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "data" / "dictionary_sources.json")
    parser.add_argument("--rights", type=Path, default=PROJECT_ROOT / "data" / "rights.json")
    parser.add_argument("--only", action="append", help="import only this source id; repeatable")
    parser.add_argument("--dry-run", action="store_true", help="read, check and report without saving")
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))["sources"]
    rights = json.loads(args.rights.read_text(encoding="utf-8"))["sources"]
    selected = args.only or list(config)
    unknown = [s for s in selected if s not in config]
    if unknown:
        sys.exit(f"Unknown source(s): {', '.join(unknown)}; listed: {', '.join(config)}")

    roots = {"data_repo": args.data_repo, "project": PROJECT_ROOT}
    problems, paths = [], {}
    for source_id in selected:
        spec = config[source_id]
        path = roots[spec["root"]] / spec["path"]
        if spec["format"] not in READERS:
            problems.append(f"{source_id}: unknown format {spec['format']}")
        elif spec["rights"] not in rights:
            problems.append(f"{source_id}: no entry {spec['rights']} in {args.rights.name}")
        elif not path.is_file():
            problems.append(f"{source_id}: file not found: {path}")
        elif file_sha256(path) != spec["sha256"]:
            problems.append(f"{source_id}: {path.name} does not match its pinned sha256; update the config on purpose")
        paths[source_id] = path
    if problems:
        sys.exit("Nothing imported:\n  " + "\n  ".join(problems))

    session_factory = get_session_factory()
    if session_factory is None:
        sys.exit("SIAMSIL_DATABASE_URL is not set")

    with session_factory() as session:
        repository = DictionaryRepository(session)
        try:
            for source_id in selected:
                spec = config[source_id]
                read = READERS[spec["format"]](paths[source_id])
                result = repository.import_source(
                    source_id,
                    title=spec["title"],
                    version=spec.get("version"),
                    file_name=paths[source_id].name,
                    sha256=spec["sha256"],
                    rights_key=spec["rights"],
                    rights=rights[spec["rights"]],
                    read=read,
                )
                if result.already_imported:
                    print(f"{source_id}: already imported from this file")
                else:
                    print(f"{source_id}: {result.senses:,} senses, {result.entries_created:,} new entries, "
                          f"{result.entries_joined:,} existing entries joined, {result.equivalents:,} equivalents, "
                          f"{result.examples:,} examples, {result.issues:,} issues"
                          + (f"; skipped {read.skipped}" if read.skipped else ""))
        except DictionaryImportConflict as error:
            session.rollback()
            sys.exit(f"Nothing imported: {error}")
        summary = repository.summary()
        if args.dry_run:
            session.rollback()
        else:
            session.commit()

    print(("Would leave" if args.dry_run else "Dictionary now has") + f" {summary['entries']:,} entries "
          f"{summary['entries_by_type']}; entries by number of sources {summary['entries_by_number_of_sources']}; "
          f"{summary['open_issues']:,} open issues")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
