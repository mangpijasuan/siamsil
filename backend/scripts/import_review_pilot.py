"""Validate a local review packet; --commit imports it as unpublished editorial jobs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from database import get_database_engine  # noqa: E402
from models.translation_review import TranslationAttempt, TranslationJob  # noqa: E402


def read_packet(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError(f"Review packet not found: {path}")
    rows: list[dict] = []
    seen: set[int] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                sentence_id = row["sentence_id"]
                if type(sentence_id) is not int or sentence_id < 1 or sentence_id in seen:
                    raise ValueError("sentence_id must be unique and positive")
                if row.get("dataset_split") != "train" or row.get("license_status") != "needs_review":
                    raise ValueError("only unlicensed training-split pilot rows are accepted")
                if not all(isinstance(row.get(key), str) and row[key].strip() for key in
                           ("english_source", "zomi_candidate", "dataset_version")):
                    raise ValueError("source, candidate, and dataset version are required")
                if not isinstance(row.get("quality_flags"), list) or not all(
                    isinstance(flag, str) for flag in row["quality_flags"]
                ):
                    raise ValueError("quality_flags must be a list of strings")
                seen.add(sentence_id)
                rows.append(row)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"Invalid packet line {line_number}: {exc}") from exc
    if not rows or len(rows) > 100:
        raise ValueError("Pilot packet must contain 1–100 rows")
    return rows


def import_packet(path: Path, *, commit: bool = False) -> tuple[int, int]:
    rows = read_packet(path)
    if not commit:
        return len(rows), 0
    engine = get_database_engine()
    if engine is None:
        raise RuntimeError("SIAMSIL_DATABASE_URL is required to import review jobs")
    inserted = 0
    with Session(engine) as session, session.begin():
        existing = set(session.execute(select(TranslationJob.dataset_version, TranslationJob.sentence_id).where(
            TranslationJob.sentence_id.in_([row["sentence_id"] for row in rows])
        )).all())
        for row in rows:
            if (row["dataset_version"], row["sentence_id"]) in existing:
                continue
            job = TranslationJob(
                sentence_id=row["sentence_id"], english_source=row["english_source"],
                source_reference=row.get("source_reference"), dataset_version=row["dataset_version"],
                quality_flags=row["quality_flags"], license_status="needs_review", status="pending",
            )
            session.add(job)
            session.flush()
            session.add(TranslationAttempt(job_id=job.id, attempt_number=1,
                                           zomi_text=row["zomi_candidate"], model=row.get("model")))
            inserted += 1
    return len(rows), inserted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--commit", action="store_true", help="Write validated jobs to PostgreSQL")
    args = parser.parse_args()
    total, inserted = import_packet(args.packet, commit=args.commit)
    print(f"Validated {total} local pilot rows; imported {inserted} unpublished jobs.")


if __name__ == "__main__":
    main()
