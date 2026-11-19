#!/usr/bin/env python3
"""SessionStart: apply Ezra's standing autoMode approvals on a local machine (ai-config#5853).

`scripts/wire-user-config.py` writes the standing approvals Ezra gave in his
own words (run cancels, #5623; claude/* branch pushes, #5682; verdict posts,
named change sets and cited user messages, #5752) into
`~/.claude/settings.json` `autoMode.allow`, the only place a local auto-mode
classifier reads them. Only `bootstrap.sh` called it, so a machine
bootstrapped before a rule merged never got it. Measured 2026-11-18: on
one lab machine `wire-user-config.py --check` reported the #5752 rules as `todo`, the
classifier denied the runner's cross-model verdict post on Morrison-Lab/gha#2115
as "Undermining Oversight", and Ezra had to type the approval by hand.
Ezra chose this hook on 2026-11-19 ("Sync now and add auto-sync hook").

WHAT IT DOES
------------
At session start on a local machine (not CLAUDE_CODE_REMOTE, which reads no
user settings), runs the three autoMode steps of wire-user-config.py in write
mode. Each is idempotent and only ever ADDS the exact rule text the script
carries, which is text Ezra approved; it removes nothing and widens nothing
beyond that text. When a step writes, it says so as additional context:
the classifier reads settings at session start, so the new rule takes effect
in the NEXT session, and the context says that too.

Silent when every rule is already present. Fails open, with a line on
stderr, when the script cannot be loaded or a step raises: a broken sync must
never block a session. Opt out with AI_CONFIG_NO_APPROVAL_SYNC=1.
"""
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.realpath(__file__))
_WIRE = os.path.join(os.path.dirname(_HERE), "scripts", "wire-user-config.py")
STEP_NAMES = ("wire_claude_run_cancel", "wire_claude_branch_push",
              "wire_claude_approval_scope")


def load_wire(path=_WIRE):
    """Import wire-user-config.py from *path*, or None with a stderr line."""
    try:
        spec = importlib.util.spec_from_file_location("_wire_user_config", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as exc:  # fail open: a sync bug must not block a session
        print(f"sync-auto-mode-approvals: cannot load {path} ({exc}); "
              "standing approvals not synced", file=sys.stderr)
        return None


def sync(wire):
    """Run each autoMode step in write mode; return the lines that wrote."""
    wrote = []
    for name in STEP_NAMES:
        step = getattr(wire, name, None)
        if step is None:
            print(f"sync-auto-mode-approvals: {name} is missing from "
                  "wire-user-config.py", file=sys.stderr)
            continue
        try:
            message, _ok = step(False)
        except Exception as exc:
            print(f"sync-auto-mode-approvals: {name} raised {exc}",
                  file=sys.stderr)
            continue
        if message.startswith("write"):
            wrote.append(message)
    return wrote


def main() -> int:
    if os.environ.get("CLAUDE_CODE_REMOTE") == "true":
        return 0
    if os.environ.get("AI_CONFIG_NO_APPROVAL_SYNC") == "1":
        return 0
    wire = load_wire()
    if wire is None:
        return 0
    wrote = sync(wire)
    if not wrote:
        return 0
    text = ("Synced Ezra's standing autoMode approvals into user settings "
            "(ai-config#5853): " + "; ".join(wrote) + ". The auto-mode "
            "classifier reads settings at session start, so these take effect "
            "in the next session; until then, a step they cover may still be "
            "denied here. Do not ask Ezra to type an approval for it: say it "
            "will pass after a restart.")
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": text}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
