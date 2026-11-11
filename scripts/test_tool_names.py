#!/usr/bin/env python3
"""Tests for scripts/lib/tool_names.py.

The module replaces per-hook copies of the tool-name alias lists
(ai-config#4266), so each case pins one spelling or input shape a harness
sends (`collaboration.spawn_agent` is still unmeasured, ai-config#3741). A
spelling missing here is a tool call some hook silently ignores.

The last section runs each hook that imports the module from a directory
without it, and pins what the hook still does on such a broken install.

Run:  python3 scripts/test_tool_names.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))

import tool_names  # noqa: E402

failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok    {label}")
    else:
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")
        failures.append(label)


for name in ("Agent", "Task", "invoke_subagent", "dispatch_agent",
             "run_agent", "spawn_agent", "collaboration.spawn_agent"):
    check(f"{name} launches a subagent", tool_names.is_subagent_tool(name), True)
for name in ("Write", "Edit", "MultiEdit", "NotebookEdit", "write_to_file",
             "replace_file_content", "apply_patch", "str_replace_editor"):
    check(f"{name} writes a file", tool_names.is_write_tool(name), True)
for name in ("Bash", "PowerShell", "run_command", "execute_command",
             "terminal", "shell"):
    check(f"{name} runs a shell command", tool_names.is_shell_tool(name), True)
for name in ("Read", "Skill", "SendMessage", "", None, 3):
    check(f"{name!r} is none of the three",
          (tool_names.is_subagent_tool(name), tool_names.is_write_tool(name),
           tool_names.is_shell_tool(name)),
          (False, False, False))

deep = "[" * 100000
W, C, B = (tool_names.write_target, tool_names.shell_command,
           tool_names.subagent_brief)
for label, fn, inp, want in (
    ("write target from file_path", W, {"file_path": "/a/b"}, "/a/b"),
    ("write target from Antigravity's TargetFile", W, {"TargetFile": "/c"}, "/c"),
    ("write target from Cursor's filePath", W, {"filePath": "/d"}, "/d"),
    ("write target missing", W, {"content": "x"}, ""),
    ("write target of a non-dict", W, "x", ""),
    ("shell command from command", C, {"command": "git status"}, "git status"),
    ("shell command from Antigravity's CommandLine", C, {"CommandLine": "ls"}, "ls"),
    ("brief from prompt and description", B,
     {"prompt": "fix it", "description": "short"}, "fix it short"),
    ("brief from an invoke_subagent Subagents list", B,
     {"Subagents": [{"Prompt": "record in ai-config", "Role": "r"}]},
     "record in ai-config r"),
    ("brief from a Subagents JSON list", B,
     {"Subagents": '[{"Prompt": "run ums"}]'}, "run ums"),
    ("brief from a Subagents JSON object", B,
     {"Subagents": '{"Prompt": "run ums"}'}, "run ums"),
    ("brief from a Subagents dict", B, {"Subagents": {"Prompt": "run ums"}}, "run ums"),
    ("brief from a Subagents JSON string literal", B,
     {"Subagents": '"run ums"'}, '"run ums"'),
    ("brief from a Subagents string that is not JSON", B,
     {"Subagents": "run ums"}, "run ums"),
    ("brief from a Subagents string too deep to parse", B, {"Subagents": deep}, deep),
    ("brief from a list of strings", B, {"subagents": ["a", "b"]}, "a b"),
    ("brief of a non-dict", B, None, ""),
):
    check(label, fn(inp), want)


def run_hook(hook_dir, name, payload):
    proc = subprocess.run(
        [sys.executable, "-I", os.path.join(hook_dir, name)],
        input=json.dumps(payload), capture_output=True, text=True, timeout=30,
        # The hooks' once-only sentinels live in the temp dir; keep them in
        # this run's own directory so a rerun starts fresh.
        env=dict(os.environ, TMPDIR=hook_dir))
    return proc.returncode, proc.stdout, proc.stderr


HOOKS = os.path.join(os.path.dirname(HERE), "hooks")
tmp = tempfile.mkdtemp()
try:
    shutil.copy(os.path.join(HOOKS, "remind-record-standing-guidance.py"), tmp)
    transcript = os.path.join(tmp, "t.jsonl")
    with open(transcript, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "user", "message": {"content": [
            {"type": "text", "text": "From now on always link every PR in tables."}]}}) + "\n")
        fh.write(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Agent",
             "input": {"prompt": "Record this rule in ai-config."}}]}}) + "\n")

    rc, out, err = run_hook(tmp, "remind-record-standing-guidance.py",
                            {"prompt": "thanks, carry on with the next step",
                             "transcript_path": transcript})
    check("broken install: remind-record exits 0", rc, 0)
    check("broken install: remind-record names the missing module",
          "tool_names.py" in err, True)
    check("broken install: remind-record still reminds (no call counts as recording)",
          "Standing-guidance reminder" in out, True)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if failures:
    print(f"\n{len(failures)} failure(s)")
    sys.exit(1)
print("\nall tests passed")
