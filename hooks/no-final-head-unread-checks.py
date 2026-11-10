#!/usr/bin/env python3
"""PreToolUse DENY: do not report a head as "final" without reading its check runs this turn.

ai-config#5198. Coordinator, 2026-11-09: owners keep calling a head "final" while
CI is still running (rme#1450 had `build` running; ai-config#5186 was reported
before its CI was read; the coordinator made the same miss on ai-config#5176).
`shared/workflow/fully-clean.md` already says to wait for every in-flight check
run, so the prose is read past and the gap is a mechanism.

The condition is decidable from the transcript:

    the message calls a head final ("final head", "is final", "now final") and
    cites a pull request  AND  no check-runs read ran since the last real user
    turn

A check-runs read that returned without error is a GitHub `pull_request_read` with `method: get_check_runs`,
a `get_check_run` call, or a Bash command naming `check-runs` or
`check-pr-fully-clean`. The read is not tied to one PR: matching the cited number
to a read made through a shell variable would deny honest reports, and a guard
that denies honest reports gets switched off. The denial says what the read must
show (every run completed, none failed, the Claude review Clean on that sha).

Denies a user-visible tool call (post_message, message_coordinator,
message_thread, edit_message). A sentence that negates the claim ("not final",
"isn't final yet") is left alone. A deny rather than a reminder because the
failing shape is lexical and reminders are read past (ai-config#4741).
ALLOW_FINAL_HEAD=1 overrides. Fails open on any parse trouble.
"""
import json
import os
import re
import sys

_LIB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib"
)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

REPORT_TOOL = re.compile(
    r"^mcp__hearthbot__(?:post_message|message_coordinator|message_thread|edit_message)$"
)
CHECK_RUNS_TOOL = re.compile(r"^mcp__github__get_check_run$")
PR_READ_TOOL = re.compile(r"^mcp__github__pull_request_read$")
CHECK_RUNS_COMMAND = re.compile(r"check-runs|check-pr-fully-clean")

FINAL = re.compile(r"\bfinal\s+heads?\b|\b(?:is|are|now|as)\s+final\b", re.I)
NEGATED = re.compile(r"\bnot\b|n't\b|\bnever\b|\bno longer\b|\buntil\b|\bonce\b|\bif\b", re.I)
PR_REF = re.compile(r"/pull/\d+|\b[\w.-]*#\d{2,}\b", re.I)

REASON = (
    "[hook: no-final-head-unread-checks] This message calls a head final "
    '("{phrase}") and nothing since the last user turn read that head\'s check runs. '
    "A head is final only when the Claude review is Clean on that sha and every check run "
    "on it has completed with none failed, read live in this turn: get_check_runs (or "
    "`gh api repos/<r>/commits/<sha>/check-runs?per_page=100`), counted against total_count. "
    "Do not call a head final from a review verdict, a check-suite wake or an earlier read "
    "(rme#1450, ai-config#5186 and #5176 were reported early). Read the runs, then resend. "
    "ai-config#5198."
)


def _is_user_turn(entry):
    try:
        from transcript_meta import is_real_user_turn

        return is_real_user_turn(entry)
    except Exception:
        return entry.get("type") == "user" and not entry.get("isMeta")


def _is_check_runs_read(block):
    name = str(block.get("name") or "")
    tool_input = block.get("input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    if CHECK_RUNS_TOOL.match(name):
        return True
    if PR_READ_TOOL.match(name):
        return str(tool_input.get("method") or "") == "get_check_runs"
    if name == "Bash":
        return bool(CHECK_RUNS_COMMAND.search(str(tool_input.get("command") or "")))
    return False


FAILED_RESULT = re.compile(r"\s*(?:exit code [1-9]|error\b|failed\b|http [45]\d\d)", re.I)


def _result_text(block):
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            str(c.get("text") or "") for c in content if isinstance(c, dict)
        )
    return ""


def read_check_runs_this_turn(path):
    """True when a check-runs read returned without error since the last real user turn.

    A read counts once its paired tool_result arrives and reports no error, so a
    403 or a failed `gh` call does not discharge the claim.
    """
    pending = set()
    seen = False
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            if _is_user_turn(entry):
                seen = False
                pending = set()
                continue
            blocks = (entry.get("message") or {}).get("content") or entry.get("content")
            for block in blocks if isinstance(blocks, list) else []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use" and _is_check_runs_read(block):
                    pending.add(block.get("id"))
                elif block.get("type") == "tool_result" and block.get("tool_use_id") in pending:
                    pending.discard(block.get("tool_use_id"))
                    failed = block.get("is_error") or FAILED_RESULT.match(_result_text(block))
                    if not failed:
                        seen = True
    return seen


def find_claim(text):
    """The first un-negated sentence calling a head final, when a PR is cited; else None."""
    if not PR_REF.search(text):
        return None
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        hit = FINAL.search(sentence)
        if hit and not NEGATED.search(sentence):
            return " ".join(sentence.split())[:120]
    return None


def main() -> int:
    if os.environ.get("ALLOW_FINAL_HEAD") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if not REPORT_TOOL.match(str(payload.get("tool_name") or "")):
        return 0
    tool_input = payload.get("tool_input")
    text = tool_input.get("text") if isinstance(tool_input, dict) else None
    if not isinstance(text, str):
        return 0
    phrase = find_claim(text)
    if not phrase:
        return 0
    path = payload.get("transcript_path")
    if not isinstance(path, str):
        return 0
    try:
        if read_check_runs_this_turn(path):
            return 0
    except OSError:
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON.format(phrase=phrase),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
