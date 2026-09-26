from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from api_schemas import (
    DictionaryEntry,
    DictionaryLettersResponse,
    DictionarySearchResponse,
    DictionarySuggestionsResponse,
)
from services.language_engine import get_engine

router = APIRouter(prefix="/dictionary", tags=["dictionary"])


@router.get("", response_model=DictionarySearchResponse)
def search_dictionary(
    q: str = Query("", max_length=200),
    letter: str | None = Query(None, min_length=1, max_length=1),
    direction: str = Query("en-zom", pattern="^(en-zom|zom-en)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    engine = get_engine()
    if not engine.available:
        raise HTTPException(status_code=503, detail="Language database is not built yet.")
    if not q.strip() and not letter:
        return {"query": q, "count": 0, "results": []}
    results = engine.search_dictionary(
        q, letter=letter, direction=direction, limit=limit, offset=offset
    )
    return {"query": q, "letter": letter, "direction": direction, "count": len(results), "results": results}


@router.get("/suggest", response_model=DictionarySuggestionsResponse)
def suggest(q: str = Query(..., min_length=1, max_length=80), limit: int = Query(8, ge=1, le=20)):
    engine = get_engine()
    if not engine.available:
        raise HTTPException(status_code=503, detail="Language database is not built yet.")
    return {"query": q, "results": engine.suggest_dictionary(q, limit)}


@router.get("/letters", response_model=DictionaryLettersResponse)
def letters():
    engine = get_engine()
    if not engine.available:
        raise HTTPException(status_code=503, detail="Language database is not built yet.")
    return {"letters": engine.letter_counts()}


@router.get("/word-of-day", response_model=DictionaryEntry)
def word_of_day():
    engine = get_engine()
    if not engine.available:
        raise HTTPException(status_code=503, detail="Language database is not built yet.")
    entry = engine.word_of_day(seed=date.today().toordinal())
    if not entry:
        raise HTTPException(status_code=404, detail="No dictionary entries")
    return entry


@router.get("/{entry_id}", response_model=DictionaryEntry)
def get_entry(entry_id: int):
    engine = get_engine()
    if not engine.available:
        raise HTTPException(status_code=503, detail="Language database is not built yet.")
    entry = engine.get_entry(entry_id, include_examples=True)
    if not entry:
        raise HTTPException(status_code=404, detail="Dictionary entry not found")
    return entry
