from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import date

from fastapi import APIRouter, HTTPException, Path, Query

from api_schemas import (
    ApiErrorResponse,
    BibleBooksResponse,
    BibleChapterResponse,
    BibleSearchResponse,
    BibleVerse,
    BibleVersionBooksResponse,
    BibleVersionChapterResponse,
    BibleVersionSearchResponse,
    BibleVersionsResponse,
)
from services.bible_lookup import BibleLookup, as_bible_verse
from services.bible_versions import BibleVersions, get_bible_versions
from services.data_loader import get_store

router = APIRouter(prefix="/bible", tags=["bible"])
logger = logging.getLogger("siamsil.bible")


@router.get("/books", response_model=BibleBooksResponse)
def list_books():
    store = get_store()
    books = store.bible_books()
    return {"count": len(books), "books": books}


@router.get("/search", response_model=BibleSearchResponse)
def search_bible(q: str = Query(..., min_length=1, max_length=200), limit: int = Query(20, ge=1, le=100)):
    store = get_store()
    results = store.search_bible(q, limit)
    return {"query": q, "count": len(results), "results": results}


@router.get("/random", response_model=BibleVerse)
def random_verse():
    """The day's verse from the cleared Zomi Bible, or the workbook Bible where no versions database is loaded."""
    seed = date.today().toordinal()
    found = BibleLookup(get_bible_versions()).daily(seed)
    verse = as_bible_verse(found) if found else get_store().random_verse(seed=seed)
    if not verse:
        raise HTTPException(status_code=404, detail="No verses available")
    return verse


@router.get("/chapter", response_model=BibleChapterResponse)
def get_chapter(book_id: int = Query(..., ge=1), chapter: int = Query(..., ge=1)):
    store = get_store()
    verses = store.bible_chapter(book_id, chapter)
    if not verses:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return {
        "book_id": book_id,
        "chapter": chapter,
        "book_english": verses[0]["book_english"],
        "book_zomi": verses[0]["book_zomi"],
        "verse_count": len(verses),
        "verses": verses,
    }


VERSION_ERRORS = {
    404: {"model": ApiErrorResponse, "description": "Bible version or chapter not found"},
    503: {"model": ApiErrorResponse, "description": "Bible versions database not loaded or unreadable"},
}


def _versions_or_503() -> BibleVersions:
    versions = get_bible_versions()
    if not versions.available:
        raise HTTPException(status_code=503, detail="Bible versions are not loaded yet.")
    return versions


@contextmanager
def _database_errors_as_503():
    try:
        yield
    except sqlite3.Error as exc:
        logger.error("Bible versions database error: %s", exc)
        raise HTTPException(status_code=503, detail="Bible versions are unavailable.") from exc


@router.get("/versions", response_model=BibleVersionsResponse, responses={503: VERSION_ERRORS[503]})
def list_versions():
    with _database_errors_as_503():
        items = _versions_or_503().versions()
    return {"count": len(items), "versions": items}


@router.get("/versions/{version_id}/books", response_model=BibleVersionBooksResponse, responses=VERSION_ERRORS)
def list_version_books(version_id: str = Path(..., pattern="^[a-z0-9_-]{1,32}$")):
    with _database_errors_as_503():
        versions = _versions_or_503()
        version = versions.version(version_id)
        books = versions.books(version_id) if version else []
    if not version:
        raise HTTPException(status_code=404, detail="Bible version not found")
    return {"version": version, "count": len(books), "books": books}


@router.get("/versions/{version_id}/chapter", response_model=BibleVersionChapterResponse, responses=VERSION_ERRORS)
def get_version_chapter(
    version_id: str = Path(..., pattern="^[a-z0-9_-]{1,32}$"),
    book_id: int = Query(..., ge=1, le=66),
    chapter: int = Query(..., ge=1, le=150),
):
    with _database_errors_as_503():
        versions = _versions_or_503()
        version = versions.version(version_id)
        if not version:
            raise HTTPException(status_code=404, detail="Bible version not found")
        book = next((b for b in versions.books(version_id) if b["book_id"] == book_id), None)
        verses = versions.chapter(version_id, book_id, chapter) if book else []
    if not verses:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return {"version": version, "book": book, "chapter": chapter, "verse_count": len(verses), "verses": verses}


@router.get("/versions/{version_id}/search", response_model=BibleVersionSearchResponse, responses=VERSION_ERRORS)
def search_version(
    version_id: str = Path(..., pattern="^[a-z0-9_-]{1,32}$"),
    q: str = Query(..., min_length=2, max_length=100, description="Words to find (all must appear), or a phrase"),
    phrase: bool = Query(False, description="Match q as one exact phrase"),
    book_id: int | None = Query(None, ge=1, le=66),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0, le=5000),
):
    with _database_errors_as_503():
        versions = _versions_or_503()
        version = versions.version(version_id)
        if not version:
            raise HTTPException(status_code=404, detail="Bible version not found")
        total, results = versions.search(version_id, q, book_id=book_id, phrase=phrase, limit=limit, offset=offset)
    return {
        "version": version, "query": q, "phrase": phrase, "book_id": book_id,
        "total": total, "limit": limit, "offset": offset, "results": results,
    }
