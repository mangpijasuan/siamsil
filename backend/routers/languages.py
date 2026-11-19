from __future__ import annotations

from fastapi import APIRouter

from api_schemas import LanguageCatalogResponse
from services.language_catalog import LANGUAGES, TRANSLATION_PAIRS
from services.language_engine import get_engine

router = APIRouter(tags=["languages"])


@router.get("/languages", response_model=LanguageCatalogResponse)
def language_catalog():
    """The languages Siamsil shows and the translation pairs it can search. Zomi is `ctd`."""
    available = get_engine().available
    return {
        "languages": LANGUAGES,
        "translation_pairs": [
            {"source_language": source, "target_language": target, "direction": direction, "available": available}
            for (source, target), direction in TRANSLATION_PAIRS.items()
        ],
    }
