#!/usr/bin/env python3
"""PreToolUse DENY: a review waiver or "quota exhausted" claim with no live probe.

ai-config#5018. Ezra, 2026-11-06: "agy is not exhausted, you cant rely on out of
date notes", "same with opencode", "cai: never rely on static notes to determine
dynamic conditions". A thread waived the cross-harness review because a
project-memory note said the agy and OpenCode quotas were exhausted. Both were
available. `shared/workflow/adversarial-self-review.md` ("Waiver when no
cross-model reviewer can run") already requires one live attempt per route.

## The condition (all must hold, or the call is DENIED)

The call posts text (a user-visible reply, or a relay message to the
coordinator or another thread; forge comments are not matched, see
ai-config#5018) in which one sentence says a reviewer, quota or tool is waived,
exhausted or unavailable AND names agy, OpenCode, a cross-harness or
cross-model reviewer.

The text is allowed only when the transcript holds, since the latest human
turn, a live probe of BOTH routes:

* agy: a Bash call whose command word is `agy`, with a first argument that
  is not `--help`, `-h` or `--version`;
* OpenCode: a Bash call whose command word is `opencode` (same exclusion),
  or a `curl` to `opencode.ai`;
* or a RELAYED probe (agy is not installed in cloud containers; it runs on
  cf463-02 through Remote Control): the result of a message-reading tool
  (`mcp__hearthbot__read_*`, `mcp__claude-code-remote__get_event|list_events`,
  `ReadNotifications`) that names the route and shows probe output.

An attempt counts whatever it returned: a quota error in the result is the
evidence the waiver needs. A version flag proves installation, not quota, so
it does not count. Fails open on any parse trouble.

Not matched: a claim made in other words, or by a tool outside the list. The
written rule covers those.
"""
import json
import os
import re
import sys

TEXT_TOOL = re.compile(
    r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message|"
    r"message_coordinator|message_thread)$")

CLAIM = re.compile(
    r"\b(?:waiv\w*|exhaust\w*|unavailable|out\s+of\s+quota|over\s+(?:its\s+|the\s+)?(?:quota|limit)|"
    r"quota\s+(?:is\s+)?(?:gone|used|spent)|rate[- ]limited)\b", re.I)
TARGET = re.compile(
    r"\b(?:agy|antigravity|opencode|cross[- ]?(?:harness|model)|reviewer)\b", re.I)
# A sentence that says the route was probed and works is not a waiver.
NOT_EXHAUSTED = re.compile(r"\b(?:not|isn'?t|aren'?t|never|no\s+longer)\s+(?:been\s+)?(?:exhausted|unavailable|waived)\b", re.I)

READ_TOOL = re.compile(
    r"^(?:mcp__hearthbot__read_\w+|mcp__claude-code-remote__(?:get_event|list_events)|ReadNotifications)$")
HELP = {"-h", "--help", "--version", "-v", "-V", "version"}
PROBE_OUTPUT = re.compile(r"probe|GoUsageLimitError|usage limit|quota|unavailable|exit\s*(?:code|status)?\s*\d|models?\b|HTTP\s*\d{3}", re.I)

REASON = (
    "[hook: no-waiver-without-live-probe] This message says a reviewer, quota or tool "
    "(agy, OpenCode, cross-harness) is exhausted, unavailable or waived, but this turn shows no live probe "
    "of both routes. A note, a memory entry or an earlier session is not evidence: quota and availability "
    "change (Ezra, 2026-11-06: \"agy is not exhausted, you cant rely on out of date notes\"). "
    "Probe now: run `agy` (a models or review call, not --version) and `opencode run -m <model> ok` or a curl to "
    "https://opencode.ai/zen/go/v1/chat/completions; agy is absent in cloud containers, so run it through a "
    "Remote Control session on cf463-02 and read the result back. Then state what the probe returned. "
    "shared/workflow/live-state-over-notes.md; adversarial-self-review.md 'Waiver when no cross-model reviewer can run'; ai-config#5018."
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
SPLIT = re.compile(r"""[\s'";&|()]+""")


def ran(tool, cmd):
    """True when *cmd* runs *tool* with an argument other than a help or version flag.

    Tokenizes the whole command, so it also sees `ssh host 'agy -p ok'` and
    `bash -c '...'`: agy runs on cf463-02 through ssh or Remote Control.
    """
    tokens = [t for t in SPLIT.split(cmd) if t]
    return any(t == tool and i + 1 < len(tokens) and tokens[i + 1] not in HELP
               for i, t in enumerate(tokens))


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
                    if ran("opencode", cmd) or ("curl" in cmd and "opencode.ai" in cmd):
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
