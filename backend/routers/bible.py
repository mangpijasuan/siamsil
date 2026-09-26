from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from services.data_loader import get_store

router = APIRouter(prefix="/bible", tags=["bible"])


@router.get("/books")
def list_books():
    store = get_store()
    books = store.bible_books()
    return {"count": len(books), "books": books}


@router.get("/search")
def search_bible(q: str = Query(..., min_length=1, max_length=200), limit: int = Query(20, ge=1, le=100)):
    store = get_store()
    results = store.search_bible(q, limit)
    return {"query": q, "count": len(results), "results": results}


@router.get("/random")
def random_verse():
    store = get_store()
    verse = store.random_verse(seed=date.today().toordinal())
    if not verse:
        raise HTTPException(status_code=404, detail="No verses available")
    return verse


@router.get("/chapter")
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
