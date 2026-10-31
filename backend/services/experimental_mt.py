"""Opt-in experimental machine translation (docs/ROADMAP.md, Phase 2 decision of 2026-10-28).

Serves a model exported by ml_pipeline/scripts/export_mt_serving.py: CTranslate2 int8
weights, the tokenizer, and serving.json. Outside development, a model is served only
when serving.json says every training source is cleared for training. Output is always
labelled experimental; it is never presented as a verified translation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from settings import get_settings

# Models trained before Zomi was labelled ctd use zom_Latn (ISO 639-3 Zou) as their token.
LANGUAGE_TOKENS = {"en": ("eng_Latn",), "ctd": ("ctd_Latn", "zom_Latn")}
DIRECTIONS = {"en-ctd": ("en", "ctd"), "ctd-en": ("ctd", "en")}
MAX_SOURCE_TOKENS = 126
LABEL = "Machine translation (experimental)"
NOTE = (
    "Made by an experimental model that may contain errors. It is not a verified translation; "
    "check important text with a Zomi speaker."
)


class ModelNotServable(RuntimeError):
    pass


@dataclass(frozen=True)
class Status:
    available: bool
    reason: str
    name: str | None = None
    version: str | None = None


class ExperimentalTranslator:
    def __init__(self, translator: Any, tokenizer: Any, serving: dict[str, Any]) -> None:
        self.translator = translator
        self.tokenizer = tokenizer
        self.name = serving["name"]
        self.version = serving["version"]
        vocab = tokenizer.get_vocab()
        self.tokens = {}
        for key, candidates in LANGUAGE_TOKENS.items():
            found = next((t for t in candidates if t in vocab), None)
            if found is None:
                raise ModelNotServable(f"the tokenizer has no language token for {key}")
            self.tokens[key] = found

    def translate(self, text: str, direction: str) -> str:
        src, tgt = DIRECTIONS[direction]
        pieces = self.tokenizer.encode(text, add_special_tokens=False).tokens[:MAX_SOURCE_TOKENS]
        result = self.translator.translate_batch(
            [[self.tokens[src], *pieces, "</s>"]],
            target_prefix=[[self.tokens[tgt]]],
            beam_size=4,
            max_decoding_length=MAX_SOURCE_TOKENS + 4,
        )[0]
        output = result.hypotheses[0][1:]  # drop the target-language token
        ids = [self.tokenizer.token_to_id(token) for token in output]
        return self.tokenizer.decode([i for i in ids if i is not None], skip_special_tokens=True).strip()


def read_serving(model_dir: Path) -> dict[str, Any]:
    path = model_dir / "serving.json"
    if not path.is_file():
        raise ModelNotServable(f"{path} not found; export the model with export_mt_serving.py")
    serving = json.loads(path.read_text(encoding="utf-8"))
    settings = get_settings()
    if not serving.get("cleared_for_serving"):
        allowed = settings.experimental_mt_allow_uncleared and settings.environment == "development"
        if not allowed:
            uncleared = ", ".join(serving.get("uncleared_sources") or ["unknown"])
            raise ModelNotServable(f"trained on sources not cleared for training ({uncleared})")
    return serving


def load(model_dir: Path) -> ExperimentalTranslator:
    serving = read_serving(model_dir)
    import ctranslate2
    from tokenizers import Tokenizer

    translator = ctranslate2.Translator(str(model_dir), device="cpu", compute_type="int8")
    return ExperimentalTranslator(translator, Tokenizer.from_file(str(model_dir / "tokenizer.json")), serving)


@lru_cache(maxsize=1)
def _loaded() -> tuple[ExperimentalTranslator | None, Status]:
    model_dir = get_settings().experimental_mt_dir
    if model_dir is None:
        return None, Status(False, "Experimental machine translation is not enabled.")
    try:
        translator = load(model_dir)
    except ModelNotServable as error:
        return None, Status(False, f"The experimental model cannot be served: {error}.")
    return translator, Status(True, "Experimental machine translation is available.", translator.name, translator.version)


def get_translator() -> ExperimentalTranslator | None:
    return _loaded()[0]


def status() -> Status:
    return _loaded()[1]
