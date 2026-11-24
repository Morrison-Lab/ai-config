#!/usr/bin/env python3
"""Guard: don't call a PR ready for review before its preview has deployed.

Ezra, 2026-11-23: "cai: don't tell me a PR is ready for review when its
preview isn't finished deploying". A project thread told him lds#3130 was
ready for his review while the "Quarto Preview Deploy" run was still in
progress, so the PR carried no preview link and he had to ask where it was.
For a repo that publishes a preview, the rendered preview is what he reviews;
a PR without one is not ready for him yet.

The condition is decidable from the transcript:

    the reply says a named PR is ready for review or merge
    AND no tool result since the last user turn, and after the last push,
        shows that PR's deployed preview

Evidence of a deployed preview is a successful tool result whose text holds a
preview URL for that PR number (`pr-preview/pr-N`, `previews/pr-N`), which the
deploy workflow posts only once the deploy finishes. A memory note or an
earlier turn does not count, and neither does evidence older than a push,
since a push starts a new deploy.

Escapes, each an honest statement rather than a claim of readiness:

  * the sentence is negated ("not ready for review yet");
  * the sentence makes readiness wait on the preview ("ready once the preview
    deploys", "after the preview finishes");
  * the message says the repo publishes no preview ("this repo has no
    preview").

Text in code spans, quotes and blockquotes is skipped. Runs at PreToolUse on
the hearthbot reply tools and at Stop, like no-unfetched-pr-state-claim.py.
Fires at most once per distinct text and twice per user turn, and fails OPEN
on any parse trouble.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

_LIB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib"
)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

try:
    from transcript_meta import is_real_user_turn as _is_user_turn
    from sibling import load_sibling

    _offer = load_sibling(__file__, "no-offer-to-file.py", "no_offer_to_file", required=True)
    last_assistant_text = _offer.last_assistant_text
    sentence_around = _offer.sentence_around
    strip_code = _offer.strip_code
except Exception:
    sys.exit(0)

REPLY_TOOL_RX = re.compile(
    r"^mcp__hearthbot__(reply|post_message|update_message|edit_message)$"
)
MAX_FIRES_PER_TURN = 2

_WHO = r"(your|ezra'?s|the user'?s|the|a|human|their)"
READY_RX = re.compile(
    r"\bready (for (" + _WHO + r" )?(review|merge|merge words?|sign-?off|look)"
    r"|for (you|ezra|the user) to (review|merge|look)"
    r"|to (be )?(reviewed|merged?))\b",
    re.I,
)
PR_CONTEXT_RX = re.compile(
    r"\b(PRs?|pull requests?|MRs?|merge requests?)\b|#\d+|/pull/\d+", re.I
)
REF_RX = re.compile(r"#(\d+)\b|/pull/(\d+)\b|\b(?:PR|pull request) (\d+)\b", re.I)
NEGATED_BEFORE_RX = re.compile(
    r"\b(not|isn'?t|aren'?t|wasn'?t|no longer|nothing|none|never)\b[^.!?,;:\n]{0,20}$",
    re.I,
)
WAITS_ON_PREVIEW_RX = re.compile(
    r"\b(once|after|when|until|as soon as)\b[^.!?\n]{0,40}\bpreview", re.I
)
NO_PREVIEW_RX = re.compile(
    r"\b(no|without (a|any)) (PR )?previews?\b"
    r"|\b(has|have|publish(es)?|builds?|deploys?) no (PR )?previews?\b"
    r"|\b(doesn'?t|does not|don'?t|do not) (have|publish|build|deploy) (a |any )?(PR )?previews?\b",
    re.I,
)
QUOTED_RX = re.compile(r'"[^"\n]*"|\u201c[^\u201d\n]*\u201d|^[ \t]*>.*$', re.M)

PREVIEW_URL_RX = re.compile(r"\bpr-?previews?/pr-?(\d+)\b|\bpreviews?/pr-?(\d+)\b", re.I)
PUSH_CMD_RX = re.compile(r"\bgit\b[^|;&\n]*\bpush\b")
PUSH_TOOL_RX = re.compile(r"^mcp__github__(push_files|create_or_update_file|delete_file)$")


def _blocks(m):
    blocks = (m.get("message") or {}).get("content") or m.get("content")
    return blocks if isinstance(blocks, list) else []


def _result_text(block):
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            str(c.get("text") or "") for c in content if isinstance(c, dict)
        )
    return ""


def _is_push(block):
    name = str(block.get("name") or "")
    if PUSH_TOOL_RX.match(name):
        return True
    inp = block.get("input") if isinstance(block.get("input"), dict) else {}
    cmd = inp.get("command")
    return isinstance(cmd, str) and bool(PUSH_CMD_RX.search(cmd))


def turn_state(path):
    """(deployed PR numbers, whether a reply went through, the turn's index).

    Deployed numbers come from successful tool results since the last user
    turn; a push since then clears every number seen before it.
    """
    deployed, replies, errored, pushes = set(), set(), set(), set()
    turn = 0
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for idx, line in enumerate(fh):
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if not isinstance(m, dict):
                    continue
                if _is_user_turn(m):
                    deployed, replies, errored, pushes, turn = set(), set(), set(), set(), idx
                for b in _blocks(m):
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use":
                        if REPLY_TOOL_RX.match(str(b.get("name") or "")):
                            replies.add(b.get("id"))
                        elif _is_push(b):
                            pushes.add(b.get("id"))
                    elif b.get("type") == "tool_result":
                        tid = b.get("tool_use_id")
                        if b.get("is_error"):
                            errored.add(tid)
                            continue
                        if tid in pushes:
                            deployed = set()
                            continue
                        for u in PREVIEW_URL_RX.finditer(_result_text(b)):
                            deployed.add(u.group(1) or u.group(2))
    except Exception:
        pass
    replied = any(r not in errored for r in replies)
    return deployed, replied, turn


def find_claim(prose, deployed):
    """(phrase, missing numbers) for the first unsupported readiness claim, or None."""
    if NO_PREVIEW_RX.search(prose):
        return None
    for m in READY_RX.finditer(prose):
        if NEGATED_BEFORE_RX.search(prose[max(0, m.start() - 30):m.start()]):
            continue
        sentence = sentence_around(prose, m.start(), m.end())
        if not PR_CONTEXT_RX.search(sentence):
            continue
        if WAITS_ON_PREVIEW_RX.search(sentence):
            continue
        named = {next(g for g in r.groups() if g) for r in REF_RX.finditer(sentence)}
        if named:
            missing = sorted((n for n in named if n not in deployed), key=int)
            if not missing:
                continue
            return m.group(0), missing
        if deployed:
            continue
        return m.group(0), []
    return None


def reason_for(phrase, missing):
    which = ", ".join("#" + n for n in missing) if missing else "the PR it names"
    return (
        "[hook: no-ready-before-preview] This message says a PR is ready "
        f"(\"{phrase.strip()}\"), and nothing since the last user turn, or since "
        f"the last push, shows the deployed preview of {which}. Ezra, "
        "2026-11-23: \"don't tell me a PR is ready for review when its preview "
        "isn't finished deploying\".\n\n"
        "Read the PR's comments or its preview deploy run now. When the preview "
        "comment is there, link the preview in the reply. When the deploy is "
        "still running, say so and that the PR will be ready once the preview "
        "deploys, and set a wake to check it. If the repo publishes no preview, "
        "say that in the message."
    )


def _may_fire(text, path, turn):
    scope = hashlib.sha256(f"{path}\0{turn}".encode()).hexdigest()[:16]
    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    ledger = os.path.join(tempfile.gettempdir(), f".claude-ready-preview-guard-{scope}")
    try:
        with open(ledger, encoding="utf-8") as fh:
            seen = fh.read().split()
    except Exception:
        seen = []
    if key in seen or len(seen) >= MAX_FIRES_PER_TURN:
        return False
    try:
        with open(ledger, "a", encoding="utf-8") as fh:
            fh.write(key + "\n")
    except Exception:
        pass
    return True


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    path = payload.get("transcript_path") or ""
    tool_name = payload.get("tool_name")

    if tool_name is not None:
        if not REPLY_TOOL_RX.match(str(tool_name)):
            return 0
        inp = payload.get("tool_input")
        text = inp.get("text") if isinstance(inp, dict) else None
        if not isinstance(text, str) or not text.strip():
            return 0
        deployed, _, turn = turn_state(path)
    else:
        text = last_assistant_text(path)
        if not text:
            return 0
        deployed, replied, turn = turn_state(path)
        if replied:
            return 0

    prose = QUOTED_RX.sub(" ", strip_code(text))
    hit = find_claim(prose, deployed)
    if not hit or not _may_fire(text, path, turn):
        return 0
    reason = reason_for(*hit)
    if tool_name is not None:
        out = {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}
    else:
        out = {"decision": "block", "reason": reason}
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
