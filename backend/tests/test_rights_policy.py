"""Rights policy: three clearance paths, per-use decisions, verified subsets (docs/RIGHTS_POLICY.md).

Fixtures only, except RegisterTests, which read the real data/rights.json and make no clearance.
"""
from __future__ import annotations

import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml_pipeline" / "scripts"))

import rights_policy as rp  # type: ignore

GOOD_IDS = ["p1", "p2", "p3"]
SHA = "5e513a996ddd84c8350f1da0539d67a4cd854f58c7bf84e0b3c8d1b259507bcf"
TERMS = {"product": "fixture", "terms_reference": "fixture", "reviewed_on": "2026-12-01"}


def restricted(**extra) -> dict:
    """A Path C clearance: decided and independently verified."""
    entry = {"status": "cleared", "path": "restricted", "evidence": "Fixture evidence.",
             "evidence_type": "written_permission", "underlying_rights_checked": True,
             "decided_on": "2026-12-01", "decided_by": "O01", "verified_by": ["R02"]}
    entry.update(extra)
    return entry


def owner(**extra) -> dict:
    """A Path A clearance: the owner's decision, no second reviewer."""
    entry = {"status": "cleared", "path": "owner_original", "evidence": "Owner's authorship statement.",
             "evidence_type": "owner_authorship", "decided_on": "2026-12-01", "decided_by": "O01"}
    entry.update(extra)
    return entry


def open_license(**extra) -> dict:
    """A Path B clearance: a verified license, no second reviewer."""
    entry = {"status": "cleared", "path": "open_license", "evidence": "License text, where kept.",
             "evidence_type": "public_domain", "license": "public-domain", "underlying_rights_checked": True,
             "decided_on": "2026-12-01", "decided_by": "O01"}
    entry.update(extra)
    return entry


def owner_source(**extra) -> dict:
    source = {"origin": "owner_original",
              "provenance": {"author": "project owner", "attested_on": "2026-11-30",
                             "attestations": ["sole_author", "no_third_party_content"],
                             "ai_assistance": "none", "sha256": SHA}}
    source.update(extra)
    return source


def rights() -> dict:
    """A combined corpus (blocked), its English and Zomi components, one verified subset, and simple sources."""
    combined_uses = {use: {"status": "blocked"} for use in rp.USE_RISK}
    needs = {use: {"status": "needs_review"} for use in rp.USE_RISK}
    return {
        "english": {"origin": "third_party", "attribution_required": True, "uses": copy.deepcopy(needs)},
        "zomi": {"origin": "third_party", "provider_derived": True, "uses": copy.deepcopy(needs)},
        "corpus": {
            "display": "blocked", "train": "blocked", "redistribute": "blocked", "commercial": "blocked",
            "components": ["english", "zomi"], "uses": combined_uses,
            "subsets": {"verified": {
                "members_sha256": rp.membership_digest(GOOD_IDS),
                "uses": {"retrieval": restricted(attribution="Tatoeba contributors, CC BY 2.0 FR",
                                                 provider_terms=TERMS)},
                "component_clearances": {
                    "english": {"retrieval": restricted(attribution="Tatoeba contributors, CC BY 2.0 FR")},
                    "zomi": {"retrieval": restricted(provider_terms=TERMS)}}}},
        },
        "bible": {"display": "cleared", "train": "cleared", "redistribute": "not_permitted",
                  "commercial": "not_permitted"},
        "pd": {"origin": "third_party", "display": "cleared"},
        "mine": owner_source(train="needs_review"),
        "refused": {"display": "not_permitted", "uses": {"retrieval": {"status": "not_permitted"}},
                    "subsets": {"s": {"members_sha256": rp.membership_digest(GOOD_IDS),
                                      "uses": {"retrieval": restricted()}}}},
    }


class DefaultDenyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rights = rights()

    def test_unknown_source_use_and_subset_are_denied(self) -> None:
        self.assertFalse(rp.authorize(self.rights, "nope", "display").allowed)
        self.assertFalse(rp.authorize(self.rights, "bible", "telepathy").allowed)
        self.assertFalse(rp.authorize(self.rights, "corpus", "retrieval", "missing", GOOD_IDS).allowed)

    def test_uses_with_no_legacy_column_default_to_denied(self) -> None:
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
        self.rights["mine"]["uses"] = {"retrieval": owner()}
        self.assertTrue(rp.authorize(self.rights, "mine", "retrieval").allowed)
        self.assertFalse(rp.authorize(self.rights, "mine", "external_llm").allowed)
        self.assertFalse(rp.authorize(self.rights, "mine", "train").allowed)


class PathATests(unittest.TestCase):
    """Owner-controlled original data: the owner decides, a second reviewer is optional."""

    def errors(self, entry: dict, source: dict | None = None) -> list[str]:
        return rp.entry_errors(entry, owner_source() if source is None else source, "train")

    def test_the_owner_alone_can_clear_owner_original_data(self) -> None:
        self.assertEqual(self.errors(owner()), [])
        self.assertNotIn("verified_by", owner())

    def test_a_second_reviewer_is_allowed_but_not_required(self) -> None:
        self.assertEqual(self.errors(owner(verified_by=["R02"])), [])

    def test_the_decision_must_be_the_owners(self) -> None:
        self.assertTrue(self.errors(owner(decided_by="R02")))
        self.assertTrue(self.errors(owner(decided_by="Jane Doe")))

    def test_provenance_is_checked_automatically(self) -> None:
        for broken in (
            {"attestations": ["sole_author"]},                           # no_third_party_content missing
            {"sha256": "not-a-checksum"},                               # file not pinned
            {"attested_on": "2026-12-05"},                              # decision predates the attestation
        ):
            source = owner_source()
            source["provenance"].update(broken)
            self.assertTrue(self.errors(owner(), source), broken)
        source = owner_source()
        del source["provenance"]["ai_assistance"]
        self.assertTrue(self.errors(owner(), source))

    def test_ai_assistance_is_disclosed_not_forbidden(self) -> None:
        source = owner_source()
        source["provenance"]["ai_assistance"] = "spell-checked with a tool; no text drafted"
        self.assertEqual(self.errors(owner(), source), [])

    def test_third_party_data_cannot_use_path_a(self) -> None:
        self.assertTrue(self.errors(owner(), {"origin": "third_party"}))
        self.assertTrue(self.errors(owner(), {}))

    def test_risk_escalates_owner_data_to_path_c(self) -> None:
        for trait in ({"disputed": True}, {"provider_derived": True}, {"risk_flags": ["authorship corrected"]}):
            source = owner_source(**trait)
            self.assertEqual(rp.eligible_paths(source), ("restricted",), trait)
            self.assertTrue(any("not available" in e for e in self.errors(owner(), source)), trait)


class PathBTests(unittest.TestCase):
    """Third-party data under a verified license or written grant: evidence-based, no mandatory second reviewer."""

    def errors(self, entry: dict, use: str = "retrieval", **source) -> list[str]:
        return rp.entry_errors(entry, {"origin": "third_party", **source}, use)

    def test_public_domain_clears_on_evidence(self) -> None:
        self.assertEqual(self.errors(open_license()), [])

    def test_the_licensor_must_hold_the_rights(self) -> None:
        self.assertTrue(self.errors(open_license(underlying_rights_checked=False)))

    def test_the_license_must_permit_the_use(self) -> None:
        nc = open_license(evidence_type="open_license", license="CC-BY-NC-4.0", attribution="Author")
        self.assertEqual(self.errors(nc, "retrieval"), [])
        self.assertTrue(self.errors(nc, "commercial_inference"))

    def test_cc_by_needs_the_attribution_text(self) -> None:
        cc_by = open_license(evidence_type="open_license", license="CC-BY-2.0-FR")
        self.assertTrue(self.errors(cc_by))
        self.assertEqual(self.errors({**cc_by, "attribution": "Tatoeba contributors, CC BY 2.0 FR"}), [])

    def test_an_unknown_license_is_uncertain_and_goes_to_path_c(self) -> None:
        self.assertTrue(self.errors(open_license(license="custom: see website")))

    def test_a_written_grant_clears_only_the_uses_it_names(self) -> None:
        grant = {"grantor": "publisher (role)", "date": "2026-12-01", "wording": "display and training",
                 "kept_at": "private storage", "scope": ["display", "train"]}
        entry = open_license(evidence_type="written_permission", grant=grant)
        del entry["license"]
        self.assertEqual(self.errors(entry, "train"), [])
        self.assertTrue(self.errors(entry, "retrieval"))
        self.assertTrue(self.errors({**entry, "grant": {"scope": ["train"]}}, "train"))  # no grantor or wording

    def test_provider_derived_and_disputed_data_cannot_use_path_b(self) -> None:
        self.assertTrue(any("not available" in e for e in self.errors(open_license(), provider_derived=True)))
        self.assertTrue(any("not available" in e for e in self.errors(open_license(), disputed=True)))

    def test_a_verbal_report_never_clears_on_path_b(self) -> None:
        self.assertTrue(self.errors(open_license(evidence_type="owner_report")))


