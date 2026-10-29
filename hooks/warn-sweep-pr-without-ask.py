#!/usr/bin/env python3
"""PreToolUse warn: a PR is titled or labelled as a sweep with no explicit sweep ask cited.

Ezra, 2026-10-29: "don't sweep new rules unless I explicitly tell you to
sweep; by default, just fix incrementally when you are editing a passage
anyway" (ai-config#4829). `shared/workflow/no-sweeps-by-default.md` is the
rule. This hook checks the action: opening a PR whose title says "sweep" (or
that carries a `sweep` label) is the visible moment an agent turns a new rule
into a pass over existing content.

It fires on:
  - `gh pr create` (title from `--title`/`-t`, labels from `--label`/`-l`)
  - `mcp__github__create_pull_request` (title)
and stays silent when the body or command holds a `Sweep authorized:` marker,
which should quote or link the message in which Ezra asked for the sweep.
It warns, never blocks: whether a title that merely contains the word is a
sweep is a judgment a hook cannot make, and a title can say "sweep" for
honest reasons (a one-off cleanup of ai-config's own code).

Deliberate limits:
  - A sweep PR titled without the word is not seen.
  - `gh pr edit` (a later retitle or relabel) and labels on an MCP create
    call are not seen.
  - The marker must be followed by at least nine characters (a message id or
    link); it is not checked against any message.
  - A PR created with `--fill` or `--title-file`-style input is not seen.
  - Fails open on any parse trouble.
"""
import json
import re
import shlex
import sys

SWEEP = re.compile(r"\bsweep(?:s|ing|ed)?\b", re.I)
AUTHORIZED = re.compile(r"\bSweep authorized:\s*\S.{8,}", re.I)
CREATE = re.compile(r"\bgh\s+pr\s+create\b")

NOTE = (
    "This PR is titled or labelled as a sweep, and nothing in it cites an explicit "
    "sweep ask. Ezra, 2026-10-29 (ai-config#4829): a new rule is not swept across "
    "existing content unless he explicitly says to sweep; by default, fix a violation "
    "incrementally when you are editing that passage anyway, and let checks look at "
    "changed lines only. If he did ask for this sweep, add a `Sweep authorized:` line "
    "to the PR body quoting or linking his message. Otherwise drop the sweep, keep the "
    "incremental fix, and file an issue only if the leftovers need a decision. See "
    "shared/workflow/no-sweeps-by-default.md."
)


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return "\n" + f.read()
    except (OSError, ValueError):
        return ""


def bash_fields(command):
    """Return (title, labels, body-ish text) of a `gh pr create` command, or None."""
    if not CREATE.search(command):
        return None
    try:
        words = shlex.split(command, comments=False)
    except ValueError:
        words = command.split()
    title, labels, text = "", [], command
    for i, w in enumerate(words):
        nxt = words[i + 1] if i + 1 < len(words) else ""
        if w in ("--body-file", "-F"):
            text += read_file(nxt)
        elif w.startswith("--body-file="):
            text += read_file(w.split("=", 1)[1])
        elif w.startswith("-t") and len(w) > 2 and not w.startswith("--"):
            title = w[2:]
        elif w.startswith("-l") and len(w) > 2 and not w.startswith("--"):
            labels += w[2:].split(",")
        elif w in ("--title", "-t"):
            title = nxt
        elif w.startswith("--title="):
            title = w.split("=", 1)[1]
        elif w in ("--label", "-l"):
            labels += nxt.split(",")
        elif w.startswith("--label="):
            labels += w.split("=", 1)[1].split(",")
    return title, labels, text


def decide(payload):
    name = payload.get("tool_name") or ""
    inp = payload.get("tool_input") or {}
    if name == "Bash":
        fields = bash_fields(inp.get("command") or "")
        if fields is None:
            return None
        title, labels, text = fields
    elif name.endswith("create_pull_request"):
        title, labels, text = inp.get("title") or "", [], inp.get("body") or ""
    else:
        return None
    if not (SWEEP.search(title) or any(SWEEP.search(label) for label in labels)):
        return None
    if AUTHORIZED.search(text):
        return None
    return NOTE


def main():
    try:
        payload = json.load(sys.stdin)
        note = decide(payload) if isinstance(payload, dict) else None
    except Exception:
        return 0
    if note:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "additionalContext": note}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
