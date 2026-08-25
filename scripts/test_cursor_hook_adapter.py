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
import time
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
check(
    "EVENT_MAPPING values are HANDLERS keys",
    mod.mapped_cursor_events() <= set(mod.HANDLERS),
)
check(
    "HANDLERS covers every Cursor event in the project hooks.json",
    set(json.loads(CURSOR_HOOKS.read_text(encoding="utf-8")).get("hooks", {}))
    <= set(mod.HANDLERS),
)
live_entries = mod.load_manifest()
check("live catalog load_manifest is non-empty", len(live_entries) >= 40)
check(
    "live Stop no-mistake-without-a-hook carries AI_CONFIG_STOP",
    any(
        e["script"] == "no-mistake-without-a-hook.py"
        and e["event"] == "Stop"
        and (e.get("env") or {}).get("AI_CONFIG_STOP") == "1"
        for e in live_entries
    ),
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
stop_hook = cursor_cfg["hooks"]["stop"][0]
check("stop loop_limit is 5", stop_hook.get("loop_limit") == 5)
check(
    "preToolUse wrapper timeout is 300",
    cursor_cfg["hooks"]["preToolUse"][0].get("timeout") == 300,
)
check(
    "postToolUse wrapper timeout is 180",
    cursor_cfg["hooks"]["postToolUse"][0].get("timeout") == 180,
)
check(
    "stop wrapper timeout is 180",
    stop_hook.get("timeout") == 180,
)
check(
    "WRAPPER_TIMEOUT_S matches project hooks.json",
    all(
        cursor_cfg["hooks"][event][0].get("timeout") == mod.WRAPPER_TIMEOUT_S[event]
        for event in mod.WRAPPER_TIMEOUT_S
    ),
)


def hooks_field_points_at_claude(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    normalized = os.path.normpath(value).replace("\\", "/")
    return normalized.endswith("hooks/hooks.json")


check(
    "path normalizer rejects ../hooks/hooks.json",
    hooks_field_points_at_claude("../hooks/hooks.json"),
)

plugin = json.loads(PLUGIN.read_text(encoding="utf-8"))
check(
    "Cursor plugin.json does not point hooks at Claude hooks/hooks.json",
    not hooks_field_points_at_claude(plugin.get("hooks")),
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
check(
    "MCP:merge_pull_request also tries mcp__github__merge_pull_request",
    "mcp__github__merge_pull_request"
    in mod.cursor_to_claude_tool_names("MCP:merge_pull_request"),
)
check(
    "result-gated scripts are skipped on Cursor",
    {"no-push-without-self-review.py", "no-unreviewed-pr.py", "no-unmonitored-pr.py"}
    <= mod.SKIP_WITHOUT_TOOL_RESULT,
)
check(
    "no-empty-promise still runs on Cursor",
    "no-empty-promise.py" not in mod.SKIP_WITHOUT_TOOL_RESULT,
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
check(
    "command env prefix extracts AI_CONFIG_STOP",
    mod.env_prefix_from_command(
        'AI_CONFIG_STOP=1 python3 "${CLAUDE_PLUGIN_ROOT}/hooks/x.py"'
    ) == {"AI_CONFIG_STOP": "1"},
)
check(
    "command without env prefix is empty",
    mod.env_prefix_from_command('python3 "hooks/x.py"') == {},
)
cursor_asst = {
    "role": "assistant",
    "message": {"content": [
        {"type": "text", "text": "hi"},
        {"type": "tool_use", "name": "Shell", "input": {"command": "git status"}},
    ]},
}
translated = mod.cursor_record_to_claude(cursor_asst)
check("Cursor role becomes Claude type", translated.get("type") == "assistant")
check(
    "Cursor Shell tool_use becomes Bash",
    translated["message"]["content"][1].get("name") == "Bash",
)
typed_shell = {
    "type": "assistant",
    "role": "assistant",
    "message": {"content": [
        {"type": "tool_use", "name": "Shell", "input": {"command": "git status"}},
    ]},
}
check(
    "typed Cursor record with Shell still needs translation",
    mod.record_needs_translation(typed_shell),
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

stop_env_py = """\
#!/usr/bin/env python3
import json, os, sys
if os.environ.get("AI_CONFIG_STOP") == "1":
    print(json.dumps({"decision": "block", "reason": "mistake needs a hook"}))
else:
    print("plain reminder")
"""

ups_sh = """\
#!/bin/sh
echo "local time: 2026-08-25 10:00 PDT"
"""

count_py = """\
#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
p = Path(os.environ["COUNT_FILE"])
n = int(p.read_text()) if p.exists() else 0
p.write_text(str(n + 1))
print(json.dumps({}))
"""

with tempfile.TemporaryDirectory() as raw:
    tmp = Path(raw)
    hooks = tmp / "hooks"
    hooks.mkdir()
    write_hook(hooks, "deny-merge.py", deny_py)
    write_hook(hooks, "warn-isolation.py", warn_py)
    write_hook(hooks, "block-stop.py", stop_py)
    write_hook(hooks, "block-stop-env.py", stop_env_py)
    write_hook(hooks, "inject-time.sh", ups_sh)
    write_hook(hooks, "count-task.py", count_py)
    manifest = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"script": "deny-merge.py", "timeout": 5}],
                },
                {
                    "matcher": "Agent",
                    "hooks": [
                        {"script": "warn-isolation.py", "timeout": 5},
                        {"script": "count-task.py", "timeout": 5},
                    ],
                },
                {
                    "matcher": "Task",
                    "hooks": [{"script": "count-task.py", "timeout": 5}],
                },
            ],
            "Stop": [
                {"hooks": [
                    {"script": "block-stop.py", "timeout": 5},
                    {
                        "script": "block-stop-env.py",
                        "timeout": 5,
                        "command": "AI_CONFIG_STOP=1 python3 block-stop-env.py",
                    },
                ]},
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
    count_file = tmp / "task-count.txt"
    env["COUNT_FILE"] = str(count_file)

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
    denied_again = run_adapter(
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
    check(
        "double-fire replays the first deny rather than a competing allow",
        denied_again.get("permission") == "deny",
    )

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
    check(
        "Task runs a dual Agent/Task script once",
        count_file.read_text() == "1",
    )
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
    check(
        "Stop catalog command env prefix is forwarded",
        "mistake needs a hook" in str(stopped.get("followup_message")),
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
    after_typed_session = run_adapter(
        "postToolUse",
        {
            "tool_name": "Shell",
            "tool_use_id": "after-typed-session",
            "conversation_id": "c-session",
            "generation_id": "g-first-user",
        },
        env,
    )
    check(
        "postToolUse after sessionStart with generation_id does not repeat UPS",
        "10:00 PDT" not in str(after_typed_session.get("additional_context") or ""),
    )
    later_typed = run_adapter(
        "postToolUse",
        {
            "tool_name": "Shell",
            "tool_use_id": "later-typed",
            "conversation_id": "c-session",
            "generation_id": "g-second-user",
        },
        env,
    )
    check(
        "later generation after typed sessionStart still gets UPS",
        "10:00 PDT" in str(later_typed.get("additional_context") or ""),
    )
    session_id_only = run_adapter(
        "sessionStart",
        {"session_id": "sid-only"},
        env,
    )
    check(
        "session_id alone keys UPS injection",
        "10:00 PDT" in str(session_id_only.get("additional_context")),
    )
    after_session = run_adapter(
        "postToolUse",
        {
            "tool_name": "Shell",
            "tool_use_id": "after-session",
            "conversation_id": "sid-only",
            "session_id": "sid-only",
            "generation_id": "g-after-session",
        },
        env,
    )
    check(
        "first postToolUse does not repeat sessionStart UPS",
        "10:00 PDT" not in str(after_session.get("additional_context") or ""),
    )
    later_gen = run_adapter(
        "postToolUse",
        {
            "tool_name": "Shell",
            "tool_use_id": "later-ups",
            "conversation_id": "sid-only",
            "session_id": "sid-only",
            "generation_id": "g-later",
        },
        env,
    )
    check(
        "later generation still gets UPS after sessionStart",
        "10:00 PDT" in str(later_gen.get("additional_context") or ""),
    )

    # Fail-open: missing manifest
    bad_env = env.copy()
    bad_env["AI_CONFIG_HOOKS_JSON"] = str(tmp / "nope.json")
    open_fail = run_adapter("preToolUse", {"tool_name": "Shell"}, bad_env)
    check("missing manifest fail-open allows", open_fail.get("permission") == "allow")

    miss_manifest = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"script": "no-such-guard.py", "timeout": 5}],
                },
            ],
            "Stop": [],
            "UserPromptSubmit": [],
        }
    }
    miss_path = tmp / "missing-hooks.json"
    miss_path.write_text(json.dumps(miss_manifest), encoding="utf-8")
    miss_env = env.copy()
    miss_env["AI_CONFIG_HOOKS_JSON"] = str(miss_path)
    miss_env["AI_CONFIG_CURSOR_HOOK_STASH"] = str(tmp / "stash-missing")
    missing = run_adapter(
        "preToolUse",
        {
            "tool_name": "Shell",
            "tool_input": {"command": "git status"},
            "tool_use_id": "missing-1",
            "conversation_id": "c-missing",
            "generation_id": "g-missing",
        },
        miss_env,
    )
    check("missing catalog script fail-closed denies", missing.get("permission") == "deny")
    old_hooks_dir = os.environ.get("AI_CONFIG_HOOKS_DIR")
    os.environ["AI_CONFIG_HOOKS_DIR"] = str(hooks)
    try:
        skipped_stop = mod.handle_stop(
            {"conversation_id": "skip-stop"},
            [{"event": "Stop", "script": "no-unreviewed-pr.py", "timeout": 1}],
        )
        check(
            "handle_stop skips no-unreviewed-pr rather than fail-closed missing",
            skipped_stop == {},
        )
        skipped_monitor = mod.handle_stop(
            {"conversation_id": "skip-mon"},
            [{"event": "Stop", "script": "no-unmonitored-pr.py", "timeout": 1}],
        )
        check(
            "handle_stop skips no-unmonitored-pr rather than fail-closed missing",
            skipped_monitor == {},
        )
        missing_stop = mod.handle_stop(
            {"conversation_id": "miss-stop"},
            [{"event": "Stop", "script": "no-such-unskipped.py", "timeout": 1}],
        )
        check(
            "unskipped missing Stop script still fail-closes",
            bool(missing_stop.get("followup_message")),
        )
    finally:
        if old_hooks_dir is None:
            os.environ.pop("AI_CONFIG_HOOKS_DIR", None)
        else:
            os.environ["AI_CONFIG_HOOKS_DIR"] = old_hooks_dir

