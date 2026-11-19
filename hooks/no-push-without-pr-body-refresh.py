#!/usr/bin/env python3
"""Stop hook: a turn that pushes must refresh the PR's title and body after it.

THE GAP THIS FILLS (ai-config#5871)
-----------------------------------
On 2026-11-19 agy returned NOT CLEAN on lds#2879 because the PR body named
only two of the three memory entries in its diff: a later push added the
third, and the body was never updated.
ardi.md's round checklist already asks for every touched PR description to be
re-read, but that rule is consulted when a round starts and broken at push
time, so this hook fires at the end of the turn that pushed.

WHAT IT CHECKS
--------------
In the current turn (the records after the last real user prompt), if the
last PUSH (`git push`, or the MCP `push_files`, `create_or_update_file` and
`delete_file` tools) has no later PR-body WRITE (`update_pull_request` with a
title or body, `create_pull_request`, `gh pr edit` with `--title`, `--body`
or `--body-file`, `gh pr create`, or a `gh api` PATCH on `pulls/N`), the stop
is blocked once with the rule.

Why it blocks once instead of refusing: whether the body already covers the
whole diff is a judgment the transcript cannot settle (a push that answers a
review nit often leaves the body accurate), so the reply may say the body
still covers the diff and stop.
Blocks at most once per turn (agent_notice.stop_notice) and fails open on any
parse trouble.
"""
import json
import os
import re
import sys

_LIB = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "scripts", "lib")
if os.path.isdir(_LIB):
    sys.path.insert(0, os.path.realpath(_LIB))
from agent_notice import stop_notice  # noqa: E402
from shellcmd import git_subcommand, simple_commands, strip_env  # noqa: E402

PUSH_TOOLS = ("push_files", "create_or_update_file", "delete_file")
BODY_FLAGS = ("--title", "--body", "--body-file", "-t", "-b", "-F")
RX_PULL_PATH = re.compile(r"(?:^|/)pulls/\d+$")


def blocks(record):
    content = (record.get("message") or {}).get("content")
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


def is_real_prompt(record):
    if record.get("type") != "user" or record.get("isMeta"):
        return False
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return bool(content.strip())
    return any(b.get("type") == "text" for b in blocks(record))


def is_patch_on_pull(args):
    """True for `gh api` args that PATCH a `pulls/N` endpoint."""
    method = None
    for i, arg in enumerate(args):
        if arg in ("-X", "--method") and i + 1 < len(args):
            method = args[i + 1]
        elif arg.startswith(("-X", "--method=")):
            method = arg.split("=", 1)[-1] if "=" in arg else arg[2:]
    return (method or "").upper() == "PATCH" and any(RX_PULL_PATH.search(a) for a in args)


def classify_argv(argv):
    """Return 'push', 'body' or None for one simple command (dequoted argv)."""
    git = git_subcommand(argv)
    if git is not None:
        return "push" if git[0] == "push" else None
    _env, rest = strip_env(argv)
    if len(rest) < 2 or rest[0] != "gh":
        return None
    if rest[1:3] == ["pr", "create"]:
        return "body"
    if rest[1:3] == ["pr", "edit"]:
        flags = [a.split("=", 1)[0] for a in rest[3:]]
        return "body" if any(f in BODY_FLAGS for f in flags) else None
    if rest[1] == "api" and is_patch_on_pull(rest[2:]):
        return "body"
    return None


def classify(block):
    """Return the ordered 'push'/'body' events for one tool_use block.

    A Bash command is split into simple commands first, so text inside a
    quoted argument (a body or commit message that mentions `git push`) is
    never read as a command, and a chained `git push && gh pr edit --body`
    yields both events in order.
    """
    name = str(block.get("name", ""))
    inputs = block.get("input") or {}
    if name.endswith(PUSH_TOOLS):
        return ["push"]
    if name.endswith("create_pull_request"):
        return ["body"]
    if name.endswith("update_pull_request"):
        return ["body"] if (inputs.get("body") or inputs.get("title")) else []
    if name != "Bash":
        return []
    commands = simple_commands(str(inputs.get("command", ""))) or []
    return [kind for kind in map(classify_argv, commands) if kind]


def unrefreshed_push(path):
    events = []
    with open(path, encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if is_real_prompt(record):
                events = []
                continue
            for block in blocks(record):
                if block.get("type") == "tool_use":
                    events.extend(classify(block))
    last_push = max((i for i, kind in enumerate(events) if kind == "push"), default=None)
    return last_push is not None and "body" not in events[last_push + 1:]


def main():
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path")
        if not path or not os.path.exists(path) or not unrefreshed_push(path):
            return 0
    except (OSError, ValueError):
        return 0
    print(stop_notice(
        payload,
        "This turn pushed and did not update a PR title or body afterwards. "
        "After a push to an open PR, update its title and body in the same turn so they "
        "cover the whole diff: re-read the diff against the body, and list every file, "
        "entry or change it now holds (ai-config#5871; lds#2879 drew a NOT CLEAN review "
        "because its body named two of three entries). If the body already covers the "
        "whole diff, or the push opened no PR yet, say so in one line and stop.",
        "no-push-without-pr-body-refresh"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
