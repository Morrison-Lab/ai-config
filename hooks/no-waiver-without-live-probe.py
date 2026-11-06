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
the transcript holds, since the latest human turn, a probe of each route the message names (a cross-harness claim names BOTH): a
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
NOT_EXHAUSTED = re.compile(
    r"\b(?:not|isn'?t|aren'?t|never|no\s+longer)\s+(?:been\s+)?"
    r"(?:exhausted|unavailable|waived|rate[- ]limited|out\s+of\s+quota)\b", re.I)


ELLIPSIS = re.compile(r"\b(?:too|also|as\s+well|so\s+(?:is|are|does|has))\b", re.I)

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
    text = re.sub(r"\b(?:e\.g|i\.e)\.", lambda m: m.group(0).replace(".", "_"), text)
    return re.split(r"(?<=[.!?])\s+|\n+", text)


def claimed_routes(text):
    """Routes ('agy', 'opencode') that a sentence calls waived, exhausted or
    unavailable. A cross-harness claim names both. Empty when nothing is claimed."""
    routes = set()
    for s in sentences(text):
        ms = list(TARGET.finditer(s))
        # Each mention owns the text up to the next mention. One with no claim
        # word shares the claim of the mention after it ("agy and OpenCode are
        # exhausted"), so a negation attaches only to the route it follows.
        spans = [s[m.start():ms[i + 1].start() if i + 1 < len(ms) else len(s)]
                 for i, m in enumerate(ms)]
        if not any(CLAIM.search(sp) for sp in spans):
            spans = [s] * len(ms)  # the claim word comes before every mention
        # An elliptical mention ("and OpenCode is too") repeats the claim before it.
        for i in range(1, len(spans)):
            if not CLAIM.search(spans[i]) and ELLIPSIS.search(spans[i - 1] + spans[i]):
                spans[i] = spans[i - 1]
        eff = ""
        for m, sp in reversed(list(zip(ms, spans))):
            eff = sp if CLAIM.search(sp) else eff
            if not CLAIM.search(eff) or NOT_EXHAUSTED.search(eff):
                continue
            w = m.group(0).lower()
            if w in ("agy", "antigravity"):
                routes.add("agy")
            elif w == "opencode":
                routes.add("opencode")
            else:
                routes |= {"agy", "opencode"}
    return routes


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
    """Split *cmd* on unquoted `;`, `&`, `|` and newlines (quote-aware).
    A `#` that starts a word comments out the rest of its line."""
    out, cur, quote, esc, comment = [], [], None, False, False
    for ch in cmd:
        if comment:
            if ch != "\n":
                continue
            comment = False
        if esc:
            esc = False
        elif ch == "\\" and quote != "'":
            esc = True
        elif quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (not cur or cur[-1] in " \t"):
            comment = True
            continue
        elif ch in ";&|\n":
            out.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    out.append("".join(cur))
    return out

def heredoc_delims(line):
    """Delimiter words of the heredoc operators on *line*, dequoted as bash
    does: quotes anywhere in the word are removed and the pieces joined.
    Operators inside quotes, and `<<<`, do not count."""
    found, quote, i, n = [], None, 0, len(line)
    while i < n:
        ch = line[i]
        if quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch == "\\":
            i += 1
        elif ch == "#" and (i == 0 or line[i - 1] in " \t;&|"):
            break  # a comment: nothing after it is an operator
        elif line.startswith("<<<", i):
            i += 2
        elif line.startswith("<<", i):
            i += 2
            dash = line.startswith("-", i)
            i += dash
            while i < n and line[i] in " \t":
                i += 1
            word, q = [], None
            while i < n:
                c = line[i]
                if q:
                    if c == q:
                        q = None
                    else:
                        word.append(c)
                elif c in "'\"":
                    q = c
                elif c == "\\" and i + 1 < n:
                    i += 1
                    word.append(line[i])
                elif c in " \t|&;<>()":
                    break
                else:
                    word.append(c)
                i += 1
            found.append(("".join(word), dash))
            continue
        i += 1
    return found


def strip_heredocs(cmd):
    """Drop heredoc bodies (data, not commands), line by line. A body ends at
    its delimiter line, or at the end of the command when none closes it, as
    bash reads it."""
    out, pending = [], []
    for line in cmd.split("\n"):
        if pending:
            word, dash = pending[0]
            if (line.lstrip("\t") if dash else line) == word:
                pending.pop(0)
            continue
        out.append(line)
        pending = heredoc_delims(line)
    return "\n".join(out)


WRAPPERS = ("nohup", "timeout", "env", "command", "exec")
SSH_ARG_OPTS = frozenset("-B -b -c -D -E -e -F -I -i -J -L -l -m -O -o -p -Q -R -S -W -w".split())


def argvs(cmd, depth=0):
    """Yield the argv of each simple command in *cmd*, looking through
    `ssh host '...'`, `bash -c '...'`, env assignments, nohup and timeout."""
    cmd = strip_heredocs(cmd)
    for seg in segments(cmd):
        try:
            argv = shlex.split(seg)
        except ValueError:
            argv = seg.split()
        while argv and (re.match(r"[A-Za-z_]\w*=", argv[0]) or os.path.basename(argv[0]) in WRAPPERS):
            was_timeout = os.path.basename(argv[0]) == "timeout"
            was_env = os.path.basename(argv[0]) in ("env", "command", "exec")
            argv = argv[1:]
            while was_env and argv and argv[0].startswith("-"):
                argv = argv[2:] if argv[0] in ("-u", "-C", "-S") else argv[1:]
            while was_timeout and argv and argv[0].startswith("-"):
                argv = argv[2:] if argv[0] in ("-k", "-s", "--kill-after", "--signal") else argv[1:]
            if was_timeout and argv and re.match(r"\d+(\.\d+)?[smhd]?$", argv[0]):
                argv = argv[1:]
        if not argv:
            continue
        yield argv
        word = os.path.basename(argv[0])
        if depth < 3 and word in ("bash", "sh", "zsh"):
            flags = [i for i, a in enumerate(argv[1:-1], 1) if re.fullmatch(r"-[abefhiklmnpstuvxBCEHPT]*c[abefhiklmnpstuvxBCEHPT]*", a)]
            if flags:
                yield from argvs(argv[flags[0] + 1], depth + 1)
        elif depth < 3 and word == "ssh":
            rest, skip = [], False
            for a in argv[1:]:
                if skip:
                    skip = False
                elif a in SSH_ARG_OPTS:
                    skip = True
                elif not a.startswith("-"):
                    rest.append(a)
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
        if "opencode.ai" in hosts and any(x.startswith(("--data", "--json")) or re.match(r"-[A-Za-z]*[dF]", x) for x in a[1:]):
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
    need = claimed_routes(text) if text else set()
    if not need:
        return 0
    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return 0
    try:
        if need <= probes(path):
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
