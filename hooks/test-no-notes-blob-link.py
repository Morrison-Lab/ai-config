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
    ("line anchor is a source view", f"{GH}/pds/blob/main/_subfiles/_def-x.qmd#L3", False),
    ("plain view is a source view", f"{GH}/pds/blob/main/_subfiles/_def-x.qmd?plain=1", False),
    ("code span quotes it", f"The URL `{GH}/lds/blob/main/{SUB}` is wrong.", False),
    ("fence quotes it", f"```\n{GH}/lds/blob/main/{SUB}\n```", False),
    ("markdown link", f"[Smarket]({GH}/lds/blob/main/{SUB})", True),
    ("pinned to a branch", f"{GH}/lds/blob/claude/fix-x/{SUB}", False),
    ("not qmd", f"{GH}/lds/blob/main/tools/check_site.py", False),
    ("qmd under tools", f"{GH}/lds/blob/main/tools/tests/fixture.qmd", False),
    ("outtake", f"{GH}/lds/blob/main/chapters/outtakes/_old.qmd", False),
    ("not a notes repo", f"{GH}/mlg/blob/main/Exams/mt1.qmd", False),
    ("not deployed yet", f"Changed in {GH}/lds/blob/main/{SUB}, not deployed yet.", False),
    ("source lines", f"The source lines {GH}/lds/blob/main/{SUB}#L4-L6 read", False),
    ("rendered link", "https://morrison-lab.github.io/lds/chapters/classification-lab.html#dat-smarket", False),
    ("exemption on another line", f"Not deployed yet.\n{GH}/lds/blob/main/{SUB}", True),
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
    check("PR title", denied(link, tool="mcp__github__create_pull_request", key="title"))
    check("other tool ignored", not denied(link, tool="Write", key="content"))
    check("path key ignored", not denied(link, tool="mcp__github__issue_write", key="path"))

    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, "lds")
        os.makedirs(os.path.join(root, "chapters/_subfiles/classification-lab"))
        for rel, body in ((SUB, "::: {#dat-smarket}\n"), ("chapters/classification-lab.qmd",
                          "{{< include _subfiles/classification-lab/_dat-smarket.qmd >}}\n")):
            with open(os.path.join(root, rel), "w", encoding="utf-8") as f:
                f.write(body)
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
