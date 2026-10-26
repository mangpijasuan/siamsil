#!/usr/bin/env python3
"""Import reference dictionaries from the private siamsil-data repository, unchanged and unreviewed.

  python3 ml_pipeline/scripts/import_reference_dictionaries.py --data-repo siamsil-data
  python3 ml_pipeline/scripts/import_reference_dictionaries.py --data-repo siamsil-data --dry-run

Reads (never modifies), as listed in data/reference_dictionaries.json:
  <data-repo>/Zomi AI Roadmap/English_Zomi_Burmese_Translation_Master_v1.0.1.json
  <data-repo>/Zomi AI Roadmap/Essential_3000_English_Zomi_Learners_Dictionary.json

Each file must match the SHA-256 pinned in that config; otherwise nothing is written.
data/raw/ is not read or written.

Writes:
  data/processed/reference/reference_dictionaries.sqlite
  data/processed/reference/manifest.json

Every sense is stored with review_status 'unreviewed'. Usage tiers and review notices
from the source are kept as information and flags; they are not approvals. Text is
imported as written. Nothing is corrected, translated, or generated. Rights are read
from data/rights.json and recorded per source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_VERSION = "1.0.0"

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_REPO = ROOT / "siamsil-data"
DEFAULT_CONFIG = ROOT / "data" / "reference_dictionaries.json"
DEFAULT_RIGHTS = ROOT / "data" / "rights.json"
DEFAULT_OUT_DB = ROOT / "data" / "processed" / "reference" / "reference_dictionaries.sqlite"
DEFAULT_MANIFEST = ROOT / "data" / "processed" / "reference" / "manifest.json"

REVIEW_STATUS = "unreviewed"
NOTICE_RE = re.compile(r"\[([^\]]+)\]")
# The Essential 3000 marks text that needs native confirmation with this tag.
NATIVE_CONFIRMATION_TAG = "[sittel-ding]"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def text(value) -> str | None:
    if value is None:
        return None
    cleaned = unicodedata.normalize("NFC", str(value)).strip()
    return cleaned or None


def normalize_word(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def notice_flags(notice: str | None) -> list[str]:
    """'[Native/editorial review required] [Translation conflict]' -> ['native_editorial_review_required', 'translation_conflict']"""
    flags = []
    for tag in NOTICE_RE.findall(notice or ""):
        slug = re.sub(r"[^a-z0-9]+", "_", tag.casefold()).strip("_")
        if slug.startswith("working_reference"):
            slug = "working_reference"
        flags.append(slug)
    return flags


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_translation_master(data: dict, source_id: str) -> tuple[list, list, list]:
    entries, senses = [], []
    for index, entry in enumerate(data["entries"], start=1):
        entry_id = f"{source_id}:{index:06d}"
        headword = text(entry.get("headword")) or ""
        entries.append((entry_id, source_id, index, headword, normalize_word(headword),
                        text(entry.get("part_of_speech")), None))
        for sense in entry.get("senses") or []:
            number = int(sense["sense_number"])
            notice = text(sense.get("review_notice"))
            flags = notice_flags(notice)
            senses.append((f"{entry_id}:{number}", entry_id, number, None, text(sense.get("definition_en")),
                           text(sense.get("zomi")), text(sense.get("burmese")), None, None, None,
                           text(sense.get("usage_tier")), notice, json.dumps(flags), REVIEW_STATUS))
    return entries, senses, []


def parse_learners_dictionary(data: dict, source_id: str) -> tuple[list, list, list]:
    entries, senses, examples = [], [], []
    for entry in data["entries"]:
        index = int(entry["id"])
        entry_id = f"{source_id}:{index:06d}"
        headword = text(entry.get("headword")) or ""
        entries.append((entry_id, source_id, index, headword, normalize_word(headword),
                        text(entry.get("part_of_speech")), text(entry.get("ipa"))))
        for sense in entry.get("senses") or []:
            number = int(sense["number"])
            sense_id = f"{entry_id}:{number}"
            fields = {key: text(sense.get(key)) for key in
                      ("heading", "definition_en", "zomi_equivalents", "explanation_zomi", "usage_en", "usage_zomi")}
            pairs = [("phrase", p) for p in sense.get("common_phrases") or []]
            pairs += [("example", e) for e in sense.get("examples") or []]
            zomi_texts = [fields["zomi_equivalents"], fields["explanation_zomi"], fields["usage_zomi"]]
            zomi_texts += [text(p.get("zomi")) for _, p in pairs]
            flags = ["native_confirmation_required"] if any(
                NATIVE_CONFIRMATION_TAG in (z or "") for z in zomi_texts) else []
            senses.append((sense_id, entry_id, number, fields["heading"], fields["definition_en"],
                           fields["zomi_equivalents"], None, fields["explanation_zomi"], fields["usage_en"],
                           fields["usage_zomi"], None, None, json.dumps(flags), REVIEW_STATUS))
            for position, (kind, pair) in enumerate(pairs, start=1):
                examples.append((f"{sense_id}:{position}", sense_id, kind, position,
                                 text(pair.get("english")), text(pair.get("zomi"))))
    return entries, senses, examples


PARSERS = {"translation_master": parse_translation_master, "learners_dictionary": parse_learners_dictionary}

SCHEMA = """
CREATE TABLE sources (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    version TEXT NOT NULL,
    file TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    rights_source TEXT NOT NULL,
    display_rights TEXT NOT NULL,
    train_rights TEXT NOT NULL,
    entries INTEGER NOT NULL,
    senses INTEGER NOT NULL,
    examples INTEGER NOT NULL
);

