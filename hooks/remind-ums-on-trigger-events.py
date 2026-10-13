#!/usr/bin/env python3
"""Reminders that a UMS pass is owed at moments no admission or review marks.

ai-config#4480. The existing UMS triggers key on an admission, a read review,
a questioned claim, or a pause. Five more moments owe a pass, each with a
decidable signature; the rest (below) stay rules in run-ums-proactively.md.

  coordinator-note   UserPromptSubmit: a <coordinator-relay> whose reason is
                     not "spawn" carries a note that steers or corrects the
                     thread. The note is a colleague's correction, and it is
                     the same lesson for every thread the coordinator tells.
  needless-question  UserPromptSubmit: the user's whole message is a grant
                     ("daytb", "yes, do it", "your call", "rec?"). The thread
                     asked something it could have decided.
  compaction         SessionStart (source compact): learnings held only in
                     the compacted context may be summarized away.
  revert             PreToolUse Bash running `git revert`, `git reset --hard`
                     or `git restore --source`: work was undone or redone.

Inject-only: every path prints context and exits 0. Fails OPEN and SILENT.
Each reminder fires once per distinct trigger text (sentinel in the temp dir).
"""
import hashlib
import json
import os
import re
import sys
import tempfile

RELAY = re.compile(r"<relay\b([^>]*)>(.*?)</relay>", re.DOTALL)
NOTE = re.compile(r"<note>(.*?)</note>", re.DOTALL)
GRANT = re.compile(
    r"^\s*(?:daytb|dmmhyh|rec\??|do as you think best|do it|yes,? do it|yes,? go ahead"
    r"|your call|up to you|you decide|go ahead|just do it)\s*[.!]?\s*$",
    re.I,
)
REVERT = re.compile(r"\bgit\s+(?:revert|reset\s+--hard|restore\s+--source)\b")

COMMON = (
    "Record the general rule in its global home in this turn (ai-config for agent rules, "
    "psw for prose rules, the repo's own instructions for repo-only rules), "
    "and name what you recorded in your reply. See run-ums-proactively.md."
)
MESSAGES = {
    "coordinator-note": (
        "[hook: remind-ums-on-trigger-events] The coordinator session's note steers or corrects "
        "this thread. A correction given to one thread is a rule for all of them. " + COMMON
    ),
    "needless-question": (
        "[hook: remind-ums-on-trigger-events] The user's reply is a grant ({quote!r}): the thread "
        "asked something it could have decided. Act on the answer, then record the decision rule "
        "that would have made the question unnecessary. " + COMMON
    ),
    "compaction": (
        "[hook: remind-ums-on-trigger-events] The context was just compacted. Learnings held only "
        "in the compacted context may be gone or reduced to a summary line. Run `ums` now over "
        "what the summary still shows (corrections, workarounds, convention failures) before "
        "continuing."
    ),
    "revert": (
        "[hook: remind-ums-on-trigger-events] This command reverts or redoes work. Once it runs, "
        "ask what decision or check would have prevented the first attempt, and record that. "
        + COMMON
    ),
}


def first_time(kind, text):
    key = hashlib.sha256(f"{kind}:{text}".encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-ums-trigger-{key}")
    if os.path.exists(sentinel):
        return False
    try:
        with open(sentinel, "w", encoding="utf-8") as fh:
            fh.write("1")
    except OSError:
        pass
    return True


def coordinator_note(prompt):
    for attrs, body in RELAY.findall(prompt):
        if 'reason="spawn"' in attrs:
            continue
        note = NOTE.search(body)
        if note and note.group(1).strip():
            return note.group(1).strip()
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        event = payload.get("hook_event_name")
        if event == "SessionStart":
            if payload.get("source") == "compact" and first_time("compaction", str(payload.get("session_id"))):
                print(MESSAGES["compaction"])
            return 0
        if event == "PreToolUse":
            inp = payload.get("tool_input")
            cmd = str(inp.get("command") or "") if isinstance(inp, dict) else ""
            if REVERT.search(cmd) and first_time("revert", cmd):
                print(json.dumps({"hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": MESSAGES["revert"],
                }}))
            return 0
        prompt = payload.get("prompt")
        if not isinstance(prompt, str):
            return 0
        note = coordinator_note(prompt)
        if note and first_time("coordinator-note", note):
            print(MESSAGES["coordinator-note"])
        elif GRANT.match(prompt) and first_time("needless-question", prompt + str(payload.get("transcript_path"))):
            print(MESSAGES["needless-question"].format(quote=prompt.strip()))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
