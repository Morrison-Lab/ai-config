#!/usr/bin/env python3
"""Hermetic tests for the Codex hook dispatcher."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADAPTER = ROOT / "plugins/ai-config/codex-hook-adapter.py"
spec = importlib.util.spec_from_file_location("codex_hook_adapter", ADAPTER)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def run(event: str, payload: dict) -> dict:
    result = subprocess.run(
        [sys.executable, str(ADAPTER), "--event", event],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=ROOT,
        env=os.environ.copy(),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


assert mod.matcher_hits("Bash", "Bash")
assert mod.matcher_hits("Edit|Write|NotebookEdit", "apply_patch")
assert mod.matcher_hits("mcp__github__.*", "mcp__github__pr_comment")
assert not mod.matcher_hits("Bash", "apply_patch")

pretool = run("PreToolUse", {
    "session_id": "test",
    "cwd": str(ROOT),
    "tool_name": "Bash",
    "tool_input": {"command": "echo harmless"},
})
assert isinstance(pretool, dict)
assert "permissionDecision" not in pretool.get("hookSpecificOutput", {})

blocked = run("PreToolUse", {
    "session_id": "test",
    "cwd": str(ROOT),
    "tool_name": "Bash",
    "tool_input": {"command": "gh pr merge 123"},
})
assert blocked["hookSpecificOutput"]["permissionDecision"] == "deny"

prompt = run("UserPromptSubmit", {
    "session_id": "test",
    "cwd": str(ROOT),
    "prompt": "hello",
})
assert isinstance(prompt, dict)

stop = run("Stop", {
    "session_id": "test",
    "cwd": str(ROOT),
    "last_assistant_message": "completed",
    "stop_hook_active": False,
})
assert isinstance(stop, dict)
print("Codex hook adapter tests passed")
