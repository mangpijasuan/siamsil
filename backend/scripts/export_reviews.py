"""Write the stored corpus review decisions back to a decisions file for language builds.

From the repository root, with SIAMSIL_DATABASE_URL set:

    python backend/scripts/export_reviews.py --out ../siamsil-data/reviews/corpus-reviews.jsonl

The file is written in the same format and order as review_sample.py writes it, so
build_language_db.py --reviews applies exactly the stored decisions. An existing file is
replaced only when every record in it is already stored at the same place; a file holding
decisions the database lacks is left alone (import it first), so no decision is lost.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "ml_pipeline" / "scripts"))

import corpus_reviews  # type: ignore  # noqa: E402
from database import get_session_factory  # noqa: E402
from reviews.repository import ReviewRecordRepository  # noqa: E402


def write_export(stored: list[dict], out: Path) -> None:
    """Write `stored` to `out` in decisions-file format, or raise ValueError and leave `out` as it was."""
    if out.exists():
        existing = corpus_reviews.load(out)
        if existing != stored[: len(existing)]:
            raise ValueError(
                f"{out.name} holds decisions that are not stored in the database. "
                "Import it first (backend/scripts/import_reviews.py), then export again."
            )

    # Write beside the target and swap in, so a failed export never leaves half a file.
    out.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".corpus-reviews-", suffix=".jsonl", dir=out.parent)
    os.close(handle)
    temporary_path = Path(temporary)
    try:
        corpus_reviews.append(temporary_path, stored)
        if corpus_reviews.load(temporary_path) != stored:
            raise ValueError("the exported file did not read back identically")
        os.replace(temporary_path, out)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export stored corpus review decisions (SOP-07) to a JSON-lines file.")
    parser.add_argument("--out", type=Path, required=True, help="decisions file to write")
    parser.add_argument("--min-reviewers", type=int, default=1, help="for the status summary, as in build_language_db.py")
    args = parser.parse_args()

    session_factory = get_session_factory()
    if session_factory is None:
        sys.exit("SIAMSIL_DATABASE_URL is not set")
    with session_factory() as session:
        stored = ReviewRecordRepository(session).records()

    try:
        write_export(stored, args.out)
    except ValueError as error:
        sys.exit(f"Nothing written: {error}")

    statuses = Counter(decision.status for decision in corpus_reviews.decide(stored, args.min_reviewers).values())
    summary = ", ".join(f"{statuses.get(status, 0)} {status}" for status in corpus_reviews.STATUSES)
    print(f"Wrote {len(stored)} records to {args.out}. Pairs: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
