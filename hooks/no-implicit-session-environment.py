#!/usr/bin/env python3
"""PreToolUse guard: a new cloud session names its environment explicitly.

ai-config#4819. `create_session` without `environment_id` gives the new
session the CALLER's environment, and nothing reports the substitution.
A coordinator's environment is chosen for coordinating, not for the target
repository's toolchain. Measured 2026-10-28: a coordinator started five lds
work sessions this way. They landed in "Default" instead of the account's
"R with ai-config" environment, which a sibling lds session was already
using. Block A then could not install Julia, so it could not render the
chapter locally, which lds's CLAUDE.md requires before every commit.

## What it decides

For a `create_session` call:

  - `environment_id` present and non-empty -> silent.
  - `environment_id` absent or empty -> DENY, naming the remedy: call
    `list_environments`, read the `environment_id` of a session already
    working on the same repository, and pass the one built for it. When the
    caller's own environment really is the right one, passing its id
    explicitly is the whole cost.

Denying rather than warning is deliberate: the remedy is one parameter, and
a warning arrives after the call has already created the session in the
wrong environment, which cannot be changed afterwards.

Run with `--dry-run '<payload json>'` to see the verdict without acting.
"""
import json
import sys

TOOL_SUFFIX = "create_session"

REASON = (
    "create_session was called without `environment_id`, so the new session "
    "would inherit THIS session's environment rather than the one built for "
    "its repository, and a session's environment cannot be changed later "
    "(ai-config#4819). Call `list_environments`, check the `environment_id` "
    "of any existing session on the same repository (`get_session`), and "
    "pass the matching id explicitly -- even when it is this session's own."
)


def _read_payload():
    if len(sys.argv) == 3 and sys.argv[1] == "--dry-run":
        return json.loads(sys.argv[2]), True
    try:
        return json.load(sys.stdin), False
    except (json.JSONDecodeError, ValueError):
        return None, False


def decide(payload):
    tool = str(payload.get("tool_name") or "")
    if not tool.endswith(TOOL_SUFFIX):
        return None, ""
    tool_input = payload.get("tool_input") or {}
    if str(tool_input.get("environment_id") or "").strip():
        return None, ""
    return "deny", REASON


def main():
    payload, dry = _read_payload()
    if not payload:
        return 0
    decision, text = decide(payload)
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
    if decision == "deny":
        out["hookSpecificOutput"]["permissionDecision"] = "deny"
        out["hookSpecificOutput"]["permissionDecisionReason"] = text
        print(json.dumps(out))
        return 0
    if dry:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
