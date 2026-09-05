#!/usr/bin/env python3
"""Hermetic tests for the Codex hook dispatcher."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
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

plugin_manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
assert plugin_manifest["skills"] == "codex-skills"
plugin_hooks = json.loads((ROOT / "plugins/ai-config/codex-hooks.json").read_text())
assert "${PLUGIN_ROOT}" in json.dumps(plugin_hooks)
assert plugin_manifest["hooks"] == "./plugins/ai-config/codex-hooks.json"

failed = mod.run_entry({"command": "exit 2", "timeout": 1}, {})
assert failed and failed["decision"] == "block"
nonblocking_failure = mod.run_entry({"command": "exit 1", "timeout": 1}, {})
assert nonblocking_failure and "systemMessage" in nonblocking_failure
malformed = mod.run_entry({"command": "printf invalid-json", "timeout": 1}, {})
assert malformed and "systemMessage" in malformed

original_manifest = mod.MANIFEST
mod.MANIFEST = ROOT / "does-not-exist-hooks.json"
assert mod.dispatch("PreToolUse", {"tool_name": "Bash"})["decision"] == "block"
with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as invalid_catalog:
    invalid_catalog.write(json.dumps({"hooks": [{"hooks": [{"command": "", "timeout": 0}]}]}))
    invalid_catalog_path = invalid_catalog.name
mod.MANIFEST = Path(invalid_catalog_path)
assert mod.dispatch("PreToolUse", {"tool_name": "Bash"})["decision"] == "block"
mod.MANIFEST = original_manifest
os.unlink(invalid_catalog_path)

pretool = run("PreToolUse", {
    "session_id": f"test-{os.getpid()}",
    "cwd": str(ROOT),
    "tool_name": "Bash",
    "tool_input": {"command": "echo harmless"},
    "call_id": "harmless",
})
assert isinstance(pretool, dict)
assert "permissionDecision" not in pretool.get("hookSpecificOutput", {})

blocked = run("PreToolUse", {
    "session_id": f"test-{os.getpid()}",
    "cwd": str(ROOT),
    "tool_name": "Bash",
    "tool_input": {"command": "gh pr merge 123"},
    "call_id": "merge",
})
assert blocked["hookSpecificOutput"]["permissionDecision"] == "deny"

prompt = run("UserPromptSubmit", {
    "session_id": "test",
    "cwd": str(ROOT),
    "prompt": "hello",
    "turn_id": "prompt",
})
assert isinstance(prompt, dict)

stop = run("Stop", {
    "session_id": "test",
    "cwd": str(ROOT),
    "last_assistant_message": "completed",
    "stop_hook_active": False,
    "turn_id": "stop",
})
assert isinstance(stop, dict)

stop_block = run("Stop", {"session_id": f"stop-block-{os.getpid()}", "cwd": str(ROOT),
                           "last_assistant_message":
                           "I will always do this going forward.",
                           "turn_id": "one"})
assert stop_block.get("decision") == "block"

with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as transcript:
    transcript.write(json.dumps({"type": "assistant", "message": {
        "role": "assistant", "content": [{"type": "text",
        "text": "I will always do this going forward."}]}}) + "\n")
    transcript_path = transcript.name
try:
    existing_transcript = run("Stop", {"session_id": f"existing-{os.getpid()}",
        "cwd": str(ROOT), "transcript_path": transcript_path,
        "last_assistant_message": "completed", "turn_id": "existing"})
    assert existing_transcript.get("decision") == "block"
finally:
    os.unlink(transcript_path)

invalid = subprocess.run([sys.executable, str(ADAPTER), "--event", "PreToolUse"],
                         input="not-json", text=True, capture_output=True,
                         cwd=ROOT, check=False)
assert json.loads(invalid.stdout)["decision"] == "block"

original_load_entries = mod.load_entries
original_run_entry = mod.run_entry
mod.load_entries = lambda event: [{"matcher": None, "command": "", "timeout": 1}]
mod.run_entry = lambda entry, payload: {"decision": "block", "reason": "prompt test"}
assert mod.dispatch("UserPromptSubmit", {"prompt": "block me"})["decision"] == "block"
mod.load_entries = original_load_entries
mod.run_entry = original_run_entry
print("Codex hook adapter tests passed")
