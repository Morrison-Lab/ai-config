#!/usr/bin/env python3
"""Tests for scripts/check-ambiguous-referents.py.

Delegates to the script's own --self-test, which carries the mutation
sweep: a known-bad sentence (the measured four-referent incident) must be
flagged, and raising the threshold above its own count must silence it
(confirming the threshold is load-bearing rather than an always-fire
check). Two negative controls -- a single clause-referring "which" and a
single pronoun -- must stay quiet, and a fenced code block must contribute
no referents.
"""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "check_ambiguous_referents",
    Path(__file__).parent / "check-ambiguous-referents.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

if __name__ == "__main__":
    raise SystemExit(mod.run_self_test())
