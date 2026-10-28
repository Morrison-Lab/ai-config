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

No other hook in this repo sets `permissionDecision: "allow"`;
this one exists to.
Its safety rests on two documented rules (https://code.claude.com/docs/en/hooks):

  - when several hooks decide, the precedence is "deny > defer > ask > allow",
    so `no-unauthorized-merge.py` still denies every merge it denies today;
  - "Deny and ask rules are still evaluated regardless of what the hook
    returns", so a settings deny or ask rule still applies.

The grant removes only the prompt that would follow once every guard has let
the call through.
It does not judge the merge's flags or target: `--repo other/repo` and
`--admin` get the allow too, and deciding whether that merge may run is left
to `no-unauthorized-merge.py` and the settings rules, as before.

## What it decides

  - `Skill` whose `skill` is exactly `mwc` or `ai-config:mwc` -> allow.
  - the cloud session's `add_repo` tool (`mcp__claude-code-remote__add_repo`,
    or the `Claude_Code_Remote` spelling) whose `owner` is one of
    `MEMBER_OWNERS` -> allow. The owner's standing rule (2026-10-28): any
    repo d-morrison is a member of may always be cloned into a session.
    A hook cannot test membership in one repository from a cloud session,
    whose GitHub API is scoped to the repos already attached, so the grant
    is by owner. The backend's own authorization check still refuses a
    repository the account cannot reach, and an owner outside the set gets
    no decision and goes to the classifier or prompt as before.
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
The cost is that a merge whose quoted subject or body contains one of those
characters, such as `--subject "Fix (x)"`, gets no decision and prompts as
before.

Run with `--dry-run '<payload json or bare command>'` to see the verdict.
"""
import json
import re
import shlex
import sys

GRANTED_SKILLS = frozenset({"mwc", "ai-config:mwc"})
ADD_REPO_TOOLS = frozenset({
    "mcp__claude-code-remote__add_repo",
    "mcp__Claude_Code_Remote__add_repo",
})
# GitHub owners whose repositories d-morrison is a member of, compared
# case-insensitively. Extend this set to widen the clone grant.
MEMBER_OWNERS = frozenset({"d-morrison", "morrison-lab", "ucd-serg"})
GRANTED_COMMANDS = (["gh", "pr", "merge"], ["glab", "mr", "merge"])
FORBIDDEN_CHARS = frozenset(";&|<>()$\\`\n\r")
ALLOWED_ASSIGNMENT = re.compile(r"ALLOW_MERGE=[A-Za-z0-9_.-]*")


def _read_payload():
    args = sys.argv[1:]
    dry = "--dry-run" in args
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
    if tool in ADD_REPO_TOOLS:
        owner = inp.get("owner")
        if isinstance(owner, str) and owner.strip().lower() in MEMBER_OWNERS:
            return (f"personal grant: add_repo for {owner.strip()}/..., "
                    "a member owner (repos d-morrison is a member of may always be cloned)")
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
