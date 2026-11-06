#!/usr/bin/env python3
"""PreToolUse DENY: a review waiver or "quota exhausted" claim with no live probe.

ai-config#5018. Ezra, 2026-11-06: "agy is not exhausted, you cant rely on out of
date notes", "same with opencode", "cai: never rely on static notes to determine
dynamic conditions". A thread waived the cross-harness review because a
project-memory note said the agy and OpenCode quotas were exhausted. Both were
available. `shared/workflow/adversarial-self-review.md` ("Waiver when no
cross-model reviewer can run") already requires one live attempt per route.

Denies a hearthbot reply or relay message with a sentence that calls agy,
OpenCode or a cross-harness reviewer waived, exhausted or unavailable, unless
the transcript holds, since the latest human turn, a probe of BOTH routes: a
Bash call running `agy` or `opencode` with an argument other than a help or
version flag (also inside `ssh host '...'`), a curl to opencode.ai, or a
message-reading tool result relaying a probe run elsewhere (agy is absent in
cloud containers). A probe counts whatever it returned. Forge comments and
claims in other words are not matched; the written rule covers them. Fails
open on any parse trouble.
"""
import json
import os
import re
import shlex
import sys
import urllib.parse

TEXT_TOOL = re.compile(
    r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message|"
    r"message_coordinator|message_thread)$")

CLAIM = re.compile(
    r"\b(?:waiv\w*|exhaust\w*|unavailable|out\s+of\s+quota|over\s+(?:its\s+|the\s+)?(?:quota|limit)|"
    r"quota\s+(?:is\s+)?(?:gone|used|spent)|rate[- ]limited)\b", re.I)
TARGET = re.compile(
    r"\b(?:agy|antigravity|opencode|cross[- ]?(?:harness|model))\b", re.I)
# A sentence that says the route was probed and works is not a waiver.
NOT_EXHAUSTED = re.compile(r"\b(?:not|isn'?t|aren'?t|never|no\s+longer)\s+(?:been\s+)?(?:exhausted|unavailable|waived)\b", re.I)

READ_TOOL = re.compile(
    r"^(?:mcp__hearthbot__read_\w+|mcp__claude-code-remote__(?:get_event|list_events)|ReadNotifications)$")
PROBE_OUTPUT = re.compile(r"probe|GoUsageLimitError|usage limit|quota|unavailable|exit\s*(?:code|status)?\s*\d|models?\b|HTTP\s*\d{3}", re.I)

REASON = (
    "[hook: no-waiver-without-live-probe] This message calls agy, OpenCode or a cross-harness reviewer "
    "exhausted, unavailable or waived, but this turn shows no live probe of both routes. A note or an earlier "
    "session is not evidence (Ezra, 2026-11-06: \"agy is not exhausted, you cant rely on out of date notes\"). "
    "Probe now: `agy` (a models or review call, not --version) through Remote Control, since agy is absent in cloud "
    "containers, and `opencode run -m <model> ok` or a curl to https://opencode.ai/zen/go/v1/chat/completions. "
    "Then state what each returned. shared/workflow/live-state-over-notes.md; ai-config#5018."
)


def sentences(text):
    return re.split(r"(?<=[.!?])\s+|\n+", text)


def claims_unavailable(text):
    return any(CLAIM.search(s) and TARGET.search(s) and not NOT_EXHAUSTED.search(s)
               for s in sentences(text))


def blocks(rec):
    msg = rec.get("message") if isinstance(rec, dict) else None
    content = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content or [] if isinstance(b, dict)]


def is_human_turn(rec):
    if rec.get("type") != "user" or rec.get("isSidechain"):
        return False
    bs = blocks(rec)
    return bool(bs) and not any(b.get("type") == "tool_result" for b in bs)


HELP = frozenset({"-h", "-v", "-V", "--help", "--version", "version"})

def segments(cmd):
    """Split *cmd* on unquoted `;`, `&`, `|` and newlines (quote-aware)."""
    out, cur, quote, esc = [], [], None, False
    for ch in cmd:
        if esc:
            esc = False
        elif ch == "\\" and quote != "'":
            esc = True
        elif quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch in ";&|\n":
            out.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    out.append("".join(cur))
    return out

HEREDOC_OP = re.compile(r"(?<!<)<<(?!<)-?[ \t]*(['\"]?)([^\s'\"<>|;&]*)\1")


