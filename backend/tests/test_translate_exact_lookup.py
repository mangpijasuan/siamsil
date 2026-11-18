"""The exact-match lookup in Translate must not scan the whole corpus (first searches took ~20 s on a cold start)."""
from __future__ import annotations

import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT / "services"))

from language_engine import (  # type: ignore  # noqa: E402
    PARALLEL_EXACT_SQL, PARALLEL_FTS_COLUMN, LanguageEngine, exact_forms, fts_match,
)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from corpus_switch import serve_corpus  # type: ignore  # noqa: E402

SCHEMA = """
CREATE TABLE parallel_sentences (
    id INTEGER PRIMARY KEY, raw_source_text TEXT, raw_target_text TEXT,
    normalized_source_text TEXT, normalized_target_text TEXT, model TEXT, source_reference TEXT,
    quality_flags TEXT, quality_score REAL, verified INTEGER, dataset_split TEXT
);
CREATE VIRTUAL TABLE parallel_fts USING fts5(
    normalized_source_text, normalized_target_text, tokenize = 'unicode61 remove_diacritics 2'
);
"""


def build(db: Path, pairs: list[tuple[int, str, str]]) -> None:
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    for pair_id, english, zomi in pairs:  # placeholder text stands in for Zomi; no Zomi data is invented here
        con.execute("INSERT INTO parallel_sentences VALUES (?,?,?,?,?,'test','test','[]',1.0,0,'train')",
                    (pair_id, english, zomi, english, zomi))
        con.execute("INSERT INTO parallel_fts (rowid, normalized_source_text, normalized_target_text) VALUES (?,?,?)",
                    (pair_id, english, zomi))
    con.commit()
    con.close()


class ExactLookupTests(unittest.TestCase):
    def setUp(self) -> None:
        serve_corpus(self)

    def engine(self, pairs: list[tuple[int, str, str]]) -> LanguageEngine:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "language.sqlite"
        build(db, pairs)
        return LanguageEngine(db)

    def test_the_corpus_is_hidden_by_default_and_shown_only_when_switched_on(self) -> None:
        from settings import Settings  # type: ignore

        self.assertFalse(Settings().serve_parallel_corpus)  # the corpus is blocked in data/rights.json
        engine = self.engine([(1, "Thank you.", "ZOMI_PLACEHOLDER_ONE")])
        self.assertEqual(len(engine.search_parallel("Thank you")), 1)  # the setUp switched it on
        serve_corpus(self, enabled=False)
        self.assertEqual(engine.search_parallel("Thank you"), [])

    def test_a_token_with_no_letter_or_digit_is_left_out_of_the_search(self) -> None:
        self.assertEqual(fts_match("Tom — Mary"), '"Tom" AND "Mary"*')
        self.assertEqual(fts_match("a & b"), '"a" AND "b"*')
        self.assertIsNone(fts_match("— & -"))

    def test_an_exact_lookup_matches_whole_words_not_prefixes(self) -> None:
        self.assertEqual(fts_match("thank you"), '"thank" AND "you"*')
        self.assertEqual(fts_match("thank you", prefix=False), '"thank" AND "you"')

    def test_a_one_word_exact_sentence_is_found_among_many_pairs_with_that_word(self) -> None:
        pairs = [(i, f"you are here {i}", f"ZOMI_PLACEHOLDER_{i}") for i in range(2, 900)]
        pairs += [(i, f"youthful{i} words", f"ZOMI_PLACEHOLDER_{i}") for i in range(1000, 1900)]
        pairs.append((1, "You.", "ZOMI_PLACEHOLDER_EXACT"))
        hits = self.engine(pairs).search_parallel("you", direction="en-ctd")
        self.assertEqual((hits[0]["id"], hits[0]["exact"]), (1, True))

    def test_a_sentence_with_a_dash_and_curly_quotes_is_found_as_an_exact_match(self) -> None:
        sentence = "She uses the “dry brush” method — mixing tiny drops of water with colours."
        engine = self.engine([(1, sentence, "ZOMI_PLACEHOLDER_ONE"), (2, "A different sentence about water", "ZOMI_PLACEHOLDER_TWO")])
        hits = engine.search_parallel(sentence, direction="en-ctd")
        self.assertEqual([(hit["id"], hit["exact"]) for hit in hits][:1], [(1, True)])

    def test_the_exact_sentence_is_found_among_many_longer_ones_with_the_same_words(self) -> None:
        pairs = [(i, f"Thank you very much for item number {i}", f"ZOMI_PLACEHOLDER_{i}") for i in range(2, 900)]
        pairs.append((1, "Thank you.", "ZOMI_PLACEHOLDER_EXACT"))
        hits = self.engine(pairs).search_parallel("thank you", direction="en-ctd")
        self.assertEqual((hits[0]["id"], hits[0]["exact"]), (1, True))

    def test_exact_matching_ignores_case_and_closing_marks(self) -> None:
        engine = self.engine([(1, "Thank you!", "ZOMI_PLACEHOLDER_A"), (2, "thank you.", "ZOMI_PLACEHOLDER_B")])
        hits = engine.search_parallel("THANK YOU", direction="en-ctd")
        self.assertEqual(sorted(hit["id"] for hit in hits if hit["exact"]), [1, 2])

    def test_the_exact_query_never_scans_the_corpus_table(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "language.sqlite"
        build(db, [(1, "Thank you.", "ZOMI_PLACEHOLDER_A")])
        con = sqlite3.connect(db)
        for direction in ("en-ctd", "ctd-en", None):
            forms = exact_forms("thank you")
            params = ("thank", *forms, *(forms if direction is None else []), 20)
            plan = " | ".join(row[3] for row in con.execute("EXPLAIN QUERY PLAN " + PARALLEL_EXACT_SQL[direction], params))
            self.assertIn("parallel_fts", plan, direction)
            # The full-text candidates may be scanned; the corpus table (alias p) is only searched by id.
            self.assertIsNone(re.search(r"SCAN (p|parallel_sentences)(?![A-Za-z_])", plan), f"{direction}: {plan}")
            self.assertIn("SEARCH p USING INTEGER PRIMARY KEY", plan, direction)
        con.close()
        self.assertEqual(PARALLEL_FTS_COLUMN["en-ctd"], "normalized_source_text")


if __name__ == "__main__":
    unittest.main()
