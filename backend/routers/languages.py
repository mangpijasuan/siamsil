from __future__ import annotations

from fastapi import APIRouter

from api_schemas import LanguageCatalogResponse
from services.language_catalog import language_catalog
from services.language_engine import get_engine

router = APIRouter(prefix="/languages", tags=["languages"])


@router.get("", response_model=LanguageCatalogResponse)
def get_languages():
    return language_catalog(language_database_available=get_engine().available)
