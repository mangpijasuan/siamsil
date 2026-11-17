"""Import the offline review decisions file into the application database.

From the repository root, with SIAMSIL_DATABASE_URL set and migrations applied:

    python backend/scripts/import_reviews.py ../siamsil-data/reviews/corpus-reviews.jsonl \
        --roster ../siamsil-data/reviews/roster.csv [--dry-run]

Safe to run again after more reviews are appended: only the new records are added. Every
record's reviewer or approver must be in the private roster with the matching role, so a
file edited by someone outside the roster cannot add reviews or approvals.
"""

from __future__ import annotations

import argparse
import sys
from hashlib import sha256
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))

import corpus_reviews  # type: ignore  # noqa: E402
from database import get_session_factory  # noqa: E402
from reviews.repository import ReviewImportConflict, ReviewRecordRepository  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Import corpus review decisions (SOP-07) into PostgreSQL.")
    parser.add_argument("reviews", type=Path, help="the decisions file, e.g. ../siamsil-data/reviews/corpus-reviews.jsonl")
    parser.add_argument("--roster", type=Path, required=True, help="private CSV: code, role[, name]")
    parser.add_argument("--dry-run", action="store_true", help="check and report without saving")
    args = parser.parse_args()

    for path in (args.reviews, args.roster):
        if not path.is_file():
            sys.exit(f"File not found: {path}")
    checksum = sha256(args.reviews.read_bytes()).hexdigest()
    try:
        records = corpus_reviews.load(args.reviews)
        roster = corpus_reviews.load_roster(args.roster)
    except ValueError as error:
        sys.exit(f"Nothing imported: {error}")
    # The checksum is the import's provenance, so it must describe the records that were read.
    if sha256(args.reviews.read_bytes()).hexdigest() != checksum:
        sys.exit(f"Nothing imported: {args.reviews.name} changed while it was being read; run the import again")
    problems = corpus_reviews.roster_problems(records, roster)
    if problems:
        sys.exit("Nothing imported:\n  " + "\n  ".join(problems))

    session_factory = get_session_factory()
    if session_factory is None:
        sys.exit("SIAMSIL_DATABASE_URL is not set")

    with session_factory() as session:
        try:
            result = ReviewRecordRepository(session).import_records(
                records,
                source_name=args.reviews.name,
                source_sha256=checksum,
            )
        except ReviewImportConflict as error:
            session.rollback()
            sys.exit(f"Nothing imported: {error}")
        if args.dry_run:
            session.rollback()
        else:
            session.commit()

    verb = "would add" if args.dry_run else "added"
    print(
        f"{result.records_in_file} records in {args.reviews.name}; "
        f"{result.already_stored} already stored; {verb} {result.added}"
        + ("" if args.dry_run else f" (import {result.import_id})")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
