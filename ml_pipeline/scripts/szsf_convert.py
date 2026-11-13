#!/usr/bin/env python3
"""Convert the training export into an SZSF master file (docs/SZSF.md).

  python3 ml_pipeline/scripts/szsf_convert.py pairs \\
      --input data/datasets/train.jsonl data/datasets/validation.jsonl data/datasets/test.jsonl \\
      --db data/processed/language/siamsil_language.sqlite --reviews data/reviews/corpus-reviews.jsonl \\
      --roster roster.csv --out szsf-master-v1.0.0.jsonl

What it does, record by record:
  * keeps `english` and `zomi` exactly as the export has them, and adds the standard form from the adopted rules
    (zolai_standard.py; with no adopted rule the standard form equals the original);
  * takes each corpus pair's review result from the saved review records (corpus_reviews.py), never from a flag:
    a record the export calls human-reviewed must have a HUMAN_APPROVED decision, or the run stops;
  * says what the Zomi's origin is. Corpus Zomi is machine-made, and counts as provider-derived unless its model is
    named with --own-model (a model Siamsil trained itself); provider-derived records stay out of training
    exports by default. Sources whose origin is not recorded are `unknown`;
  * writes only records that pass `szsf.py`; the others go to a rejects file with their problems, never silently
    corrected (`zomi` is the source's text).

The output is checked as a whole (rights file, adopted rules, roster) before it is put in place, together with its
manifest. A master file is immutable: an existing file is never overwritten. Nothing here clears a source for use.

  python3 ml_pipeline/scripts/szsf_convert.py senses \
      --db data/processed/language/siamsil_language.sqlite --reviews dictionary-reviews.jsonl \
      --roster roster.csv --out szsf-master-v1.0.0.jsonl

`senses` converts the live dictionary's senses (`kind: dictionary_sense`; `english` is the headword, `zomi` its Zomi
equivalents as the source gives them). Review results come from the saved dictionary reviews (dictionary_reviews.py),
and a review of Zomi that has since changed counts for nothing. Only senses that have a sense ID (ZD-000123) are
converted. A sense whose Zomi was replaced by an approved correction is left out and counted: SZSF 1.0 has no
field for a correction, so that needs the owner's decision. Senses matching a human evaluation item are left out.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Iterator

import corpus_reviews
import dictionary_reviews
import szsf
import zolai_standard

# Origin of the Zomi text by source. Anything not listed is "unknown": SZSF says so rather than guessing.
MACHINE_SOURCES = {"parallel_corpus"}
HUMAN_SOURCES = {"daily_use_phrases"}
HUMAN_PREFIXES = ("bible_",)


class ConversionError(Exception):
    """The input contradicts the review records; the run stops instead of writing a wrong master file."""


def origin_of(source: str) -> str:
    if source in MACHINE_SOURCES:
        return "machine_generated"
    if source in HUMAN_SOURCES or source.startswith(HUMAN_PREFIXES):
        return "human_written"
    return "unknown"


def corpus_decisions(db: Path, review_records: list[dict], min_reviewers: int) -> dict[str, corpus_reviews.Decision]:
    """Decision per corpus record id (`corpus-<row>`), found through each review's pair hash."""
    decisions = corpus_reviews.decide(review_records, min_reviewers)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        found = {}
        for pair_hash, decision in decisions.items():
            row = con.execute("SELECT id FROM parallel_sentences WHERE pair_hash = ?", (pair_hash,)).fetchone()
            if row is not None:
                found[f"corpus-{row[0]}"] = decision
        return found
    finally:
        con.close()


def review_block(record: dict, decision: corpus_reviews.Decision | None) -> dict[str, Any]:
    if decision is None:
        if record.get("human_reviewed"):
            raise ConversionError(f"{record['id']} is marked human-reviewed but has no saved review decision")
        return {"status": "UNREVIEWED", "reviewers": [], "approver": None}
    if record.get("human_reviewed") and decision.status != corpus_reviews.HUMAN_APPROVED:
        raise ConversionError(
            f"{record['id']} is marked human-reviewed but its decision is {decision.status}: "
            "export and reviews are from different runs"
        )
    return {"status": decision.status, "reviewers": list(decision.reviewers), "approver": decision.approver}