def strip_heredocs(cmd):
    """Drop heredoc bodies (data, not commands), line by line. A body ends at
    its delimiter line, or at the end of the command when none closes it, as
    bash reads it."""
    out, pending = [], []
    for line in cmd.split("\n"):
        if pending:
            if line.strip(" \t") == pending[0]:
                pending.pop(0)
            continue
        out.append(line)
        pending = [m.group(2) for m in HEREDOC_OP.finditer(line)]
    return "\n".join(out)


def argvs(cmd, depth=0):
    """Yield the argv of each simple command in *cmd*, looking through
    `ssh host '...'`, `bash -c '...'`, env assignments, nohup and timeout."""
    cmd = strip_heredocs(cmd)
    for seg in segments(cmd):
        try:
            argv = shlex.split(seg)
        except ValueError:
            argv = seg.split()
        while argv and (re.match(r"[A-Za-z_]\w*=", argv[0]) or os.path.basename(argv[0]) in ("nohup", "timeout")):
            was_timeout = os.path.basename(argv[0]) == "timeout"
            argv = argv[1:]
            if was_timeout and argv and re.match(r"\d+[smhd]?$", argv[0]):
                argv = argv[1:]
        if not argv:
            continue
        yield argv
        word = os.path.basename(argv[0])
        if depth < 3 and word in ("bash", "sh", "zsh") and "-c" in argv[:-1]:
            yield from argvs(argv[argv.index("-c") + 1], depth + 1)
        elif depth < 3 and word == "ssh":
            rest = [a for a in argv[1:] if not a.startswith("-")]
            if len(rest) > 1:
                yield from argvs(" ".join(rest[1:]), depth + 1)


def ran(tool, cmd):
    """True when *cmd* runs *tool* as a command with an argument other than a
    help or version flag. Mentions in `echo`, `grep` and the like do not count."""
    return any(os.path.basename(a[0]) == tool and len(a) > 1 and a[1] not in HELP for a in argvs(cmd))


def curled(cmd):
    """True when *cmd* POSTs a payload to opencode.ai."""
    for a in argvs(cmd):
        if os.path.basename(a[0]) != "curl":
            continue
        hosts = {urllib.parse.urlsplit(x).netloc.split(":")[0].lower() for x in a[1:] if "://" in x}
        if "opencode.ai" in hosts and any(x.startswith(("-d", "--data", "--json", "-F")) for x in a[1:]):
            return True
    return False


def text_of(block):
    c = block.get("content")
    if isinstance(c, str):
        return c
    return " ".join(x.get("text", "") for x in c or [] if isinstance(x, dict))


def probes(path):
    """Set of routes ('agy', 'opencode') probed since the latest human turn."""
    recs = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                recs.append(json.loads(line))
            except ValueError:
                continue
    start = 0
    for i, rec in enumerate(recs):
        if isinstance(rec, dict) and is_human_turn(rec):
            start = i
    found = set()
    names = {}
    for rec in recs[start:]:
        if not isinstance(rec, dict) or rec.get("isSidechain"):
            continue
        for b in blocks(rec):
            if b.get("type") == "tool_use":
                names[b.get("id")] = b.get("name") or ""
                cmd = (b.get("input") or {}).get("command")
                if isinstance(cmd, str):
                    if ran("agy", cmd):
                        found.add("agy")
                    if ran("opencode", cmd) or curled(cmd):
                        found.add("opencode")
            elif b.get("type") == "tool_result" and READ_TOOL.match(names.get(b.get("tool_use_id"), "")):
                t = text_of(b)
                if PROBE_OUTPUT.search(t):
                    if re.search(r"\bagy\b", t, re.I):
                        found.add("agy")
                    if re.search(r"opencode", t, re.I):
                        found.add("opencode")
    return found


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    if not isinstance(payload, dict) or not TEXT_TOOL.match(str(payload.get("tool_name") or "")):
        return 0
    ti = payload.get("tool_input")
    if not isinstance(ti, dict):
        return 0
    text = " \n".join(str(ti[k]) for k in ("text", "body", "message") if isinstance(ti.get(k), str))
    if not text or not claims_unavailable(text):
        return 0
    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return 0
    try:
        if {"agy", "opencode"} <= probes(path):
            return 0
    except Exception:
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": REASON}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
