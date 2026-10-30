from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from api_schemas import TranslationResponse, TranslationSearchResponse
from rate_limit import rate_limited
from services.data_loader import get_store
from services.language_engine import DIRECTION_PATTERN, canonical_direction, entry_zomi, get_engine
from services.translation import active_system

router = APIRouter(prefix="/translate", tags=["translate"], dependencies=[Depends(rate_limited("translate"))])


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    direction: str = Field(default="en-ctd", pattern=DIRECTION_PATTERN)

    @field_validator("direction")
    @classmethod
    def _canonical(cls, value: str) -> str:
        return canonical_direction(value)


def _overlay_matches(query: str, limit: int, direction: str | None) -> list[dict]:
    store = get_store()
    return store.search_translate(query, limit, direction)


@router.get("/search", response_model=TranslationSearchResponse)
def search_matches(
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(20, ge=1, le=50),
    direction: str | None = Query(
        None,
        pattern=DIRECTION_PATTERN,
        description="Search only the side translated from: English for en-ctd, Zomi for ctd-en. Omit to search both."
        " The older names en-zom and zom-en are still accepted.",
    ),
):
    direction = canonical_direction(direction)
    engine = get_engine()
    if not engine.available:
        raise HTTPException(status_code=503, detail="Language database is not built yet.")

    dictionary = engine.search_dictionary(q, direction=direction or "en-ctd", limit=min(8, limit))
    corpus = engine.search_parallel(q, limit=limit, direction=direction)
    overlay = _overlay_matches(q, limit=8, direction=direction)

    results: list[dict] = []

    for entry in dictionary:
        results.append(
            {
                "source": "dictionary",
                "english": entry["english"],
                "zomi": entry_zomi(entry),
                "verified": entry["verified"],
                "verification_status": entry["verification_status"],
                "flagged": entry["flagged"],
                "label": "Verified dictionary" if entry["verified"] else "Dictionary (unreviewed)",
                "id": entry["id"],
                "part_of_speech": entry["part_of_speech"],
            }
        )

    for item in overlay:
        source = item.get("source")
        if source == "dictionary":
            continue
        label = {
            "daily_use": "Teacher-verified phrase",
            "translation_pair": "Workbook translation pair",
            "bible": "Bible (ISO text)",
        }.get(source, source)
        results.append({**item, "label": label, "verified": bool(item.get("verified")) or source == "bible"})

    for pair in corpus:
        results.append(pair)

    return {
        "query": q,
        "count": len(results[:limit]),
        "results": results[:limit],
        "note": "Parallel corpus matches are machine-translated; only those marked verified were approved by Zomi reviewers.",
    }


@router.post("", response_model=TranslationResponse)
def translate(request: TranslateRequest):
    payload = search_matches(request.text, limit=8, direction=request.direction)
    exact = next((item for item in payload["results"] if item.get("exact") or item.get("source") == "dictionary"), None)
    system = active_system()
    return {
        "input": request.text,
        "direction": request.direction,
        "mode": "retrieval",
        "note": "No neural translation model is enabled. Showing retrieved Siamsil data only.",
        "system": system.name,
        "system_version": system.version,
        "language_release": get_engine().release(),
        "primary": exact or (payload["results"][0] if payload["results"] else None),
        "matches": payload["results"],
    }
