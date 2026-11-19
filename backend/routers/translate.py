from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from api_schemas import (
    ExperimentalTranslationResponse,
    ExperimentalTranslationStatus,
    TranslationResponse,
    TranslationSearchResponse,
)
from rate_limit import rate_limited
from services.bible_lookup import BibleLookup
from services.bible_versions import get_bible_versions
from services.data_loader import get_store
from services.language_catalog import canonical_code, direction_for
from services import experimental_mt
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


class ExperimentalTranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
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
    source_language: str | None = Query(None, max_length=8, description="With target_language, instead of direction: "
                                        "en or ctd (zom is read as ctd). See GET /api/v1/languages."),
    target_language: str | None = Query(None, max_length=8, description="With source_language."),
):
    direction = canonical_direction(direction)
    pair: tuple[str, str] | None = None
    if (source_language is None) != (target_language is None):
        raise HTTPException(status_code=422, detail="Give both source_language and target_language, or neither.")
    if source_language is not None and target_language is not None:
        pair = (canonical_code(source_language) or "", canonical_code(target_language) or "")
        pair_direction = direction_for(*pair)
        if pair_direction is None:
            raise HTTPException(status_code=409, detail=f"Translation from {pair[0]} to {pair[1]} is not available. "
                                                        "See GET /api/v1/languages for the pairs Siamsil can search.")
        if direction is not None and direction != pair_direction:
            raise HTTPException(status_code=422, detail="direction and the language pair disagree; give one of them.")
        direction = pair_direction
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
        # The workbook's Bible column is an edited text of unknown authorship (data/rights.json,
        # bible_iso_improved); Bible matches come from the cleared versions below instead.
        if source in ("dictionary", "bible"):
            continue
        label = {
            "daily_use": "Teacher-verified phrase",
            "translation_pair": "Workbook translation pair",
        }.get(source, source)
        results.append({**item, "label": label, "verified": bool(item.get("verified"))})

    side = "ctd" if direction == "ctd-en" else "eng"
    verses = [
        {
            "source": "bible",
            "english": verse["english"],
            "zomi": verse["zomi"],
            "reference": verse["reference"],
            "label": f"Bible: {verse['source']}",
            "verified": False,
        }
        for verse in BibleLookup(get_bible_versions()).search_side(q, side, limit=3)
        if verse["english"] and verse["zomi"]
    ]
    # Sentences and verses together, closest first: exact matches, then the shortest text searched.
    searched = "zomi" if direction == "ctd-en" else "english"
    results.extend(sorted([*corpus, *verses], key=lambda item: (not item.get("exact"), len(item[searched] or ""))))

    return {
        "query": q,
        "count": len(results[:limit]),
        "results": results[:limit],
        "note": "Parallel corpus matches are machine-translated; only those marked verified were approved by Zomi reviewers.",
        "source_language": pair[0] if pair else ({"en-ctd": "en", "ctd-en": "ctd"}.get(direction or "")),
        "target_language": pair[1] if pair else ({"en-ctd": "ctd", "ctd-en": "en"}.get(direction or "")),
    }


@router.post("", response_model=TranslationResponse)
def translate(request: TranslateRequest):
    payload = search_matches(request.text, limit=8, direction=request.direction, source_language=None,
                             target_language=None)
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


@router.get("/experimental", response_model=ExperimentalTranslationStatus)
def experimental_status():
    """Whether the opt-in experimental model is available, so the page can offer it."""
    current = experimental_mt.status()
    return {"available": current.available, "note": current.reason,
            "system": current.name, "system_version": current.version}


@router.post("/experimental", response_model=ExperimentalTranslationResponse)
def translate_experimental(request: ExperimentalTranslateRequest):
    """Opt-in machine translation, always labelled experimental (docs/ROADMAP.md, Phase 2)."""
    translator = experimental_mt.get_translator()
    if translator is None:
        raise HTTPException(status_code=503, detail=experimental_mt.status().reason)
    return {
        "input": request.text,
        "direction": request.direction,
        "translation": translator.translate(request.text, request.direction),
        "label": experimental_mt.LABEL,
        "note": experimental_mt.NOTE,
        "system": translator.name,
        "system_version": translator.version,
    }
