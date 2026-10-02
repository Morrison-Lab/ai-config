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

It looks in the transcript, after the last `git push`, for a clean verdict
(`Verdict: Ready for merge`, `"verdict": "CLEAN"`, `fully clean`). If it finds
none, it adds a note. It never blocks: an explicit instruction from the user to
request review now is a valid reason, and a hook cannot see that reliably.

Deliberate limits:
  - It reads only the transcript. It does not call GitHub, so a verdict that was
    never printed in this session is not seen. The note says how to proceed.
  - A missing or unreadable transcript is silent (fail open).
"""
import json
import os
import re
import shlex
import sys

BOT = re.compile(r"bot|copilot|claude", re.I)
CLEAN = re.compile(
    r"Verdict:\s*\**\s*Ready for merge|\"verdict\":\s*\"CLEAN\"|fully clean",
    re.I)
PUSH = re.compile(r"git push")

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


def clean_since_last_push(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
    except (OSError, TypeError):
        return True
    last_push = 0
    for number, line in enumerate(lines):
        if PUSH.search(line):
            last_push = number
    return any(CLEAN.search(line) for line in lines[last_push:])


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
