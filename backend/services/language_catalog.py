"""Which languages Siamsil shows, and which pairs it can search for translations (GET /api/v1/languages).

Zomi is `ctd` (ISO 639-3 Tedim, the base of Zolai writing; docs/DATA_RIGHTS.md, "Language code"). `zom` is the ISO
code of Zou, a different language: it is accepted from older links and read as `ctd`, never returned.
Burmese appears as reference and learning text (dictionary reference column, the Judson Bible); Siamsil does not
translate to or from it.
"""
from __future__ import annotations

LEGACY_CODES = {"zom": "ctd"}

LANGUAGES = [
    {"code": "en", "name": "English", "role": "translation"},
    {"code": "ctd", "name": "Zomi (Zolai), Tedim-based", "role": "translation"},
    {"code": "my", "name": "Burmese", "role": "learning_content",
     "note": "Shown as reference text in the dictionary and in the Bible reader; not translated."},
]

# (source, target) -> the direction name the search engine uses.
TRANSLATION_PAIRS = {("en", "ctd"): "en-ctd", ("ctd", "en"): "ctd-en"}


def canonical_code(code: str | None) -> str | None:
    if code is None:
        return None
    value = code.strip().lower()
    return LEGACY_CODES.get(value, value)


def direction_for(source: str, target: str) -> str | None:
    """The engine direction for a pair, or None when Siamsil cannot search it."""
    return TRANSLATION_PAIRS.get((canonical_code(source) or "", canonical_code(target) or ""))
