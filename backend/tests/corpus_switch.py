"""Tests that exercise corpus sentence matches turn the serving switch on.

`serve_parallel_corpus` defaults to false (the corpus is blocked in data/rights.json), so a test that needs
corpus matches opts in here. `get_settings` is cached, so the opt-in patches the engine module directly. The
switch is not enough on its own: the engine also asks the rights register (services/rights.py), so the opt-in
stands in a register decision that clears the whole corpus. test_rights_wiring.py tests the real gate.
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from settings import Settings  # type: ignore


def serve_corpus(case: unittest.TestCase, enabled: bool = True) -> None:
    configured = Settings(serve_parallel_corpus=enabled)
    for name in ("language_engine", "services.language_engine"):
        module = sys.modules.get(name)
        if module is not None:
            patcher = patch.object(module, "get_settings", return_value=configured)
            patcher.start()
            case.addCleanup(patcher.stop)
            cleared = patch.object(module.rights, "usable_ids", return_value=None if enabled else frozenset())
            cleared.start()
            case.addCleanup(cleared.stop)
