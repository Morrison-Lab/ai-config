"""Compatibility wrapper for plugins/ai-config/enforce-mwc-review-gate.py.

All implementation lives in hooks/enforce-mwc-review-gate.py. This file re-exports
all symbols for backwards compatibility with bootstrap.sh and test_enforce_mwc_review_gate.py.
"""
import os
import sys
import importlib.util

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
_HOOK_PATH = os.path.join(_ROOT, "hooks", "enforce-mwc-review-gate.py")

_spec = importlib.util.spec_from_file_location("enforce_mwc_review_gate_hook", _HOOK_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Re-export all symbols
globals().update({k: v for k, v in _mod.__dict__.items() if not k.startswith("__")})

if __name__ == "__main__":
    _mod.main()
