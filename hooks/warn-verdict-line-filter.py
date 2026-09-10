#!/usr/bin/env python3
"""PreToolUse warning: review round comments read through a verdict-line filter.

A Bash command that fetches PR review comments and narrows the comment body to
verdict lines drops non-blocking findings in the body and in the review-data
JSON findings array.
Measured 2026-09-09 on ai-config#3493: two findings carried over unaddressed.
Filter files passed via -f / --from-file are also inspected (ai-config#3494).
"""

from __future__ import annotations

import json
import os
import re
import sys

RX_FETCH_COMMENTS = re.compile(
    r"issues/\d+/comments|pulls/\d+/comments|--json\s+[\w,]*\b(?:comments|reviews)\b"
)

RX_VERDICT_LINES = re.compile(
    r'test\("[^"]*(?:Verdict|Ready for merge|Needs more work|NOT CLEAN|NOT_CLEAN|Reviewed commit)[^"]*"\)'
)

# A split of the body on its own is not a verdict-line read: a split followed
# by length counts lines. It becomes one when the split lines are then sliced,
# with any bound shape: .[0:4], .[:4], .[-4:], .[-4:-1].
RX_SPLIT_THEN_SLICE = re.compile(r'split\("(\\n|\n)"\).*\.\[-?\d*:-?\d*\]')

RX_JQ_FILTER_FILE = re.compile(
    r"""\bjq\b[^\n|;&]*?\s+(?:-[a-zA-Z]*f(?:\s+|=)|--from-file(?:\s+|=))(?:"([^"]+)"|'([^']+)'|([^\s|;&]+))""",
    re.I,
)

NOTE = (
    "this filter prints only the verdict lines of a review round; a round can "
    "be Ready for merge and still carry non-blocking findings in its body and "
    "in the review-data JSON findings array, which this filter drops "
    "(measured 2026-09-09, ai-config#3493, two findings carried over unaddressed); "
    "read the full body of every round since the last one you processed, or parse "
    "the review-data findings array, before reporting the PR's state."
)


def _read_filter_file(raw_path: str, cwd: str | None = None) -> str | None:
    """Read filter file text if it exists on disk. Never crashes."""
    if not raw_path:
        return None
    try:
        try:
            expanded = os.path.expanduser(raw_path)
        except Exception:
            expanded = raw_path

        base_cwd = cwd or os.getcwd()
        if os.path.isabs(expanded):
            resolved = expanded
        else:
            resolved = os.path.join(base_cwd, expanded)

        candidates = [resolved, expanded, raw_path]
        if os.name == "nt":
            m = re.match(r"^/([a-zA-Z])/(.*)", expanded)
            if m:
                win_path = f"{m.group(1)}:/{m.group(2)}"
                candidates.extend([win_path, os.path.join(base_cwd, win_path)])

        for cand in candidates:
            try:
                if os.path.isfile(cand):
                    with open(cand, "r", encoding="utf-8", errors="ignore") as fh:
                        return fh.read()
            except Exception:
                pass
    except Exception:
        return None
    return None


def should_warn(command: str, cwd: str | None = None) -> bool:
    """True when command matches comment fetch and verdict lines without findings."""
    if not RX_FETCH_COMMENTS.search(command):
        return False

    file_texts = []
    for m in RX_JQ_FILTER_FILE.finditer(command):
        raw_path = m.group(1) or m.group(2) or m.group(3)
        if raw_path:
            text = _read_filter_file(raw_path, cwd)
            if text:
                file_texts.append(text)

    union_text = "\n".join([command] + file_texts) if file_texts else command

    if not RX_VERDICT_LINES.search(union_text) and not RX_SPLIT_THEN_SLICE.search(union_text):
        return False
    if "findings" in union_text or "review-data" in union_text:
        return False
    return True


def _emit(note: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": note,
                }
            }
        )
    )


def _read_payload() -> tuple[dict, bool]:
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw_cmd = positional[0].strip()
            if raw_cmd.startswith("{") and raw_cmd.endswith("}"):
                try:
                    return json.loads(raw_cmd), True
                except Exception:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw_cmd}}, True

    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception:
        return {}, is_dry_run


def main() -> int:
    try:
        payload, _is_dry_run = _read_payload()
        if not payload or not isinstance(payload, dict):
            return 0

        tool_name = payload.get("tool_name")
        if tool_name not in (
            "Bash",
            "bash",
            "run_command",
            "execute_command",
            "terminal",
            "shell",
        ):
            return 0

        tool_input = payload.get("tool_input")
        if not isinstance(tool_input, dict):
            return 0

        command = (
            tool_input.get("command")
            or tool_input.get("cmd")
            or tool_input.get("CommandLine")
            or ""
        )
        if not isinstance(command, str) or not command.strip():
            return 0

        cwd = payload.get("cwd") or (payload.get("tool_input") or {}).get("cwd") or os.getcwd()
        if should_warn(command, cwd=cwd):
            _emit(NOTE)
    except Exception:
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
