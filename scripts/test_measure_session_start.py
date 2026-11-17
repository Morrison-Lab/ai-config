#!/usr/bin/env python3
"""Tests for scripts/measure-session-start.py."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
from pathlib import Path

PATH = Path(__file__).with_name("measure-session-start.py")
spec = importlib.util.spec_from_file_location("measure_session_start", PATH)
mss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mss)

fails = []


def run(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = mss.main(argv)
    return code, buf.getvalue()


# Every session kind names only components that exist.
for kind, names in mss.SESSION_KINDS.items():
    missing = [n for n in names if n not in mss.COMPONENTS]
    if missing:
        fails.append(f"{kind}: unknown components {missing}")

# Every component measures to a positive size: a zero means a hook printed
# nothing or a file moved, and the report would then understate the load.
for name, spec_ in mss.COMPONENTS.items():
    size = spec_[0]()
    if size <= 0:
        fails.append(f"{name}: measured {size}")

# Report-only by default, whatever the sizes are.
code, out = run([])
if code != 0:
    fails.append(f"default run exited {code}")
if "component(s) measured" not in out:
    fails.append("default run printed no summary")
# A kind mixing bytes and characters must say so in its total.
if "Codex: " not in out or "bytes and chars at start" not in out.split("Codex: ")[1].splitlines()[0]:
    fails.append("Codex total does not name both of its units")

# Negative control: with no headroom allowed, --strict must fail.
saved = mss.TARGET_FRACTION
mss.TARGET_FRACTION = 0.0
code, out = run(["--strict"])
mss.TARGET_FRACTION = saved
if code != 1 or "over target" not in out:
    fails.append(f"--strict with a zero target exited {code}")

# And with the target at twice the cap, --strict passes.
mss.TARGET_FRACTION = 2.0
code, _ = run(["--strict"])
mss.TARGET_FRACTION = saved
if code != 0:
    fails.append(f"--strict with a 200% target exited {code}")

for f in fails:
    print("FAIL:", f)
print("ok" if not fails else f"{len(fails)} failed")
sys.exit(1 if fails else 0)
