#!/usr/bin/env python3
"""SubagentStart: put the core rules in front of every dispatched subagent.

`inject-core-rules.py` runs at SessionStart and the reminders run at
UserPromptSubmit, and neither fires inside a subagent, so a dispatched agent
began with only its brief (ai-config#4698; Ezra, 2026-10-23: "why aren't the
subagents following our rules reliably?"). This hook reads
`shared/workflow/subagent-core-rules.md` and returns it as
SubagentStart `additionalContext`.

It only ADDS context and never blocks. Claude Code caps an injected hook
string at 10,000 characters, so a file over the cap is cut to it, with a
pointer to the full file. Fails OPEN and SILENT: any trouble prints nothing.
"""
import json
import sys
from pathlib import Path

CAP = 9_000
RULES = Path(__file__).resolve().parent.parent / "shared" / "workflow" / "subagent-core-rules.md"


def main() -> int:
    try:
        json.load(sys.stdin)
    except Exception:
        pass
    try:
        text = RULES.read_text(encoding="utf-8").strip()
    except Exception:
        return 0
    if not text:
        return 0
    if len(text) > CAP:
        text = text[:CAP] + f"\n\n[cut at {CAP} characters; full rules: {RULES}]"
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SubagentStart",
        "additionalContext": "# Lab rules for this subagent (ai-config)\n\n" + text,
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