# --- live catalog, not the fixture ---
with tempfile.TemporaryDirectory() as live_raw:
    live_stash = Path(live_raw)
    live_env = os.environ.copy()
    live_env.pop("AI_CONFIG_HOOKS_DIR", None)
    live_env.pop("AI_CONFIG_HOOKS_JSON", None)
    live_env["AI_CONFIG_CURSOR_HOOK_STASH"] = str(live_stash)
    live_allow = run_adapter(
        "preToolUse",
        {
            "tool_name": "Shell",
            "tool_input": {"command": "git status"},
            "tool_use_id": "live-allow-1",
            "conversation_id": "live-c",
            "generation_id": "live-g-allow",
        },
        live_env,
    )
    check("live catalog allows git status", live_allow.get("permission") == "allow")
    live_deny = run_adapter(
        "preToolUse",
        {
            "tool_name": "Shell",
            "tool_input": {"command": "gh pr merge 1"},
            "tool_use_id": "live-deny-1",
            "conversation_id": "live-c",
            "generation_id": "live-g-deny",
        },
        live_env,
    )
    check("live catalog denies gh pr merge", live_deny.get("permission") == "deny")
    live_push = run_adapter(
        "preToolUse",
        {
            "tool_name": "Shell",
            "tool_input": {"command": "git push origin HEAD"},
            "tool_use_id": "live-push-1",
            "conversation_id": "live-c",
            "generation_id": "live-g-push",
        },
        live_env,
    )
    check(
        "live catalog does not lock out git push without tool_result",
        live_push.get("permission") == "allow",
    )
    nonce = str(time.time_ns())
    cursor_tx = live_stash / "cursor-offer.jsonl"
    cursor_tx.write_text(
        json.dumps({
            "role": "assistant",
            "message": {"content": [
                {
                    "type": "text",
                    "text": f"Want me to file an issue for that ({nonce})?",
                },
            ]},
        }) + "\n",
        encoding="utf-8",
    )
    live_stop = run_adapter(
        "stop",
        {
            "status": "completed",
            "loop_count": 0,
            "conversation_id": "live-c",
            "generation_id": "live-g-stop",
            "transcript_path": str(cursor_tx),
        },
        live_env,
    )
    check(
        "live Stop reads a Cursor-shaped transcript",
        "offers to file" in str(live_stop.get("followup_message") or "").lower()
        or "want me to file" in str(live_stop.get("followup_message") or "").lower(),
    )

print(f"\n{passes} passed, {failures} failed")
raise SystemExit(1 if failures else 0)
