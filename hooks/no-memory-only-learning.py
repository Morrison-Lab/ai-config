#!/usr/bin/env python3
"""Stop: a turn that writes project memory must also reach a repo.

ai-config#4698; shared/workflow/lab-operating-rules.md. Ezra, 2026-10-23: "I
hope you're recording everything we learn in one of our repos". Project memory
is not versioned, reviewed or visible to other agents' hooks, so a learning
recorded only there is lost to everything but the next session that happens to
read it ("memory alone isn't enough").

At Stop, look at the assistant records since the latest human message. If one
wrote or edited a file under a memory directory (a path containing `/memory/`,
or named MEMORY.md) and nothing in the same turn reached a repo, block once
per message. "Reached a repo" means any of:

  * a tool call that names `hooks/<script>.py`, `hooks.json`, a `shared/`
    markdown fragment, AGENTS.md, CLAUDE.md, `check-*/`, or `.github/`;
  * a GitHub tool call that files an issue, opens a PR or pushes files;
  * a line of its own starting "Mechanism: <issue or PR URL>"; or
  * a plain statement that the fact is not repo-worthy, with the reason
    ("memory only: ...").

Fails OPEN and SILENT on any parse trouble.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

MEMORY_PATH = re.compile(r"(?:/memory/|(?:^|/)MEMORY\.md$)", re.I)
REPO_WORK = re.compile(
    r"hooks/[\w-]+\.py|hooks\.json|shared/[\w/.-]+\.md|AGENTS\.md|CLAUDE\.md"
    r"|check-[\w-]+/|\.github/|mcp__github__(?:issue_write|create_pull_request|push_files|create_or_update_file)",
    re.I,
)
MECHANISM_LINE = re.compile(r"^\s*Mechanism:\s*https?://\S+", re.M)
MEMORY_ONLY_REASON = re.compile(r"\bmemory only:\s*\S", re.I)
FILE_TOOLS = {"Write", "Edit", "NotebookEdit"}


def human_text(record):
    if (record.get("type") or record.get("role")) != "user":
        return None
    blocks = (record.get("message") or {}).get("content")
    if blocks is None:
        blocks = record.get("content")
    if isinstance(blocks, str):
        return blocks
    if not isinstance(blocks, list):
        return None
    if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in blocks):
        return None
    parts = [b.get("text") or "" for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
    return "\n".join(parts) if parts else None


def owed(path):
    """Return a key when the current turn wrote memory and reached no repo."""
    records = []
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                m = json.loads(line)
            except Exception:
                continue
            if isinstance(m, dict) and not m.get("isSidechain"):
                records.append(m)
    turn_start = 0
    for i, m in enumerate(records):
        text = human_text(m)
        if text is not None and text.strip():
            turn_start = i
    wrote_memory = reached_repo = False
    for m in records[turn_start + 1:]:
        if (m.get("type") or m.get("role")) != "assistant":
            continue
        blocks = (m.get("message") or {}).get("content") or m.get("content") or []
        if isinstance(blocks, str):
            blocks = [{"type": "text", "text": blocks}]
        for b in blocks if isinstance(blocks, list) else []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                name = b.get("name") or ""
                inp = b.get("input") or {}
                target = str(inp.get("file_path") or inp.get("path") or "")
                if name in FILE_TOOLS and MEMORY_PATH.search(target):
                    wrote_memory = True
                elif REPO_WORK.search(name + " " + json.dumps(inp)):
                    reached_repo = True
            elif b.get("type") == "text":
                text = b.get("text") or ""
                if MECHANISM_LINE.search(text) or MEMORY_ONLY_REASON.search(text):
                    reached_repo = True
    if wrote_memory and not reached_repo:
        return hashlib.sha256(f"{path}:{turn_start}".encode()).hexdigest()[:16]
    return None


MESSAGE = (
    "[hook: no-memory-only-learning] This turn wrote project memory and nothing "
    "in it reached a repo. Memory is not versioned or reviewed, and no hook reads "
    "it, so a learning kept only there is lost to every agent that does not load "
    "it (Ezra, 2026-10-23: \"I hope you're recording everything we learn in one "
    "of our repos\").\n\n"
    "Before ending this turn, do one of:\n"
    "  * write the hook or failing check, or the shared/ fragment, in ai-config, "
    "psw or gha (global by default);\n"
    "  * put a line of its own that starts \"Mechanism: <issue or PR URL>\";\n"
    "  * say \"memory only: <reason>\" if the fact really is not repo-worthy "
    "(for example a one-off device detail)."
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path") or ""
        key = owed(path) if path and os.path.isfile(path) else None
    except Exception:
        return 0
    if not key:
        return 0
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-no-memory-only-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        with open(sentinel, "w", encoding="utf-8") as fh:
            fh.write("1")
    except Exception:
        pass
    print(json.dumps({"decision": "block", "reason": MESSAGE}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
