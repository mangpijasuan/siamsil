"""The API's view of the rights register (docs/RIGHTS_POLICY.md).

Application code asks one question: may this source be used for this purpose? The register is
`data/rights.json`; the API finds it at SIAMSIL_RIGHTS_FILE, else in the data directory (the deploy bundle puts it
in /data/json), else in the repository. With no register found, every gated use is denied.

    from services import rights
    rights.allowed("bible_web", "retrieval")            -> bool
    rights.decision("parallel_corpus", "display")       -> rights_policy.Decision, with the reason
    rights.usable_ids("parallel_corpus", "display")     -> None (whole source) or the ids of cleared subsets

The register is re-read when the file changes, so a recorded decision applies without a restart.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

try:
    from services import rights_policy
except ModuleNotFoundError:  # scripts that put backend/services itself on sys.path
    import rights_policy  # type: ignore[no-redef]

from settings import PROJECT_ROOT, get_settings

log = logging.getLogger(__name__)
_lock = threading.Lock()
_cache: dict[str, object] = {"key": None, "sources": {}}


def register_path() -> Path | None:
    settings = get_settings()
    candidates = [settings.rights_file, settings.data_dir / "rights.json", PROJECT_ROOT / "data" / "rights.json"]
    for candidate in candidates:
        if candidate is not None and Path(candidate).is_file():
            return Path(candidate)
    return None


def sources() -> dict[str, dict]:
    """The register's sources; empty (deny everything) if it is missing or unreadable."""
    path = register_path()
    if path is None:
        return {}
    try:
        stat = path.stat()
        key = (str(path), stat.st_ino, stat.st_mtime_ns, stat.st_size)
    except OSError:
        return {}
    with _lock:
        if _cache["key"] != key:
            try:
                _cache["sources"] = json.loads(path.read_text(encoding="utf-8"))["sources"]
            except (OSError, ValueError, KeyError) as error:
                log.error("rights register %s unreadable, denying all gated uses: %s", path, error)
                _cache["sources"] = {}
            _cache["key"] = key
        return _cache["sources"]  # type: ignore[return-value]


def decision(source: str, use: str) -> rights_policy.Decision:
    return rights_policy.authorize(sources(), source, use)


def allowed(source: str, use: str) -> bool:
    return decision(source, use).allowed


def usable_ids(source: str, *uses: str) -> frozenset[str] | None:
    """None when the whole source is cleared for every use given; otherwise the ids of records in subsets cleared
    for all of them (empty when none are). A subset's `members_file` is read relative to the register's folder."""
    path = register_path()
    base = path.parent if path is not None else PROJECT_ROOT / "data"
    register = sources()
    result: frozenset[str] | None = None
    for use in uses or ("display",):
        ids = rights_policy.usable_ids(register, source, use, base)
        if ids is None:
            continue
        result = ids if result is None else result & ids
    return result