class PathCTests(unittest.TestCase):
    """Restricted or uncertain data: an independent verifier is mandatory."""

    def errors(self, entry: dict, **source) -> list[str]:
        return rp.entry_errors(entry, {"origin": "third_party", **source}, "retrieval")

    def test_a_complete_restricted_clearance_is_valid(self) -> None:
        self.assertEqual(self.errors(restricted()), [])

    def test_it_needs_an_independent_verifier(self) -> None:
        self.assertTrue(self.errors(restricted(verified_by=[])))
        self.assertTrue(self.errors(restricted(verified_by=["O01"])))  # the decider cannot verify themselves
        self.assertTrue(self.errors({k: v for k, v in restricted().items() if k != "verified_by"}))

    def test_cc0_or_publisher_permission_is_not_enough_on_its_own(self) -> None:
        for kind in ("cc0_declaration", "open_license", "publisher_permission"):
            self.assertTrue(self.errors(restricted(evidence_type=kind, underlying_rights_checked=False)), kind)
            self.assertEqual(self.errors(restricted(evidence_type=kind)), [], kind)

    def test_provider_derived_text_needs_the_provider_terms(self) -> None:
        self.assertTrue(self.errors(restricted(), provider_derived=True))
        self.assertEqual(self.errors(restricted(provider_terms=TERMS), provider_derived=True), [])

    def test_basic_fields_are_still_required(self) -> None:
        self.assertTrue(self.errors(restricted(evidence="")))
        self.assertTrue(self.errors(restricted(decided_on="soon")))
        self.assertTrue(self.errors(restricted(path=None)))

    def test_an_invalid_clearance_does_not_authorize(self) -> None:
        rights_ = rights()
        rights_["bible"]["uses"] = {"retrieval": restricted(verified_by=[])}
        decision = rp.authorize(rights_, "bible", "retrieval")
        self.assertFalse(decision.allowed)
        self.assertIn("not valid", decision.reason)


