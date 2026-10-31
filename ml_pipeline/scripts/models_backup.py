#!/usr/bin/env python3
"""Back up trained models to the private Hugging Face repository, check the backup, or restore it.

  python3 ml_pipeline/scripts/models_backup.py manifest           # checksums of models/<folders> -> models/BACKUP_MANIFEST.sha256
  python3 ml_pipeline/scripts/models_backup.py upload             # upload the folders, the manifest and README
  python3 ml_pipeline/scripts/models_backup.py verify             # compare the backup with the manifest (no download)
  python3 ml_pipeline/scripts/models_backup.py restore            # download into models/ and check every file

The repository is ZomiDatasets/siamsil-models (the Siamsil organization), private; --repo overrides it.
Uploading refuses a public repository, and verify fails if the repository is public. Needs huggingface_hub and a
token that can write to the organization (huggingface.co/settings/tokens; `hf auth login`).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "models"
REPO = "ZomiDatasets/siamsil-models"
FOLDERS = ("nllb-zomi-bible-v1", "nllb-zomi-bible-v1-serving",
           "nllb-zomi-everyday-v2-exp", "nllb-zomi-everyday-v2-exp-serving")
MANIFEST = "BACKUP_MANIFEST.sha256"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_lines(models: Path, folders: tuple[str, ...]) -> list[str]:
    lines = []
    for folder in folders:
        for path in sorted((models / folder).rglob("*")):
            if path.is_file() and path.name != ".DS_Store":
                lines.append(f"{sha256(path)}  {path.relative_to(models).as_posix()}")
    return lines


def read_manifest(models: Path) -> list[tuple[str, str]]:
    return [tuple(line.split(maxsplit=1)) for line in (models / MANIFEST).read_text().splitlines() if line.strip()]


def api():
    from huggingface_hub import HfApi

    return HfApi()


def cmd_manifest(args) -> int:
    lines = manifest_lines(args.models, args.folders)
    (args.models / MANIFEST).write_text("\n".join(lines) + "\n")
    print(f"wrote {len(lines)} checksums to {args.models / MANIFEST}")
    return 0


def cmd_upload(args) -> int:
    hub = api()
    hub.create_repo(args.repo, repo_type="model", private=True, exist_ok=True)
    if not hub.repo_info(args.repo).private:
        sys.exit(f"{args.repo} is public; make it private before uploading")
    readme = args.models / "HF_README.md"
    if readme.exists():
        hub.upload_file(path_or_fileobj=str(readme), path_in_repo="README.md", repo_id=args.repo)
    hub.upload_file(path_or_fileobj=str(args.models / MANIFEST), path_in_repo=MANIFEST, repo_id=args.repo)
    for folder in args.folders:
        print(f"== {folder}")
        hub.upload_folder(folder_path=str(args.models / folder), path_in_repo=folder, repo_id=args.repo,
                          ignore_patterns=[".DS_Store"], commit_message=f"Back up {folder}")
    print(f"done: {args.repo} (private)")
    return 0


def cmd_verify(args) -> int:
    info = api().repo_info(args.repo, files_metadata=True)
    remote = {item.rfilename: item for item in info.siblings}
    problems = []
    for digest, name in read_manifest(args.models):
        item = remote.get(name)
        if item is None:
            problems.append(f"missing on Hugging Face: {name}")
        elif item.lfs is not None and item.lfs.sha256 != digest:
            problems.append(f"different: {name}")
        elif item.lfs is None:
            local = args.models / name
            data = local.read_bytes() if local.exists() else b""
            if not data or hashlib.sha256(data).hexdigest() != digest or \
                    item.blob_id != hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest():
                problems.append(f"different (or not present locally to compare): {name}")
    if not info.private:
        problems.append("the repository is PUBLIC")
    print(f"{args.repo}: private={info.private}; checked {len(read_manifest(args.models))} files")
    print("\n".join(problems) if problems else "ALL MATCH")
    return 1 if problems else 0


def cmd_restore(args) -> int:
    from huggingface_hub import snapshot_download

    args.models.mkdir(parents=True, exist_ok=True)
    snapshot_download(args.repo, local_dir=str(args.models), allow_patterns=[f"{f}/*" for f in args.folders] + [MANIFEST])
    bad = [name for digest, name in read_manifest(args.models)
           if not (args.models / name).exists() or sha256(args.models / name) != digest]
    print("\n".join(f"different or missing: {name}" for name in bad) if bad else "restored; every file matches")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=REPO)
    parser.add_argument("--models", type=Path, default=MODELS)
    parser.add_argument("--folder", dest="folders", action="append",
                        help="a model folder under models/; repeatable (default: the four backed-up folders)")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("manifest", "upload", "verify", "restore"):
        commands.add_parser(name)
    args = parser.parse_args(argv)
    args.folders = tuple(args.folders or FOLDERS)
    handlers = {"manifest": cmd_manifest, "upload": cmd_upload, "verify": cmd_verify, "restore": cmd_restore}
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
