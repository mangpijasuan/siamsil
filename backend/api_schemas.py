from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class TranslateMatch(ApiModel):
    source: str
    english: str
    zomi: str
    reference: str | None = None
    category: str | None = None
    domain: str | None = None
    verified: bool = False
    verification_status: str | None = None
    flagged: bool | None = None
    label: str | None = None
    exact: bool | None = None
    quality_score: float | None = None
    quality_flags: list[str] = Field(default_factory=list)
    model: str | None = None
    id: int | None = None
    part_of_speech: str | None = None


class DictionaryEntry(ApiModel):
    id: int
    english: str
    source_word: str | None = None
    normalized_word: str | None = None
    language: str | None = None
    dialect: str | None = None
    part_of_speech: str | None = None
    part_of_speech_full: str | None = None
    zomi: str | None = None
    definition: str | None = None
    pronunciation: str | None = None
    usage_notes: str | None = None
    domain: str | None = None
    source: str | None = None
    source_reference: str | None = None
    confidence: float | None = None
    verification_status: str | None = None
    verified: bool = False
    flagged: bool = False
    suggested_correction: str | None = None
    letter: str | None = None
    version: str | None = None
    examples: list[TranslateMatch] = Field(default_factory=list)


class DictionarySearchResponse(ApiModel):
    query: str
    letter: str | None = None
    direction: str = "en-zom"
    count: int
    results: list[DictionaryEntry]


class DictionarySuggestion(ApiModel):
    id: int
    source_word: str
    part_of_speech: str | None = None
    definition: str | None = None
    verification_status: str | None = None


class DictionarySuggestionsResponse(ApiModel):
    query: str
    results: list[DictionarySuggestion]


class DictionaryLetter(ApiModel):
    letter: str
    count: int


class DictionaryLettersResponse(ApiModel):
    letters: list[DictionaryLetter]


class BibleVerse(ApiModel):
    testament: str
    book_id: int
    book_english: str
    book_zomi: str
    chapter: int
    verse: int
    reference: str
    english: str | None = None
    zomi_original: str
    zomi_iso: str
    changes_applied: str | None = None


class BibleBook(ApiModel):
    book_id: int
    book_english: str
    book_zomi: str
    testament: str


class BibleBooksResponse(ApiModel):
    count: int
    books: list[BibleBook]


class BibleSearchResponse(ApiModel):
    query: str
    count: int
    results: list[BibleVerse]


class BibleChapterResponse(ApiModel):
    book_id: int
    chapter: int
    book_english: str
    book_zomi: str
    verse_count: int
    verses: list[BibleVerse]


class TranslationSearchResponse(ApiModel):
    query: str
    count: int
    results: list[TranslateMatch]
    note: str | None = None


class TranslationResponse(ApiModel):
    input: str
    direction: str
    mode: str
    note: str
    system: str
    system_version: str
    language_release: str | None = None
    primary: TranslateMatch | None = None
    matches: list[TranslateMatch]


class LearningEntry(ApiModel):
    id: int
    category: str
    sub_category: str
    english: str
    zomi: str
    notes: str | None = None
    verified: bool
    source: str


class LearningGroupsResponse(ApiModel):
    count: int
    groups: dict[str, list[LearningEntry]]
    note: str


class UnifiedSearchResponse(ApiModel):
    query: str
    dictionary: list[DictionaryEntry]
    translations: list[TranslateMatch]
    bible: list[BibleVerse]


class AskSource(ApiModel):
    type: str
    id: int | None = None
    english: str | None = None
    zomi: str | None = None
    verified: bool | None = None
    verification_status: str | None = None
    source: str | None = None
    label: str | None = None
    reference: str | None = None


class AskResponse(ApiModel):
    mode: str
    intent: str
    confidence: str
    answer: str
    sources: list[AskSource]
    note: str


class HealthResponse(ApiModel):
    status: str
    version: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    language: dict[str, Any] | None = None
    checks: dict[str, Any] | None = None


class LivenessResponse(ApiModel):
    status: str
    version: str
