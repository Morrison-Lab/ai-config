#!/usr/bin/env python3
"""Tests for hooks/warn-example-without-figure.py (ai-config#4851 follow-up).

Run: python3 hooks/test-warn-example-without-figure.py [hooks/warn-example-without-figure.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "warn-example-without-figure.py")

PAGE = "/home/user/lds/chapters/_subfiles/logistic/_exm_odds.qmd"
BARE = "::: {#exm-odds}\nThe odds are 3 to 1.\n:::\n"


def run(payload, raw=None):
    p = subprocess.run([sys.executable, HOOK], input=raw if raw is not None else json.dumps(payload),
                       capture_output=True, text=True, timeout=20)
    assert p.returncode == 0, p.stderr
    if not p.stdout.strip():
        return False
    note = json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "no-figure" in note and "#exm-" in note, note
    return True


def write(path, content):
    return {"tool_name": "Write", "tool_input": {"file_path": path, "content": content}}


def edit(path, old, new):
    return {"tool_name": "Edit", "tool_input": {"file_path": path, "old_string": old, "new_string": new}}


CASES = [
    ("write adds bare example", write(PAGE, BARE), True),
    ("edit adds bare example", edit(PAGE, "x", BARE), True),
    ("image in div", write(PAGE, "::: {#exm-a}\ntext\n![alt](a.png)\n:::\n"), False),
    ("fig label", write(PAGE, "::: {#exm-a}\n```{r}\n#| label: fig-a\n```\n:::\n"), False),
    ("fig reference", write(PAGE, "::: {#exm-a}\nSee @fig-a.\n:::\n"), False),
    ("fig subfile include", write(PAGE, "::: {#exm-a}\n{{< include _fig-odds.qmd >}}\n:::\n"), False),
    ("no-figure comment", write(PAGE, "::: {#exm-a}\n<!-- no-figure: one number -->\n:::\n"), False),
    ("figured example does not silence a bare one after it",
     write(PAGE, "::: {#exm-a}\n![alt](a.png)\n:::\n\n" + BARE), True),
    ("figured example does not silence a bare one before it",
     write(PAGE, BARE + "\n::: {#exm-b}\n![alt](b.png)\n:::\n"), True),
    ("two figured examples", write(
        PAGE, "::: {#exm-a}\n![alt](a.png)\n:::\n\n::: {#exm-b}\n<!-- no-figure: one number -->\n:::\n"), False),
    ("edit keeps the example count", edit(PAGE, BARE, BARE + "more\n"), False),
    ("no example div", write(PAGE, "::: {#def-a}\ntext\n:::\n"), False),
    ("not a qmd file", write("/home/user/lds/README.md", BARE), False),
    ("not a notes repo", write("/home/user/other/chapters/a.qmd", BARE), False),
    ("outtakes are skipped", write("/home/user/lds/chapters/outtakes/_a.qmd", BARE), False),
    ("other tool ignored", {"tool_name": "Bash", "tool_input": {"command": "echo"}}, False),
]


def main():
    failed = 0
    for name, payload, want in CASES:
        got = run(payload)
        ok = got == want
        failed += not ok
        print(("PASS" if ok else "FAIL") + ": " + name)
    # Negative control: the hook must fail open on garbage input.
    ok = run(None, raw="not json") is False
    failed += not ok
    print(("PASS" if ok else "FAIL") + ": malformed input fails open")
    print(f"{len(CASES) + 1 - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
