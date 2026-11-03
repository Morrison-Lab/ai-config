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
    a Write, Edit or MultiEdit to a `.qmd` or `.Rmd` file adds a code line that
    bins a variable (`cut()`, `breaks =`, `bins =`, `binwidth =`)
    AND the same edit adds no prose line that explains a choice
    AND no added line carries `check-unexplained-choices: allow`

An explaining line is one outside a code fence that contains a reason word
(`because`, `chose`, `choice`, `so that`, `compromise`, `rather than`, ...).

It BLOCKS (Ezra, 2026-11-03: agents ignore a warning, so a rule becomes a
failing mechanism). To keep false positives low it recognizes binning only, not
seeds or splits, and it asks for the existence of a reason word, not for proof
that the explanation is good. The escape hatch is a line carrying
`check-unexplained-choices: allow`, the same marker the gha check honors.
"""
from __future__ import annotations

import json
import re
import sys

PAGE_SUFFIXES = (".qmd", ".Rmd", ".rmd")
EDIT_TOOLS = ("Write", "Edit", "MultiEdit", "write_to_file", "StrReplace")

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
    r"fixed for reproducibility|reproducib\w+|steady|noisy|stable)\b",
    re.I,
)

NOTE = """BLOCKED: this edit to {path} adds a binning choice in code ({found}) \
and no prose explaining it.

Ezra's rule (ai-config#4905, 2026-11-03): every arbitrary analysis choice, \
such as binning, is explained in detail in the prose next to it. Say what was \
chosen, what the alternatives were, and why this one, with numbers from the \
data where they bear on it, and put that prose in the same edit. If a choice \
has no good reason, remove it (the lds age bins became one point per age).

If the explanation already sits elsewhere in the page, or the call is not an \
analysis choice, add `<!-- check-unexplained-choices: allow -->` or a comment \
`# check-unexplained-choices: allow` on that code line and edit again."""


def added_text(tool: str, inp: dict) -> str:
    """The text an edit adds, or the empty string."""
    if tool in ("Write", "write_to_file"):
        return str(inp.get("content") or inp.get("file_text") or "")
    if tool == "MultiEdit":
        edits = inp.get("edits")
        edits = edits if isinstance(edits, list) else []
        return "\n".join(str(e.get("new_string", "")) for e in edits
                         if isinstance(e, dict))
    return str(inp.get("new_string") or inp.get("replacement") or "")


def split_code_and_prose(text: str) -> tuple[list[str], list[str]]:
    """Lines inside a fenced code block, and lines outside one."""
    code, prose, in_fence = [], [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        (code if in_fence else prose).append(line)
    return code, prose


def choices_without_reason(text: str) -> list[str]:
    """The choice patterns found in code when no prose explains one."""
    code, prose = split_code_and_prose(text)
    found = []
    for line in code:
        if line.lstrip().startswith(("#", "//")) or ALLOW_MARKER in line:
            continue
        m = RX_CHOICE.search(line)
        if m and m.group(0).strip() not in found:
            found.append(m.group(0).strip())
    if not found:
        return []
    if any(RX_REASON.search(line) for line in prose):
        return []
    return found


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
    found = choices_without_reason(added_text(tool, inp))
    if not found:
        return 0
    shown = ", ".join(f"`{f}`" for f in found[:4])
    reason = NOTE.format(path=path, found=shown)
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
