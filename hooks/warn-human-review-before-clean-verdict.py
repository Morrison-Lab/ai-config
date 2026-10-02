#!/usr/bin/env python3
"""PreToolUse warn: a person is asked to review before an automated review is clean.

ai-config#4247. AGENTS.md says to get a clean automated review before asking a
person to review. The rule was skipped, and the fix for the skip was again
prose (ai-config#4241), so this hook checks the action itself.

It fires on a request for a human reviewer:
  - `gh pr edit --add-reviewer NAME`
  - `gh api .../requested_reviewers` with `reviewers[]=NAME`
  - `mcp__github__update_pull_request` with a `reviewers` list
A reviewer is a person unless the login contains `bot`, `copilot` or `claude`.

It looks in the transcript (JSONL), after the last pushed command, for a clean
review result: a `Verdict: Ready for merge` line or a `"verdict": "CLEAN"`
payload together with a 40-hex commit. Quoted instructions name the verdict
but carry no commit, so they do not count. If it finds none, it adds a note. It never blocks: an explicit instruction from the user to
request review now is a valid reason, and a hook cannot see that reliably.

Deliberate limits:
  - It reads only the transcript. It does not call GitHub, so a verdict that was
    never printed in this session is not seen. The note says how to proceed.
  - A missing or unreadable transcript is silent (fail open).
  - A reviewer request that removes a reviewer (`-X DELETE`) is ignored. A
    request whose reviewers sit in a `--input` JSON file is not seen.
"""
import json
import os
import re
import shlex
import sys

BOT = re.compile(r"bot|copilot|claude", re.I)
# A clean review result: a verdict line or payload AND the commit it covers.
# Quoted instruction text names the verdict but carries no 40-hex commit.
VERDICT = re.compile(
    r"^[ \t#>*]*Verdict:[ \t*]*Ready for merge|\"verdict\":\s*\"CLEAN\"",
    re.I | re.M)
COMMIT = re.compile(r"(Reviewed-Commit:|\"commit_sha\":)\s*\"?[0-9a-f]{40}", re.I)
PUSH = re.compile(r"(^|[;&|]\s*)git\s+push\b")
DELETE = re.compile(r"(-X|--method)[ =]+DELETE", re.I)

NOTE = """\
[hook: warn-human-review-before-clean-verdict] This call asks a person \
({who}) to review, and the transcript since the last push shows no clean \
automated verdict.
Get a clean automated review of the current head first (the repo's review \
workflow, or an adversarial-reviewer run), and ask the person after it is \
clean. Ignore this note if the user told you to request review now, the PR \
is a redaction PR, or no automated reviewer can run here."""


def humans(names):
    return [n for n in names if n and not BOT.search(n)]


def reviewers_from_bash(command):
    try:
        words = shlex.split(command)
    except ValueError:
        return []
    names = []
    for i, word in enumerate(words):
        if word == "--add-reviewer" and i + 1 < len(words):
            names += words[i + 1].split(",")
        elif word.startswith("--add-reviewer="):
            names += word.split("=", 1)[1].split(",")
        elif word.startswith("reviewers[]="):
            names.append(word.split("=", 1)[1])
    if DELETE.search(command):
        return []
    if "requested_reviewers" in command or "--add-reviewer" in command:
        return names
    return []


def requested_humans(payload):
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return []
    if tool == "Bash" and isinstance(tool_input.get("command"), str):
        return humans(reviewers_from_bash(tool_input["command"]))
    if tool.endswith("update_pull_request"):
        names = tool_input.get("reviewers")
        if isinstance(names, list):
            return humans([n for n in names if isinstance(n, str)])
    return []


def strings(node):
    """Every string inside a decoded transcript record."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value)


def commands(node):
    """Every Bash `command` value inside a decoded transcript record."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "command" and isinstance(value, str):
                yield value
            else:
                yield from commands(value)
    elif isinstance(node, list):
        for value in node:
            yield from commands(value)


def clean_since_last_push(path):
    """True when a clean review result follows the last pushed command.

    Fails open (True) when the transcript cannot be read.
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            raw = handle.read().splitlines()
    except (OSError, TypeError):
        return True
    records = []
    for line in raw:
        try:
            records.append(json.loads(line))
        except ValueError:
            records.append(line)
    last_push = 0
    for number, record in enumerate(records):
        cmds = commands(record) if not isinstance(record, str) else [record]
        if any(PUSH.search(c) for c in cmds):
            last_push = number
    for record in records[last_push:]:
        for text in strings(record):
            if VERDICT.search(text) and COMMIT.search(text):
                return True
    return False


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    who = requested_humans(payload)
    if not who:
        return 0
    path = payload.get("transcript_path")
    if not isinstance(path, str) or not os.path.exists(path):
        return 0
    if clean_since_last_push(path):
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(who=", ".join(who)),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
