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
  ums-word           UserPromptSubmit: the user wrote the word "ums" (ai-config#5162).
                     The reminder is inject-only because no deny can decide
                     whether a lesson was persisted; a correction has no
                     lexical signature, so AGENTS.md carries that half.
  compaction         SessionStart (source compact): learnings held only in
                     the compacted context may be summarized away.
  revert             PreToolUse Bash running `git revert`, `git reset --hard`
                     or `git restore --source`: work was undone or redone.
  tool-error         PreToolUse, any tool (ai-config#5630): the transcript's
                     most recent tool result is an error (a non-zero exit, a
                     hook denial, an InputValidationError, an MCP error), so
                     this call is usually its revision. Ezra, 2026-11-13: "any
                     time you format a command incorrectly and need to revise
                     it, run ums?", then "in other words, any time a command
                     produces an error?". Inject-only, because a deny would
                     block the retry that fixes the error. EXPECTED_ERRORS
                     lists results that are not mistakes (a grep with no
                     match, a false test, a diff, a call marked expect-fail).

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

# Errors that are not mistakes: (command regex, error-text regex) pairs. When
# both search-match the failed call's command (its input, for a non-Bash tool)
# and its error text, the tool-error reminder is skipped. Ezra said "daytb" on
# which expected non-zero results to exempt (2026-11-13, ai-config#5630); edit
# this list to change the answer.
_EXIT_1_ONLY = r"\A\s*Exit code 1\s*\Z"
EXPECTED_ERRORS = (
    # A search that finds nothing: grep, rg or git grep, exit 1, no output.
    (r"\A\s*(?:git\s+grep|grep|egrep|fgrep|rg)\b", _EXIT_1_ONLY),
    # A test whose answer is "no": test, [ or [[, exit 1.
    (r"\A\s*(?:test|\[\[?)\s", r"\A\s*Exit code 1\b"),
    # diff, cmp or git diff --exit-code reporting a difference: exit 1.
    (r"\A\s*(?:diff|cmp)\b|\bgit\s+diff\b.*--(?:exit-code|quiet)\b", r"\A\s*Exit code 1\b"),
    # A command the agent marked as expected to fail: an EXPECT_FAIL=1 prefix
    # or an "# expect-fail" comment.
    (r"\bEXPECT_FAIL=1\b|#\s*expect(?:ed)?[- ]fail", r""),
)

# Read only the end of a long transcript: the newest tool result is all we need.
TAIL_BYTES = 400_000

COMMON = (
    "Record the general rule in its global home in this turn (ai-config for agent rules, "
    "psw for prose rules, the repo's own instructions for repo-only rules), "
    "and name what you recorded in your reply. See run-ums-proactively.md."
)
BOTH_PLACES = (
    " Persist it in the same turn in BOTH the project memory store AND ai-config and/or the "
    "project repo (Ezra, 2026-11-09, ai-config#5162): every 'ums', every correction of you, "
    "and every correction you make to yourself."
)
UMS_WORD = re.compile(r"(?<![\w/:.-])ums(?![\w-])", re.I)
MESSAGES = {
    "coordinator-note": (
        "[hook: remind-ums-on-trigger-events] The coordinator session's note steers or corrects "
        "this thread. A correction given to one thread is a rule for all of them. " + COMMON
        + BOTH_PLACES
    ),
    "ums-word": (
        "[hook: remind-ums-on-trigger-events] The user wrote 'ums'. Run the pass now, before "
        "anything else." + BOTH_PLACES
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
    "tool-error": (
        "[hook: remind-ums-on-trigger-events] The previous {tool} call returned an error "
        "({error!r}). Ezra, 2026-11-13: any command that produces an error owes a UMS pass. "
        "Once the revised call works, record what caused the error and the form that works, "
        "so the next session writes it right the first time. " + COMMON
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


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(b.get("text", "")) for b in content if isinstance(b, dict))
    return ""


def last_tool_error(transcript_path):
    """(tool_use_id, tool name, input, error text) when the newest tool result is an error."""
    with open(transcript_path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        fh.seek(max(0, fh.tell() - TAIL_BYTES))
        lines = fh.read().decode("utf-8", errors="replace").splitlines()
    uses = {}
    last = None
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        content = (entry.get("message") or {}).get("content") if isinstance(entry, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                uses[block.get("id")] = (block.get("name"), block.get("input"))
            elif block.get("type") == "tool_result":
                last = block
    if not last or not last.get("is_error"):
        return None
    use_id = last.get("tool_use_id")
    name, inp = uses.get(use_id, ("a tool", None))
    return use_id, name, inp, _text(last.get("content"))


def tool_error_reminder(payload):
    path = payload.get("transcript_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return None
    found = last_tool_error(path)
    if not found:
        return None
    use_id, name, inp, error = found
    command = str(inp.get("command") or "") if isinstance(inp, dict) else json.dumps(inp or "")
    if any(re.search(cmd_re, command) and re.search(err_re, error) for cmd_re, err_re in EXPECTED_ERRORS):
        return None
    if not first_time("tool-error", f"{path}:{use_id}"):
        return None
    # "Exit code N" alone says nothing about the cause, so quote the next line too.
    shown = [ln.strip() for ln in error.splitlines() if ln.strip()][:2] or ["error"]
    if not shown[0].startswith("Exit code"):
        shown = shown[:1]
    return MESSAGES["tool-error"].format(tool=name, error=": ".join(shown)[:200])


def coordinator_note(prompt):
    for attrs, body in RELAY.findall(prompt):
        if 'reason="spawn"' in attrs:
            continue
        note = NOTE.search(body)
        if note and note.group(1).strip():
            return note.group(1).strip()
    return None


def main() -> int:
    # A prompt or a relayed coordinator note can hold curly quotes, which a
    # cp1252 console can neither read from a UTF-8 payload nor write for a
    # UTF-8 reader (ai-config#5462). Read stdin and write stdout as UTF-8
    # whatever the console says.
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
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
            notes = []
            if REVERT.search(cmd) and first_time("revert", cmd):
                notes.append(MESSAGES["revert"])
            error_note = tool_error_reminder(payload)
            if error_note:
                notes.append(error_note)
            if notes:
                print(json.dumps({"hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": "\n\n".join(notes),
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
        elif UMS_WORD.search(prompt) and first_time("ums-word", prompt):
            print(MESSAGES["ums-word"])
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
