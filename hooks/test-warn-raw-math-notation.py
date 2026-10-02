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
    ("Write", {"file_path": "a.tex", "content": "${\\rm E}[X]$"}, "\\Ep"),
    ("Write", {"file_path": "a.tex", "content": "\\mathop{\\rm Var}(X)"}, "\\Var"),
    ("Write", {"file_path": "a.qmd", "content": "$\\mathbb{E}\\left[Y\\right]$"}, "\\Ep"),
    ("Write", {"file_path": "a.tex", "content": "\\def\\Foo{1} $\\mathbb{E}[X]$"}, "\\Ep"),
    ("NotebookEdit", {"notebook_path": "n.ipynb", "new_source": "$\\operatorname{logit}(p)$"}, "\\logit"),
    ("Write", {"file_path": "a.qmd", "content": "$\\mathit{Var}(X)$"}, "\\Var"),
    ("Write", {"file_path": "a.md", "content": "````\n```\n````\n$\\mathbb{E}[Y]$"}, "\\Ep"),
    ("Write", {"file_path": "a.tex", "content": "\\def\\Foo{%\n1}\n$\\mathbb{E}[X]$"}, "\\Ep"),
    ("Write", {"file_path": "a.tex", "content": "\\def\\lb{\\{}\n$\\mathbb{E}[X]$"}, "\\Ep"),
    ("Write", {"file_path": "a.tex", "content": "\\newcommand{\\foo}{x\n$\\mathbb{E}[X]$"}, "\\Ep"),
    ("Write", {"file_path": "a.tex", "content": "\\def\\Ex\n\n$\\mathbb{E}[X]$"}, "\\Ep"),
    ("Write", {"file_path": "a.tex", "content": "Use \\newcommand to make macros: $\\mathbb{E}[X]$"}, "\\Ep"),
    ("Write", {"file_path": "a.tex", "content": "\\def\\a{1}\n[see] $\\mathrm{Var}(X)$"}, "\\Var"),
    ("Write", {"file_path": "a.md", "content": "```x``` text\n$\\mathbb{E}[Y]$"}, "\\Ep"),
    ("Write", {"file_path": "a.md", "content": "> ```\n> x\n$\\mathbb{E}[Y]$"}, "\\Ep"),
    ("Write", {"file_path": "a.md", "content": "- ```\n  code\n  ```\nREAL $\\mathbb{E}[Y]$"}, "\\Ep"),
    ("Write", {"file_path": "a.md", "content": "1. ```r\n   x <- 1\n   ```\n\nREAL $\\mathbb{E}[Y]$"}, "\\Ep"),
    ("Write", {"file_path": "a.md", "content": "```md\n> ```\n```\nREAL $\\mathbb{E}[Y]$"}, "\\Ep"),
    ("Write", {"file_path": "a.md", "content": "\\`$\\mathbb{E}[Y]$\\`"}, "\\Ep"),
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
    ("Write", {"file_path": "x.qmd", "content": "$\\mathbf{E}\\mathbf{x}$"}, "a bold matrix named E"),
    ("Write", {"file_path": "x.tex", "content": "$\\mathbf{P}$ and $\\mathsf{P}$"}, "a bold or sans-serif P"),
    ("Write", {"file_path": "x.qmd", "content": "the $\\text{E}$-value"}, "an E-value in text"),
    ("Write", {"file_path": "x.qmd", "content": "Never write `\\mathbb{E}`; use the macro."}, "an inline code span"),
    ("Write", {"file_path": "x.md", "content": "```\n$\\mathbb{E}[Y]$\n```"}, "a fenced code block"),
    ("Write", {"file_path": "x.tex", "content": "\\newcommand{\\Ex}[1]{\\mathbb{E}\\left[#1\\right]}"}, "a newcommand body"),
    ("Write", {"file_path": "x.tex", "content": "the \\textit{logit} link"}, "italic prose with textit"),
    ("Write", {"file_path": "x.tex", "content": "\\newcommand{\\Ex}{%\n\\mathbb{E}}"}, "a definition body on the next line"),
    ("Write", {"file_path": "x.md", "content": "````\n```\n$\\mathbb{E}[Y]$\n```\n````"}, "a nested fence"),
    ("Write", {"file_path": "x.md", "content": "~~~\n```\n$\\mathbb{E}[Y]$\n~~~"}, "a tilde fence holding a backtick line"),
    ("Write", {"file_path": "x.md", "content": "> ```\n> $\\mathbb{E}[Y]$\n> ```"}, "a fence inside a blockquote"),
    ("Write", {"file_path": "x.md", "content": "    ```\n$\\mathbb{E}[Y]$"}, "an indented fence line (treated as a fence)"),
    ("Write", {"file_path": "x.md", "content": "- ```\n  $\\mathbb{E}[Y]$\n  ```"}, "a fence inside a list item"),
    ("Write", {"file_path": "x.md", "content": "use ``$\\mathbb{E}$`` here"}, "a double-backtick code span"),
    ("Write", {"file_path": "x.tex", "content": "\\newcommand*{\\Ex}{\\mathbb{E}}"}, "a starred newcommand"),
    ("Write", {"file_path": "x.tex", "content": "\\DeclareMathOperator*{\\Vx}{\\mathrm{Var}}"}, "a starred DeclareMathOperator"),
    ("Write", {"file_path": "x.tex", "content": "\\newcommand{\\Ex}[1]{\\mathbb{E}\\{#1\\}}"}, "a definition with escaped braces"),
    ("Write", {"file_path": "x.tex", "content": "\\newcommand{\\Vx}[1][X]{\\operatorname{Var}(#1)}"}, "a definition with an optional default"),
    ("Write", {"file_path": "x.qmd", "content": "$\\mathit{E} + \\mathit{P}$"}, "a single italic letter"),
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
    with open(dirty, "w", encoding="utf-8") as f:
        f.write("ok line\n$\\mathbb{E}[Y]$ and $\\operatorname{sinc}(x)$\n")
    with open(clean, "w", encoding="utf-8") as f:
        f.write("$\\Ep[Y]$\n")
    with open(macros, "w", encoding="utf-8") as f:
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
    for sub in ("a/macros", "b/macros"):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
        with open(os.path.join(d, sub, "macros.qmd"), "w", encoding="utf-8") as f:
            f.write("\\def\\sinc{\\operatorname{sinc}}\n")
    r = subprocess.run([sys.executable, LINT, clean], capture_output=True, text=True, cwd=d)
    check(r.returncode == 2 and "--macros" in r.stderr,
          "lint stops when several macros libraries are found")
    nm = os.path.join(d, "node_modules", "pkg")
    os.makedirs(nm)
    with open(os.path.join(nm, "vendored.qmd"), "w", encoding="utf-8") as f:
        f.write("$\\mathbb{E}[Y]$\n")
    r = subprocess.run([sys.executable, LINT, "--macros", macros, d],
                       capture_output=True, text=True)
    check("vendored.qmd" not in r.stdout, "lint skips node_modules")
    bad = os.path.join(d, "bad-macros.qmd")
    with open(bad, "wb") as f:
        f.write(b"\xff\xfe\\def\n")
    r = subprocess.run([sys.executable, LINT, "--macros", bad, clean],
                       capture_output=True, text=True)
    check(r.returncode == 2 and "Traceback" not in r.stderr,
          "lint exits 2 on an undecodable --macros file")
    os.symlink(os.path.join(d, "nowhere"), os.path.join(d, "dangling.qmd"))
    r = subprocess.run([sys.executable, LINT, "--macros", macros, d],
                       capture_output=True, text=True)
    check(r.returncode == 1 and "dangling" not in r.stderr,
          "lint skips a dangling symlink")
    if os.geteuid() != 0:  # root can list any directory
        locked = os.path.join(d, "locked")
        os.makedirs(locked)
        os.chmod(locked, 0)
        r = subprocess.run([sys.executable, LINT, "--macros", macros, d],
                           capture_output=True, text=True)
        os.chmod(locked, 0o700)
        check(r.returncode == 2, "lint exits 2 on an unlistable directory")
    r = subprocess.run([sys.executable, LINT, os.path.join(d, "missing.qmd")],
                       capture_output=True, text=True)
    check(r.returncode == 2 and "no such file" in r.stderr,
          "lint exits 2 on a missing path and says why")

# --- definition masking is linear, not quadratic ---------------------------
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts", "lib"))
import time  # noqa: E402

from raw_math import find_raw  # noqa: E402

big = "\\def\\a{1}\n" * 100_000 + "$\\mathbb{E}[X]$\n"
t0 = time.monotonic()
hits = list(find_raw(big))
check(len(hits) == 1 and time.monotonic() - t0 < 5,
      "100,000 definitions scan in under 5 s and the trailing hit is found")

big = "\\newcommand{\\a}{ x\n" * 20_000 + "$\\mathbb{E}[X]$\n"
t0 = time.monotonic()
hits = list(find_raw(big))
check(len(hits) == 1 and time.monotonic() - t0 < 5,
      "20,000 unclosed definitions scan in under 5 s and the trailing hit is found")

big = "a " + "`" * 40_000 + " $\\mathbb{E}[X]$"
t0 = time.monotonic()
hits = list(find_raw(big, markdown=True))
check(len(hits) == 1 and time.monotonic() - t0 < 5,
      "a line with 40,000 unmatched backticks scans in under 5 s")

print(f"\n{len(FAILURES)} failure(s)")
sys.exit(1 if FAILURES else 0)
