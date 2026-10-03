#!/usr/bin/env python3
"""PreToolUse warn: a person is asked to review before an automated review is clean.

ai-config#4247. AGENTS.md says to get a clean automated review before asking a
person to review. The rule was skipped, and the fix for the skip was again
prose (ai-config#4241), so this hook checks the action itself.

It fires on a request for a human reviewer:
  - `gh pr edit --add-reviewer NAME`, `gh pr create --reviewer/-r NAME`
  - `gh api .../requested_reviewers` with `reviewers[]=NAME`
  - `mcp__github__update_pull_request` or `create_pull_request` with a
    `reviewers` list
A reviewer is a person unless the login contains `bot`, `copilot` or `claude`.

It looks in the transcript (JSONL), after the last pushed command, for a clean
review result: a `Verdict: Ready for merge` line or a `"verdict": "CLEAN"`
payload together with a 40-hex commit.
Quoted instructions name the verdict but carry no commit, so they do not count.
If it finds none, it adds a note.
It never blocks: an explicit instruction from the user to request review now
is a valid reason, and a hook cannot see that reliably.

Deliberate limits:
  - It reads only the transcript. It does not call GitHub, so a verdict that was
    never printed in this session is not seen. The note says how to proceed.
  - A missing or unreadable transcript is silent (fail open).
  - A reviewer request that removes a reviewer (`-X DELETE`) is ignored. A
    request whose reviewers sit in a `--input` JSON file is not seen.
  - Only tool results count as a review result, so a verdict the agent
    wrote itself does not.
  - When a command cannot be tokenised (an apostrophe in a heredoc body),
    reviewer flags are found by a plain text scan, without splitting on
    shell operators.
  - Commands joined by a newline share one segment, so a DELETE on one
    line can hide a request on the next.
  - A verdict is not compared with the pushed head. One printed before the
    last push (the usual pre-push review) does not count, and one for an
    older commit printed after it does.
  - A push counts when a Bash command runs `git push` (also `git -C DIR
    push`) or an MCP file-write tool runs. Other ways of pushing are not seen.
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
# `git`, then options (`-C DIR`, `-c k=v`, `--flag`), then `push` as the
# subcommand; the bound keeps the match linear.
PUSH = re.compile(
    r"(^|[\s;&|(])git(?:\s+-[cC]\s+\S+|\s+-\S+){0,6}\s+push\b")
# Fallback when a command cannot be tokenised (an apostrophe in a heredoc).
REVIEWER_FLAG = re.compile(
    r"(?:--add-reviewer|--reviewer|-r)[ =]+([^\s\"']+)|reviewers\[\]=([^\s\"']+)")
MCP_PUSH = re.compile(r"mcp__github__(push_files|create_or_update_file)")
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


OPERATORS = {";", "&&", "||", "|", "&", "(", ")", ";;"}


def reviewers_from_words(words):
    names = []
    for i, word in enumerate(words):
        if word in ("--add-reviewer", "--reviewer", "-r") and i + 1 < len(words):
            names += words[i + 1].split(",")
        elif word.startswith(("--add-reviewer=", "--reviewer=")):
            names += word.split("=", 1)[1].split(",")
        elif word.startswith("reviewers[]="):
            names.append(word.split("=", 1)[1])
    text = " ".join(words)
    if DELETE.search(text):
        return []
    if "requested_reviewers" in text or re.search(
            r"--add-reviewer|gh pr create", text):
        return names
    return []


def segments(command):
    """Word lists of the simple commands in a compound line, or None.

    The whole command is tokenised first, so quotes (a multi-line `--body`)
    stay intact, and then split on the shell operator tokens.
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        words = list(lexer)
    except ValueError:
        return None
    found, segment = [], []
    for word in words + [";"]:
        if word in OPERATORS:
            found.append(segment)
            segment = []
        else:
            segment.append(word)
    return found


def is_push(command):
    """True when the line runs `git [options] push` outside any quotes."""
    parts = segments(command)
    if parts is None:
        return bool(PUSH.search(command))
    for words in parts:
        for i, word in enumerate(words):
            if word != "git":
                continue
            rest = words[i + 1:]
            while rest and rest[0].startswith("-"):
                rest = rest[2:] if rest[0] in ("-C", "-c") else rest[1:]
            if rest and rest[0] == "push":
                return True
    return False


def reviewers_from_bash(command):
    """Reviewer logins requested by any simple command in a compound line."""
    parts = segments(command)
    if parts is None:
        if DELETE.search(command) or not re.search(
                r"gh pr (create|edit)|requested_reviewers", command):
            return []
        found = [a or b for a, b in REVIEWER_FLAG.findall(command)]
        return [n for name in found for n in name.split(",")]
    names = []
    for words in parts:
        names += reviewers_from_words(words)
    return names


def requested_humans(payload):
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return []
    if tool == "Bash" and isinstance(tool_input.get("command"), str):
        return humans(reviewers_from_bash(tool_input["command"]))
    if tool.endswith(("update_pull_request", "create_pull_request")):
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


def results(node):
    """Strings inside tool_result blocks: output the agent did not write."""
    if isinstance(node, dict):
        if node.get("type") == "tool_result":
            yield from strings(node)
        else:
            for value in node.values():
                yield from results(value)
    elif isinstance(node, list):
        for value in node:
            yield from results(value)


def tool_names(node):
    """Names of tools the agent called (tool_use blocks only)."""
    if isinstance(node, dict):
        if node.get("type") == "tool_use" and isinstance(node.get("name"), str):
            yield node["name"]
        for value in node.values():
            yield from tool_names(value)
    elif isinstance(node, list):
        for value in node:
            yield from tool_names(value)


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
        if any(is_push(c) for c in cmds) or any(
                MCP_PUSH.search(n) for n in tool_names(record)):
            last_push = number
    for record in records[last_push:]:
        for text in results(record):
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
