#!/usr/bin/env python3
"""Stop-hook guard: a relationship written in prose must also be recorded.

shared/workflow/github-relationships.md (ai-config#4907): an issue or PR body
saying "Blocked by #N", "Stacked on #N" or "Part of #N" is not a relationship
in GitHub's relationships field. When a turn creates or edits an issue or PR
with such a body and makes no relationship call at or after it, block the stop
once so the agent records it (parent/sub-issue, blocked-by/blocking).

Code spans and fences are ignored, so a body that quotes the phrase is fine.
Fails open on any error.
"""
from __future__ import annotations

import json
import os
import re
import sys

_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
from agent_notice import stop_notice  # noqa: E402

WRITE_TOOL = re.compile(r"issue_write|create_pull_request|update_pull_request")
WRITE_CMD = re.compile(r"\bgh\s+(?:issue|pr)\s+(?:create|edit)\b")
# A relationship call: MCP sub-issue tool, the REST endpoints, or the gh flags.
LINK = re.compile(
    r"sub_issue_write|parent_issue_number|dependencies/(?:blocked_by|blocking)|"
    r"/sub_issues\b|--add-blocked-by|--add-blocking|--add-parent"
)
REF = r"(?:[\w.-]+/[\w.-]+)?#\d+"
CUE = re.compile(
    r"\b(?:blocked\s+by|blocks|depends\s+on|stacked\s+on|stacks\s+on|"
    r"sub-?issue\s+of|child\s+of|part\s+of|parent(?:\s+issue)?|tracked\s+(?:in|by))"
    r"\s*:?\s*" + REF,
    re.I,
)
CODE = re.compile(r"```.*?```|`[^`\n]*`", re.S)


def body_of(name: str, inp: dict) -> str | None:
    """The body text of an issue/PR write call, else None."""
    if WRITE_TOOL.search(name or ""):
        return str(inp.get("body") or "")
    cmd = str(inp.get("command") or "")
    if WRITE_CMD.search(cmd):
        return cmd
    return None


def scan(path: str):
    """Return (cue phrase of the first unlinked write this turn, or None)."""
    pending = None
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                m = json.loads(line)
            except Exception:
                continue
            blocks = (m.get("message") or {}).get("content") or []
            if not isinstance(blocks, list):
                continue
            if (m.get("type") or m.get("role")) == "user":
                if any(isinstance(b, dict) and b.get("type") == "text" for b in blocks):
                    pending = None  # a new human turn
                continue
            for b in blocks:
                if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                    continue
                inp = b.get("input") or {}
                blob = (b.get("name") or "") + " " + json.dumps(inp)
                if LINK.search(blob):
                    pending = None
                    continue
                body = body_of(b.get("name") or "", inp)
                if body is not None and pending is None:
                    hit = CUE.search(CODE.sub("", body))
                    if hit:
                        pending = hit.group(0).strip()
    return pending


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        phrase = scan(payload.get("transcript_path") or "")
    except Exception:
        return 0
    if not phrase:
        return 0
    print(stop_notice(
        payload,
        f"An issue or PR body this turn says \"{phrase}\" in prose, and no relationship call followed. "
        "Record it in GitHub's relationships field (REST, not GraphQL): sub-issue via `sub_issue_write` "
        "or `POST .../issues/<parent>/sub_issues`, blocked-by via `gh issue edit --add-blocked-by` or "
        "`POST .../issues/<n>/dependencies/blocked_by`; a PR closing an issue needs a `Closes #N` keyword. "
        "See shared/workflow/github-relationships.md.",
        "flag-prose-relationship-without-link",
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
