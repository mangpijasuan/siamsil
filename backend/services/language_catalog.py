from __future__ import annotations

from fastapi import HTTPException

# Coverage describes content that Siamsil actually serves, not languages that a
# model might theoretically understand. Add a pair only after its licensed data
# has been imported, checked, and connected to the retrieval engine.
LANGUAGES = (
    {"code": "en", "name": "English", "native_name": "English", "role": "translation"},
    {"code": "zom", "name": "Zomi", "native_name": "Zomi", "role": "translation"},
    {"code": "my", "name": "Burmese", "native_name": "မြန်မာ", "role": "learning_content"},
)

TRANSLATION_PAIRS = (("en", "zom"), ("zom", "en"))


def translation_direction(source: str, target: str) -> str:
    if (source, target) not in TRANSLATION_PAIRS:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Translation from {source} to {target} is not available. "
                "Only English and Zomi retrieval is currently supported."
            ),
        )
    return f"{source}-{target}"


def resolve_translation_pair(
    *, direction: str = "en-zom", source_language: str | None = None,
    target_language: str | None = None,
) -> tuple[str, str, str]:
    if (source_language is None) != (target_language is None):
        raise HTTPException(status_code=422, detail="Provide both source_language and target_language.")
    if source_language is None:
        source_language, target_language = direction.split("-", 1)
    assert target_language is not None
    return source_language, target_language, translation_direction(source_language, target_language)


def language_catalog(*, language_database_available: bool) -> dict:
    status = "available" if language_database_available else "data_unavailable"
    return {
        "languages": list(LANGUAGES),
        "translation_pairs": [
            {
                "source_language": source,
                "target_language": target,
                "status": status,
                "mode": "retrieval",
                "review_status": "mixed",
            }
            for source, target in TRANSLATION_PAIRS
        ],
        "note": (
            "Burmese currently appears in citizenship learning content, not in the translation engine. "
            "No neural translation model is enabled."
        ),
    }
