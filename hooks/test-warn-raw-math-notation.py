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
    ("Write", {"file_path": "a.md", "content": "`\\` real $\\mathbb{E}[Y]$ `x`"}, "\\Ep"),
    ("Write", {"file_path": "a.md", "content": "```\n- ```\nx\n```\n\nREAL $\\mathbb{E}[Y]$"}, "\\Ep"),
    ("Write", {"file_path": "a.qmd", "content": "$\\ell(\\theta)$"}, "\\llik"),
    ("Write", {"file_path": "a.qmd", "content": "the $\\ell_1$ penalty"}, "\\lpnorm"),
    ("Write", {"file_path": "a.qmd", "content": "$\\big( x \\big)$"}, "\\paren"),
    ("Write", {"file_path": "a.qmd", "content": "$\\left( x \\right)$"}, "\\paren"),
    ("Write", {"file_path": "a.qmd", "content": "$X^\\top y$"}, "\\tp"),
    ("Write", {"file_path": "a.qmd", "content": "$X^{\\top}$"}, "\\tp"),
    ("Write", {"file_path": "a.qmd", "content": "$\\mathcal{L}(\\theta)$"}, "concept macro"),
    ("Write", {"file_path": "a.qmd", "content": "$\\mathbb{R}^n$"}, "concept macro"),
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
    ("Write", {"file_path": "x.qmd", "content": "$\\operatorname{rank}(A)$"}, "an operator with no macro rule"),
    ("Write", {"file_path": "x.qmd", "content": "$\\operatorname{Exp}(x)$"}, "a longer name sharing a prefix"),
    ("Write", {"file_path": "x.qmd", "content": "$\\llik(\\theta)$"}, "the macro already used"),
    ("Write", {"file_path": "x.qmd", "content": "$\\ellipsis$"}, "a longer command sharing a prefix"),
    ("Write", {"file_path": "x.qmd", "content": "$\\bigcup_i A_i$"}, "a big operator, not delimiter sizing"),
    ("Write", {"file_path": "x.qmd", "content": "$x \\leftarrow y \\rightarrow z$"}, "arrows, not delimiter sizing"),
    ("Write", {"file_path": "x.qmd", "content": "$\\tp{X} \\dprod{a}{b}$"}, "the macros already used"),
    ("Write", {"file_path": "x.qmd", "content": "$\\mathbf{X}$"}, "bold is not flagged"),
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
    ("Write", {"file_path": "x.md", "content": "use \\``$\\mathbb{E}$` here"}, "a span after an escaped backtick"),
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

# --- the macros library is found through .gitmodules ------------------------
ESE_DEF = "\\def\\ESEt{\\operatorname{ESE}}\n"
ESE_RAW = "$\\mathrm{ESE}(x)$ and $\\mathbb{E}[Y]$"


def make_repo(d, url="https://github.com/Morrison-Lab/macros.git",
              sub="latex-macros", lib=ESE_DEF):
    os.makedirs(os.path.join(d, ".git"))
    with open(os.path.join(d, ".gitmodules"), "w", encoding="utf-8") as f:
        f.write(f'[submodule "{sub}"]\n\tpath = {sub}\n\turl = {url}\n')
    if lib is not None:
        os.makedirs(os.path.join(d, sub))
        with open(os.path.join(d, sub, "macros.qmd"), "wb") as f:
            f.write(lib if isinstance(lib, bytes) else lib.encode("utf-8"))
    return d


