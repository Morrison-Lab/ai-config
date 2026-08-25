#!/usr/bin/env python3
"""Tests for .cursor/hooks/adapt-claude-hooks.py (ai-config#1934).

The adapter is the Cursor protocol side of the Claude `hooks/` catalog.
These cases pin translation, fail-open, once-per-generation UPS injection,
and that every Claude event in the live catalog has a mapping row.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADAPTER = ROOT / ".cursor" / "hooks" / "adapt-claude-hooks.py"
CURSOR_HOOKS = ROOT / ".cursor" / "hooks.json"
PLUGIN = ROOT / ".cursor-plugin" / "plugin.json"
MANIFEST = ROOT / "hooks" / "hooks.json"

spec = importlib.util.spec_from_file_location("adapt_claude_hooks", ADAPTER)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

passes = failures = 0


def check(name: str, condition: bool) -> None:
    global passes, failures
    print(f"{'PASS' if condition else 'FAIL'}: {name}")
    passes += condition
    failures += not condition


def write_hook(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def run_adapter(event: str, payload: dict, env: dict[str, str]) -> dict:
    proc = subprocess.run(
        [sys.executable, str(ADAPTER), "--event", event],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        cwd=str(ROOT),
    )
    check(f"{event} adapter exit 0", proc.returncode == 0)
    try:
        parsed = json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError:
        check(f"{event} stdout is JSON", False)
        return {}
    check(f"{event} stdout is object", isinstance(parsed, dict))
    return parsed if isinstance(parsed, dict) else {}


# --- live catalog: every Claude event is mapped ---
live = json.loads(MANIFEST.read_text(encoding="utf-8"))["hooks"]
check(
    "every Claude event in hooks.json is in EVENT_MAPPING",
    set(live) <= set(mod.EVENT_MAPPING),
)
check(
    "EVENT_MAPPING has no extra Claude events the catalog lacks",
    set(mod.EVENT_MAPPING) <= set(live),
)
check(
    "SendMessage is an explicit no-analog, not an omitted mapping",
    "SendMessage" in mod.NO_CURSOR_ANALOG,
)

# --- Cursor manifest is native schema, not Claude's ---
cursor_cfg = json.loads(CURSOR_HOOKS.read_text(encoding="utf-8"))
check("project hooks.json has version 1", cursor_cfg.get("version") == 1)
check(
    "project hooks.json uses Cursor event names",
    set(cursor_cfg.get("hooks", {})) <= {
        "preToolUse", "postToolUse", "stop", "sessionStart",
    },
)
check(
    "project hooks.json does not use Claude event names",
    not ({"PreToolUse", "Stop", "UserPromptSubmit"} & set(cursor_cfg.get("hooks", {}))),
)
for event, hooks in cursor_cfg.get("hooks", {}).items():
    cmds = [h.get("command", "") for h in hooks]
    check(
        f"{event} command invokes the adapter",
        all("adapt-claude-hooks.py" in c and f"--event {event}" in c for c in cmds),
    )

plugin = json.loads(PLUGIN.read_text(encoding="utf-8"))
check(
    "Cursor plugin.json does not point hooks at Claude hooks/hooks.json",
    plugin.get("hooks") != "hooks/hooks.json"
    and plugin.get("hooks") != "./hooks/hooks.json",
)

# --- unit: tool-name and matcher translation ---
check(
    "Shell maps to Bash",
    "Bash" in mod.cursor_to_claude_tool_names("Shell"),
)
check(
    "Task maps to Agent and Task",
    {"Agent", "Task"} <= set(mod.cursor_to_claude_tool_names("Task")),
)
check(
    "MCP:github-merge_pull_request maps to mcp__github__merge_pull_request",
    "mcp__github__merge_pull_request"
    in mod.cursor_to_claude_tool_names("MCP:github-merge_pull_request"),
)
check("empty matcher hits", mod.matcher_hits(None, "Bash"))
check("Bash matcher hits Bash", mod.matcher_hits("Bash", "Bash"))
check("Bash matcher misses Agent", not mod.matcher_hits("Bash", "Agent"))
check(
    "regex matcher hits mcp github",
    mod.matcher_hits("mcp__github__.*", "mcp__github__merge_pull_request"),
)
check(
    "regex matcher misses Bash",
    not mod.matcher_hits("mcp__github__.*", "Bash"),
)

# --- subprocess fixtures ---
deny_py = """\
#!/usr/bin/env python3
import json, sys
payload = json.load(sys.stdin)
if (payload.get("tool_input") or {}).get("command") == "gh pr merge 1":
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "merge blocked",
        }
    }))
