#!/usr/bin/env python3
"""PreToolUse deny: do not hand a denied action to another session (ai-config#5914).

`shared/workflow/ask-for-manual-approval.md` says a classifier-denied action is
reported, not handed to another session to run. On 2026-11-18 a parent session
did exactly that: the classifier denied a child session's `opencode run` and
two merge calls, and the parent then started a second session whose opening
prompt told it to make the same attempt (ai-config#5913 records the
recurrence). The parent's own transcript held no denial for the action, so a
hook keyed on the parent's own denials (`block-redo-denied-write-via-other-tool.py`)
could not fire. The parent saw the denials only inside a read of the child.

WHAT IT DOES
------------
Matched on `mcp__claude-code-remote__create_session` and `__send_message`
(and the `Claude_Code_Remote` spelling). It reads the transcript for results of
`list_events`, `get_event` and `get_session`, and records a denial from either

  * a `permission_denials` array (each entry: the denied tool and its input), or
  * a `tool_result` carrying "denied by the Claude Code auto mode classifier",
    keyed through its `tool_use_id` to the `tool_use` in the same read.

Each denial yields needles: every string input of 20 or more characters, or
12 or more with a space (the shell command, a body), compared with whitespace collapsed. An
input with no such string, such as a merge call whose input is owner, repo and
a number, yields the tool name together with every scalar value, all of which
must appear. The new `prompt` (create_session) or `message` (send_message) is
DENIED when it contains every part of a needle verbatim.

The denial is released by a typed user message after the read that names the
action and the session: the session id (the denied child's, which is also the
target of a `send_message`) and the action's words (the command's first two
words, or the tool's name). Only a user-role text block counts. A system
reminder, a relayed message, a `<cited>` entry from another author and the
new prompt itself (which may quote the user) do not.

OPEN QUESTIONS, AS DECIDED
--------------------------
  * A verbatim match is narrow: a prompt that describes the action without
    quoting it passes. Accepted, because a looser match would deny honest
    reports. The fix for a paraphrase is the rule text, not this hook.
  * A seeded opening prompt that carries the user's earlier words is not a
    user message: only a user-role block in the transcript is read.
  * The child's own session is not readable from here, so the denial is read
    from the parent's view of it, the only place the parent can see it.

Fails OPEN and SILENT on unreadable input, a missing transcript, an unparseable
read result or a result with no denial.
"""
import json
import os
import re
import sys

READ_TOOLS = re.compile(
    r"claude[-_]code[-_]remote__(?:list_events|get_event|get_session)$",
    re.IGNORECASE)
SEND_FIELDS = {"create_session": "prompt", "send_message": "message"}
CLASSIFIER_MARKER = "denied by the Claude Code auto mode classifier"
MIN_NEEDLE = 20
MIN_PHRASE = 12
RX_SESSION = re.compile(r"session_[A-Za-z0-9]+")
RX_STRIP = re.compile(
    r"<system-reminder>.*?</system-reminder>"
    r"|<note>.*?</note>"
    r"|<cited\b[^>]*author=\"(?!user\")[^\"]*\"[^>]*>.*?</cited>"
    r"|<message\b[^>]*trust=\"relay\"[^>]*>.*?</message>",
    re.IGNORECASE | re.DOTALL)

# realpath, not abspath: the plugin registers hooks through a symlinked path
# (scripts/check-hook-file-resolution.py).
MESSAGE = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                       "messages", "no-handoff-of-denied-action.md")
FALLBACK = ("[hook: no-handoff-of-denied-action] The classifier denied {what} "
            "in session {sid}; report it, do not hand it to another session "
            "(ai-config#5914).")


def _reason_template():
    try:
        with open(MESSAGE, encoding="utf-8") as fh:
            return " ".join(fh.read().split())
    except OSError:
        return FALLBACK


def _ws(text):
    return " ".join(str(text).split())


def _blocks(rec):
    msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
    content = msg.get("content", rec.get("content"))
    return content if isinstance(content, list) else []


def _text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            c.get("text") or "" for c in content if isinstance(c, dict))
    return ""


def _json_of(text):
    """Parse *text* as JSON, or from its first brace or bracket; else None."""
    for start in (0, *[i for i in (text.find("{"), text.find("[")) if i > 0]):
        try:
            return json.loads(text[start:])
        except Exception:
            continue
    return None