def to_szsf(
    record: dict, standard: zolai_standard.Standard, decision: corpus_reviews.Decision | None, own_models: set[str],
) -> dict[str, Any]:
    source = str(record["source"])
    origin = origin_of(source)
    review = review_block(record, decision)
    result = zolai_standard.standardize(record["zomi"], standard)
    out: dict[str, Any] = {
        "szsf_version": szsf.SZSF_VERSION,
        "id": record["id"],
        "kind": "translation_pair",
        "english": record["english"],
        "zomi": record["zomi"],
        "zomi_standard": result.text,
        "standard_version": standard.version,
        "source": source,
        "origin": origin,
        "tier": record["tier"],
        "split": "excluded" if review["status"] == "REJECTED" else record["split"],
        "review": review,
    }
    if result.rules:
        out["zomi_standard_rules"] = result.rules
    if result.flags:
        out["zomi_standard_flags"] = [f"{flag['rule']}:{flag['text']}" for flag in result.flags]
    if record.get("english_source"):
        out["english_source"] = record["english_source"]
    if origin == "machine_generated":
        model = str(record.get("model") or "unknown")
        out["model"] = model
        # Safe by default: a machine's Zomi counts as an outside provider's output unless it is our own model.
        out["provider_derived"] = model not in own_models
    if record.get("quality_score") is not None:
        out["quality_score"] = record["quality_score"]
    if record.get("quality_flags"):
        out["quality_flags"] = list(record["quality_flags"])
    reference = record.get("reference") or (f"corpus index {record['id'][7:]}" if str(record["id"]).startswith("corpus-") else None)
    if reference:
        out["reference"] = reference
    return out


def read_jsonl(paths: Iterable[Path]) -> Iterator[dict]:
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, start=1):
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as error:
                        raise ConversionError(f"{path.name} line {number}: not JSON ({error.msg})") from None


def convert(
    records: Iterable[dict], standard: zolai_standard.Standard, decisions: dict[str, corpus_reviews.Decision],
    own_models: set[str], standard_check: dict[str, Any] | None = None,
) -> Iterator[tuple[dict, list[str]]]:
    """(SZSF record, its problems) for every input record, in order."""
    for record in records:
        converted = to_szsf(record, standard, decisions.get(record["id"]), own_models)
        yield converted, szsf.check_record(converted, standard_check)


# Dictionary senses --------------------------------------------------------------------------------------------

# The database stores the source's display name; the rights file is keyed by the source's id.
SENSE_SOURCES = {"English–Zomi–Burmese Translation Master": "translation_master_50k"}


def stale_reviews(review_records: list[dict]) -> dict[str, dict[str, str]]:
    """sense id -> reviewer -> the fingerprint of the Zomi that reviewer saw (their latest record)."""
    shown: dict[str, dict[str, str]] = {}
    for record in review_records:
        if corpus_reviews.kind_of(record) == "review":
            shown.setdefault(record["sense_id"], {})[record["reviewer"]] = record["shown"]
    return shown


def sense_to_szsf(
    row: dict, standard: zolai_standard.Standard, decision: dictionary_reviews.Decision | None,
    shown: dict[str, str] | None, split: str,
) -> tuple[dict[str, Any], bool]:
    """(SZSF record, True when the sense's reviews were of different Zomi and so were not counted)."""
    sense_id, zomi, source = row["sense_id"], row["zomi"] or "", SENSE_SOURCES[row["source"]]
    stale = bool(decision and shown and any(d != dictionary_reviews.shown_digest(zomi) for d in shown.values()))
    if decision is None or stale:
        review = {"status": "UNREVIEWED", "reviewers": [], "approver": None}
    else:
        review = {"status": decision.status, "reviewers": list(decision.reviewers), "approver": decision.approver}
    result = zolai_standard.standardize(zomi, standard)
    out: dict[str, Any] = {
        "szsf_version": szsf.SZSF_VERSION,
        "id": sense_id,
        "kind": "dictionary_sense",
        "english": row["headword"],
        "zomi": zomi,
        "zomi_standard": result.text,
        "standard_version": standard.version,
        "source": source,
        "origin": origin_of(source),
        # Approved senses are silver like approved corpus pairs; nothing machine-made is gold.
        "tier": "silver" if review["status"] == "HUMAN_APPROVED" else "bronze",
        "split": "excluded" if review["status"] == "REJECTED" else split,
        "review": review,
        "reference": sense_id,
    }
    if result.rules:
        out["zomi_standard_rules"] = result.rules
    if result.flags:
        out["zomi_standard_flags"] = [f"{flag['rule']}:{flag['text']}" for flag in result.flags]
    return out, stale