"""

warn_py = """\
#!/usr/bin/env python3
import json, sys
payload = json.load(sys.stdin)
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": "assign isolation",
    },
    "systemMessage": "no isolation",
}))
"""

stop_py = """\
#!/usr/bin/env python3
import json, sys
payload = json.load(sys.stdin)
print(json.dumps({"decision": "block", "reason": "empty promise"}))
"""

ups_sh = """\
#!/bin/sh
echo "local time: 2026-08-25 10:00 PDT"
"""

with tempfile.TemporaryDirectory() as raw:
    tmp = Path(raw)
    hooks = tmp / "hooks"
    hooks.mkdir()
    write_hook(hooks, "deny-merge.py", deny_py)
    write_hook(hooks, "warn-isolation.py", warn_py)
    write_hook(hooks, "block-stop.py", stop_py)
    write_hook(hooks, "inject-time.sh", ups_sh)
    manifest = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"script": "deny-merge.py", "timeout": 5}],
                },
                {
                    "matcher": "Agent",
                    "hooks": [{"script": "warn-isolation.py", "timeout": 5}],
                },
            ],
            "Stop": [
                {"hooks": [{"script": "block-stop.py", "timeout": 5}]},
            ],
            "UserPromptSubmit": [
                {"hooks": [{"script": "inject-time.sh", "timeout": 5}]},
            ],
        }
    }
    manifest_path = tmp / "hooks.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    stash = tmp / "stash"
    stash.mkdir()
    env = os.environ.copy()
    env["AI_CONFIG_HOOKS_DIR"] = str(hooks)
    env["AI_CONFIG_HOOKS_JSON"] = str(manifest_path)
    env["AI_CONFIG_CURSOR_HOOK_STASH"] = str(stash)

    denied = run_adapter(
        "preToolUse",
        {
            "tool_name": "Shell",
            "tool_input": {"command": "gh pr merge 1"},
            "tool_use_id": "deny-1",
            "conversation_id": "c1",
            "generation_id": "g-deny",
        },
        env,
    )
    check("Shell merge is denied", denied.get("permission") == "deny")
    check("deny reason is forwarded", "merge blocked" in str(denied.get("agent_message")))

    allowed = run_adapter(
        "preToolUse",
        {
            "tool_name": "Shell",
            "tool_input": {"command": "git status"},
            "tool_use_id": "allow-1",
            "conversation_id": "c1",
            "generation_id": "g-allow",
        },
        env,
    )
    check("innocent Shell is allowed", allowed.get("permission") == "allow")

    warned = run_adapter(
        "preToolUse",
        {
            "tool_name": "Task",
            "tool_input": {"prompt": "edit files", "subagent_type": "generalPurpose"},
            "tool_use_id": "warn-1",
            "conversation_id": "c1",
            "generation_id": "g-warn",
        },
        env,
    )
    check("warn-only Agent launch is allowed", warned.get("permission") == "allow")
    replayed = run_adapter(
        "postToolUse",
        {
            "tool_name": "Task",
            "tool_use_id": "warn-1",
            "conversation_id": "c1",
            "generation_id": "g-warn",
        },
        env,
    )
    ctx = replayed.get("additional_context") or ""
    check("warn-only PreToolUse context replays on postToolUse", "assign isolation" in ctx)

    stopped = run_adapter(
        "stop",
        {
            "status": "completed",
            "loop_count": 0,
            "conversation_id": "c1",
            "generation_id": "g-stop",
            "transcript_path": str(tmp / "missing.jsonl"),
        },
        env,
    )
    check(
        "Stop block becomes followup_message",
        "empty promise" in str(stopped.get("followup_message")),
    )

    injected = run_adapter(
        "postToolUse",
        {
            "tool_name": "Shell",
            "tool_use_id": "ups-1",
            "conversation_id": "c1",
            "generation_id": "g-ups",
        },
        env,
    )
    check(
        "UPS stdout injects on first postToolUse",
        "10:00 PDT" in str(injected.get("additional_context")),
    )
    second = run_adapter(
        "postToolUse",
        {
            "tool_name": "Shell",
            "tool_use_id": "ups-2",
            "conversation_id": "c1",
            "generation_id": "g-ups",
        },
        env,
    )
    check(
        "UPS injects only once per generation",
        "10:00 PDT" not in str(second.get("additional_context") or ""),
    )

    session = run_adapter(
        "sessionStart",
        {"session_id": "s1", "conversation_id": "c-session", "generation_id": "g-session"},
        env,
    )
    check(
        "sessionStart injects UPS additional_context",
        "10:00 PDT" in str(session.get("additional_context")),
    )

    # Fail-open: missing manifest
    bad_env = env.copy()
    bad_env["AI_CONFIG_HOOKS_JSON"] = str(tmp / "nope.json")
    open_fail = run_adapter("preToolUse", {"tool_name": "Shell"}, bad_env)
    check("missing manifest fail-open allows", open_fail.get("permission") == "allow")

print(f"\n{passes} passed, {failures} failed")
raise SystemExit(1 if failures else 0)
