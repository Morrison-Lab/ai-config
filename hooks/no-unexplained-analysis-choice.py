#!/usr/bin/env python3
"""PreToolUse guard: a binning choice added to a page with no prose explaining it.

Ezra's rule (2026-11-03, ai-config#4905): every time an agent makes an arbitrary
analysis choice, such as binning a variable, it must explain the decision in
detail in the prose.

Measured on Morrison-Lab/lds `fig-logistic-regression`: age was cut into
three-year bins (a six-year last bin) with `cut(age, breaks = c(38, 41, ...))`
and neither the caption nor the surrounding text said why. Each age had 17 to
144 men per behavior pattern, so the binning was not forced by the data, and
the reader had no way to know that.

WHAT IT CHECKS
--------------
The hook rebuilds the page as it will read after the edit (the file on disk with
the edit applied, or the whole `Write` content) and looks at the lines the edit
adds, so a line added inside an existing chunk is seen as code even though the
edit carries no fence marker (the review finding on ai-config#4908).

    a Write, Edit or MultiEdit to a `.qmd` or `.Rmd` file adds a code line that
    bins a variable (`cut()`, `breaks =`, `bins =`, `binwidth =`)
    AND no prose line within 30 lines of it holds a reason word
    AND the added line does not carry `check-unexplained-choices: allow`

A reason word (`because`, `chose`, `choice`, `so that`, `compromise`,
`rather than`, ...) counts only in prose, outside a code fence.

It BLOCKS (Ezra, 2026-11-03: agents ignore a warning, so a rule becomes a
failing mechanism). To keep false positives low it recognizes binning only, not
seeds or splits, it looks only at added lines, and it asks for the existence of
a reason word, not for proof that the explanation is good. The escape hatch is a
line carrying `check-unexplained-choices: allow`, the same marker the gha check
honors.
"""
from __future__ import annotations

import collections
import json
import re
import sys

PAGE_SUFFIXES = (".qmd", ".Rmd", ".rmd")
EDIT_TOOLS = ("Write", "Edit", "MultiEdit", "write_to_file", "StrReplace",
              "replace_file_content")
WINDOW = 30

# Binning calls and arguments: the one analysis choice recognized.
RX_CHOICE = re.compile(
    r"\bcut\s*\("
    r"|\bcut_(?:number|interval|width)\s*\("
    r"|\bpd\.(?:cut|qcut)\s*\("
    r"|\b(?:breaks|bins|binwidth|nbins|n_bins)\s*="
)
ALLOW_MARKER = "check-unexplained-choices: allow"

# A reason word in prose: the decision is being explained.
RX_REASON = re.compile(
    r"\b(?:because|chose|chosen|choice|choose|so that|compromise|rather than|"
    r"trade-?off|in order to|why|reason|arbitrary|alternative|we pick|picked|"
    r"reproducib\w+)\b",
    re.I,
)

NOTE = """BLOCKED: this edit to {path} adds a binning choice in code ({found}) \
and no prose within {window} lines explaining it.

Ezra's rule (ai-config#4905, 2026-11-03): every arbitrary analysis choice, \
such as binning, is explained in detail in the prose next to it. Say what was \
chosen, what the alternatives were, and why this one, with numbers from the \
data where they bear on it, and put that prose in the same edit. If a choice \
has no good reason, remove it (the lds age bins became one point per age).

If the explanation already sits elsewhere in the page, or the call is not an \
analysis choice, put `# check-unexplained-choices: allow` on that code line \
and edit again."""


def read_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def apply_edits(tool: str, inp: dict, pre: str) -> str:
    """The page text as it will read once the edit lands."""
    if tool in ("Write", "write_to_file"):
        return str(inp.get("content") or inp.get("file_text") or "")
    edits = inp.get("edits") if tool == "MultiEdit" else [inp]
    edits = edits if isinstance(edits, list) else []
    post = pre
    for edit in edits:
        if not isinstance(edit, dict):
            continue
        old = str(edit.get("old_string") or edit.get("target") or "")
        new = str(edit.get("new_string") or edit.get("replacement") or "")
        if old and old in post:
            post = post.replace(old, new, 1)
        elif not pre:
            post = post + "\n" + new
    return post


def line_kinds(lines: list[str]) -> list[str]:
    """Label each line 'fence', 'code' or 'prose'."""
    kinds, in_fence = [], False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            kinds.append("fence")
        else:
            kinds.append("code" if in_fence else "prose")
    return kinds


def unexplained_choices(pre: str, post: str) -> list[str]:
    """Binning calls on lines the edit adds, with no reason word nearby."""
    seen = collections.Counter(pre.splitlines())
    lines = post.splitlines()
    kinds = line_kinds(lines)
    found: list[str] = []
    for i, line in enumerate(lines):
        if seen[line] > 0:
            seen[line] -= 1
            continue
        if kinds[i] != "code" or ALLOW_MARKER in line:
            continue
        if line.lstrip().startswith(("#", "//")):
            continue
        hit = RX_CHOICE.search(line)
        if not hit:
            continue
        lo, hi = max(0, i - WINDOW), min(len(lines), i + WINDOW + 1)
        near = (lines[j] for j in range(lo, hi) if kinds[j] == "prose")
        if any(RX_REASON.search(text) for text in near):
            continue
        name = hit.group(0).strip()
        if name not in found:
            found.append(name)
    return found


def choices_without_reason(text: str, pre: str = "") -> list[str]:
    """The unexplained binning in ``text``, as an edit to ``pre``."""
    return unexplained_choices(pre, text)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    tool = payload.get("tool_name")
    inp = payload.get("tool_input")
    inp = inp if isinstance(inp, dict) else {}
    path = str(inp.get("file_path") or inp.get("path") or "")
    if tool not in EDIT_TOOLS or not path.endswith(PAGE_SUFFIXES):
        return 0
    pre = read_file(path)
    found = unexplained_choices(pre, apply_edits(tool, inp, pre))
    if not found:
        return 0
    shown = ", ".join(f"`{f}`" for f in found[:4])
    reason = NOTE.format(path=path, found=shown, window=WINDOW)
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": reason,
        },
        "systemMessage": (
            "Blocked: binning with no explanation in the prose "
            "(say what was chosen, the alternatives and why)."
        ),
    }
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
