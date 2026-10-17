"""Split a canonical CSV into independently readable, compressed private parts.

Uses csv.reader/writer rather than splitting lines, so quoted newlines cannot
corrupt records. Each part repeats the header and can be ingested on its own.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package(source: Path, output: Path, rows_per_part: int) -> dict:
    if rows_per_part < 1:
        raise ValueError("rows_per_part must be positive")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.glob("zomi_english_sentences.part-*.csv.gz")):
        raise FileExistsError("Remove or move existing parts before repackaging")

    parts: list[dict] = []
    total = 0
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        expected = {"index", "en", "zomi"}
        if not expected.issubset(header):
            raise ValueError(f"Expected CSV columns {sorted(expected)}")
        target = None
        writer = None
        try:
            for row in reader:
                if len(row) != len(header):
                    raise ValueError(f"Malformed CSV record at row {total + 1}")
                if total % rows_per_part == 0:
                    if target is not None:
                        target.close()
                    path = output / f"zomi_english_sentences.part-{len(parts) + 1:04d}.csv.gz"
                    target = gzip.open(path, "wt", encoding="utf-8", newline="")
                    writer = csv.writer(target)
                    writer.writerow(header)
                    parts.append({"file": path.name, "rows": 0})
                assert writer is not None
                writer.writerow(row)
                parts[-1]["rows"] += 1
                total += 1
        finally:
            if target is not None:
                target.close()

    for part in parts:
        path = output / part["file"]
        part["bytes"] = path.stat().st_size
        if part["bytes"] >= 100_000_000:
            raise ValueError(f"{path.name} exceeds the 100 MB limit")
        part["sha256"] = sha256(path)
    manifest = {
        "source": str(source),
        "source_sha256": sha256(source),
        "format": "gzip-compressed UTF-8 CSV; each part includes the header",
        "total_rows": total,
        "parts": parts,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rows-per-part", type=int, default=200_000)
    args = parser.parse_args()
    result = package(args.source, args.output, args.rows_per_part)
    print(f"Packaged {result['total_rows']:,} rows in {len(result['parts'])} parts")
