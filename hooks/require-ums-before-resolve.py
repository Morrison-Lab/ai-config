#!/usr/bin/env python3
"""UMS is owed before a thread is resolved, and when its PR merges.

Two entry points, one rule (AGENTS.md "Run UMS before every pause" and
"Run UMS when work is scrutinized"; ai-config#4480):

  * PreToolUse on `mcp__hearthbot__set_thread_resolved` with `resolved: true`.
    A resolved thread loses its message box, so the learnings from the thread
    must be banked BEFORE the call. If the transcript shows no explicit UMS
    action since the last user message, the FIRST attempt is denied with the
    instruction to run `ums`; the retry is allowed. A sentinel keyed on the
    transcript and the thread makes that one refusal, never a loop, because
    "nothing was learned" is a legitimate answer that no matcher can judge.

  * UserPromptSubmit carrying a GitHub event that reports a merged PR. The
    merge arrives as a wake nobody has to act on, and nothing else runs the
    wrap-up (`post-merge`: verify the merge, tidy, confirm follow-ups, UMS).
    Injects a reminder, once per distinct merge event, and never blocks.

WHAT COUNTS AS UMS
------------------
The same words the sibling reminders use (`remind-ums-after-error.UMS_WORD`)
on a Skill name, an Agent or Task prompt, or a Bash command, or a Write or
Edit under an ai-config memory or shared path. Prose saying "I ran UMS" does
not count: the tool call is the evidence.

Fails OPEN and SILENT on any parse trouble. The deny is the only blocking
path in this file, and it fires at most once per thread.
"""
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RESOLVE_TOOL = "set_thread_resolved"

EVENT = re.compile(r"<event\b([^>]*\bsource=\"github\"[^>]*)>(.*?)</event>", re.DOTALL)
MERGED = re.compile(r"\bkind=\"[^\"]*merged[^\"]*\"|\"merged\"\s*:\s*true|\"state\"\s*:\s*\"merged\"", re.I)

UMS_PATH = re.compile(r"(?:^|/)(?:memories|shared)/|(?:^|/)(?:AGENTS|CLAUDE)\.md$|ai-config")
WRITE_TOOLS = {"write", "edit", "multiedit", "notebookedit", "write_to_file", "replace_file_content"}
BASH_TOOLS = {"bash", "run_command", "execute_command", "terminal", "shell"}
AGENT_TOOLS = {"task", "agent", "invoke_subagent"}


def load_ums_word():
    spec = importlib.util.spec_from_file_location(
        "ums_after_error", os.path.join(HERE, "remind-ums-after-error.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UMS_WORD


def text_of(record):
    content = (record.get("message") or {}).get("content", record.get("content"))
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get("text") or "" for b in content
                 if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(parts) if parts else None
    return None


def ums_since_last_user_message(path, ums_word):
    """True when a UMS tool call follows the last text-bearing user record."""
    last_user, evidence = -1, -1
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for i, line in enumerate(fh):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict) or rec.get("isSidechain"):
                continue
            role = rec.get("type") or rec.get("role")
            if role == "user":
                if (text_of(rec) or "").strip():
                    last_user = i
                continue
            if role != "assistant":
                continue
            blocks = (rec.get("message") or {}).get("content") or rec.get("content") or []
            for b in blocks if isinstance(blocks, list) else []:
                if not isinstance(b, dict) or b.get("type") != "tool_use":
                    continue
                name = (b.get("name") or "").lower()
                inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                blob = ""
                if name in WRITE_TOOLS:
                    target = str(inp.get("file_path") or inp.get("path") or inp.get("TargetFile") or "")
                    if UMS_PATH.search(target):
                        evidence = i
                    continue
                if name in AGENT_TOOLS:
                    blob = str(inp.get("prompt") or "") + str(inp.get("description") or "")
                elif name in BASH_TOOLS:
                    blob = str(inp.get("command") or "")
                elif name == "skill":
                    blob = str(inp.get("skill") or "")
                if blob and ums_word.search(blob):
                    evidence = i
    return evidence > last_user


def first_time(key_text):
    key = hashlib.sha256(key_text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-ums-before-resolve-{key}")
    if os.path.exists(sentinel):
        return False
    try:
        with open(sentinel, "w", encoding="utf-8") as fh:
            fh.write("1")
    except OSError:
        pass
    return True


DENY = (
    "Run UMS before resolving this thread. A resolved thread loses its message box, "
    "so the learnings from this thread (a corrected mistake, an owner's feedback, a "
    "tool quirk, a workflow gap) have to be recorded first, in their global home "
    "(ai-config for agent rules, psw for prose rules, the repo's own instructions "
    "for repo-only rules). No UMS action appears since the last user message. "
    "Run `ums` (or `wrap-up` / `post-merge` when a PR merged) now, say in your "
    "reply what you recorded, then call set_thread_resolved again. If nothing was "
    "learned, say so in the reply and retry: this refusal happens once per thread."
)

MERGE_REMINDER = (
    "[hook: require-ums-before-resolve] A GitHub event reports a merged pull request. "
    "Run the wrap-up for it before this thread is resolved or reported done: verify "
    "the merge, tidy the branch, confirm follow-up issues are filed, and run `ums` "
    "(the `post-merge` skill does all four). A resolved thread loses its message box, "
    "so do this first."
)


def handle_pre_tool_use(payload):
    name = str(payload.get("tool_name") or "")
    inp = payload.get("tool_input")
    if not name.endswith(RESOLVE_TOOL) or not isinstance(inp, dict) or inp.get("resolved") is not True:
        return 0
    path = payload.get("transcript_path") or ""
    if not isinstance(path, str) or not os.path.isfile(path):
        return 0
    if ums_since_last_user_message(path, load_ums_word()):
        return 0
    thread = str(inp.get("thread_id") or payload.get("session_id") or "")
    if not first_time(f"{path}:{thread}"):
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": DENY,
    }}))
    return 0


def handle_prompt(payload):
    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        return 0
    for attrs, body in EVENT.findall(prompt):
        if MERGED.search(attrs) or MERGED.search(body):
            if first_time("merge:" + hashlib.sha256(body.encode()).hexdigest()):
                print(MERGE_REMINDER)
            return 0
    return 0


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        if payload.get("hook_event_name") == "UserPromptSubmit" or "prompt" in payload:
            return handle_prompt(payload)
        return handle_pre_tool_use(payload)
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
