from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api_schemas import WordSuggestionsResponse
from services.word_suggest import MAX_PREFIX, MIN_PREFIX, ZOMI, get_zomi_words

from services.zomi_spelling import MAX_LENGTH, suggest_spelling


class SpellingRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_LENGTH)


router = APIRouter(prefix="/words", tags=["words"])


@router.get("/suggest", response_model=WordSuggestionsResponse)
def suggest_words(
    prefix: str = Query(..., min_length=MIN_PREFIX, max_length=MAX_PREFIX, description="The start of a Zomi word"),
    limit: int = Query(8, ge=1, le=20),
):
    """Zomi words starting with `prefix`, most frequent first. English completion is /dictionary/suggest."""
    words = get_zomi_words()
    if not words.available:
        raise HTTPException(status_code=503, detail="Bible versions database is not built yet.")
    results, sources = words.complete(prefix, limit)
    return {"prefix": prefix, "language": ZOMI, "sources": list(sources), "words": results}


@router.post("/spelling/suggest")
def suggest_standard_spelling(request: SpellingRequest):
    """Return approved Standard Zomi spelling proposals without modifying user text."""
    try:
        return suggest_spelling(request.text)
    except (ValueError, OSError) as error:
        # Invalid/contradictory rules are a configuration failure, not a guess.
        raise HTTPException(status_code=503, detail="Approved Zomi spelling rules are unavailable.") from error
