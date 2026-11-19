"""The API's corpus search obeys the rights register, not only the serving switch (docs/RIGHTS_POLICY.md).

Fixture pairs use placeholder text; no Zomi data is invented here.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT / "services"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import language_engine  # type: ignore
from language_engine import LanguageEngine  # type: ignore
from settings import Settings  # type: ignore
from test_translate_exact_lookup import build  # type: ignore

rights = language_engine.rights
rp = rights.rights_policy

PAIRS = [(1, "good morning", "placeholder one"), (2, "good evening", "placeholder two"),
         (3, "good night", "placeholder three")]
TERMS = {"product": "fixture", "terms_reference": "fixture", "reviewed_on": "2026-12-01"}


def restricted(**extra) -> dict:
    entry = {"status": "cleared", "path": "restricted", "evidence": "Fixture.", "evidence_type": "written_permission",
             "underlying_rights_checked": True, "decided_on": "2026-12-01", "decided_by": "O01",
             "verified_by": ["R02"]}
    entry.update(extra)
    return entry


class CorpusGateTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        build(self.dir / "language.sqlite", PAIRS)
        self.engine = LanguageEngine(self.dir / "language.sqlite")

    def use_register(self, register: dict | None, serve: bool = True) -> None:
        path = self.dir / "rights.json"
        if register is not None:
            path.write_text(json.dumps(register), encoding="utf-8")
        configured = Settings(serve_parallel_corpus=serve, rights_file=path if register is not None else None,
                              data_dir=self.dir / "nowhere")
        for module in (language_engine, rights):
            patcher = patch.object(module, "get_settings", return_value=configured)
            patcher.start()
            self.addCleanup(patcher.stop)
        if register is None:  # no register anywhere: the repository copy must not be found either
            patcher = patch.object(rights, "PROJECT_ROOT", self.dir / "nowhere")
            patcher.start()
            self.addCleanup(patcher.stop)

    def real_register(self) -> dict:
        return json.loads((PROJECT_ROOT / "data" / "rights.json").read_text(encoding="utf-8"))

    def with_cleared_subset(self, ids: list[str]) -> dict:
        register = copy.deepcopy(self.real_register())
        (self.dir / "members.txt").write_text("\n".join(ids) + "\n", encoding="utf-8")
        clearances = {"display": restricted(attribution="Tatoeba contributors, CC BY 2.0 FR", provider_terms=TERMS),
                      "retrieval": restricted(attribution="Tatoeba contributors, CC BY 2.0 FR", provider_terms=TERMS)}
        register["sources"]["parallel_corpus"]["subsets"] = {"fixture": {
            "members_sha256": rp.membership_digest(ids), "members_file": "members.txt",
            "uses": clearances,
            "component_clearances": {
                "parallel_corpus_english_tatoeba": {u: restricted(attribution="Tatoeba contributors")
                                                    for u in clearances},
                "parallel_corpus_zomi_gemini": {u: restricted(provider_terms=TERMS) for u in clearances}}}}
        return register

    def test_the_switch_alone_does_not_serve_a_blocked_corpus(self) -> None:
        self.use_register(self.real_register())
        self.assertEqual(self.engine.search_parallel("good"), [])

    def test_no_register_means_nothing_is_served(self) -> None:
        self.use_register(None)
        self.assertEqual(self.engine.search_parallel("good"), [])

    def test_the_switch_off_still_hides_everything(self) -> None:
        self.use_register(self.with_cleared_subset(["1"]), serve=False)
        self.assertEqual(self.engine.search_parallel("good"), [])

    def test_only_a_cleared_subset_is_served(self) -> None:
        self.use_register(self.with_cleared_subset(["1", "3"]))
        self.assertEqual(sorted(r["id"] for r in self.engine.search_parallel("good")), [1, 3])
        self.assertEqual([r["id"] for r in self.engine.search_parallel("good night", direction="en-ctd")], [3])

    def test_siamsil_ai_needs_retrieval_as_well_as_display(self) -> None:
        register = self.with_cleared_subset(["1"])
        del register["sources"]["parallel_corpus"]["subsets"]["fixture"]["uses"]["retrieval"]
        self.use_register(register)
        self.assertEqual([r["id"] for r in self.engine.search_parallel("good")], [1])
        self.assertEqual(self.engine.search_parallel("good", uses=("display", "retrieval")), [])

    def test_a_changed_membership_file_stops_serving(self) -> None:
        self.use_register(self.with_cleared_subset(["1"]))
        (self.dir / "members.txt").write_text("1\n2\n", encoding="utf-8")
        self.assertEqual(self.engine.search_parallel("good"), [])


class FacadeTests(unittest.TestCase):
    def test_the_api_reads_the_real_register(self) -> None:
        self.assertTrue(rights.allowed("bible_web", "display"))
        self.assertFalse(rights.allowed("parallel_corpus", "display"))
        self.assertIn("blocked", rights.decision("parallel_corpus", "retrieval").reason)


if __name__ == "__main__":
    unittest.main()