def git(*args, cwd):
    subprocess.run(["git", "-c", "protocol.file.allow=always", *args], cwd=cwd,
                   check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


with tempfile.TemporaryDirectory() as d:
    repo = make_repo(os.path.join(d, "lds"))
    target = os.path.join(repo, "chapters", "new.qmd")  # not yet on disk
    out = hook("Write", {"file_path": target, "content": ESE_RAW})
    check("\\ESEt" in out and "\\Ep" in out,
          "a latex-macros/ submodule's derived rule is used (\\mathrm{ESE} -> \\ESEt)")
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(
        {"tool_name": "Write", "cwd": repo,
         "tool_input": {"file_path": "chapters/new.qmd", "content": ESE_RAW}}),
        capture_output=True, text=True)
    check("\\ESEt" in p.stdout, "a relative file_path is resolved against the payload cwd")

    epi = make_repo(os.path.join(d, "epi"), url="https://github.com/d-morrison/macros",
                    sub="macros")
    out = hook("Write", {"file_path": os.path.join(epi, "a.qmd"), "content": ESE_RAW})
    check("\\ESEt" in out, "a macros/ submodule from d-morrison/macros is found too")

    other = make_repo(os.path.join(d, "other"), url="https://github.com/x/macros")
    out = hook("Write", {"file_path": os.path.join(other, "a.qmd"), "content": ESE_RAW})
    check("\\ESEt" not in out and "\\Ep" in out,
          "a submodule from another repository is not the library; built-ins apply")

    bare = os.path.join(d, "no-git")
    os.makedirs(bare)
    out = hook("Write", {"file_path": os.path.join(bare, "a.qmd"), "content": ESE_RAW})
    check("\\ESEt" not in out and "\\Ep" in out,
          "no git root or library: falls back to the built-in rules")

    unchecked = make_repo(os.path.join(d, "unchecked"), lib=None)
    out = hook("Write", {"file_path": os.path.join(unchecked, "a.qmd"), "content": ESE_RAW})
    check("\\ESEt" not in out and "\\Ep" in out,
          "a submodule not checked out and with no clone: built-in rules")

    undecodable = make_repo(os.path.join(d, "undecodable"), lib=b"\xff\xfe\\def\n")
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(
        {"tool_name": "Write", "tool_input": {
            "file_path": os.path.join(undecodable, "a.qmd"), "content": ESE_RAW}}),
        capture_output=True, text=True)
    check(p.returncode == 0 and "\\Ep" in p.stdout and "Traceback" not in p.stderr,
          "an undecodable library fails open to the built-in rules")

    if os.geteuid() != 0:  # root can read any file
        locked = make_repo(os.path.join(d, "locked"))
        lib = os.path.join(locked, "latex-macros", "macros.qmd")
        os.chmod(lib, 0)
        p = subprocess.run([sys.executable, HOOK], input=json.dumps(
            {"tool_name": "Write", "tool_input": {
                "file_path": os.path.join(locked, "a.qmd"), "content": ESE_RAW}}),
            capture_output=True, text=True)
        os.chmod(lib, 0o600)
        check(p.returncode == 0 and "\\Ep" in p.stdout and "\\ESEt" not in p.stdout
              and "Traceback" not in p.stderr,
              "an unreadable library fails open to the built-in rules")

    os.makedirs(os.path.join(repo, "chapters"))
    with open(target, "w", encoding="utf-8") as f:
        f.write(ESE_RAW + "\n")
    r = subprocess.run([sys.executable, LINT, "chapters"],
                       capture_output=True, text=True, cwd=repo)
    check(r.returncode == 1 and "\\ESEt" in r.stdout,
          "lint finds a latex-macros/ submodule through .gitmodules without --macros")

    # The library must stay inside the repo: no `..` path, no symlink out.
    outside = os.path.join(d, "outside")
    os.makedirs(outside)
    with open(os.path.join(outside, "macros.qmd"), "w", encoding="utf-8") as f:
        f.write(ESE_DEF)
    escape = make_repo(os.path.join(d, "escape"), sub="../outside", lib=None)
    out = hook("Write", {"file_path": os.path.join(escape, "a.qmd"), "content": ESE_RAW})
    check("\\ESEt" not in out and "\\Ep" in out,
          "a submodule path with `..` leading out of the repo is not read")
    linked = make_repo(os.path.join(d, "linked"), lib=None)
    os.makedirs(os.path.join(linked, "latex-macros"))
    os.symlink(os.path.join(outside, "macros.qmd"),
               os.path.join(linked, "latex-macros", "macros.qmd"))
    out = hook("Write", {"file_path": os.path.join(linked, "a.qmd"), "content": ESE_RAW})
    check("\\ESEt" not in out and "\\Ep" in out,
          "a macros.qmd symlinked out of the repo is not read")

    # A path reached through a symlinked directory finds the real repo.
    alias = os.path.join(d, "alias")
    os.symlink(os.path.join(repo, "chapters"), alias)
    out = hook("Write", {"file_path": os.path.join(alias, "x.qmd"), "content": ESE_RAW})
    check("\\ESEt" in out, "a symlinked directory is resolved before the walk up")

    # A deleted working directory fails open instead of crashing.
    gone = os.path.join(d, "gone")
    os.makedirs(gone)
    script = ("import os, subprocess, sys; os.chdir(sys.argv[1]); os.rmdir(sys.argv[1]); "
              "p = subprocess.run([sys.executable, sys.argv[2]], input=sys.argv[3], "
              "capture_output=True, text=True); "
              "print(p.returncode, 'Traceback' in p.stderr, '\\\\Ep' in p.stdout)")
    p = subprocess.run([sys.executable, "-c", script, gone, HOOK, json.dumps(
        {"tool_name": "Write", "tool_input": {"file_path": "a.qmd", "content": ESE_RAW}})],
        capture_output=True, text=True)
    check(p.stdout.split() == ["0", "False", "True"],
          "a deleted working directory fails open to the built-in rules")

    # A worktree leaves the submodule uninitialised: read it from the clone.
    lib_src = os.path.join(d, "macros-src")
    os.makedirs(lib_src)
    with open(os.path.join(lib_src, "macros.qmd"), "w", encoding="utf-8") as f:
        f.write(ESE_DEF)
    git("init", "-q", "-b", "main", cwd=lib_src)
    git("add", ".", cwd=lib_src)
    git("commit", "-qm", "lib", cwd=lib_src)
    sup = os.path.join(d, "sup")
    os.makedirs(sup)
    git("init", "-q", "-b", "main", cwd=sup)
    git("submodule", "add", "-q", lib_src, "latex-macros", cwd=sup)
    git("config", "-f", ".gitmodules", "submodule.latex-macros.url",
        "https://github.com/Morrison-Lab/macros.git", cwd=sup)
    git("commit", "-qam", "sub", cwd=sup)
    wt = os.path.join(d, "wt")
    git("worktree", "add", "-q", wt, cwd=sup)
    check(not os.path.exists(os.path.join(wt, "latex-macros", "macros.qmd")),
          "(setup) the worktree's submodule is not checked out")
    # Move the clone's HEAD past the pin, to a library without \ESEt.
    clone = os.path.join(sup, "latex-macros")
    with open(os.path.join(clone, "macros.qmd"), "w", encoding="utf-8") as f:
        f.write("\\def\\FOOt{\\operatorname{FOO}}\n")
    git("commit", "-qam", "moved", cwd=clone)
    raw = ESE_RAW + " $\\mathrm{FOO}$"
    out = hook("Write", {"file_path": os.path.join(wt, "ch", "a.qmd"), "content": raw})
    check("\\ESEt" in out and "\\FOOt" not in out,
          "an uninitialised submodule in a worktree is read from its clone at the pinned commit")
    git("-C", wt, "update-index", "--add", "--cacheinfo",
        "160000," + "1" * 40 + ",latex-macros", cwd=wt)
    git("-C", wt, "commit", "-qm", "unfetched pin", cwd=wt)
    out = hook("Write", {"file_path": os.path.join(wt, "ch", "a.qmd"), "content": raw})
    check("\\FOOt" in out and "\\ESEt" not in out,
          "a pin the clone never fetched falls back to the clone's HEAD")

    rel = make_repo(os.path.join(d, "rel"), url="../macros.git  # sibling")
    git("init", "-q", "-b", "main", cwd=rel)
    git("remote", "add", "origin", "git@github.com:Morrison-Lab/lds.git", cwd=rel)
    out = hook("Write", {"file_path": os.path.join(rel, "a.qmd"), "content": ESE_RAW})
    check("\\ESEt" in out,
          "a relative URL with a trailing comment resolves against the origin remote")
    git("remote", "set-url", "origin", "https://github.com/x/lds", cwd=rel)
    out = hook("Write", {"file_path": os.path.join(rel, "a.qmd"), "content": ESE_RAW})
    check("\\ESEt" not in out and "\\Ep" in out,
          "a relative URL under another owner is not the library")

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