def sense_rows(db: Path) -> Iterator[dict]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        for row_id, headword, zomi, source, reference, status in con.execute(
            "SELECT id, source_word, zomi, source, source_reference, verification_status "
            "FROM dictionary_entries ORDER BY id"
        ):
            yield {"row": row_id, "headword": headword, "zomi": zomi, "source": source, "sense_id": reference, "status": status}
    finally:
        con.close()


def convert_senses(
    rows: Iterable[dict], standard: zolai_standard.Standard, decisions: dict[str, dictionary_reviews.Decision],
    shown: dict[str, dict[str, str]], eval_keys: tuple[set[str], set[str]], standard_check: dict[str, Any],
    left_out: collections.Counter[str],
) -> Iterator[tuple[dict, list[str]]]:
    """(SZSF record, its problems) for each sense that can be converted; the others are counted in `left_out`."""
    from build_language_db import normalize_word, split_for_key, template_key  # type: ignore

    eval_english, eval_zomi = eval_keys
    for row in rows:
        if not isinstance(row["sense_id"], str) or not szsf.SENSE_ID.match(row["sense_id"]):
            left_out["no sense ID (not a ZD- or ZS- sense)"] += 1
        elif row["source"] not in SENSE_SOURCES:
            left_out["source not mapped to a rights key"] += 1
        elif row["status"] != "unreviewed":
            left_out["Zomi replaced by an approved correction (SZSF has no field for it yet)"] += 1
        elif (eval_english or eval_zomi) and (
            template_key(row["headword"], set()) in eval_english or normalize_word(row["zomi"] or "") in eval_zomi
        ):
            left_out["matches a human evaluation item"] += 1
        else:
            split = split_for_key(template_key(row["headword"], set()))
            converted, stale = sense_to_szsf(row, standard, decisions.get(row["sense_id"]), shown.get(row["sense_id"]), split)
            if stale:
                left_out["reviews of since-changed Zomi not counted (sense kept as UNREVIEWED)"] += 1
            yield converted, szsf.check_record(converted, standard_check)


def write_master(
    results: Iterable[tuple[dict, list[str]]], out: Path, rejects: Path | None,
) -> tuple[int, int, collections.Counter[str]]:
    """Write the valid records to `out` (named szsf-master-vX.jsonl); return (written, rejected, records per problem)."""
    written = rejected = 0
    problems: collections.Counter[str] = collections.Counter()
    reject_handle = rejects.open("w", encoding="utf-8") if rejects else None
    try:
        with out.open("w", encoding="utf-8") as handle:
            for converted, found in results:
                if found:
                    rejected += 1
                    problems.update(found)
                    if reject_handle:
                        reject_handle.write(json.dumps({"id": converted["id"], "problems": found}, ensure_ascii=False) + "\n")
                    continue
                handle.write(json.dumps(converted, ensure_ascii=False) + "\n")
                written += 1
    finally:
        if reject_handle:
            reject_handle.close()
    return written, rejected, problems


def add_common(command: argparse.ArgumentParser) -> None:
    command.add_argument("--out", type=Path, required=True, help="szsf-master-v<MAJOR.MINOR.PATCH>.jsonl (must not exist)")
    command.add_argument("--db", type=Path, help="language database")
    command.add_argument("--reviews", type=Path, help="saved review records")
    command.add_argument("--roster", type=Path, help="private reviewer roster; checks every reviewer and approver")
    command.add_argument("--min-reviewers", type=int, default=1)
    command.add_argument("--standard", type=Path, default=zolai_standard.DEFAULT_STANDARD)
    command.add_argument("--rights", type=Path, default=szsf.DEFAULT_RIGHTS)
    command.add_argument("--rejects", type=Path, help="write records that fail the format here, with their problems")


