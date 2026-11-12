#!/usr/bin/env python3
"""PreToolUse deny: a reply about which model a thread runs needs get_session first.

2026-11-12, Machine Learning course project. The coordinator told the user that
every thread had been moved off Fable. One thread was still on
claude-fable-5-2. Asked about it, the coordinator then said it could not see a
thread's live model. It could: `mcp__claude-code-remote__get_session` on a
thread's session returns `configured_model`, `session_context.model` and
`external_metadata.last_served_model`.

The written rule (shared/workflow/check-thread-models.md) is read at read time
and broken at composition time, so this hook fires at the composition: a reply
tool call (scripts/lib/tool_names.py REPLY_TOOLS) whose text has a paragraph
naming both a thread or session and a Claude model is denied when no
get_session call appears since the last user message.

WHY DENY ONCE, NOT ALWAYS
-------------------------
Whether a paragraph CLAIMS a thread's model, or only mentions one ("the rule
says never dispatch a worker on Fable"), is not decidable from the text. So the
first such reply in a turn is denied with the instruction, and the retry is
allowed, as in require-ums-before-resolve.py. A real claim gets one forced
pause to make the call; a mention costs one resend.

Fails OPEN and SILENT on any parse trouble.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
_LIB = os.path.join(os.path.dirname(HERE), "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
try:
    from tool_names import reply_text
except Exception:  # broken install: no reply text, so never deny
    def reply_text(name, inp):  # noqa: D103
        return ""

THREAD = re.compile(r"\b(?:threads?|sessions?|coordinator)\b", re.I)
MODEL = re.compile(
    r"\b(?:fable|opus|sonnet|haiku)\b|\bclaude-(?:fable|opus|sonnet|haiku)[\w.-]*",
    re.I,
)
CODE = re.compile(r"```.*?```|`[^`\n]*`", re.S)
CHECK_TOOL = "get_session"

DENY = (
    "[hook: no-thread-model-claim-without-get-session] This reply names a "
    "thread or session together with a model, and no get_session call appears "
    "since the last user message. Before saying which model any thread runs, "
    "or that threads were switched, call "
    "mcp__claude-code-remote__get_session on each thread's session "
    "(thread cse_X is session_X; list every thread with list_threads, every "
    "page and state) and compare configured_model, session_context.model and "
    "external_metadata.last_served_model. Report what those calls returned, "
    "not what you remember doing (shared/workflow/check-thread-models.md). "
    "If the paragraph only mentions a model and claims nothing about a thread, "
    "resend it: this refusal happens once per turn."
)


def claims_thread_model(text):
    prose = CODE.sub(" ", text)
    for para in re.split(r"\n\s*\n", prose):
        if THREAD.search(para) and MODEL.search(para):
            return True
    return False


def _is_user_text(rec):
    if rec.get("type") != "user" and rec.get("role") != "user":
        return False
    content = (rec.get("message") or {}).get("content", rec.get("content"))
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return any(isinstance(b, dict) and b.get("type") == "text"
                   and (b.get("text") or "").strip() for b in content)
    return False


def scan(path):
    """Return (index of last user text record, True if get_session follows it)."""
    last_user, checked_at = -1, -1
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for i, line in enumerate(fh):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict) or rec.get("isSidechain"):
                continue
            if _is_user_text(rec):
                last_user = i
                continue
            blocks = (rec.get("message") or {}).get("content") or []
            for b in blocks if isinstance(blocks, list) else []:
                if (isinstance(b, dict) and b.get("type") == "tool_use"
                        and str(b.get("name") or "").endswith(CHECK_TOOL)):
                    checked_at = i
    return last_user, checked_at > last_user


def first_time(key_text):
    key = hashlib.sha256(key_text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-thread-model-claim-{key}")
    if os.path.exists(sentinel):
        return False
    try:
        with open(sentinel, "w", encoding="utf-8") as fh:
            fh.write("1")
    except OSError:
        return False  # cannot record the refusal, so do not risk repeating it
    return True


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        text = reply_text(payload.get("tool_name"), payload.get("tool_input"))
        if not text or not claims_thread_model(text):
            return 0
        path = payload.get("transcript_path") or ""
        if not isinstance(path, str) or not os.path.isfile(path):
            return 0
        last_user, checked = scan(path)
    except Exception:
        return 0
    if checked or not first_time(f"{path}:{last_user}"):
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": DENY,
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
