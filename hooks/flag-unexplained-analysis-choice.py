#!/usr/bin/env python3
"""PreToolUse guard: an arbitrary analysis choice added to a page with no prose explaining it.

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
    makes a recognized analysis choice (a bin, a cutoff, a seed, a bandwidth,
    a train/test split)
    AND the same edit adds no prose line that explains a choice

An explaining line is one outside a code fence that contains a reason word
(`because`, `chose`, `choice`, `so that`, `compromise`, `rather than`, ...).

It warns and never blocks. Whether a sentence explains a choice cannot be
decided lexically, and a blocking guard on that judgment would be switched off.
The failing check for a pull request is the gha companion, which asks for prose
in the diff, not for proof that the prose is good.
"""
from __future__ import annotations

import json
import re
import sys

PAGE_SUFFIXES = (".qmd", ".Rmd", ".rmd")
EDIT_TOOLS = ("Write", "Edit", "MultiEdit", "write_to_file", "StrReplace")

# Calls and arguments that are an analysis choice rather than plumbing.
RX_CHOICE = re.compile(
    r"\bcut\s*\("
    r"|\bcut_(?:number|interval|width)\s*\("
    r"|\bpd\.(?:cut|qcut)\s*\("
    r"|\bnp\.histogram\s*\("
    r"|\b(?:breaks|bins|binwidth|nbins|n_bins)\s*=\s*"
    r"|\bset\.seed\s*\(|\brandom_state\s*=|\bnp\.random\.seed\s*\(|\bseed\s*="
    r"|\b(?:bw|bandwidth|span|df|degree|lambda|alpha|threshold|cutoff)\s*=\s*[-0-9.]"
    r"|\b(?:train_test_split|initial_split|sample_frac)\s*\("
    r"|\btest_size\s*=|\bprop\s*=\s*[0-9.]"
)

# A reason word in prose: the decision is being explained.
RX_REASON = re.compile(
    r"\b(?:because|chose|chosen|choice|choose|so that|compromise|rather than|"
    r"trade-?off|in order to|why|reason|arbitrary|alternative|we pick|picked|"
    r"fixed for reproducibility|reproducib\w+|steady|noisy|stable)\b",
    re.I,
)

NOTE = """This edit to {path} adds an analysis choice in code ({found}) \
and no prose explaining it.

Ezra's rule (ai-config#4905, 2026-11-03): every arbitrary analysis choice, \
such as a bin, a cutoff, a seed, a bandwidth or a train/test split, is \
explained in detail in the prose next to it. Say what was chosen, what the \
alternatives were, and why this one, with numbers from the data where they \
bear on it. If a choice has no good reason, remove it \
(the lds age bins were removed in favour of one point per age).

If the explanation already sits in the page outside this edit, name it in \
your reply and carry on. This is a reminder, not a refusal."""


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
        if line.lstrip().startswith(("#", "//")):
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
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(path=path, found=shown),
        },
        "systemMessage": (
            "Analysis choice without an explanation in the prose: "
            "say what was chosen, the alternatives and why."
        ),
    }
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
