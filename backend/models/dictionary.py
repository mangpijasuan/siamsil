"""The editorial Siamsil Dictionary (docs/DICTIONARY.md).

PostgreSQL is the master copy; published entries are copied into the read-only
SQLite language release. Every source record becomes one sense, imported as
written and unreviewed; entries group senses that share a headword and part of
speech. Nothing is merged or corrected automatically.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


ENTRY_TYPES = ("word", "term", "name", "phrase")
ENTRY_STATUSES = ("draft", "in_review", "approved", "published", "rejected", "deferred", "merged")
SENSE_STATUSES = ("draft", "in_review", "approved", "published", "rejected", "deferred")
REVIEW_STATUSES = ("unreviewed", "in_review", "needs_correction", "approved", "rejected")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class DictionarySource(Base):
    """One imported file, pinned by checksum, with the rights recorded when it was imported."""

    __tablename__ = "dictionary_sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[Optional[str]] = mapped_column(Text)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    rights_key: Mapped[str] = mapped_column(String(64), nullable=False)
    rights: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    records: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DictionaryEntry(Base):
    """A headword and part of speech. Senses from any source with the same key share an entry."""

    __tablename__ = "dictionary_entries"
    __table_args__ = (
        UniqueConstraint("match_key", "pos_key", name="uq_dictionary_entries_key"),
        CheckConstraint("id ~ '^ZE-[0-9]{6,}$'", name="ck_dictionary_entries_id"),
        CheckConstraint(_in("entry_type", ENTRY_TYPES), name="ck_dictionary_entries_type"),
        CheckConstraint(_in("status", ENTRY_STATUSES), name="ck_dictionary_entries_status"),
        CheckConstraint("(status = 'merged') = (merged_into IS NOT NULL)", name="ck_dictionary_entries_merged"),
    )

    # Numbered by DictionaryRepository under its import lock, not by a sequence, so a
    # rolled-back import or dry run leaves no gaps.
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    headword: Mapped[str] = mapped_column(Text, nullable=False)
    match_key: Mapped[str] = mapped_column(Text, nullable=False)
    part_of_speech: Mapped[Optional[str]] = mapped_column(String(16))
    pos_key: Mapped[str] = mapped_column(String(16), nullable=False, server_default="")
    entry_type: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    merged_into: Mapped[Optional[str]] = mapped_column(String(16), ForeignKey("dictionary_entries.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DictionarySense(Base):
    """One meaning, exactly as one source record gives it. ZD- ids come from the 50K Master; Siamsil mints ZS- ids."""

    __tablename__ = "dictionary_senses"
    __table_args__ = (
        UniqueConstraint("source_id", "source_record_id", name="uq_dictionary_senses_source_record"),
        CheckConstraint("id ~ '^(ZD|ZS)-[0-9]{6,}$'", name="ck_dictionary_senses_id"),
        CheckConstraint(_in("status", SENSE_STATUSES), name="ck_dictionary_senses_status"),
        CheckConstraint(_in("review_status", REVIEW_STATUSES), name="ck_dictionary_senses_review_status"),
    )

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    entry_id: Mapped[str] = mapped_column(String(16), ForeignKey("dictionary_entries.id"), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(64), ForeignKey("dictionary_sources.id"), nullable=False, index=True)
    source_record_id: Mapped[str] = mapped_column(Text, nullable=False)
    sense_number: Mapped[Optional[int]] = mapped_column(SmallInteger)
    definition_en: Mapped[Optional[str]] = mapped_column(Text)
    explanation_ctd: Mapped[Optional[str]] = mapped_column(Text)
    usage_tier: Mapped[Optional[str]] = mapped_column(String(2))
    domain: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    review_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="unreviewed")
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DictionaryEquivalent(Base):
    """A Zomi translation of a sense, or a Burmese one kept for reference. Alternatives are separate rows."""

    __tablename__ = "dictionary_equivalents"
    __table_args__ = (
        UniqueConstraint("sense_id", "language", "position", name="uq_dictionary_equivalents_position"),
        CheckConstraint("language IN ('ctd', 'my')", name="ck_dictionary_equivalents_language"),
        CheckConstraint("kind IN ('equivalent', 'gloss')", name="ck_dictionary_equivalents_kind"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    sense_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("dictionary_senses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)


class DictionaryExample(Base):
    __tablename__ = "dictionary_examples"
    __table_args__ = (
        UniqueConstraint("sense_id", "kind", "position", name="uq_dictionary_examples_position"),
        CheckConstraint("kind IN ('example', 'phrase')", name="ck_dictionary_examples_kind"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    sense_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("dictionary_senses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    english: Mapped[Optional[str]] = mapped_column(Text)
    ctd: Mapped[Optional[str]] = mapped_column(Text)


class DictionaryIssue(Base):
    """A quality-control finding from a source, tracked on its own until resolved or dismissed."""

    __tablename__ = "dictionary_issues"
    __table_args__ = (
        UniqueConstraint("source_id", "source_issue_id", name="uq_dictionary_issues_source_issue"),
        CheckConstraint("status IN ('open', 'resolved', 'dismissed')", name="ck_dictionary_issues_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), ForeignKey("dictionary_sources.id"), nullable=False)
    source_issue_id: Mapped[str] = mapped_column(Text, nullable=False)
    sense_id: Mapped[Optional[str]] = mapped_column(String(16), ForeignKey("dictionary_senses.id"), index=True)
    category: Mapped[Optional[str]] = mapped_column(Text)
    code: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    priority: Mapped[Optional[str]] = mapped_column(String(16))
    required_reviewer: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="open")
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
