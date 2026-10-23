#!/usr/bin/env python3
"""PreToolUse grant: carry the owner's personal permission rules to every machine.

ai-config#4374. The owner runs `Skill(mwc)`, `gh pr merge`, and
`glab mr merge` without a permission prompt. Those allow rules lived in one
machine's `~/.claude/settings.json`, which nothing syncs, and neither synced
surface can carry them:

  - a plugin's `settings.json` applies only the `agent` and
    `subagentStatusLine` keys, so a `permissions` block shipped there is
    ignored (https://code.claude.com/docs/en/plugins-reference);
  - a project's `.claude/settings.json` reaches every collaborator too,
    handing them prompt-free merges as well.

A plugin hook reaches every machine with the plugin enabled, and a
`PreToolUse` hook may return `permissionDecision: "allow"`, which skips the
prompt as an allow rule does.

## Why this does not loosen the merge guard

Other hooks in this repo never emit `allow`; this one exists to. Its safety
rests on two documented rules (https://code.claude.com/docs/en/hooks):

  - when several hooks decide, the precedence is "deny > defer > ask > allow",
    so `no-unauthorized-merge.py` still denies every merge it denies today;
  - "Deny and ask rules are still evaluated regardless of what the hook
    returns", so a settings deny or ask rule still applies.

The grant removes only the prompt that would follow once every guard has let
the call through.

## What it decides

  - `Skill` whose `skill` is exactly `mwc` or `ai-config:mwc` -> allow.
  - `Bash` whose command is one `gh pr merge ...` or `glab mr merge ...`
    invocation -> allow. The command must contain none of
    ``; & | < > ( ) $ \\ ` `` or a newline or carriage return, must parse with
    `shlex.split`, and may be preceded only by `ALLOW_MERGE=<value>`
    assignments (the documented merge-guard override).
  - anything else, unreadable stdin included -> no output (normal flow).

The Bash test is narrower than a settings prefix rule on purpose. The
built-in matcher checks each `&&`/`;`/`|` segment separately, but a hook
`allow` covers the whole command string, so a chained command would carry
its other segments through on the merge's grant. Rejecting every operator,
substitution, and escape character -- quoted or not -- keeps the allowed set
to exactly one merge invocation.

Run with `--dry-run '<payload json or bare command>'` to see the verdict.
"""
import json
import re
import shlex
import sys

GRANTED_SKILLS = frozenset({"mwc", "ai-config:mwc"})
GRANTED_COMMANDS = (["gh", "pr", "merge"], ["glab", "mr", "merge"])
FORBIDDEN_CHARS = frozenset(";&|<>()$\\`\n\r")
ALLOWED_ASSIGNMENT = re.compile(r"ALLOW_MERGE=[A-Za-z0-9_.-]*")


def _read_payload():
    args = sys.argv[1:]
    dry = "--dry-run" in args or "--simulate" in args
    if dry:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw = positional[0].strip()
            if raw.startswith("{"):
                try:
                    return json.loads(raw), True
                except Exception:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw}}, True
    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), dry
    except Exception:
        return {}, dry


def granted_command(command):
    """The granted command (e.g. `gh pr merge`) that `command` is, or None."""
    if not isinstance(command, str) or FORBIDDEN_CHARS & set(command):
        return None
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    while argv and ALLOWED_ASSIGNMENT.fullmatch(argv[0]):
        argv = argv[1:]
    if argv[:3] in GRANTED_COMMANDS:
        return " ".join(argv[:3])
    return None


def decide(payload):
    """The `permissionDecisionReason` to allow with, or None for no decision."""
    tool = payload.get("tool_name") or ""
    inp = payload.get("tool_input")
    if not isinstance(inp, dict):
        return None
    if tool == "Skill":
        skill = inp.get("skill")
        if isinstance(skill, str) and skill in GRANTED_SKILLS:
            return f"ai-config#4374 personal grant: Skill({skill})"
        return None
    if tool == "Bash":
        name = granted_command(inp.get("command"))
        if name:
            return (f"ai-config#4374 personal grant: Bash({name}); "
                    "merge guards and settings deny/ask rules still apply")
    return None


def main():
    payload, dry = _read_payload()
    reason = decide(payload) if payload else None
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
    if reason:
        out["hookSpecificOutput"]["permissionDecision"] = "allow"
        out["hookSpecificOutput"]["permissionDecisionReason"] = reason
        print(json.dumps(out))
    elif dry:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
