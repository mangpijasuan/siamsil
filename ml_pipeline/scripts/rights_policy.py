#!/usr/bin/env python3
"""Command line and import path for the rights policy (docs/RIGHTS_POLICY.md).

The implementation lives in backend/services/rights_policy.py so the API and the build scripts share one checker;
this file keeps `python3 ml_pipeline/scripts/rights_policy.py ...` and `import rights_policy` working.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_IMPL = Path(__file__).resolve().parents[2] / "backend" / "services" / "rights_policy.py"
_spec = importlib.util.spec_from_file_location("siamsil_rights_policy", _IMPL)
_module = importlib.util.module_from_spec(_spec)
sys.modules["siamsil_rights_policy"] = _module  # dataclasses resolve their module by name
_spec.loader.exec_module(_module)

if __name__ == "__main__":
    _module.main()
else:
    sys.modules[__name__] = _module
