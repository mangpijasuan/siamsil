from __future__ import annotations

from fastapi import APIRouter, Query

from services.data_loader import get_store
from services.language_engine import get_engine

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def unified_search(q: str = Query(..., min_length=1, max_length=200), limit: int = Query(8, ge=1, le=20)):
    engine = get_engine()
    store = get_store()
    dictionary = engine.search_dictionary(q, limit=limit) if engine.available else []
    corpus = engine.search_parallel(q, limit=limit) if engine.available else []
    bible = store.search_bible(q, limit=limit)
    return {
        "query": q,
        "dictionary": dictionary,
        "translations": corpus,
        "bible": bible,
    }
