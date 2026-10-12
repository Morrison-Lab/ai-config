#!/usr/bin/env python3
"""Stop-hook reminder: a PR/MR status report owes a mergeability reading.

On 2026-10-08 an abridge MR sat with merge conflicts for hours while the session
reported it as "open, pipeline green" (ai-config#4380). The MR was stacked: it
targeted another MR's branch, which gained commits, so the conflicts came from
the base moving, not from main. The session read state and pipeline status only,
and assumed the thread holding the merge grant would resolve the conflicts.

A green pipeline is a statement about one commit's checks. Whether the PR/MR can
merge into its ACTUAL target (which for a stacked PR is not the default branch)
is a different field: `has_conflicts` / `detailed_merge_status` on GitLab,
`mergeable` / `mergeStateStatus` on GitHub. Reporting the first as the PR's
state hides the second.

The condition is exactly decidable from the transcript:

    final message reports PR/MR status (a PR/MR reference AND pipeline/CI/checks
    state wording)  AND  no tool call since the last real user prompt queried
    mergeability

Warns rather than blocks. The status report is RIGHT to send; only the missing
reading is owed, and a guard that suppressed the report would hide the very
signal it exists to complete. It emits a `systemMessage`, which is the field a
`Stop` hook's output surfaces without `decision: block`.

Fenced code, blockquotes and inline code are stripped first, so a reply quoting
the trigger wording is not asserting it. Fails OPEN on any parse trouble, and
fires at most once per distinct message, so it cannot wedge a session.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

_LIB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
try:
    from fences import strip_code
    from transcript_meta import is_harness_meta, is_skill_load_meta
except Exception as _exc:  # broken install: degrade loudly, never crash a Stop
    print(f"remind-mergeability-on-status: cannot load scripts/lib "
          f"({_exc}); staying silent", file=sys.stderr)
    strip_code = None

# A PR/MR reference: a forge URL, `!NNN` (GitLab MR), or `#NNN`.
RX_PR_REF = re.compile(
    r"github\.com/[\w.-]+/[\w.-]+/pull/\d+"
    r"|/-/merge_requests/\d+"
    r"|/merge_requests/\d+"
    r"|(?<![\w/])![0-9]+\b"
    r"|(?<![&/])(?<!issue )(?<!issues )(?<!step )#[0-9]+\b"
    r"|\b(?:PR|MR|pull request|merge request)s?\s+#?!?\d+",
    re.I,
)

# Pipeline/CI/checks state wording. `\b(?:pipeline|ci|checks?)` followed within
# a short window by a state word (either order), so "CI is green" and "green
# pipeline" both count while a bare "check" (a verb) does not.
_SUBJECT = r"(?:pipelines?|ci|checks?|builds?|jobs?)"
_STATE = r"(?:green|passing|pass|passed|passes|success(?:ful(?:ly)?)?|running|in\s+progress|pending|queued|complete|completed|fail|failed|failing|canceled|red)"
RX_STATUS = re.compile(
    rf"\b{_SUBJECT}\b[^.\n]{{0,40}}\b{_STATE}\b"
    rf"|\b{_STATE}\b[^.\n]{{0,40}}\b{_SUBJECT}\b",
    re.I,
)

# Any query of mergeability. Searched over a shell tool's `command` text only
# (never Write/Edit content, Agent prompts, or search patterns, which can
# mention these words without reading anything), so a
# `gh pr view --json mergeable,mergeStateStatus` or a `glab mr view` counts.
# MCP reads carry no such words in their input, so they are matched by tool
# name instead.
RX_MCP_MERGEABILITY_TOOL = re.compile(
    r"^mcp__(?:github|ccd_pr)__(?:pull_request_read|get_status)$", re.I)
# pull_request_read serves many methods; only `get` returns mergeable and
# mergeable_state. Its `get_status` method is the combined CI-status read
# (memories/github-mcp-tools.md), so it must not discharge the check. The
# standalone ccd_pr get_status tool is a different tool and keeps counting.
MCP_MERGEABILITY_METHODS = {"get"}
# A shell command counts only when it runs a forge client, so `echo mergeable`
# or a grep for the word is not a read.
RX_FORGE_CLIENT = re.compile(r"\b(?:gh|glab|curl)\b")
# A report about a PR that is already merged or closed makes mergeability moot.
RX_TERMINAL_PR = re.compile(r"\b(?:merged|closed|abandoned)\b", re.I)
RX_MERGEABILITY_QUERY = re.compile(
    r"has_conflicts|detailed_merge_status|merge_status|mergeStateStatus"
    r"|\bmergeable(?:_state)?\b|\bglab\s+mr\s+view\b",
    re.I,
)


def _blocks(entry):
    content = (entry.get("message") or {}).get("content")
    if content is None:
        content = entry.get("content")
    return content


def _is_real_prompt(entry):
    """True for a user record the person typed (not a tool_result or meta)."""
    if entry.get("type") != "user" or entry.get("isSidechain"):
        return False
    # A harness injection is not a prompt; an sdk wake continuation is (it is a
    # genuine new turn, see scripts/lib/transcript_meta.py).
    if is_skill_load_meta(entry) or is_harness_meta(entry):
        return False
    content = _blocks(entry)
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        return any(isinstance(b, dict) and b.get("type") == "text" for b in content)
    return False


def scan(path):
    """Return (final_assistant_text, queried_mergeability_since_last_prompt)."""
    text = ""
    queried = False
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if _is_real_prompt(entry):
                text, queried = "", False
                continue
            if entry.get("type") != "assistant" or entry.get("isSidechain"):
                continue
            content = _blocks(entry)
            if isinstance(content, str):
                text = content
                continue
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text = block.get("text") or ""
                elif block.get("type") == "tool_use":
                    inp = block.get("input") or {}
                    cmd = inp.get("command") if isinstance(inp, dict) else None
                    if (isinstance(cmd, str) and RX_FORGE_CLIENT.search(cmd)
                            and RX_MERGEABILITY_QUERY.search(cmd)):
                        queried = True
                    elif RX_MCP_MERGEABILITY_TOOL.search(block.get("name") or ""):
                        name = block.get("name") or ""
                        method = inp.get("method") if isinstance(inp, dict) else None
                        if not name.lower().endswith("__pull_request_read"):
                            queried = True
                        elif method is None or method in MCP_MERGEABILITY_METHODS:
                            queried = True
    return text, queried


def main() -> int:
    if strip_code is None:
        return 0
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path") or ""
        if not path or not os.path.isfile(path):
            return 0
        text, queried = scan(path)
    except Exception:
        return 0  # fail open

    if not text or queried:
        return 0
    prose = strip_code(text)
    prose = re.sub(r"(?m)^\s*>.*$", " ", prose)
    # Reference and status wording must share a sentence, so an unrelated
    # issue number and an unrelated build remark do not combine.
    sentences = re.split(r"(?<=[.!?])\s+|\n", prose)
    if not any(RX_PR_REF.search(x) and RX_STATUS.search(x)
               and not RX_TERMINAL_PR.search(x) for x in sentences):
        return 0

    key = hashlib.sha256((path + ":" + text).encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-mergeability-status-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        with open(sentinel, "w", encoding="utf-8"):
            pass
    except Exception:
        pass

    print(json.dumps({
        "systemMessage": (
            "Mergeability reminder (ai-config#4380): this reply reports a PR/MR's "
            "status (pipeline/CI/checks), but no command this turn read its "
            "mergeability. A green pipeline says nothing about whether it merges.\n"
            "Query mergeability against the PR's ACTUAL target branch -- for a "
            "stacked PR that is the base PR's branch, not main: `has_conflicts` / "
            "`detailed_merge_status` on GitLab (`glab mr view`), `mergeable` / "
            "`mergeStateStatus` on GitHub (`gh pr view --json mergeable,"
            "mergeStateStatus,baseRefName`).\n"
            "If it has conflicts and the PR is yours, resolve them now; do not "
            "assume whichever thread holds the merge grant owns them.\n"
            "If this is a false positive (the PR is not yours to merge, or you "
            "read mergeability another way), disregard it."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
