#!/usr/bin/env python3
"""PreToolUse deny: a post excuses skipped work because a tool is missing or too old.

Ezra, 2026-11-24, quoting an mlg thread reply "LaTeX is too old for the exam
template": "cai: never make excuses like this; install the software you need".
The same rule, 2026-11-02: "cai: no excuses; always install what you need".
flag-tool-gap-handling.py warns on the final reply at Stop, after the excuse
has reached the user, and never sees a thread post or a forge comment; this
hook refuses the post itself.

DENIES a user-visible post, a forge comment, issue or PR body, or a
`gh issue|pr` --body/--title in Bash, where one sentence says work was skipped
(skipped, couldn't, can't, haven't rendered/tested/built ...) because a tool is
missing or too old (not installed, not available, the toolchain lacks it, too
old, an outdated version), unless the text also says the tool was installed.
The sentence matching is flag-tool-gap-handling.py's excuse(), so the two
hooks agree on every wording. A deny, not a reminder, because the failing shape
is lexical (ai-config#4741). ALLOW_TOOL_GAP_EXCUSE=1 overrides, for a quote of
someone else's words or a tool that truly cannot be installed after trying.
Fails open on parse trouble or a missing helper.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

OVERRIDE = "ALLOW_TOOL_GAP_EXCUSE"

REASON = (
    "[hook: no-tool-gap-excuse] \"{sentence}\" excuses skipped work because a tool is missing "
    "or too old. Ezra, 2026-11-24: \"never make excuses like this; install the software you "
    "need.\" Install or upgrade it (apt, pip, uv, install.packages, tinytex::install_tinytex(), "
    "tlmgr from a CTAN mirror, juliaup ...), run the work, and then report the result. If it "
    "truly cannot be installed, say every route you tried and set ALLOW_TOOL_GAP_EXCUSE=1. "
    "See shared/workflow/growth-mindset.md."
)


def load(name, alias):
    path = Path(__file__).resolve().parent / name
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def denial(payload):
    if os.environ.get(OVERRIDE) or not isinstance(payload, dict):
        return None
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    blob = load("no-notes-blob-link.py", "_ntge_blob_link")
    if tool == "Bash":
        text = blob.bash_text(str(tool_input.get("command") or ""))
    elif blob.TOOL.search(tool):
        text = "\n".join(blob.strings(tool_input))
    else:
        return None
    if not text.strip():
        return None
    gap = load("flag-tool-gap-handling.py", "_ntge_tool_gap")
    hit = gap.excuse(text)
    return REASON.format(sentence=hit[:200]) if hit else None


def main():
    try:
        payload = json.load(sys.stdin)
        reason = denial(payload)
    except Exception:
        return 0
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
