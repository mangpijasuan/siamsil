"""Import the offline corpus review decisions (SOP-07) into PostgreSQL.

The decisions file is append-only, so the database holds the same records in the same
order: record N of the file is stored at position N. An import adds only the records
past what is already stored, after checking that the stored ones still match the file.
Re-importing a file, or an older copy of it, adds nothing but is still logged; a file whose
history differs from what is stored is refused. The database refuses to edit, delete, or
truncate stored records.

Each record is kept as a JSON value (`record`), so it reads back equal to what was imported,
and a file written by review_sample.py exports back byte for byte. Formatting that JSON does
not keep (spacing, key order, how a number is spelled) is not preserved.

Records arrive already validated by ml_pipeline/scripts/corpus_reviews.py (load), which
is also what decides each pair's status; this module stores them and gives them back.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from models import AuditEvent, CorpusReviewRecord, ReviewImport

# Any constant works; it only has to be the same for every importer.
IMPORT_LOCK_KEY = 0x5E1A_5157


class ReviewImportConflict(ValueError):
    """The file disagrees with the records already stored."""


@dataclass(frozen=True)
class ImportResult:
    records_in_file: int
    already_stored: int
    added: int
    import_id: UUID


def canonical(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def record_ids(records: Iterable[dict[str, Any]]) -> list[str]:
    """A stable identity per record: its content, plus how many identical records came before it.

    Two identical lines in the file are two records, and keep two identities.
    """
    seen: dict[str, int] = {}
    ids = []
    for record in records:
        text_form = canonical(record)
        occurrence = seen.get(text_form, 0)
        seen[text_form] = occurrence + 1
        ids.append(sha256(f"{text_form}\0{occurrence}".encode("utf-8")).hexdigest())
    return ids


def _row(position: int, record_id: str, import_id: UUID, record: dict[str, Any]) -> CorpusReviewRecord:
    # Records saved before approvals existed have no kind and are reviews (corpus_reviews.kind_of).
    kind = record.get("kind", "review")
    is_review = kind == "review"
    return CorpusReviewRecord(
        position=position,
        record_id=record_id,
        import_id=import_id,
        kind=kind,
        pair_hash=record["pair_hash"],
        actor_code=record["reviewer"] if is_review else record["approver"],
        decided_on=record["reviewed_on"] if is_review else record["approved_on"],
        batch=record.get("batch"),
        meaning=record["meaning"] if is_review else None,
        fluency=record["fluency"] if is_review else None,
        decision=None if is_review else record["decision"],
        record=record,
    )


class ReviewRecordRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def import_records(
        self,
        records: list[dict[str, Any]],
        *,
        source_name: str,
        source_sha256: str,
        request_id: str | None = None,
    ) -> ImportResult:
        """Add the records not yet stored. The caller commits or rolls back."""
        # One import at a time, so two at once cannot both add the same records.
        self.session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": IMPORT_LOCK_KEY})

        stored = list(self.session.scalars(select(CorpusReviewRecord.record_id).order_by(CorpusReviewRecord.position)))
        ids = record_ids(records)
        for position, (stored_id, file_id) in enumerate(zip(stored, ids)):
            if stored_id != file_id:
                raise ReviewImportConflict(
                    f"{source_name} record {position + 1} differs from the stored record at the same place; "
                    "the decisions file must only ever be appended to"
                )

        # Every import is logged, including one that adds nothing, so each check of a file is on record.
        new = list(range(len(stored), len(records)))
        batch = ReviewImport(
            source_name=source_name,
            source_sha256=source_sha256,
            records_in_file=len(records),
            records_added=len(new),
        )
        self.session.add(batch)
        self.session.flush()
        self.session.add_all(_row(position, ids[position], batch.id, records[position]) for position in new)
        self.session.add(
            AuditEvent(
                action="reviews.records_imported",
                target_type="review_import",
                target_id=str(batch.id),
                request_id=request_id,
                event_data={
                    "source_name": source_name,
                    "source_sha256": source_sha256,
                    "records_added": len(new),
                    "records_in_file": len(records),
                    "already_stored": len(stored),
                },
            )
        )
        self.session.flush()
        return ImportResult(len(records), len(stored), len(new), batch.id)

    def records(self) -> list[dict[str, Any]]:
        """Every stored record, exactly as recorded, in file order."""
        return list(self.session.scalars(select(CorpusReviewRecord.record).order_by(CorpusReviewRecord.position)))
