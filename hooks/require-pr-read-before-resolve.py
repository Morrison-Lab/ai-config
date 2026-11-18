#!/usr/bin/env python3
"""PreToolUse: never resolve a thread without reading its PR state this turn.

ai-config#5806. On 2026-11-17 the coordinator resolved the thread "Add psw rule
for choosing result div types" in an idle-thread sweep while its PR (lds#2623)
was still open. A resolved thread is hidden from the user and loses its message
box, so a thread that owns an open PR must never be resolved.

Rule, on `mcp__hearthbot__set_thread_resolved` with `resolved: true`:

  1. DENY when no `list_threads` call with `include_pull_requests` set ran since
     the last real user turn. This part is lexically decidable and always on.
  2. DENY when such a call ran and its result, in the row for the target thread
     (the `thread_id` argument, when the call carries one), shows an open or
     draft PR.

WHY PART 2 IS BEST-EFFORT
-------------------------
The hook sees the tool result only as text in the transcript, and the row format
of `list_threads` is not a contract this repo owns. Part 2 therefore looks for
the thread id and an `open`/`draft` pull-request marker within that row's
window, and gives up quietly (allows) when the id is absent from the result.
Part 1 is the narrow deny that cannot depend on the format: it forces the read
that the 2026-11-17 miss skipped. The denial text tells the agent to skip any
thread whose row shows an open or draft PR, so a missed pattern in part 2 still
meets a human-readable instruction.

Fails open on any parse trouble, including a missing transcript.
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

RESOLVE_TOOL = "set_thread_resolved"
LIST_TOOL = re.compile(r"^mcp__hearthbot__list_threads$")

# A pull request marker that is not merged or closed, within one row's window.
OPEN_PR = re.compile(
    r"(?:\bpull[_ ]?requests?\b|\bprs?\b)[^\n]{0,200}?\b(?:open|draft)\b"
    r"|\b(?:open|draft)\b[^\n]{0,40}?\b(?:pull[_ ]?requests?|prs?)\b"
    r"|[\"']state[\"']\s*:\s*[\"'](?:open|draft)[\"']",
    re.I,
)
ROW_WINDOW = 600

DENY_UNREAD = (
    "[hook: require-pr-read-before-resolve] Do not resolve this thread yet: no list_threads "
    "call with include_pull_requests ran since the last user turn. On 2026-11-17 a thread "
    "was resolved while its PR (lds#2623) was still open. Call list_threads with "
    "include_pull_requests (page state=done with every cursor, plus review_ready and "
    "blocked, for a sweep), then resolve only a thread whose row shows no open or draft "
    "PR. ai-config#5806."
)
DENY_OPEN = (
    "[hook: require-pr-read-before-resolve] The list_threads row for this thread shows an "
    "open or draft PR. A thread with an open PR stays unresolved until the PR merges or "
    "closes. Skip it. ai-config#5806."
)


def _is_user_turn(entry):
    try:
        from transcript_meta import is_real_user_turn

        return is_real_user_turn(entry)
    except Exception:
        return entry.get("type") == "user" and not entry.get("isMeta")


def _blocks(entry):
    blocks = (entry.get("message") or {}).get("content") or entry.get("content")
    return blocks if isinstance(blocks, list) else []


def _result_text(block):
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(b.get("text") or "") for b in content if isinstance(b, dict)
        )
    return ""


def list_reads_this_turn(path):
    """Result texts of list_threads calls with include_pull_requests since the last user turn.

    Returns (ran, texts). `ran` is True when the call itself ran, even if its
    result is not in the transcript.
    """
    ids, texts, ran = set(), [], False
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            if _is_user_turn(entry):
                ids, texts, ran = set(), [], False
                continue
            for block in _blocks(entry):
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use" and LIST_TOOL.match(str(block.get("name") or "")):
                    args = block.get("input") or {}
                    if isinstance(args, dict) and args.get("include_pull_requests"):
                        ran = True
                        ids.add(block.get("id"))
                elif block.get("type") == "tool_result" and block.get("tool_use_id") in ids:
                    texts.append(_result_text(block))
    return ran, texts


def row_shows_open_pr(texts, thread_id):
    for text in texts:
        for m in re.finditer(re.escape(thread_id), text):
            window = text[max(0, m.start() - 100): m.start() + ROW_WINDOW]
            if OPEN_PR.search(window):
                return True
    return False


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        name = str(payload.get("tool_name") or "")
        inp = payload.get("tool_input")
        if not name.endswith(RESOLVE_TOOL) or not isinstance(inp, dict) or inp.get("resolved") is not True:
            return 0
        path = payload.get("transcript_path")
        if not isinstance(path, str) or not os.path.isfile(path):
            return 0
        ran, texts = list_reads_this_turn(path)
        if not ran:
            deny(DENY_UNREAD)
            return 0
        thread_id = inp.get("thread_id")
        if isinstance(thread_id, str) and thread_id and row_shows_open_pr(texts, thread_id):
            deny(DENY_OPEN)
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
