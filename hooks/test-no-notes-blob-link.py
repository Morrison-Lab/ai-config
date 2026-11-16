#!/usr/bin/env python3
"""Tests for hooks/no-notes-blob-link.py (ai-config#5705).

Run: python3 hooks/test-no-notes-blob-link.py
"""
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
spec = importlib.util.spec_from_file_location("hook", os.path.join(HERE, "no-notes-blob-link.py"))
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

POST = "mcp__hearthbot__post_message"
GH = "https://github.com/Morrison-Lab"
SUB = "chapters/_subfiles/classification-lab/_dat-smarket.qmd"

# (name, text, should_deny)
CASES = [
    ("subfile on main", f"See [Smarket]({GH}/lds/blob/main/{SUB}).", True),
    ("page on main", f"See {GH}/psw/blob/main/chapters/conciseness.qmd.", True),
    ("lowercase owner", f"https://github.com/morrison-lab/mds/blob/main/algebra.qmd", True),
    ("line anchor still content", f"{GH}/pds/blob/main/_subfiles/_def-x.qmd#L3", True),
    ("pinned to a branch", f"{GH}/lds/blob/claude/fix-x/{SUB}", False),
    ("pinned to a sha", f"{GH}/lds/blob/5ee8d52/{SUB}", False),
    ("not qmd", f"{GH}/lds/blob/main/tools/check_site.py", False),
    ("qmd under tools", f"{GH}/lds/blob/main/tools/tests/fixture.qmd", False),
    ("outtake", f"{GH}/lds/blob/main/chapters/outtakes/_old.qmd", False),
    ("not a notes repo", f"{GH}/mlg/blob/main/Exams/mt1.qmd", False),
    ("not deployed yet", f"Changed in {GH}/lds/blob/main/{SUB}, not deployed yet.", False),
    ("source lines", f"The source lines {GH}/lds/blob/main/{SUB}#L4-L6 read", False),
    ("rendered link", "https://morrison-lab.github.io/lds/chapters/classification-lab.html#dat-smarket", False),
    ("exemption on another line", f"Not deployed yet.\n{GH}/lds/blob/main/{SUB}", True),
    ("empty", "", False),
]


def denied(text, tool=POST, key="text"):
    os.environ.pop(hook.OVERRIDE, None)
    return hook.denial({"tool_name": tool, "tool_input": {key: text}}) is not None


def main() -> int:
    wrong = 0

    def check(name, ok):
        nonlocal wrong
        wrong += not ok
        print(f"  {'ok  ' if ok else 'FAIL'}   {name}")

    for name, text, want in CASES:
        check(name, denied(text) == want)
    link = f"{GH}/lds/blob/main/{SUB}"
    check("github comment body", denied(link, tool="mcp__github__add_issue_comment", key="body"))
    check("gh pr comment in Bash", denied(f"gh pr comment 5 --body '{link}'", tool="Bash", key="command"))
    check("other Bash ignored", not denied(f"curl {link}", tool="Bash", key="command"))
    check("other tool ignored", not denied(link, tool="Write", key="content"))
    check("path key ignored", not denied(link, tool="mcp__github__issue_write", key="path"))

    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, "lds")
        os.makedirs(os.path.join(root, "chapters/_subfiles/classification-lab"))
        with open(os.path.join(root, SUB), "w", encoding="utf-8") as f:
            f.write("::: {#dat-smarket}\nText.\n:::\n")
        with open(os.path.join(root, "chapters/classification-lab.qmd"), "w", encoding="utf-8") as f:
            f.write("{{< include _subfiles/classification-lab/_dat-smarket.qmd >}}\n")
        os.environ["CLAUDE_PROJECT_DIR"] = root
        reason = hook.denial({"tool_name": POST, "tool_input": {"text": link}}) or ""
        check("suggests page plus anchor",
              "https://morrison-lab.github.io/lds/chapters/classification-lab.html#dat-smarket" in reason)
        os.environ.pop("CLAUDE_PROJECT_DIR")
    reason = hook.denial({"tool_name": POST, "tool_input": {
        "text": f"{GH}/psw/blob/main/chapters/conciseness.qmd"}}) or ""
    check("page maps to html", "morrison-lab.github.io/psw/chapters/conciseness.html" in reason)

    os.environ[hook.OVERRIDE] = "1"
    check("override allows", hook.denial({"tool_name": POST, "tool_input": {"text": link}}) is None)
    os.environ.pop(hook.OVERRIDE)
    check("malformed payload fails open", hook.denial("not a dict") is None)
    print(f"\n{'all passed' if not wrong else 'FAILED'}: {wrong} wrong")
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
