#!/usr/bin/env python3
"""PreToolUse deny: an 11th PR on one ask with no sweep ask (ai-config#4829, #5773).

DENIES a PR create once LIMIT (default 10) PRs succeeded since the user's latest
message, unless a clause the user wrote asks to sweep (not a question, no
negation before the word) or they typed gia, gii, gip or gmd; the grant lasts until
the next user message. Only the user's
words count (user_bodies() in remind-plain-english-merge-word.py: a principal
wake message, a relay's cited user entries, never a `<note>`); a relay citing an
old message again does not reset the count. No agent-side bypass. Not seen:
creates in subagent transcripts; a slow sweep across many user messages. Fails
open on a missing transcript or helper.
"""
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_LIMIT = 10
# "sweep", or a typed backlog-run skill that opens many PRs by design.
SWEEP = re.compile(r"\bsweep(?:s|ing)?\b|(?:^|\s)/?(?:gia|gii|gip|gmd|giardia)\b", re.I)
NEGATED = re.compile(r"\b(?:don'?t|do\s+not|never|no|not|stop|without|isn'?t)\b", re.I)
SENTENCE = re.compile(r"[^.!?\n]+[.!?]*")
CLAUSE = re.compile(r"[,;:]")
GH_CREATE = re.compile(r"\bgh\s+pr\s+create\b")

REASON = (
    "[hook: no-unrequested-sweep-pr] This would be PR number {n} since the user's latest "
    "message, and no message the user wrote in this session asks for a sweep (ai-config#4829, "
    "#5773). Do not open it. If it fixes existing content nobody asked you to fix, stop: "
    "fix it when someone next edits that passage, or file one issue listing it. If the ask "
    "really needs more PRs (a stack or a split), ask the user, naming the PRs already opened; "
    "their reply resets the count, and a reply saying to sweep allows the rest. See "
    "shared/workflow/no-sweeps-by-default.md."
)


def load_user_bodies():
    path = Path(__file__).resolve().parent / "remind-plain-english-merge-word.py"
    spec = importlib.util.spec_from_file_location("_nusp_merge_word", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.user_bodies, module.typed


def is_pr_create(name, inp):
    if name == "Bash":
        return bool(GH_CREATE.search((inp or {}).get("command") or ""))
    return name.endswith("create_pull_request")


def asks_for_sweep(text, typed):
    """A non-question clause with an ask word (SWEEP) and no negation before it."""
    for sentence in SENTENCE.findall(typed(text)):
        if sentence.rstrip().endswith("?"):
            continue
        for clause in CLAUSE.split(sentence):
            hit = SWEEP.search(clause)
            if hit and not NEGATED.search(clause[:hit.start()]):
                return True
    return False


def prompt_text(content):
    """A user record's prompt text, or None for a tool-result record."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return None
    if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
        return None
    return "\n".join(b.get("text", "") for b in content
                     if isinstance(b, dict) and b.get("type") == "text")


def scan(transcript_path, user_bodies, typed):
    """(PRs opened since the user's latest message, whether the user asked to sweep)."""
    pending = []
    count, granted, seen = 0, False, set()
    with open(transcript_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            msg = rec.get("message")
            content = msg.get("content") if isinstance(msg, dict) else None
            if rec.get("type") == "assistant" and isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_use" \
                            and is_pr_create(b.get("name") or "", b.get("input")):
                        pending.append(b.get("id"))
                continue
            if rec.get("type") != "user":
                continue
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result" \
                            and b.get("tool_use_id") in pending:
                        pending.remove(b.get("tool_use_id"))
                        if not b.get("is_error"):
                            count += 1
            if rec.get("isMeta") or rec.get("isSidechain") or rec.get("isCompactSummary"):
                continue
            text = prompt_text(content)
            if not text:
                continue
            relayed = "<coordinator-relay" in text  # a relay may cite an old message again
            bodies = [b for b in user_bodies(text) if b.strip() and not (relayed and b.strip() in seen)]
            if not bodies:
                continue
            seen.update(b.strip() for b in bodies)
            count = 0
            granted = any(asks_for_sweep(b, typed) for b in bodies)  # lasts until the next message
    return count, granted


def decide(payload):
    name = payload.get("tool_name") or ""
    if not is_pr_create(name, payload.get("tool_input")):
        return None
    path = payload.get("transcript_path") or payload.get("transcriptPath")
    if not isinstance(path, str) or not os.path.isfile(path):
        return None
    try:
        limit = int(os.environ.get("AI_CONFIG_SWEEP_PR_LIMIT") or DEFAULT_LIMIT)
    except ValueError:
        limit = DEFAULT_LIMIT
    user_bodies, typed = load_user_bodies()
    count, granted = scan(path, user_bodies, typed)
    if granted or count < limit:
        return None
    return REASON.format(n=count + 1)


def main():
    try:
        payload = json.load(sys.stdin)
        reason = decide(payload) if isinstance(payload, dict) else None
    except Exception:
        return 0
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
