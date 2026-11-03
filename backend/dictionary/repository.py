"""Store dictionary source records as entries, senses, equivalents, examples and issues.

Records arrive from ml_pipeline/scripts/dictionary_sources.py. A source is imported once,
completely, inside the caller's transaction: importing the same file again adds nothing,
and a different file under the same source id is refused (updating a source is a later
step). Senses whose headword and part of speech match an existing entry join it; nothing
else is merged, corrected, or approved.
"""

from __future__ import annotations

import datetime as dt
import decimal
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Integer, func, insert, select, text
from sqlalchemy.orm import Session

from models import (
    AuditEvent,
    DictionaryEntry,
    DictionaryEquivalent,
    DictionaryExample,
    DictionaryIssue,
    DictionarySense,
    DictionarySource,
)

# Any constant works; it only has to be the same for every importer.
IMPORT_LOCK_KEY = 0xD1C7_0001
BATCH = 5000


class DictionaryImportConflict(ValueError):
    pass


@dataclass(frozen=True)
class ImportResult:
    source_id: str
    already_imported: bool
    senses: int = 0
    entries_created: int = 0
    entries_joined: int = 0
    equivalents: int = 0
    examples: int = 0
    issues: int = 0


def match_key(headword: str) -> str:
    """Entries are matched on this: case-folded, Unicode-normalised, single-spaced."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", headword).casefold()).strip()


def entry_type(headword: str, part_of_speech: str | None) -> str:
    if part_of_speech == "prop. n.":
        return "name"
    if part_of_speech in ("phr.", "phrasal v."):
        return "phrase"
    return "term" if " " in headword.strip() else "word"


def jsonable(value: Any) -> Any:
    """Workbook cells can hold dates and decimals; JSON keeps them as text."""
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (dt.date, dt.datetime, dt.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return str(value)
    return value


class DictionaryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _next_ids(self, column, prefix: str, count: int) -> list[str]:
        """The next `count` ids after the highest stored one; safe because imports hold the lock."""
        highest = self.session.scalar(
            select(func.max(func.substr(column, len(prefix) + 1).cast(Integer))).where(column.like(f"{prefix}%"))
        ) or 0
        return [f"{prefix}{n:06d}" for n in range(highest + 1, highest + 1 + count)]

    def _insert(self, table, rows: list[dict[str, Any]]) -> None:
        for start in range(0, len(rows), BATCH):
            self.session.execute(insert(table), rows[start : start + BATCH])

    def import_source(
        self,
        source_id: str,
        *,
        title: str,
        version: str | None,
        file_name: str,
        sha256: str,
        rights_key: str,
        rights: dict[str, Any],
        read: Any,
        request_id: str | None = None,
    ) -> ImportResult:
        """Add one source's records. The caller commits or rolls back."""
        self.session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": IMPORT_LOCK_KEY})
        existing = self.session.get(DictionarySource, source_id)
        if existing is not None:
            if existing.sha256 == sha256:
                return ImportResult(source_id, already_imported=True)
            raise DictionaryImportConflict(
                f"{source_id} was imported from a different file (sha256 {existing.sha256[:12]}); "
                "updating an imported source is not supported yet"
            )
        if not rights:
            raise DictionaryImportConflict(f"{source_id} has no entry in data/rights.json")

        self.session.add(DictionarySource(
            id=source_id, title=title, version=version, file_name=file_name, sha256=sha256,
            rights_key=rights_key, rights=rights, records=len(read.records),
        ))
        self.session.flush()

        entries: dict[tuple[str, str], str] = {}
        for entry_id, key, pos_key, status, merged_into in self.session.execute(
            select(DictionaryEntry.id, DictionaryEntry.match_key, DictionaryEntry.pos_key,
                   DictionaryEntry.status, DictionaryEntry.merged_into)
        ):
            entries[(key, pos_key)] = merged_into or entry_id

        new_keys: dict[tuple[str, str], Any] = {}
        for record in read.records:
            key = (match_key(record.headword), record.part_of_speech or "")
            if key not in entries and key not in new_keys:
                new_keys[key] = record
        new_ids = self._next_ids(DictionaryEntry.id, "ZE-", len(new_keys))
        entry_rows = []
        for (key, record), entry_id in zip(new_keys.items(), new_ids):
            entries[key] = entry_id
            entry_rows.append({
                "id": entry_id, "headword": record.headword, "match_key": key[0],
                "part_of_speech": record.part_of_speech, "pos_key": key[1],
                "entry_type": entry_type(record.headword, record.part_of_speech),
            })
        self._insert(DictionaryEntry.__table__, entry_rows)

        minted = iter(self._next_ids(DictionarySense.id, "ZS-", sum(1 for r in read.records if not r.sense_id)))
        sense_rows, equivalent_rows, example_rows, issue_rows = [], [], [], []
        for record in read.records:
            sense_id = record.sense_id or next(minted)
            sense_rows.append({
                "id": sense_id,
                "entry_id": entries[(match_key(record.headword), record.part_of_speech or "")],
                "source_id": source_id,
                "source_record_id": record.record_id,
                "sense_number": record.sense_number,
                "definition_en": record.definition_en,
                "explanation_ctd": record.explanation_ctd,
                "usage_tier": record.usage_tier,
                "domain": record.domain,
                "raw": jsonable(record.raw),
            })
            positions: dict[str, int] = {}
            for language, kind, value in record.equivalents:
                positions[language] = positions.get(language, 0) + 1
                equivalent_rows.append({"sense_id": sense_id, "language": language, "kind": kind,
                                        "position": positions[language], "text": value})
            kinds: dict[str, int] = {}
            for kind, english, ctd in record.examples:
                kinds[kind] = kinds.get(kind, 0) + 1
                example_rows.append({"sense_id": sense_id, "kind": kind, "position": kinds[kind],
                                     "english": english, "ctd": ctd})
            issue_rows += [self._issue(source_id, sense_id, issue) for issue in record.issues]
        issue_rows += [self._issue(source_id, None, issue) for issue in read.unlinked_issues]

        self._insert(DictionarySense.__table__, sense_rows)
        self._insert(DictionaryEquivalent.__table__, equivalent_rows)
        self._insert(DictionaryExample.__table__, example_rows)
        self._insert(DictionaryIssue.__table__, issue_rows)

        result = ImportResult(
            source_id,
            already_imported=False,
            senses=len(sense_rows),
            entries_created=len(entry_rows),
            entries_joined=len({row["entry_id"] for row in sense_rows} - set(new_ids)),
            equivalents=len(equivalent_rows),
            examples=len(example_rows),
            issues=len(issue_rows),
        )
        self.session.add(AuditEvent(
            action="dictionary.source_imported",
            target_type="dictionary_source",
            target_id=source_id,
            request_id=request_id,
            event_data={"sha256": sha256, "file_name": file_name, "skipped": dict(read.skipped),
                        **{k: v for k, v in result.__dict__.items() if isinstance(v, int) and not isinstance(v, bool)}},
        ))
        self.session.flush()
        return result

    @staticmethod
    def _issue(source_id: str, sense_id: str | None, issue: Any) -> dict[str, Any]:
        return {
            "source_id": source_id, "source_issue_id": issue.source_issue_id, "sense_id": sense_id,
            "category": issue.category, "code": issue.code, "description": issue.description,
            "priority": issue.priority, "required_reviewer": issue.required_reviewer, "raw": jsonable(issue.raw),
        }

    def summary(self) -> dict[str, Any]:
        """Counts for the import report: senses per source, and entries by how many sources they have."""
        per_source = dict(self.session.execute(
            select(DictionarySense.source_id, func.count()).group_by(DictionarySense.source_id)
        ).all())
        sources_per_entry = (
            select(func.count(func.distinct(DictionarySense.source_id)).label("n"))
            .group_by(DictionarySense.entry_id)
            .subquery()
        )
        by_sources = dict(self.session.execute(
            select(sources_per_entry.c.n, func.count()).group_by(sources_per_entry.c.n)
        ).all())
        by_type = dict(self.session.execute(
            select(DictionaryEntry.entry_type, func.count()).group_by(DictionaryEntry.entry_type)
        ).all())
        open_issues = self.session.scalar(select(func.count()).where(DictionaryIssue.status == "open"))
        return {
            "entries": sum(by_type.values()),
            "entries_by_type": by_type,
            "entries_by_number_of_sources": dict(sorted(by_sources.items())),
            "senses_by_source": per_source,
            "open_issues": open_issues,
        }
