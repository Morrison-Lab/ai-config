"""Compatibility wrapper for plugins/ai-config/enforce-mwc-review-gate.py.

All implementation lives in hooks/enforce-mwc-review-gate.py. This file re-exports
all symbols for backwards compatibility with bootstrap.sh and test_enforce_mwc_review_gate.py.
"""
import os
import sys
import importlib.util

_DIR = os.path.dirname(os.path.realpath(__file__))
_candidate1 = os.path.join(_DIR, "hooks", "enforce-mwc-review-gate.py")
_candidate2 = os.path.join(os.path.dirname(os.path.dirname(_DIR)), "hooks", "enforce-mwc-review-gate.py")

if os.path.isfile(_candidate1):
    _HOOK_PATH = _candidate1
elif os.path.isfile(_candidate2):
    _HOOK_PATH = _candidate2
else:
    _HOOK_PATH = _candidate1

_spec = importlib.util.spec_from_file_location("enforce_mwc_review_gate_hook", _HOOK_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Re-export all symbols
globals().update({k: v for k, v in _mod.__dict__.items() if not k.startswith("__")})

if __name__ == "__main__":
    _mod.main()