CREATE TABLE entries (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(id),
    source_index INTEGER NOT NULL,
    headword TEXT NOT NULL,
    normalized_headword TEXT NOT NULL,
    part_of_speech TEXT,
    ipa TEXT
);
CREATE INDEX idx_entries_headword ON entries(normalized_headword);

CREATE TABLE senses (
    id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES entries(id),
    sense_number INTEGER NOT NULL,
    heading TEXT,
    definition_en TEXT,
    zomi TEXT,
    burmese TEXT,
    explanation_zomi TEXT,
    usage_en TEXT,
    usage_zomi TEXT,
    usage_tier TEXT,
    review_notice TEXT,
    flags TEXT NOT NULL,
    review_status TEXT NOT NULL
);
CREATE INDEX idx_senses_entry ON senses(entry_id);
CREATE INDEX idx_senses_status ON senses(review_status);

CREATE TABLE examples (
    id TEXT PRIMARY KEY,
    sense_id TEXT NOT NULL REFERENCES senses(id),
    kind TEXT NOT NULL,
    position INTEGER NOT NULL,
    english TEXT,
    zomi TEXT
);
CREATE INDEX idx_examples_sense ON examples(sense_id);

CREATE VIRTUAL TABLE senses_fts USING fts5(
    sense_id UNINDEXED,
    headword,
    definition_en,
    zomi,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


def import_source(source_id: str, spec: dict, data_repo: Path) -> dict:
    path = data_repo / spec["path"]
    if not path.exists():
        raise SystemExit(f"Missing {path}")
    actual = sha256(path)
    if actual != spec["sha256"]:
        raise SystemExit(f"Checksum mismatch for {path}\n  expected {spec['sha256']}\n  found    {actual}\n"
                         "The original changed. Record the new file in siamsil-data's README and "
                         "data/reference_dictionaries.json before importing it.")
    if spec["format"] not in PARSERS:
        raise SystemExit(f"Unknown format {spec['format']!r} for {source_id}")
    entries, senses, examples = PARSERS[spec["format"]](load_json(path), source_id)
    flags = Counter(flag for sense in senses for flag in json.loads(sense[12]))
    tiers = Counter(sense[10] for sense in senses if sense[10])
    return {"id": source_id, "spec": spec, "path": path, "sha256": actual, "entries": entries,
            "senses": senses, "examples": examples, "flags": dict(flags.most_common()), "tiers": dict(sorted(tiers.items()))}


def write_db(path: Path, sources: list[dict], rights: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".sqlite.tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)
    for source in sources:
        right = rights.get(source["id"], {})
        con.execute("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            source["id"], source["spec"]["title"], source["spec"]["version"], source["spec"]["path"],
            source["sha256"], source["id"], right.get("display", "needs_review"), right.get("train", "needs_review"),
            len(source["entries"]), len(source["senses"]), len(source["examples"])))
        con.executemany("INSERT INTO entries VALUES (?,?,?,?,?,?,?)", source["entries"])
        con.executemany("INSERT INTO senses VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", source["senses"])
        con.executemany("INSERT INTO examples VALUES (?,?,?,?,?,?)", source["examples"])
        headwords = {entry[0]: entry[3] for entry in source["entries"]}
        con.executemany("INSERT INTO senses_fts VALUES (?,?,?,?)",
                        [(s[0], headwords[s[1]], s[4] or "", s[5] or "") for s in source["senses"]])
    con.commit()
    con.close()
    tmp.replace(path)


def display_path(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-repo", type=Path, default=DEFAULT_DATA_REPO, help="clone of the private siamsil-data")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--rights", type=Path, default=DEFAULT_RIGHTS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DB)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--dry-run", action="store_true", help="verify and report; write nothing")
    args = parser.parse_args(argv)

    config = load_json(args.config)["sources"]
    rights = load_json(args.rights).get("sources", {}) if args.rights.exists() else {}
    sources = [import_source(source_id, spec, args.data_repo) for source_id, spec in config.items()]

    report = []
    for source in sources:
        right = rights.get(source["id"], {})
        row = {
            "id": source["id"],
            "file": source["spec"]["path"],
            "sha256": source["sha256"],
            "entries": len(source["entries"]),
            "senses": len(source["senses"]),
            "examples": len(source["examples"]),
            "review_status": {REVIEW_STATUS: len(source["senses"])},
            "usage_tiers": source["tiers"],
            "flags": source["flags"],
            "display_rights": right.get("display", "needs_review"),
            "train_rights": right.get("train", "needs_review"),
            "rights_recorded": source["id"] in rights,
        }
        report.append(row)
        print(f"{row['id']:<24} {row['entries']:>6} entries {row['senses']:>6} senses {row['examples']:>6} examples  "
              f"all {REVIEW_STATUS}  display={row['display_rights']} train={row['train_rights']}")
    missing = [row["id"] for row in report if not row["rights_recorded"]]
    if missing:
        print(f"warning: no entry in {args.rights.name} for {', '.join(missing)}; recorded as needs_review",
              file=sys.stderr)
    if args.dry_run:
        return 0

    write_db(args.out, sources, rights)
    manifest = {
        "script": "import_reference_dictionaries.py",
        "script_version": SCRIPT_VERSION,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "database": display_path(args.out),
        "database_sha256": sha256(args.out),
        "config_sha256": sha256(args.config),
        "sources": report,
        "note": "Unreviewed reference data. Not human-approved; not cleared for training.",
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {display_path(args.out)} and {display_path(args.manifest)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