def _walk(node):
    """Yield every dict inside *node*."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _scalars(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from _scalars(v)
    elif isinstance(value, list):
        for v in value:
            yield from _scalars(v)
    elif isinstance(value, (str, int)) and not isinstance(value, bool):
        yield value


def denials_in(payload):
    """[(tool, input dict)] for every recorded denial in a parsed read."""
    uses = {d.get("id"): d for d in _walk(payload)
            if d.get("type") == "tool_use" and d.get("id")}
    found = []
    for d in _walk(payload):
        for item in d.get("permission_denials") or []:
            if isinstance(item, dict):
                tool = item.get("tool_name") or item.get("toolName") or ""
                inp = item.get("tool_input") or item.get("toolInput")
                if tool and isinstance(inp, dict):
                    found.append((tool, inp))
        if d.get("type") == "tool_result" and \
                CLASSIFIER_MARKER.lower() in _text_of(
                    d.get("content")).lower():
            use = uses.get(d.get("tool_use_id"))
            if use and isinstance(use.get("input"), dict):
                found.append((use.get("name") or "", use["input"]))
    return found


def needles(tool, inp):
    """The verbatim parts a prompt must all contain to carry this denial."""
    long_strings = [_ws(v) for v in _scalars(inp)
                    if isinstance(v, str) and (
                        len(_ws(v)) >= MIN_NEEDLE
                        or (" " in _ws(v) and len(_ws(v)) >= MIN_PHRASE))]
    if long_strings:
        return long_strings, "command or input"
    parts = [tool] + [str(v) for v in _scalars(inp)]
    return [p for p in parts if p], "tool call"


def carries(text, parts):
    """True when *text* contains every part, numbers on digit boundaries."""
    flat = _ws(text)
    for part in parts:
        if part.isdigit():
            if not re.search(rf"(?<!\d){part}(?!\d)", flat):
                return False
        elif part not in flat:
            return False
    return True


def action_words(tool, inp):
    """Regex for the words that name the denied action."""
    for key in ("command", "cmd"):
        cmd = inp.get(key)
        if isinstance(cmd, str) and cmd.split():
            words = cmd.split()[:2]
            return r"\s+".join(re.escape(w) for w in words)
    last = tool.rsplit("__", 1)[-1]
    return r"[\s_]+".join(re.escape(w) for w in last.split("_") if w)


def scan(path):
    """Return (reads, users): reads [(index, session ids, denials)], users
    [(index, text)] of user-role typed text."""
    reads, users, calls = [], [], {}
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for i, line in enumerate(fh):
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if not isinstance(rec, dict) or rec.get("isSidechain"):
                continue
            role = rec.get("type") or (rec.get("message") or {}).get("role")
            msg = rec.get("message") if isinstance(rec.get("message"),
                                                   dict) else {}
            content = msg.get("content", rec.get("content"))
            if role in ("user", "USER_INPUT") and isinstance(content, str):
                users.append((i, RX_STRIP.sub(" ", content)))
                continue
            for b in _blocks(rec):
                if not isinstance(b, dict):
                    continue
                kind = b.get("type")
                if kind == "tool_use" and READ_TOOLS.search(b.get("name") or ""):
                    calls[b.get("id")] = b.get("input") or {}
                elif kind == "tool_result" and b.get("tool_use_id") in calls:
                    text = _text_of(b.get("content"))
                    payload = _json_of(text)
                    if payload is None:
                        continue
                    found = denials_in(payload)
                    if not found:
                        continue
                    arg = calls[b.get("tool_use_id")]
                    sids = {str(arg.get("session_id") or "")} - {""}
                    sids |= {m for m in RX_SESSION.findall(text)} \
                        if not sids else set()
                    reads.append((i, sids, found))
                elif kind == "text" and role in ("user", "USER_INPUT"):
                    users.append((i, RX_STRIP.sub(" ", b.get("text") or "")))
    return reads, users


def released(at, sids, tool, inp, users, target_sid):
    """True when a typed user message after *at* names the action and session."""
    rx_action = re.compile(action_words(tool, inp), re.IGNORECASE)
    for i, text in users:
        if i <= at or not rx_action.search(text):
            continue
        named = set(RX_SESSION.findall(text))
        if (sids & named) or (target_sid and target_sid in named):
            return True
    return False


def deny(reason):
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason}}


def decide(payload):
    """The deny dict for *payload*, or None."""
    tool = payload.get("tool_name") or payload.get("toolName") or ""
    inp = payload.get("tool_input")
    if not isinstance(inp, dict):
        inp = payload.get("toolInput")
    if not isinstance(inp, dict):
        return None
    field = SEND_FIELDS.get(tool.rsplit("__", 1)[-1])
    if field is None or not re.search(r"claude[-_]code[-_]remote__", tool,
                                      re.IGNORECASE):
        return None
    text = inp.get(field)
    path = payload.get("transcript_path") or ""
    if not isinstance(text, str) or not path or not os.path.isfile(path):
        return None
    reads, users = scan(path)
    target_sid = str(inp.get("session_id") or "")
    for at, sids, found in reads:
        for dtool, dinp in found:
            parts, kind = needles(dtool, dinp)
            if not carries(text, parts):
                continue
            if released(at, sids, dtool, dinp, users, target_sid):
                continue
            sid = sorted(sids)[0] if sids else "another session"
            what = f"`{dtool}`" if dtool else "an action"
            return deny(_reason_template().format(
                what=what, sid=sid, tool=tool, kind=kind,
                action=action_words(dtool, dinp).replace("\\s+", " ")
                .replace("[\\s_]+", " ").replace("\\", "")))
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        out = decide(payload)
    except Exception:
        return 0
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