class RightsAreNotQualityTests(unittest.TestCase):
    def test_review_fields_are_rejected_in_a_rights_decision(self) -> None:
        for field in ("review_status", "quality_tier", "reviewed_by"):
            errors = rp.entry_errors(owner(**{field: "x"}), owner_source(), "train")
            self.assertTrue(any("linguistic review" in e for e in errors), field)


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

    def test_a_subset_of_combined_data_cannot_skip_path_c(self) -> None:
        subset = self.rights["corpus"]["subsets"]["verified"]
        subset["uses"]["retrieval"] = open_license(attribution="x", provider_terms=TERMS)
        self.assertFalse(rp.authorize(self.rights, "corpus", "retrieval", "verified", GOOD_IDS).allowed)

    def test_owner_written_rows_of_a_third_party_file_can_be_a_path_a_subset(self) -> None:
        self.rights["pd"]["subsets"] = {"owner_rows": {
            "members_sha256": rp.membership_digest(GOOD_IDS),
            "origin": "owner_original", "provenance": owner_source()["provenance"],
            "uses": {"train": owner()}}}
        self.assertTrue(rp.authorize(self.rights, "pd", "train", "owner_rows", GOOD_IDS).allowed)
        self.assertEqual([p for p in rp.validate_rights(self.rights) if p.startswith("pd.")], [])

    def test_a_subset_cannot_override_a_rights_holder_refusal(self) -> None:
        self.assertFalse(rp.authorize(self.rights, "refused", "retrieval", "s", GOOD_IDS).allowed)

    def test_combined_record_cannot_clear_before_its_components(self) -> None:
        self.rights["corpus"]["uses"]["retrieval"] = restricted(attribution="x", provider_terms=TERMS)
        self.assertFalse(rp.authorize(self.rights, "corpus", "retrieval").allowed)
        self.assertTrue(any("before its components" in p for p in rp.validate_rights(self.rights)))

    def test_usable_ids_reads_the_membership_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "members.txt").write_text("# cleared\np3\np1\np2\n", encoding="utf-8")
            self.rights["corpus"]["subsets"]["verified"]["members_file"] = "members.txt"
            self.assertEqual(rp.usable_ids(self.rights, "corpus", "retrieval", Path(tmp)), frozenset(GOOD_IDS))
            self.assertEqual(rp.usable_ids(self.rights, "corpus", "train", Path(tmp)), frozenset())
            self.assertIsNone(rp.usable_ids(self.rights, "bible", "train", Path(tmp)))
            (Path(tmp) / "members.txt").write_text("p1\np2\np3\np4\n", encoding="utf-8")  # members drifted
            self.assertEqual(rp.usable_ids(self.rights, "corpus", "retrieval", Path(tmp)), frozenset())


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

    def test_without_membership_nothing_from_the_corpus_is_usable(self) -> None:
        usable, _ = rp.select_usable(self.records, self.rights, "retrieval")
        self.assertEqual(usable, [])

    def test_the_same_subset_is_excluded_for_an_undecided_use(self) -> None:
        usable, _ = rp.select_usable(self.records, self.rights, "train", members={"verified": GOOD_IDS})
        self.assertEqual([r["id"] for r in usable], ["b1"])


class DecideTests(unittest.TestCase):
    """`decide` and `attest` record decisions; they never invent one."""

    def setUp(self) -> None:
        self.register = {"sources": rights()}

    def test_decide_records_appends_history_and_syncs_the_legacy_column(self) -> None:
        new = rp.record_decision(self.register, "mine", "train", owner())
        source = new["sources"]["mine"]
        self.assertEqual(source["train"], "cleared")
        self.assertEqual(source["history"][-1]["previous"], "needs_review")
        self.assertTrue(rp.authorize(new["sources"], "mine", "train").allowed)
        self.assertEqual(self.register["sources"]["mine"]["train"], "needs_review")  # input not mutated

    def test_an_incomplete_decision_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            rp.record_decision(self.register, "mine", "train", owner(decided_by="R02"))
        with self.assertRaises(ValueError):
            rp.record_decision(self.register, "zomi", "retrieval", open_license())

    def test_history_is_appended_in_order(self) -> None:
        self.register["sources"]["mine"]["history"] = [{"date": "2026-12-03", "status": "needs_review"}]
        new = rp.record_decision(self.register, "mine", "train", owner())
        self.assertEqual([h["date"] for h in new["sources"]["mine"]["history"]], ["2026-12-03", "2026-12-03"])

    def test_attest_moves_a_pending_attestation(self) -> None:
        source = self.register["sources"]["mine"]
        source["provenance"]["attestations"] = ["sole_author"]
        source["provenance"]["attestations_pending"] = ["no_third_party_content"]
        with self.assertRaises(ValueError):
            rp.record_decision(self.register, "mine", "train", owner())
        attested = rp.record_attestation(self.register, "mine", "no_third_party_content", "O01", "2026-12-01")
        self.assertNotIn("attestations_pending", attested["sources"]["mine"]["provenance"])
        rp.record_decision(attested, "mine", "train", owner())
        with self.assertRaises(ValueError):
            rp.record_attestation(self.register, "mine", "no_third_party_content", "R02", "2026-12-01")
        with self.assertRaises(ValueError):
            rp.record_attestation(self.register, "bible", "no_third_party_content", "O01", "2026-12-01")


