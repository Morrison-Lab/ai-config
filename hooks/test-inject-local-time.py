#!/usr/bin/env python3
"""Tests for hooks/inject-local-time.sh (ai-config#1080).

The hook prints the current Pacific time for the model to quote verbatim, and
must refuse to label a non-Pacific reading as local. Two cases:

  1. On a host with a TZ database (every CI runner, every macOS/Linux dev box)
     the output carries a real PDT/PST reading plus the verbatim-use line.
  2. When every rung of the ladder answers in a non-Pacific zone -- simulated
     by a `date` stub on PATH that always prints GMT and a `powershell` stub
     that fails -- the hook prints the UTC-only fallback and the explicit
     "do NOT state a PDT/PST time" warning, never a GMT value labelled local.

Case 2 is the negative control: without it, case 1 alone cannot tell a hook
that checks the zone from one that merely prints whatever `date` said
(ai-config#1918, the Git Bash GMT fallback).
"""
import os
import re
import stat
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "inject-local-time.sh")
LOCAL = re.compile(r"^Current time -- local: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} P[DS]T \| UTC: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", re.M)
VERBATIM = "Use the local value verbatim in recaps."
FALLBACK = re.compile(r"^Current time -- UTC: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z \(no Pacific reading available", re.M)
WARN = "Do NOT state a PDT/PST time in this turn without measuring it first."


def run(env):
    p = subprocess.run(["sh", HOOK], capture_output=True, text=True, env=env)
    return p.returncode, p.stdout


wrong = 0


def check(desc, cond):
    global wrong
    wrong += not cond
    print(f"  {'ok' if cond else 'WRONG':<6} {desc}")


print("with a TZ database:")
rc, out = run(dict(os.environ))
check("exit 0", rc == 0)
check("prints a Pacific local reading and the UTC reading", bool(LOCAL.search(out)))
check("prints the verbatim-use instruction", VERBATIM in out)
check("does not print the fallback warning", WARN not in out)

print("\nwith every rung answering GMT (negative control):")
with tempfile.TemporaryDirectory() as stubs:
    # A `date` that ignores TZ and the format string's zone: always GMT, the
    # Windows Git Bash shape from ai-config#1918. `-u` must still work so the
    # UTC line can be produced.
    date_stub = os.path.join(stubs, "date")
    with open(date_stub, "w") as fh:
        fh.write("#!/bin/sh\n"
                 "if [ \"$1\" = -u ]; then printf '2026-01-01T00:00:00Z\\n'; exit 0; fi\n"
                 "printf '2026-01-01 00:00:00 GMT\\n'\n")
    ps_stub = os.path.join(stubs, "powershell")
    with open(ps_stub, "w") as fh:
        fh.write("#!/bin/sh\nexit 1\n")
    for f in (date_stub, ps_stub):
        os.chmod(f, os.stat(f).st_mode | stat.S_IXUSR)
    env = dict(os.environ, PATH=stubs + os.pathsep + os.environ.get("PATH", ""))
    rc, out = run(env)
    check("exit 0 (a failed reading is reported, not a crash)", rc == 0)
    check("prints the UTC-only fallback line", bool(FALLBACK.search(out)))
    check("prints the do-NOT-state warning", WARN in out)
    check("never labels the GMT reading as local", "local:" not in out and "GMT" not in out)

total = 8
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
