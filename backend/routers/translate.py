from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api_schemas import TranslationResponse, TranslationSearchResponse
from services.data_loader import get_store
from services.language_engine import get_engine

router = APIRouter(prefix="/translate", tags=["translate"])


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    direction: str = Field(default="en-zom", pattern="^(en-zom|zom-en)$")


def _overlay_matches(query: str, limit: int) -> list[dict]:
    store = get_store()
    return store.search_translate(query, limit)


@router.get("/search", response_model=TranslationSearchResponse)
def search_matches(q: str = Query(..., min_length=1, max_length=500), limit: int = Query(20, ge=1, le=50)):
    engine = get_engine()
    if not engine.available:
        raise HTTPException(status_code=503, detail="Language database is not built yet.")

    dictionary = engine.search_dictionary(q, limit=min(8, limit))
    corpus = engine.search_parallel(q, limit=limit)
    overlay = _overlay_matches(q, limit=8)

    results: list[dict] = []

    for entry in dictionary:
        results.append(
            {
                "source": "dictionary",
                "english": entry["english"],
                "zomi": entry["definition"],
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
        "note": "Parallel corpus matches are machine-translated and unverified.",
    }


@router.post("", response_model=TranslationResponse)
def translate(request: TranslateRequest):
    payload = search_matches(request.text, limit=8)
    exact = next((item for item in payload["results"] if item.get("exact") or item.get("source") == "dictionary"), None)
    return {
        "input": request.text,
        "direction": request.direction,
        "mode": "retrieval",
        "note": "No neural translation model is enabled. Showing retrieved Siamsil data only.",
        "primary": exact or (payload["results"][0] if payload["results"] else None),
        "matches": payload["results"],
    }