class RegisterTests(unittest.TestCase):
    """The real register: consistent, and nothing newly cleared by this change."""

    def setUp(self) -> None:
        self.sources = rp.load_rights()

    def test_the_real_register_validates(self) -> None:
        self.assertEqual(rp.validate_rights(self.sources), [])

    def test_the_real_corpus_is_still_excluded_for_every_use(self) -> None:
        for name in ("parallel_corpus", "parallel_corpus_english_tatoeba", "parallel_corpus_zomi_gemini"):
            for use in rp.USE_RISK:
                self.assertFalse(rp.authorize(self.sources, name, use).allowed, f"{name} {use}")

    def test_existing_cleared_legacy_uses_are_unchanged(self) -> None:
        self.assertTrue(rp.authorize(self.sources, "bible_web", "display").allowed)
        self.assertTrue(rp.authorize(self.sources, "bible_tdb", "train").allowed)
        self.assertFalse(rp.authorize(self.sources, "bible_tdb", "commercial_inference").allowed)
        self.assertFalse(rp.authorize(self.sources, "translation_master_50k", "display").allowed)

    def test_paths_follow_the_recorded_facts(self) -> None:
        self.assertEqual(rp.eligible_paths(self.sources["essential_3000"])[0], "owner_original")
        self.assertEqual(rp.eligible_paths(self.sources["bible_web"])[0], "open_license")
        for name in ("translation_master_50k", "parallel_corpus_zomi_gemini", "parallel_corpus",
                     "zomi_standard_dictionary"):
            self.assertEqual(rp.eligible_paths(self.sources[name]), ("restricted",), name)

    def test_essential_3000_waits_for_the_owners_attestation(self) -> None:
        provenance = self.sources["essential_3000"]["provenance"]
        self.assertIn("no_third_party_content", provenance.get("attestations_pending", []))
        self.assertFalse(rp.authorize(self.sources, "essential_3000", "train").allowed)

    def test_validation_catches_drift_and_rewritten_history(self) -> None:
        sources = rights()
        sources["corpus"]["subsets"]["verified"]["members_sha256"] = "bad"
        sources["bible"]["history"] = [{"date": "2026-12-02"}, {"date": "2026-12-01"}]
        sources["mine"]["uses"] = {"train": owner()}
        problems = "\n".join(rp.validate_rights(sources))
        self.assertIn("members_sha256", problems)
        self.assertIn("history", problems)
        self.assertIn("legacy column train", problems)


class OwnerDataFlowTests(unittest.TestCase):
    """The real Essential 3000 record, after the owner's attestation and Path A decision, reaches the training
    export; before them it does not. Runs on a copy of data/rights.json; the real register is not changed."""

    def test_owner_decision_admits_essential_3000_to_the_training_export(self) -> None:
        import export_datasets  # type: ignore

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rights.json"
            path.write_text((ROOT / "data" / "rights.json").read_text(encoding="utf-8"), encoding="utf-8")
            self.assertEqual(export_datasets.load_rights(path)["essential_3000"], "needs_review")
            with redirect_stdout(io.StringIO()):
                rp.main(["attest", "essential_3000", "no_third_party_content", "--by", "O01", "--on", "2026-11-19",
                         "--rights", str(path)])
                rp.main(["decide", "essential_3000", "train", "--path", "owner_original", "--by", "O01",
                         "--on", "2026-11-19", "--rights", str(path),
                         "--evidence", "Owner's statements of 2026-10-25 and 2026-10-26 (docs/DATA_RIGHTS.md)"])
            admitted = export_datasets.load_rights(path)
            self.assertEqual(admitted["essential_3000"], "cleared")
            self.assertEqual(admitted["translation_master_50k"], "needs_review")  # sibling dictionary unaffected
            self.assertEqual(admitted["parallel_corpus"], "blocked")
            record = json.loads(path.read_text(encoding="utf-8"))["sources"]["essential_3000"]
            self.assertNotIn("verified_by", record["uses"]["train"])
            self.assertEqual(record["display"], "needs_review")  # only the use decided


if __name__ == "__main__":
    unittest.main()
