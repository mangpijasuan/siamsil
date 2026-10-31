"""Term decisions for dictionary reviews (data/dictionary_terms.json, docs/DICTIONARY.md).

A term records the Zomi words a Zomi speaker gave for an English word. For each sense whose
headword uses the term, `suggestion` rewrites the sense's Zomi into a draft and `note` lists the
words to choose from. Drafts go into review sheets only: a reviewer confirms or changes every row
and a lead editor approves it before anything in the dictionary changes.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TERMS_PATH = ROOT / "data" / "dictionary_terms.json"


@dataclass(frozen=True)
class Term:
    key: str
    english: tuple[str, ...]
    zomi: tuple[tuple[str, str], ...]
    note: str
    headword: str | None
    suggest: tuple[tuple[str, str], ...]
    confirmed: bool

    def matches(self, headword: str) -> bool:
        """Whether an English headword uses this term as a whole word ("refugee camp", not "refugeeism")."""
        words = re.findall(r"[a-z]+", headword.lower())
        return any(word in self.english for word in words)

    def suggestion(self, headword: str, zomi: str) -> str:
        """A draft of the Zomi with the term's replacements applied; "" when nothing would change."""
        if self.headword and headword.strip().lower() in self.english:
            return self.headword if zomi.strip() != self.headword else ""
        draft = zomi
        # Longest form first, whole words only, case kept for a capitalised first letter.
        for old, new in sorted(self.suggest, key=lambda pair: -len(pair[0])):
            pattern = re.compile(rf"(?<![\w'’-]){re.escape(old)}", re.IGNORECASE)
            draft = pattern.sub(lambda m: new[:1].upper() + new[1:] if m.group(0)[:1].isupper() else new, draft)
        return draft if draft != zomi else ""

    def choices(self) -> str:
        words = "; ".join(f"{word} ({meaning})" for word, meaning in self.zomi)
        status = "confirmed" if self.confirmed else "not yet confirmed by a second person"
        return f"{self.english[0]}: {words}. {self.note} [{status}]"


def load_terms(path: Path = TERMS_PATH) -> dict[str, Term]:
    data = json.loads(path.read_text(encoding="utf-8"))
    terms: dict[str, Term] = {}
    for key, spec in data.get("terms", {}).items():
        english = tuple(word.lower() for word in spec.get("english", []))
        zomi = tuple((item["word"], item.get("meaning", "")) for item in spec.get("zomi", []))
        if not english or not zomi:
            raise ValueError(f"term {key!r} needs English words and Zomi words")
        if not spec.get("decided_by") or not spec.get("decided_on"):
            raise ValueError(f"term {key!r} must say who decided it and when")
        suggest = tuple((pair["from"], pair["to"]) for pair in spec.get("suggest", []))
        terms[key] = Term(key, english, zomi, spec.get("note", ""), spec.get("headword"), suggest,
                          bool(spec.get("confirmed_by")))
    return terms
