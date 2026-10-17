from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from api_schemas import (
    BibleBooksResponse, BibleChapterResponse, BibleSearchResponse, BibleVerse,
    BibleVersionBooksResponse, BibleVersionChapterResponse, BibleVersionSearchResponse, BibleVersionsResponse,
)
from services.data_loader import get_store
from services.scripture_catalog import ScriptureCatalog
from settings import get_settings

router = APIRouter(prefix="/bible", tags=["bible"])


def get_scripture_catalog() -> ScriptureCatalog:
    return ScriptureCatalog(get_settings().scripture_releases_dir, get_store())


@router.get("/versions", response_model=BibleVersionsResponse)
def list_versions():
    versions = get_scripture_catalog().versions()
    return {"count": len(versions), "versions": versions}


@router.get("/versions/{version_id}/books", response_model=BibleVersionBooksResponse)
def list_version_books(version_id: str):
    catalog = get_scripture_catalog()
    version = catalog.version(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Bible version not found")
    books = catalog.books(version_id)
    return {"version": version, "count": len(books), "books": books}


@router.get("/versions/{version_id}/chapter", response_model=BibleVersionChapterResponse)
def get_version_chapter(version_id: str, book_id: int = Query(..., ge=1), chapter: int = Query(..., ge=1)):
    catalog = get_scripture_catalog()
    version = catalog.version(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Bible version not found")
    verses = catalog.chapter(version_id, book_id, chapter)
    if not verses:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return {
        "version": version, "book_id": book_id, "chapter": chapter,
        "book_english": verses[0]["book_english"], "book_zomi": verses[0]["book_zomi"],
        "verse_count": len(verses), "verses": verses,
    }


@router.get("/versions/{version_id}/search", response_model=BibleVersionSearchResponse)
def search_version(version_id: str, q: str = Query(..., min_length=1, max_length=200), limit: int = Query(20, ge=1, le=100)):
    catalog = get_scripture_catalog()
    version = catalog.version(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Bible version not found")
    results = catalog.search(version_id, q, limit)
    return {"version": version, "query": q, "count": len(results), "results": results}


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
    store = get_store()
    verse = store.random_verse(seed=date.today().toordinal())
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
