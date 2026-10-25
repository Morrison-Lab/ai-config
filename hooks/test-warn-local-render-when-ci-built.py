#!/usr/bin/env python3
"""Tests for hooks/warn-local-render-when-ci-built.py (ai-config#4724).

Run: python3 hooks/test-warn-local-render-when-ci-built.py [hooks/warn-local-render-when-ci-built.py]
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "warn-local-render-when-ci-built.py")

# (name, tool, command, repo kind, should_warn)
CASES = [
    ("render in gh-pages repo", "Bash", "quarto render chapters/a.qmd --to pdf", "pages", True),
    ("bare render", "Bash", "quarto render", "pages", True),
    ("render after cd", "Bash", "cd x && quarto render --to html", "pages", True),
    ("render in plain repo", "Bash", "quarto render chapters/a.qmd", "plain", False),
    ("quarto preview", "Bash", "quarto preview", "pages", False),
    ("quarto check", "Bash", "quarto check", "pages", False),
    ("word merely containing quarto", "Bash", "echo notquarto render", "pages", False),
    ("other tool", "Edit", "quarto render", "pages", False),
    ("cwd missing", "Bash", "quarto render", "missing", False),
]


def make_repo(kind, root):
    path = os.path.join(root, kind)
    if kind == "missing":
        return os.path.join(root, "does-not-exist")
    os.makedirs(path)
    git = ["git", "-C", path, "-c", "user.email=t@example.com", "-c", "user.name=t"]
    subprocess.run(git + ["init", "-q", "-b", "main"], check=True)
    subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "x"], check=True)
    if kind == "pages":
        subprocess.run(git + ["branch", "gh-pages"], check=True)
    return path


def run(tool, command, cwd):
    payload = {"tool_name": tool, "tool_input": {"command": command}, "cwd": cwd}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True)
    return p.returncode, p.stdout


def main():
    fails = 0
    with tempfile.TemporaryDirectory() as root:
        repos = {k: make_repo(k, root) for k in ("pages", "plain", "missing")}
        for name, tool, command, kind, warn in CASES:
            rc, out = run(tool, command, repos[kind])
            warned = "additionalContext" in out and "deny" not in out
            ok = rc == 0 and warned == warn
            print(("  ok      " if ok else "  FAIL    ") + name)
            fails += 0 if ok else 1
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
    ok = p.returncode == 0 and not p.stdout
    print(("  ok      " if ok else "  FAIL    ") + "fails open on garbage stdin")
    fails += 0 if ok else 1
    total = len(CASES) + 1
    print(f"\n{total - fails}/{total} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
