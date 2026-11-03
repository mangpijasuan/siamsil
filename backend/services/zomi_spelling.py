"""Suggestion-only spelling checks against human-adopted Siamsil Zomi Standard Form rules.

The authoritative source is data/zolai_standard/standard.json, maintained by the
existing reviewer workflow. Only versioned rules with two distinct reviewer
codes may be used. No ML/LLM inference, guesswork, or automatic user-text edits.
The API never writes back to the source text, dictionary or training data.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

APOSTROPHES = "'’‘ʼ"
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
RULE_ID = re.compile(r"^ZS-\d{3}$")
REVIEWER = re.compile(r"^[A-Z]\d{2}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BASE_PATH = Path(__file__).resolve().parents[2] / "data" / "zolai_standard" / "standard.json"
MAX_LENGTH = 4000


def canonical(value: str) -> str:
    return " ".join(value.translate(str.maketrans({char: "'" for char in APOSTROPHES})).lower().split())


def case_like(original: str, replacement: str) -> str:
    letters = [char for char in original if char.isalpha()]
    if letters and all(char.isupper() for char in letters):
        return replacement.upper()
    if letters and letters[0].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def form_pattern(value: str) -> str:
    parts = []
    for char in canonical(value):
        if char == "'":
            parts.append("[" + re.escape(APOSTROPHES) + "]")
        elif char == " ":
            parts.append(r"[ \t]+")
        else:
            parts.append(re.escape(char))
    return "".join(parts)


def read_standard(path: Path) -> tuple[str, list[dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    version = data.get("version")
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ValueError("Invalid standard version")
    rules = data.get("rules")
    if not isinstance(rules, list):
        raise ValueError("Invalid standard rules")
    seen_variants: set[str] = set()
    seen_ids: set[str] = set()
    standard_forms: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("Invalid rule")
        approved = rule.get("approved_by")
        variants = rule.get("variants")
        if not isinstance(rule.get("id"), str) or not RULE_ID.fullmatch(rule["id"]) or rule["id"] in seen_ids:
            raise ValueError("Invalid or duplicate rule ID")
        seen_ids.add(rule["id"])
        if not isinstance(rule.get("standard"), str) or not rule["standard"].strip():
            raise ValueError("Missing standard spelling")
        if not isinstance(variants, list) or not variants or not all(isinstance(v, str) and v.strip() for v in variants):
            raise ValueError("Invalid variants")
        if rule.get("mode") not in ("replace", "flag"):
            raise ValueError("Invalid spelling mode")
        if not isinstance(approved, list) or len(set(approved)) < 2 or not all(isinstance(v, str) and REVIEWER.fullmatch(v) for v in approved):
            raise ValueError("Two distinct human reviewer codes are required")
        if not isinstance(rule.get("approved_on"), str) or not DATE.fullmatch(rule["approved_on"]):
            raise ValueError("Missing approval date")
        if not isinstance(rule.get("reason"), str) or not rule["reason"].strip():
            raise ValueError("Missing approval reason")
        key = canonical(rule["standard"])
        standard_forms.add(key)
        for value in variants:
            variant = canonical(value)
            if variant == key or variant in seen_variants:
                raise ValueError("Conflicting spelling variants")
            seen_variants.add(variant)
    if standard_forms & seen_variants:
        raise ValueError("A standard spelling cannot also be a variant")
    return version, rules


@lru_cache(maxsize=16)
def _load_cached(path: str, mtime_ns: int, size: int) -> tuple[str, list[dict]]:
    return read_standard(Path(path))


def standard_path() -> Path:
    return Path(os.environ.get("SIAMSIL_ZOMI_STANDARD_PATH") or BASE_PATH)


def suggest_spelling(text: str, path: Path | None = None) -> dict:
    if len(text) > MAX_LENGTH:
        raise ValueError("Text is too long")
    path = path or standard_path()
    if not path.is_file():
        return {"original": text, "suggested": text, "standard_version": None,
                "status": "not_configured", "suggestions": []}
    stat = path.stat()
    version, rules = _load_cached(str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    if not rules:
        return {"original": text, "suggested": text, "standard_version": version,
                "status": "no_approved_rules", "suggestions": []}
    indexed = []
    for rule in rules:
        for value in rule["variants"]:
            indexed.append((value, rule))
    indexed.sort(key=lambda row: len(row[0]), reverse=True)
    pattern = re.compile(
        r"(?<![^\W\d_])(?<!['’‘ʼ-])(?:" +
        "|".join(f"(?P<v{i}>" + form_pattern(value) + ")" for i, (value, _) in enumerate(indexed)) +
        r")(?![^\W\d_])(?!['’‘ʼ-])", re.IGNORECASE
    )
    suggestions = []
    pieces = []
    cursor = 0
    for match in pattern.finditer(text):
        value, rule = indexed[int(match.lastgroup[1:])]
        original = match.group()
        proposed = case_like(original, rule["standard"])
        suggestions.append({"start": match.start(), "end": match.end(),
                            "original": original, "suggested": proposed,
                            "rule_id": rule["id"], "mode": rule["mode"],
                            "reason": rule["reason"]})
        pieces.extend((text[cursor:match.start()],
                       proposed if rule["mode"] == "replace" else original))
        cursor = match.end()
    pieces.append(text[cursor:])
    return {"original": text, "suggested": "".join(pieces),
            "standard_version": version, "status": "suggestions_available",
            "suggestions": suggestions}
