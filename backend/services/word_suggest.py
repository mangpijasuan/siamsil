"""Zomi word completion: the words people write, most frequent first.

Built from the Zomi text Siamsil may show (the Zomi Bible versions served by the app, whose
display right is cleared). Other sources join when their display right is cleared
(docs/DATA_RIGHTS.md). Never from the machine-translated corpus: completions must be words
Zomi writers use. Only single words are suggested; nothing composes text.
"""

from __future__ import annotations

import bisect
import re
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional

from services.bible_versions import BibleVersions, get_bible_versions

ZOMI = "ctd"
APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'"})
# Words with inner apostrophes or hyphens (ki-it, Zeisu'n) and an optional final apostrophe
# (the possessive, Pasian'). Case is kept so names are suggested as written.
WORD = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*'?")
MIN_PREFIX = 1
MAX_PREFIX = 40


@dataclass(frozen=True)
class WordList:
    keys: list[str]  # lowercase, sorted, for prefix search
    words: dict[str, tuple[str, int]]  # lowercase -> (most common written form, count)
    sources: tuple[str, ...]

    def complete(self, prefix: str, limit: int) -> list[dict[str, Any]]:
        needle = prefix.strip().lower().translate(APOSTROPHES).rstrip("'")
        if not needle:
            return []
        start = bisect.bisect_left(self.keys, needle)
        end = bisect.bisect_left(self.keys, needle + "￿", lo=start)
        matches = sorted(self.keys[start:end], key=lambda key: (-self.words[key][1], key))
        return [{"word": self.words[key][0], "count": self.words[key][1]} for key in matches[:limit]]


def build_word_list(texts: dict[str, list[str]]) -> WordList:
    """Count words in each source's texts, keeping each word's most common written form."""
    counts: Counter = Counter()
    forms: dict[str, Counter] = defaultdict(Counter)
    for lines in texts.values():
        for line in lines:
            for word in WORD.findall(line.translate(APOSTROPHES)):
                # A final apostrophe is the possessive (Pasian'), typed after the word, not part of it.
                word = word.rstrip("'")
                key = word.lower()
                counts[key] += 1
                forms[key][word] += 1
    words = {key: (forms[key].most_common(1)[0][0], count) for key, count in counts.items()}
    return WordList(sorted(words), words, tuple(sorted(texts)))


class ZomiWords:
    """The word list, rebuilt when the Bible versions database is replaced."""

    def __init__(self, versions: BibleVersions) -> None:
        self.versions = versions
        self._lock = threading.Lock()
        self._list: Optional[WordList] = None
        self._identity: Optional[tuple[int, int]] = None

    @property
    def available(self) -> bool:
        return self.versions.available

    def _texts(self) -> dict[str, list[str]]:
        zomi = [version["id"] for version in self.versions.versions() if version["language_iso"] == ZOMI]
        con = self.versions.connect()
        return {
            version_id: [row[0] for row in con.execute("SELECT text FROM verses WHERE version_id = ?", (version_id,))]
            for version_id in zomi
        }

    def word_list(self) -> WordList:
        identity = self.versions._file_identity()
        with self._lock:
            if self._list is None or self._identity != identity:
                self._list = build_word_list(self._texts())
                self._identity = identity
            return self._list

    def warm(self) -> None:
        """Build the list ahead of the first request; a failure here only delays it to that request."""
        if self.available:
            try:
                self.word_list()
            except Exception:  # noqa: BLE001 - the request path reports real errors
                pass

    def complete(self, prefix: str, limit: int = 8) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
        words = self.word_list()
        return words.complete(prefix, limit), words.sources


@lru_cache(maxsize=1)
def get_zomi_words() -> ZomiWords:
    return ZomiWords(get_bible_versions())