def publish(
    args: argparse.Namespace, make_results, rights: dict[str, dict], standard_check: dict[str, Any],
    roster: dict[str, str] | None,
) -> int:
    """Stage the master file, check the whole of it, then put it and its manifest in place (or write nothing)."""
    manifest_path = args.out.with_name(args.out.name.removesuffix(".jsonl") + ".manifest.json")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".szsf-convert-", dir=args.out.parent))
    try:
        staged = work / args.out.name
        try:
            written, rejected, problems = write_master(make_results(), staged, args.rejects)
        except ConversionError as error:
            print(f"Stopped: {error}", file=sys.stderr)
            return 1
        found = szsf.validate(staged, rights, standard=standard_check, roster=roster)
        if found:
            print("The converted file does not follow SZSF; nothing was written:\n  " + "\n  ".join(found[:20]), file=sys.stderr)
            return 1
        manifest = szsf.build_manifest(staged, rights)
        (work / manifest_path.name).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(staged, args.out)
        os.replace(work / manifest_path.name, manifest_path)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print(f"Wrote {written:,} records to {args.out} and its manifest.")
    if rejected:
        print(f"Left out {rejected:,} records that do not follow SZSF"
              + (f" (listed in {args.rejects})" if args.rejects else " (use --rejects to list them)") + "; records per problem:", file=sys.stderr)
        for problem, count in problems.most_common(10):
            print(f"  {count:,}  {problem}", file=sys.stderr)
    print("Nothing here clears a source: check rights with `szsf.py validate --purpose training` before training.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    pairs = commands.add_parser("pairs", help="convert translation pairs from the training export")
    pairs.add_argument("--input", type=Path, nargs="+", required=True, help="export files (train, validation, test .jsonl)")
    add_common(pairs)
    pairs.add_argument("--own-model", action="append", default=[], metavar="NAME",
                       help="a model Siamsil trained itself, so its output is not provider-derived (repeatable)")
    senses = commands.add_parser("senses", help="convert the dictionary's senses from the language database")
    add_common(senses)
    senses.add_argument("--eval", type=Path, nargs="*", help="human evaluation files to keep out (default: the private evaluation folder)")
    args = parser.parse_args(argv)

    if args.command == "pairs" and bool(args.reviews) != bool(args.db):
        parser.error("--reviews and --db go together: reviews are keyed by pair hash, the database maps it to a pair")
    if args.command == "senses" and not args.db:
        parser.error("--db is required: the senses are read from the language database")
    if not szsf.MASTER_NAME.match(args.out.name):
        parser.error("--out must be named like szsf-master-v1.0.0.jsonl")
    if args.out.exists():
        parser.error(f"{args.out} exists: a master file is never overwritten; make a new version")

    standard = zolai_standard.load(args.standard)
    standard_check = szsf.load_standard(args.standard)
    rights = szsf.load_rights(args.rights)
    roster = corpus_reviews.load_roster(args.roster) if args.roster else None

    if args.command == "pairs":
        decisions: dict[str, corpus_reviews.Decision] = {}
        if args.reviews:
            review_records = corpus_reviews.load(args.reviews)
            if roster is not None and (bad := corpus_reviews.roster_problems(review_records, roster)):
                print("The review records do not match the roster:\n  " + "\n  ".join(bad[:20]), file=sys.stderr)
                return 1
            decisions = corpus_decisions(args.db, review_records, args.min_reviewers)
        own_models = set(args.own_model)
        return publish(args, lambda: convert(read_jsonl(args.input), standard, decisions, own_models, standard_check),
                       rights, standard_check, roster)

    # senses
    from build_language_db import default_eval_paths, eval_match_keys, load_eval_items  # type: ignore

    sense_decisions: dict[str, dictionary_reviews.Decision] = {}
    shown: dict[str, dict[str, str]] = {}
    if args.reviews:
        review_records = dictionary_reviews.load(args.reviews)
        if roster is not None and (bad := corpus_reviews.roster_problems(review_records, roster)):
            print("The review records do not match the roster:\n  " + "\n  ".join(bad[:20]), file=sys.stderr)
            return 1
        sense_decisions = dictionary_reviews.decide(review_records, args.min_reviewers)
        shown = stale_reviews(review_records)
    eval_items = load_eval_items(args.eval if args.eval else default_eval_paths())
    eval_keys = eval_match_keys(eval_items, set())
    left_out: collections.Counter[str] = collections.Counter()
    code = publish(args, lambda: convert_senses(sense_rows(args.db), standard, sense_decisions, shown, eval_keys,
                                                standard_check, left_out), rights, standard_check, roster)
    if left_out:
        print("Not converted or not counted:", file=sys.stderr)
        for reason, count in left_out.most_common():
            print(f"  {count:,}  {reason}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
