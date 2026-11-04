#!/usr/bin/env python3
"""PreToolUse: refuse a Write, Edit or MultiEdit to a project memory store file.

Ezra, 2026-11-03 23:47 UTC (lds thread): "cai: always save memories as tracked
files in repos". The rule already existed (memories/project-memory-store.md,
owner directive 2026-10-16; shared/workflow/encode-reusable-feedback.md), and
the Stop hook no-memory-only-learning.py only asked for a repo change AFTER the
write, and let "memory only: <reason>" through, so a session wrote the memory
anyway and explained it away. This hook stops the write itself.

The project memory store is a directory under a path containing
`/memory/team/` (hosted harness: `/tmp/claude/memory/team/<project>/`). Blocked:
any Write, Edit or MultiEdit whose file_path is inside it, except the
`MEMORY.md` index, which may still hold pointers to repo files.

The reason names where the memory belongs, so the agent can act at once:
the project's primary repo (a dev-facing file such as
`.claude/project-memory.md`), `ai-config` for a global rule, or a repo's own
CLAUDE.md for a repo rule.

Fails OPEN and SILENT on any parse trouble.
"""
import json
import re
import sys

STORE_PATH = re.compile(r"/memory/team/", re.I)
INDEX_FILE = re.compile(r"(?:^|/)MEMORY\.md$")
EDIT_TOOLS = {"Write", "Edit", "MultiEdit"}

REASON = (
    "[hook: block-project-memory-write] `{path}` is in the project memory "
    "store, which is not version-controlled: it cannot be reviewed, other "
    "tools and hooks cannot read it, and concurrent writes are silently lost "
    "(memories/project-memory-store.md). Ezra, 2026-10-16 and 2026-11-03: "
    "always save memories as tracked files in repos.\n\n"
    "Write it where it belongs instead, and open the PR:\n"
    "  * the project's primary repo, in a dev-facing file such as "
    "`.claude/project-memory.md`, for a fact or decision true of that project;\n"
    "  * `ai-config` (a `shared/` fragment, `AGENTS.md`, `memories/` or a "
    "hook) for a global rule;\n"
    "  * a repository's own `CLAUDE.md` for a rule about that repo alone.\n"
    "The store may hold `MEMORY.md` pointers to those files, and nothing else."
)


def blocked_path(payload):
    if payload.get("tool_name") not in EDIT_TOOLS:
        return None
    inp = payload.get("tool_input")
    inp = inp if isinstance(inp, dict) else {}
    path = str(inp.get("file_path") or inp.get("path") or "")
    if STORE_PATH.search(path) and not INDEX_FILE.search(path):
        return path
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        path = blocked_path(payload)
    except Exception:
        return 0
    if not path:
        return 0
    reason = REASON.format(path=path)
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": reason,
        },
        "systemMessage": "Blocked: write the memory to a tracked repo file, not the project memory store.",
    }
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
