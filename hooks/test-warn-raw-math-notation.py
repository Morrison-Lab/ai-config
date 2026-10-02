#!/usr/bin/env python3
"""Tests for warn-raw-math-notation.py and scripts/check-raw-math.py.

Run: python3 hooks/test-warn-raw-math-notation.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
HOOK = os.path.join(HERE, "warn-raw-math-notation.py")
LINT = os.path.join(os.path.dirname(HERE), "scripts", "check-raw-math.py")

FAILURES = []


def hook(tool, ti) -> str:
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(
        {"tool_name": tool, "tool_input": ti}), capture_output=True, text=True)
    return p.stdout


def check(cond, label):
    print(("ok   " if cond else "FAIL ") + label)
    if not cond:
        FAILURES.append(label)


# --- the hook warns on raw operators in math-bearing files -----------------
WARN = [
    ("Write", {"file_path": "paper.qmd", "content": "$$\\mathbb{E}[Y] = 1$$"}, "\\Ep"),
    ("Edit", {"file_path": "a.tex", "new_string": "\\operatorname{Var}(X)"}, "\\Var"),
    ("Write", {"file_path": "R/f.R", "content": "#' @return \\eqn{\\text{logit}(p)}"}, "\\logit"),
    ("Write", {"file_path": "notes.Rmd", "content": "$\\mathbb E[X]$"}, "\\Ep"),
    ("Edit", {"file_path": "s.qmd", "new_string": "$\\mathrm{Cov}(X, Y)$"}, "\\Cov"),
]
for tool, ti, macro in WARN:
    out = hook(tool, ti)
    check(macro in out and "additionalContext" in out, f"warns: {ti}")

# --- and stays quiet where it should ----------------------------------------
QUIET = [
    ("Write", {"file_path": "paper.qmd", "content": "$$\\Ep[Y] = \\Var{X}$$"}, "macros already used"),
    ("Write", {"file_path": "main.py", "content": "s = '\\\\mathbb{E}'"}, "not a math-bearing file type"),
    ("Write", {"file_path": "macros/macros.qmd", "content": "\\def\\Ep{\\mathbb{E}}"}, "the library itself"),
    ("Write", {"file_path": "x.qmd", "content": "\\def\\Ex{\\operatorname{E}}"}, "a definition line"),
    ("Write", {"file_path": "x.qmd", "content": "$\\mathbb{R}^n$"}, "an operator with no macro rule"),
    ("Write", {"file_path": "x.qmd", "content": "$\\operatorname{Exp}(x)$"}, "a longer name sharing a prefix"),
    ("Bash", {"command": "echo '\\mathbb{E}' > a.qmd"}, "not a file-write tool"),
]
for tool, ti, why in QUIET:
    check(hook(tool, ti) == "", f"quiet: {why}")

check(hook("Write", {"file_path": "x.qmd"}) == "", "quiet: no content")
p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
check(p.returncode == 0 and p.stdout == "", "fails open on bad input")

# --- the lint: exit codes and derived rules ---------------------------------
with tempfile.TemporaryDirectory() as d:
    dirty = os.path.join(d, "dirty.qmd")
    clean = os.path.join(d, "clean.qmd")
    macros = os.path.join(d, "macros.qmd")
    with open(dirty, "w") as f:
        f.write("ok line\n$\\mathbb{E}[Y]$ and $\\operatorname{sinc}(x)$\n")
    with open(clean, "w") as f:
        f.write("$\\Ep[Y]$\n")
    with open(macros, "w") as f:
        f.write("\\def\\sinc{\\operatorname{sinc}}\n")

    r = subprocess.run([sys.executable, LINT, clean], capture_output=True, text=True)
    check(r.returncode == 0, "lint exits 0 on a clean file")
    r = subprocess.run([sys.executable, LINT, dirty], capture_output=True, text=True)
    check(r.returncode == 1 and "dirty.qmd:2:" in r.stdout and "sinc" not in r.stdout,
          "lint exits 1 and reports file:line; no derived rule without --macros")
    r = subprocess.run([sys.executable, LINT, "--macros", macros, d],
                       capture_output=True, text=True)
    check(r.returncode == 1 and "\\sinc" in r.stdout and "macros.qmd:" not in r.stdout,
          "--macros derives a rule and skips the library file itself")
    r = subprocess.run([sys.executable, LINT, os.path.join(d, "missing.qmd")],
                       capture_output=True, text=True)
    check(r.returncode == 2, "lint exits 2 on a missing path")

print(f"\n{len(FAILURES)} failure(s)")
sys.exit(1 if FAILURES else 0)
