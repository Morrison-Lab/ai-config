#!/usr/bin/env python3
"""Stop-hook guard: a relationship written in prose must also be recorded.

shared/workflow/github-relationships.md (ai-config#4907): an issue or PR body
saying "Blocked by #N", "Stacked on #N" or "Part of #N" is not a relationship
in GitHub's relationships field. When a turn creates or edits an issue
with such a body and makes no relationship call at or after it, block the stop
once so the agent records it (parent/sub-issue, blocked-by/blocking).

Code spans and fences are ignored, so a body that quotes the phrase is fine.
Only bodies written by tool calls in the current turn are scanned (the turn
boundary is `transcript_meta.is_real_user_turn`), never assistant reply text.
A PR body is never flagged (ai-config#5442, #5772): GitHub rejects a PR on either
end of a dependency link (422 "Source issue may only be an issue", measured on
dependencies/blocked_by), so a PR body has nothing to record. The decision is
offline: `create_pull_request`, `update_pull_request` and a command with no
`gh issue create|edit` invocation are never flagged (see `has_issue_write`).
`issue_write` is treated as an issue body even for method=update on a PR's number,
which cannot be told apart offline. An issue body naming a PR as its blocker is
still flagged and cannot be recorded; the notice says to reword the cue or link
the issue that PR closes (no network call). A stacked PR is recorded by its base
branch and the `> [!IMPORTANT]` alert.
Known edge: a command that chains an issue write with a PR write is scanned
whole, so a cue in the PR body is flagged too. It blocks once per turn.
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
from shellcmd import nested_shell_commands, simple_commands, strip_env  # noqa: E402
from transcript_meta import is_real_user_turn  # noqa: E402

WRITE_TOOL = re.compile(r"issue_write|create_pull_request|update_pull_request")
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
PR_TOOL = re.compile(r"create_pull_request|update_pull_request")


# Programs that may precede `gh` (`command gh ...`, `sudo -u me gh ...`).
GH_WRAPPERS = {"command", "sudo", "time", "nohup", "env", "exec", "nice", "timeout"}
GH_VALUE_FLAGS = ("-R", "--repo", "--hostname")
ISSUE_CMD = re.compile(r"\bgh\b[^\n]*?\bissue\s+(?:create|edit)\b")


def _is_issue_write(argv: list[str]) -> bool:
    """True when argv is `[wrappers] gh [global flags] issue create|edit`."""
    _env, argv = strip_env(argv)
    for i, tok in enumerate(argv[:8]):
        if os.path.basename(tok) == "gh":
            toks = argv[i + 1:]
            j = 0
            while j < len(toks) and toks[j].startswith("-"):
                j += 2 if toks[j] in GH_VALUE_FLAGS else 1
            return toks[j:j + 2] in (["issue", "create"], ["issue", "edit"])
        prev = argv[i - 1] if i else ""
        if not (tok in GH_WRAPPERS or tok.startswith("-") or prev.startswith("-")):
            return False
    return False


def has_issue_write(cmd: str, depth: int = 0) -> bool:
    """True when some invocation in the command is `gh issue create|edit`.

    Decided at shell level only (the question is which verbs run, not what the
    bodies say): `shellcmd.simple_commands` splits the command, `strip_env`
    peels env assignments and shell keywords, and the script argument of
    `bash -c` is searched too. An unparseable command falls back to a text match.
    """
    cmds = simple_commands(cmd)
    if cmds is None:
        return bool(ISSUE_CMD.search(cmd))
    for argv in cmds:
        if depth < 3 and any(has_issue_write(c, depth + 1) for c in nested_shell_commands(argv)):
            return True
        if _is_issue_write(argv):
            return True
    return False


def body_of(name: str, inp: dict) -> list[tuple[str, bool]]:
    """(body text, whether it belongs to a PR) for each issue/PR write in a tool call.

    A command with any issue write is scanned whole, heredocs included, as an
    issue body; a command with only PR writes (or none) is never flagged.
    """
    if WRITE_TOOL.search(name or ""):
        return [(str(inp.get("body") or ""), bool(PR_TOOL.search(name or "")))]
    cmd = str(inp.get("command") or "")
    return [(cmd, False)] if has_issue_write(cmd) else []


def first_cue(body: str, is_pr: bool) -> str | None:
    """The first cue phrase in an issue body; a PR body has no recordable relationship."""
    if is_pr:
        return None
    hit = CUE.search(CODE.sub("", body))
    return hit.group(0).strip() if hit else None


def scan(path: str):
    """Return (cue phrase of the first unlinked write this turn, or None)."""
    pending = None
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                m = json.loads(line)
            except Exception:
                continue
            if is_real_user_turn(m):
                pending = None  # a new human turn, string or block content
                continue
            blocks = (m.get("message") or {}).get("content") or []
            if not isinstance(blocks, list) or (m.get("type") or m.get("role")) == "user":
                continue
            for b in blocks:
                if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                    continue
                inp = b.get("input") or {}
                blob = (b.get("name") or "") + " " + json.dumps(inp)
                if LINK.search(blob):
                    pending = None
                    continue
                for written in body_of(b.get("name") or "", inp):
                    if pending is None:
                        pending = first_cue(*written)
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
        f"An issue body this turn says \"{phrase}\" in prose, and no relationship call followed. "
        "Record it in GitHub's relationships field (REST, not GraphQL): sub-issue via `sub_issue_write` "
        "or `POST .../issues/<parent>/sub_issues`, blocked-by via `gh issue edit --add-blocked-by` or "
        "`POST .../issues/<n>/dependencies/blocked_by`. GitHub cannot record a PR on either end of a "
        "link: a stacked PR is recorded by its base branch plus a leading `> [!IMPORTANT]` alert in the "
        "PR body, and a PR closing an issue needs a `Closes #N` keyword. If #N is a PR, no call can "
        "record the link (422 \"Target issue may only be an issue\"): reword the cue in plain prose "
        "(e.g. \"needs #N merged first\") or link the issue that PR closes. "
        "See shared/workflow/github-relationships.md.",
        "flag-prose-relationship-without-link",
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
