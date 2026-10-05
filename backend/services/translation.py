from __future__ import annotations

from dataclasses import dataclass

from settings import get_settings


@dataclass(frozen=True)
class TranslationSystem:
    name: str
    version: str
    generates_text: bool


# Systems the API may route /translate to. A model joins this registry only after
# passing the evaluation gate in docs/MODEL_EVALUATION.md and human review.
SYSTEMS: dict[str, TranslationSystem] = {
    "retrieval": TranslationSystem(name="retrieval", version="1", generates_text=False),
}


def active_system() -> TranslationSystem:
    return SYSTEMS[get_settings().translation_system]
