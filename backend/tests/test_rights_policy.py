"""Per-use rights decisions and verified subsets (docs/RIGHTS_POLICY.md). Fixtures only: no real clearance."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml_pipeline" / "scripts"))

import rights_policy as rp  # type: ignore  # noqa: E402

GOOD_IDS = ["p1", "p2", "p3"]


def clearance(**extra) -> dict:
    entry = {"status": "cleared", "evidence": "Fixture evidence.", "evidence_type": "written_permission",
             "decided_on": "2026-12-01", "decided_by": "O01", "verified_by": ["R02"]}
    entry.update(extra)
    return entry


def rights() -> dict:
    """A combined corpus (blocked), its English and Zomi components, and one verified subset."""
    combined_uses = {use: {"status": "blocked"} for use in rp.USE_RISK}
    needs = {use: {"status": "needs_review"} for use in rp.USE_RISK}
    return {
        "english": {"attribution_required": True, "uses": copy.deepcopy(needs)},
        "zomi": {"provider_derived": True, "uses": copy.deepcopy(needs)},
        "corpus": {
            "display": "blocked", "train": "blocked", "redistribute": "blocked", "commercial": "blocked",
            "components": ["english", "zomi"], "uses": combined_uses,
            "subsets": {"verified": {
                "members_sha256": rp.membership_digest(GOOD_IDS),
                "uses": {"retrieval": clearance(attribution="Tatoeba contributors, CC BY 2.0 FR",
                                                provider_terms={"product": "fixture", "terms_reference": "fixture",
                                                                "reviewed_on": "2026-12-01"})},
                "component_clearances": {
                    "english": {"retrieval": clearance(attribution="Tatoeba contributors, CC BY 2.0 FR")},
                    "zomi": {"retrieval": clearance(provider_terms={"product": "fixture", "terms_reference": "fixture",
                                                                    "reviewed_on": "2026-12-01"})}}}},
        },
        "bible": {"display": "cleared", "train": "cleared", "redistribute": "not_permitted",
                  "commercial": "not_permitted"},
        "refused": {"display": "not_permitted", "uses": {"retrieval": {"status": "not_permitted"}},
                    "subsets": {"s": {"members_sha256": rp.membership_digest(GOOD_IDS),
                                      "uses": {"retrieval": clearance()}}}},
    }


class DefaultDenyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rights = rights()

    def test_unknown_source_use_and_subset_are_denied(self) -> None:
        self.assertFalse(rp.authorize(self.rights, "nope", "display").allowed)
        self.assertFalse(rp.authorize(self.rights, "bible", "telepathy").allowed)
        self.assertFalse(rp.authorize(self.rights, "corpus", "retrieval", "missing", GOOD_IDS).allowed)

    def test_uses_with_no_legacy_column_default_to_denied(self) -> None:
        # Bible display is cleared, but nothing says it may be embedded or sent to an external LLM.
        self.assertTrue(rp.authorize(self.rights, "bible", "display").allowed)
        for use in ("retrieval", "local_embeddings", "external_llm"):
            self.assertFalse(rp.authorize(self.rights, "bible", use).allowed, use)

    def test_legacy_columns_still_decide_their_uses(self) -> None:
        self.assertTrue(rp.authorize(self.rights, "bible", "train").allowed)
        self.assertFalse(rp.authorize(self.rights, "bible", "redistribute").allowed)
        self.assertFalse(rp.authorize(self.rights, "bible", "commercial_inference").allowed)

    def test_each_state_other_than_cleared_is_denied(self) -> None:
        for state in ("needs_review", "blocked", "not_permitted"):
            self.rights["bible"]["uses"] = {"retrieval": {"status": state}}
            self.assertFalse(rp.authorize(self.rights, "bible", "retrieval").allowed, state)

    def test_uses_are_decided_separately(self) -> None:
        self.rights["bible"]["uses"] = {"retrieval": clearance()}
        self.assertTrue(rp.authorize(self.rights, "bible", "retrieval").allowed)
        self.assertFalse(rp.authorize(self.rights, "bible", "external_llm").allowed)
        self.assertFalse(rp.authorize(self.rights, "bible", "local_embeddings").allowed)


class ClearanceEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = {"uses": {}}

    def errors(self, entry: dict, **source) -> list[str]:
        return rp.entry_errors(entry, {**self.source, **source}, "retrieval")

    def test_a_complete_clearance_is_valid(self) -> None:
        self.assertEqual(self.errors(clearance()), [])

    def test_clearance_needs_evidence_a_code_and_an_independent_verifier(self) -> None:
        self.assertTrue(self.errors(clearance(evidence="")))
        self.assertTrue(self.errors(clearance(decided_by="Jane Doe")))
        self.assertTrue(self.errors(clearance(verified_by=[])))
        self.assertTrue(self.errors(clearance(verified_by=["O01"])))  # the decider cannot verify themselves
        self.assertTrue(self.errors(clearance(decided_on="soon")))

    def test_cc0_or_publisher_permission_is_not_enough_on_its_own(self) -> None:
        for kind in ("cc0_declaration", "open_license", "publisher_permission"):
            self.assertTrue(self.errors(clearance(evidence_type=kind)), kind)
            self.assertEqual(self.errors(clearance(evidence_type=kind, underlying_rights_checked=True)), [], kind)

    def test_cc_by_needs_the_attribution_text(self) -> None:
        self.assertTrue(self.errors(clearance(), attribution_required=True))
        self.assertEqual(self.errors(clearance(attribution="Tatoeba contributors"), attribution_required=True), [])

    def test_provider_derived_text_needs_the_provider_terms(self) -> None:
        self.assertTrue(self.errors(clearance(), provider_derived=True))
        terms = {"product": "p", "terms_reference": "t", "reviewed_on": "2026-12-01"}
        self.assertEqual(self.errors(clearance(provider_terms=terms), provider_derived=True), [])

    def test_an_invalid_clearance_does_not_authorize(self) -> None:
        rights_ = rights()
        rights_["bible"]["uses"] = {"retrieval": clearance(verified_by=[])}
        decision = rp.authorize(rights_, "bible", "retrieval")
        self.assertFalse(decision.allowed)
        self.assertIn("not valid", decision.reason)


class SubsetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rights = rights()

    def test_a_verified_subset_is_usable_while_the_corpus_stays_blocked(self) -> None:
        self.assertFalse(rp.authorize(self.rights, "corpus", "retrieval").allowed)
        decision = rp.authorize(self.rights, "corpus", "retrieval", "verified", GOOD_IDS)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.basis, "subset")

    def test_the_subset_is_cleared_only_for_the_uses_decided(self) -> None:
        for use in ("train", "external_llm", "commercial_inference", "redistribute", "local_embeddings"):
            self.assertFalse(rp.authorize(self.rights, "corpus", use, "verified", GOOD_IDS).allowed, use)

    def test_changed_membership_voids_the_clearance(self) -> None:
        self.assertFalse(rp.authorize(self.rights, "corpus", "retrieval", "verified", GOOD_IDS + ["p4"]).allowed)
        self.assertFalse(rp.authorize(self.rights, "corpus", "retrieval", "verified", GOOD_IDS[:2]).allowed)
        self.assertFalse(rp.authorize(self.rights, "corpus", "retrieval", "verified", None).allowed)

    def test_a_subset_of_a_combined_record_needs_both_components_cleared(self) -> None:
        del self.rights["corpus"]["subsets"]["verified"]["component_clearances"]["zomi"]
        decision = rp.authorize(self.rights, "corpus", "retrieval", "verified", GOOD_IDS)
        self.assertFalse(decision.allowed)
        self.assertIn("zomi", decision.reason)

    def test_a_subset_cannot_override_a_rights_holder_refusal(self) -> None:
        self.assertFalse(rp.authorize(self.rights, "refused", "retrieval", "s", GOOD_IDS).allowed)

    def test_combined_record_cannot_clear_before_its_components(self) -> None:
        self.rights["corpus"]["uses"]["retrieval"] = clearance(
            attribution="x", provider_terms={"product": "p", "terms_reference": "t", "reviewed_on": "2026-12-01"})
        self.assertFalse(rp.authorize(self.rights, "corpus", "retrieval").allowed)
        self.assertTrue(any("before its components" in p for p in rp.validate_rights(self.rights)))


class SelectUsableTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rights = rights()
        self.records = (
            [{"id": i, "source": "corpus", "subset": "verified"} for i in GOOD_IDS]
            + [{"id": "u1", "source": "corpus"}, {"id": "u2", "source": "corpus"}]
            + [{"id": "claim", "source": "corpus", "subset": "verified"}]  # claims the subset, not a member
            + [{"id": "b1", "source": "bible"}])

    def test_verified_members_pass_and_the_rest_are_excluded_with_reasons(self) -> None:
        usable, excluded = rp.select_usable(self.records, self.rights, "retrieval", members={"verified": GOOD_IDS})
        self.assertEqual({r["id"] for r in usable}, set(GOOD_IDS))
        self.assertEqual(sum(excluded.values()), 4)  # u1, u2, claim, b1 (the Bible has no retrieval decision)
        self.assertTrue(all("corpus" in k or "bible" in k for k in excluded))

    def test_without_membership_nothing_from_the_corpus_is_usable(self) -> None:
        usable, _ = rp.select_usable(self.records, self.rights, "retrieval")
        self.assertEqual(usable, [])

    def test_the_same_subset_is_excluded_for_an_undecided_use(self) -> None:
        usable, excluded = rp.select_usable(self.records, self.rights, "train", members={"verified": GOOD_IDS})
        self.assertEqual([r["id"] for r in usable], ["b1"])  # only the Bible's legacy train clearance applies
        self.assertGreater(sum(excluded.values()), 0)


class RegisterTests(unittest.TestCase):
    def test_the_real_register_validates(self) -> None:
        sources = rp.load_rights()
        self.assertEqual(rp.validate_rights(sources), [])

    def test_the_real_corpus_is_still_excluded_for_every_use(self) -> None:
        sources = rp.load_rights()
        for name in ("parallel_corpus", "parallel_corpus_english_tatoeba", "parallel_corpus_zomi_gemini"):
            for use in rp.USE_RISK:
                self.assertFalse(rp.authorize(sources, name, use).allowed, f"{name} {use}")

    def test_existing_cleared_legacy_uses_are_unchanged(self) -> None:
        sources = rp.load_rights()
        self.assertTrue(rp.authorize(sources, "bible_web", "display").allowed)
        self.assertTrue(rp.authorize(sources, "bible_tdb", "train").allowed)
        self.assertFalse(rp.authorize(sources, "bible_tdb", "commercial_inference").allowed)
        self.assertFalse(rp.authorize(sources, "translation_master_50k", "display").allowed)

    def test_validation_catches_drift_and_rewritten_history(self) -> None:
        sources = rights()
        sources["corpus"]["subsets"]["verified"]["members_sha256"] = "bad"
        sources["bible"]["history"] = [{"date": "2026-12-02"}, {"date": "2026-12-01"}]
        sources["bible"]["uses"] = {"display": clearance()}
        sources["bible"]["display"] = "needs_review"
        problems = "\n".join(rp.validate_rights(sources))
        self.assertIn("members_sha256", problems)
        self.assertIn("history", problems)
        self.assertIn("legacy column display", problems)


if __name__ == "__main__":
    unittest.main()
