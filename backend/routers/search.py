from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api_schemas import UnifiedSearchResponse
from rate_limit import rate_limited
from services.bible_lookup import BibleLookup, as_bible_verse
from services.bible_versions import get_bible_versions
from services.data_loader import get_store
from services.language_engine import get_engine

router = APIRouter(prefix="/search", tags=["search"], dependencies=[Depends(rate_limited("search"))])


@router.get("", response_model=UnifiedSearchResponse)
def unified_search(q: str = Query(..., min_length=1, max_length=200), limit: int = Query(8, ge=1, le=20)):
    engine = get_engine()
    store = get_store()
    dictionary = engine.search_dictionary(q, limit=limit) if engine.available else []
    corpus = engine.search_parallel(q, limit=limit) if engine.available else []
    # The cleared Bible versions; the workbook Bible only where no versions database is loaded.
    versions = get_bible_versions()
    if versions.available:
        bible = [as_bible_verse(verse) for verse in BibleLookup(versions).search_words(q, limit=limit)]
    else:
        bible = store.search_bible(q, limit=limit)
    return {
        "query": q,
        "dictionary": dictionary,
        "translations": corpus,
        "bible": bible,
    }
