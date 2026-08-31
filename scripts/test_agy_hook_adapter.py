#!/usr/bin/env python3
"""Test suite for the Antigravity hook adapter (`plugins/ai-config/claude-hook-adapter.py`).

Tests the adapter in hermetic isolation by mocking `hooks/hooks.json` and subprocess calls.
Verifies event mapping (Bash, Agent, SendMessage, Task, generic/MCP tools), multi-subagent fanout,
regex & wildcard matchers, flat and grouped schema tolerance, Stop block-to-continue translation,
PreInvocation context injection, denial paths, and missing config fallback.
"""
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock, mock_open

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADAPTER_SCRIPT = os.path.join(ROOT, "plugins", "ai-config", "claude-hook-adapter.py")
PLUGIN_HOOKS_JSON = os.path.join(ROOT, "plugins", "ai-config", "hooks.json")

def load_adapter():
    if not os.path.isfile(ADAPTER_SCRIPT):
        raise FileNotFoundError(f"Adapter script not found at {ADAPTER_SCRIPT}")
    spec = importlib.util.spec_from_file_location("claude_hook_adapter", ADAPTER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

MOCK_HOOKS_DEF = {
    "hooks": {
        "UserPromptSubmit": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/test-prompt1.py\"",
                        "timeout": 10
                    },
                    {
                        "type": "command",
                        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/test-prompt2.py\"",
                        "timeout": 10
                    }
                ]
            }
        ],
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/test-bash.py\"",
                        "timeout": "10"
                    }
                ]
            },
            {
                "matcher": "Agent",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/test-agent.py\"",
                        "timeout": 10
                    }
                ]
            },
            {
                "matcher": "SendMessage",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/test-send.py\"",
                        "timeout": 10
                    }
                ]
            },
            {
                "matcher": "Task",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/test-task.py\"",
                        "timeout": 10
                    }
                ]
            },
            {
                "matcher": "mcp__github__.*",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/test-mcp.py\"",
                        "timeout": 10
                    }
                ]
            },
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/test-wildcard.py\"",
                        "timeout": 10
                    }
                ]
            }
        ],
        "Stop": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/test-stop.py\"",
                        "timeout": 10
                    }
                ]
            }
        ]
    }
}

MOCK_FLAT_HOOKS_DEF = {
    "hooks": {
        "UserPromptSubmit": [
            {
                "type": "command",
                "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/test-flat-prompt.py\"",
                "timeout": 10
            }
        ],
        "Stop": [
            {
                "type": "command",
                "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/test-flat-stop.py\"",
                "timeout": 10
            }
        ]
    }
}

class TestAgyHookAdapter(unittest.TestCase):
    def setUp(self):
        self.assertTrue(os.path.isfile(ADAPTER_SCRIPT), f"Adapter script missing at {ADAPTER_SCRIPT}")
        self.adapter = load_adapter()

    def test_plugins_hooks_json_valid_json(self):
        self.assertTrue(os.path.isfile(PLUGIN_HOOKS_JSON), f"Manifest missing at {PLUGIN_HOOKS_JSON}")
        with open(PLUGIN_HOOKS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("enforce-merge-control", data)
        bundle = data["enforce-merge-control"]
        self.assertIn("PreToolUse", bundle)
        self.assertIn("Stop", bundle)
        self.assertIn("PreInvocation", bundle)

    def test_plugins_hooks_json_run_command_split_into_its_own_group(self):
        # De-risk regression guard: "run_command" must sit in its own
        # literal-matcher group, separate from the newer tool names' regex
        # alternation, so a wrong assumption about Antigravity treating
        # `matcher` as a regex costs only the newer coverage and never the
        # pre-existing merge-control gate on run_command.
        with open(PLUGIN_HOOKS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        pre_tool_use = data["enforce-merge-control"]["PreToolUse"]
        matchers = [group.get("matcher") for group in pre_tool_use]
        self.assertIn("run_command", matchers, "run_command must have its own literal-matcher group")
        run_command_group = next(g for g in pre_tool_use if g.get("matcher") == "run_command")
        run_command_commands = [h.get("command", "") for h in run_command_group.get("hooks", [])]
        self.assertTrue(
            any("enforce-mwc-review-gate.py" in c for c in run_command_commands),
            "run_command's group must still carry enforce-mwc-review-gate.py",
        )
        for matcher in matchers:
            self.assertNotIn(
                "run_command|", matcher or "",
                "run_command must not be combined into a regex alternation with other tool names",
            )

    @patch('os.path.exists', return_value=False)
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    def test_missing_hooks_json_fallback(self, mock_stderr, mock_stdout, mock_stdin, mock_exists):
        payload = {"toolCall": {"name": "run_command", "args": {"CommandLine": "ls"}}}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "allow")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    def test_unknown_event_payload(self, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        payload = {"randomUnknownField": 1234}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "allow")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_run_command_allow(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"hookSpecificOutput": {}}), stderr="")
        mock_run.return_value = mock_result
        
        payload = {
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "git status", "Cwd": "/tmp"}
            }
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "allow")
        
        call_input = json.loads(mock_run.call_args_list[0].kwargs['input'])
        self.assertEqual(call_input["tool_name"], "Bash")
        self.assertEqual(call_input["tool_input"]["command"], "git status")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_run_command_deny(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({
            "hookSpecificOutput": {
                "permissionDecision": "deny",
                "permissionDecisionReason": "Unauthorized command"
            }
        }), stderr="")
        mock_run.return_value = mock_result
        
        payload = {
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "rm -rf /"}
            }
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "deny")
        self.assertEqual(out.get("reason"), "Unauthorized command")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_send_message_allow_and_deny(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_deny = MagicMock(returncode=0, stdout=json.dumps({
            "hookSpecificOutput": {
                "permissionDecision": "deny",
                "permissionDecisionReason": "Messaging not permitted"
            }
        }), stderr="")
        mock_run.return_value = mock_deny
        
        payload_send = {
            "toolCall": {
                "name": "send_message",
                "args": {"Recipient": "agent-123", "Message": "hello"}
            }
        }
        mock_stdin.write(json.dumps(payload_send))
        mock_stdin.seek(0)
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "deny")
        self.assertEqual(out.get("reason"), "[send_message] Messaging not permitted")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_define_subagent_deny(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_deny = MagicMock(returncode=0, stdout=json.dumps({
            "hookSpecificOutput": {
                "permissionDecision": "deny",
                "permissionDecisionReason": "Agent definition denied"
            }
        }), stderr="")
        mock_run.return_value = mock_deny
        
        payload_def = {
            "toolCall": {
                "name": "define_subagent",
                "args": {"name": "sub1", "description": "desc", "system_prompt": "prompt"}
            }
        }
        mock_stdin.write(json.dumps(payload_def))
        mock_stdin.seek(0)
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "deny")
        self.assertEqual(out.get("reason"), "[define_subagent] Agent definition denied")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_pre_invocation_multi_message_steps(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        res1 = MagicMock(returncode=0, stdout="Message 1\n", stderr="")
        res2 = MagicMock(returncode=0, stdout=json.dumps({"systemMessage": "Message 2"}), stderr="")
        mock_run.side_effect = [res1, res2]
        
        payload = {"invocationNum": 1, "transcriptPath": "/tmp/transcript.jsonl"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertIn("injectSteps", out)
        self.assertEqual(len(out["injectSteps"]), 2)
        self.assertEqual(out["injectSteps"][0]["ephemeralMessage"], "Message 1")
        self.assertEqual(out["injectSteps"][1]["ephemeralMessage"], "Message 2")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_pre_invocation_twenty_message_cap(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        # 25 hooks returning distinct messages
        many_hooks = {
            "hooks": {
                "UserPromptSubmit": [
                    {"hooks": [{"command": f"cmd_{i}"} for i in range(25)]}
                ]
            }
        }
        mock_file.return_value.read.return_value = json.dumps(many_hooks)
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"systemMessage": "test message"}), stderr="")
        mock_run.return_value = mock_result
        
        payload = {"invocationNum": 1, "prompt": "test"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        # Capped at exactly 20 injected steps
        self.assertEqual(len(out.get("injectSteps", [])), 20)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_mcp_github_tool_regex_matching(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"hookSpecificOutput": {}}), stderr="")
        mock_run.return_value = mock_result
        
        payload = {
            "toolCall": {
                "name": "mcp__github__create_pull_request",
                "args": {"title": "New PR"}
            }
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "allow")
        self.assertEqual(mock_run.call_count, 2)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_pre_invocation_thirty_kb_exact_boundary(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        # 4 hooks, each returning 10KB of text
        four_hooks = {
            "hooks": {
                "UserPromptSubmit": [
                    {"hooks": [{"command": f"cmd_{i}"} for i in range(4)]}
                ]
            }
        }
        mock_file.return_value.read.return_value = json.dumps(four_hooks)
        mock_result = MagicMock(returncode=0, stdout="B" * 10000, stderr="")
        mock_run.return_value = mock_result
        
        payload = {"invocationNum": 1, "prompt": "test"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        total_len = sum(len(step["ephemeralMessage"].encode("utf-8")) for step in out.get("injectSteps", []))
        self.assertEqual(total_len, 30000)
        self.assertEqual(len(out.get("injectSteps", [])), 3)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_pre_invocation_multibyte_boundary_no_empty_ephemeral_messages(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        # Regression guard: when the total byte cap lands mid a multi-byte
        # UTF-8 character, `errors="ignore"` yields an empty
        # trimmed_chunk. That must NOT be appended as another empty
        # ephemeralMessage step for every remaining hook (up to the
        # message cap) -- it must be dropped, and accumulation must stop
        # since no further hook output can fit either.
        #
        # Reproduces the reviewer's scenario: hooks consuming 29999 of
        # 30000 bytes, then hooks returning 2-byte UTF-8 characters
        # ("e" with an acute accent, U+00E9) that cannot fit in the
        # single remaining byte.
        five_hooks = {
            "hooks": {
                "UserPromptSubmit": [
                    {"hooks": [{"command": f"cmd_{i}"} for i in range(5)]}
                ]
            }
        }
        mock_file.return_value.read.return_value = json.dumps(five_hooks)

        multibyte_chunk = "é" * 10  # 10 chars, 20 bytes in UTF-8
        results = [
            MagicMock(returncode=0, stdout="A" * 9999, stderr=""),   # 9999 bytes
            MagicMock(returncode=0, stdout="B" * 10000, stderr=""),  # 10000 bytes (total 19999)
            MagicMock(returncode=0, stdout="C" * 10000, stderr=""),  # 10000 bytes (total 29999)
            MagicMock(returncode=0, stdout=multibyte_chunk, stderr=""),  # overflows by 1 byte mid-char
            MagicMock(returncode=0, stdout="Z", stderr=""),  # ASCII: fits the 1 leftover byte
        ]
        mock_run.side_effect = results

        payload = {"invocationNum": 1, "prompt": "test"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        out = json.loads(mock_stdout.getvalue())
        steps = out.get("injectSteps", [])
        messages = [step["ephemeralMessage"] for step in steps]

        # No empty ephemeralMessage entries, however many hooks the
        # boundary overflow would otherwise have visited.
        self.assertNotIn("", messages)
        # The fourth hook's content could not fit even one code point
        # (a boundary mid multi-byte UTF-8 character), so it is skipped
        # entirely rather than padded in as an empty step -- but the
        # loop keeps going, so the fifth hook's ASCII output fills the
        # single leftover byte.
        self.assertEqual(len(steps), 4)
        self.assertEqual(messages[-1], "Z")
        total_len = sum(len(m.encode("utf-8")) for m in messages)
        self.assertEqual(total_len, 30000)
        # All five hooks ran: an unfittable chunk skips itself, it does
        # not end accumulation for later hooks that might still fit.
        self.assertEqual(mock_run.call_count, 5)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_stop_event_unrecognized_decision_falls_through(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"decision": "abort"}), stderr="")
        mock_run.return_value = mock_result
        
        payload = {"terminationReason": "completed"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out, {})

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    @patch('os.getcwd', return_value='/tmp/mock-caller-project')
    def test_run_command_cwd_falls_back_to_process_cwd_not_repo_root(self, mock_getcwd, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        # Regression guard: when Cwd is absent from the tool args, the hook
        # subprocess's cwd must be this process's own cwd (the caller's
        # real project), never ai-config's own repo root -- a guard hook
        # like hooks/no-clobbering-push.py inherits this cwd to evaluate
        # the user's project's own git state, and pointing it at
        # ai-config's checkout instead makes it evaluate the wrong repo.
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"hookSpecificOutput": {}}), stderr="")
        mock_run.return_value = mock_result

        payload = {
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "ls"}
            }
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "allow")
        actual_cwd = mock_run.call_args_list[0].kwargs['cwd']
        self.assertEqual(actual_cwd, '/tmp/mock-caller-project')
        self.assertNotEqual(actual_cwd, ROOT)
        call_input = json.loads(mock_run.call_args_list[0].kwargs['input'])
        self.assertEqual(call_input.get("cwd"), '/tmp/mock-caller-project')

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    @patch('os.getcwd', return_value='/tmp/mock-caller-project')
    def test_generic_tool_cwd_falls_back_to_process_cwd_not_repo_root(self, mock_getcwd, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        # Same regression, on the generic/MCP-tool dispatch path (previously
        # hardcoded to repo_root regardless of the Cwd fallback).
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"hookSpecificOutput": {}}), stderr="")
        mock_run.return_value = mock_result

        payload = {
            "toolCall": {
                "name": "mcp__github__create_pull_request",
                "args": {"title": "New PR"}
            }
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "allow")
        for call in mock_run.call_args_list:
            self.assertEqual(call.kwargs['cwd'], '/tmp/mock-caller-project')
            self.assertNotEqual(call.kwargs['cwd'], ROOT)
            call_input = json.loads(call.kwargs['input'])
            self.assertEqual(call_input.get("cwd"), '/tmp/mock-caller-project')

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    @patch('os.getcwd', return_value='/tmp/mock-caller-project')
    def test_stop_hook_cwd_falls_back_to_process_cwd_not_repo_root(self, mock_getcwd, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({}), stderr="")
        mock_run.return_value = mock_result

        payload = {"terminationReason": "model_stop"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        self.assertEqual(mock_run.call_args_list[0].kwargs['cwd'], '/tmp/mock-caller-project')
        self.assertNotEqual(mock_run.call_args_list[0].kwargs['cwd'], ROOT)
        call_input = json.loads(mock_run.call_args_list[0].kwargs['input'])
        self.assertEqual(call_input.get("cwd"), '/tmp/mock-caller-project')

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_stop_hook_forwards_explicit_payload_cwd(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({}), stderr="")
        mock_run.return_value = mock_result

        payload = {
            "terminationReason": "model_stop",
            "cwd": "/path/to/explicit-project"
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        self.assertEqual(mock_run.call_args_list[0].kwargs['cwd'], '/path/to/explicit-project')
        call_input = json.loads(mock_run.call_args_list[0].kwargs['input'])
        self.assertEqual(call_input.get("cwd"), '/path/to/explicit-project')

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_stop_hook_forwards_workspace_paths_cwd(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({}), stderr="")
        mock_run.return_value = mock_result

        payload = {
            "terminationReason": "model_stop",
            "workspacePaths": ["file:///path/to/workspace-project"]
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        self.assertEqual(mock_run.call_args_list[0].kwargs['cwd'], '/path/to/workspace-project')
        call_input = json.loads(mock_run.call_args_list[0].kwargs['input'])
        self.assertEqual(call_input.get("cwd"), '/path/to/workspace-project')

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    @patch('os.getcwd', return_value='/tmp/mock-caller-project')
    def test_pre_invocation_hook_cwd_falls_back_to_process_cwd_not_repo_root(self, mock_getcwd, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({}), stderr="")
        mock_run.return_value = mock_result

        payload = {"invocationNum": 1, "prompt": "test"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        self.assertEqual(mock_run.call_args_list[0].kwargs['cwd'], '/tmp/mock-caller-project')
        self.assertNotEqual(mock_run.call_args_list[0].kwargs['cwd'], ROOT)
        call_input = json.loads(mock_run.call_args_list[0].kwargs['input'])
        self.assertEqual(call_input.get("cwd"), '/tmp/mock-caller-project')

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_pre_invocation_hook_forwards_explicit_payload_cwd(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({}), stderr="")
        mock_run.return_value = mock_result

        payload = {
            "invocationNum": 1,
            "prompt": "test",
            "cwd": "/path/to/explicit-inv-project"
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        self.assertEqual(mock_run.call_args_list[0].kwargs['cwd'], '/path/to/explicit-inv-project')
        call_input = json.loads(mock_run.call_args_list[0].kwargs['input'])
        self.assertEqual(call_input.get("cwd"), '/path/to/explicit-inv-project')

    def test_extract_cwd_helper(self):
        # 1. tool_args Cwd / cwd takes priority
        self.assertEqual(self.adapter.extract_cwd({}, {"Cwd": "/path/from/tool_args"}), "/path/from/tool_args")
        self.assertEqual(self.adapter.extract_cwd({}, {"cwd": "/path/from/tool_args_lower"}), "/path/from/tool_args_lower")
        self.assertEqual(self.adapter.extract_cwd({}, {"Cwd": "file:///path/from/tool_args_uri"}), "/path/from/tool_args_uri")
        self.assertEqual(self.adapter.extract_cwd({}, {"Cwd": "file:///path/with%20space/tool_args"}), "/path/with space/tool_args")

        # 2. payload direct cwd fields
        self.assertEqual(self.adapter.extract_cwd({"cwd": "/path/from/payload_cwd"}), "/path/from/payload_cwd")
        self.assertEqual(self.adapter.extract_cwd({"Cwd": "/path/from/payload_Cwd"}), "/path/from/payload_Cwd")
        self.assertEqual(self.adapter.extract_cwd({"workingDirectory": "/path/from/wd"}), "/path/from/wd")
        self.assertEqual(self.adapter.extract_cwd({"workspacePath": "/path/from/wspath"}), "/path/from/wspath")
        self.assertEqual(self.adapter.extract_cwd({"workspace": "file:///path/from/ws_uri"}), "/path/from/ws_uri")
        self.assertEqual(self.adapter.extract_cwd({"cwd": "file:///path/with%20space/payload"}), "/path/with space/payload")

        # 3. payload workspacePaths / workspaces list or string
        self.assertEqual(self.adapter.extract_cwd({"workspacePaths": "/single/ws/string"}), "/single/ws/string")
        self.assertEqual(self.adapter.extract_cwd({"workspacePaths": ["/first/ws/path", "/second/ws/path"]}), "/first/ws/path")
        self.assertEqual(self.adapter.extract_cwd({"workspacePaths": ["file:///uri/ws/path"]}), "/uri/ws/path")
        self.assertEqual(self.adapter.extract_cwd({"workspacePaths": ["file:///uri/with%20space/path"]}), "/uri/with space/path")
        self.assertEqual(self.adapter.extract_cwd({"workspaces": [{"path": "/dict/ws/path"}]}), "/dict/ws/path")
        self.assertEqual(self.adapter.extract_cwd({"workspaces": [{"uri": "file:///dict/uri/path"}]}), "/dict/uri/path")
        self.assertEqual(self.adapter.extract_cwd({"workspaces": [{"uri": "file:///dict/with%20space/path"}]}), "/dict/with space/path")

        # 4. Fallback to os.getcwd() on empty / whitespace / degenerate inputs
        with patch('os.getcwd', return_value='/tmp/fallback-process-cwd'):
            self.assertEqual(self.adapter.extract_cwd({}), "/tmp/fallback-process-cwd")
            self.assertEqual(self.adapter.extract_cwd({"workspacePaths": []}), "/tmp/fallback-process-cwd")
            self.assertEqual(self.adapter.extract_cwd({"cwd": "file://"}), "/tmp/fallback-process-cwd")
            self.assertEqual(self.adapter.extract_cwd({"cwd": "   "}), "/tmp/fallback-process-cwd")
            self.assertEqual(self.adapter.extract_cwd({"workspacePaths": ["file://", "  "]}), "/tmp/fallback-process-cwd")

    def test_extract_hook_list_supports_script_key(self):
        item = [{"script": "python3 /path/to/script.py"}]
        res = self.adapter.extract_hook_list(item)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["script"], "python3 /path/to/script.py")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_ambiguous_tool_call_and_invocation_num_payload(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"hookSpecificOutput": {}}), stderr="")
        mock_run.return_value = mock_result
        
        payload = {
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "ls"}
            },
            "invocationNum": 1
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        # PreToolUse takes priority when toolCall is present
        self.assertEqual(out.get("decision"), "allow")
        self.assertNotIn("injectSteps", out)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_pre_invocation_zero_invocation_num(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"systemMessage": "Zero step"}), stderr="")
        mock_run.return_value = mock_result
        
        payload = {"invocationNum": 0, "prompt": "test prompt"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(len(out.get("injectSteps", [])), 2)
        call_input = json.loads(mock_run.call_args_list[0].kwargs['input'])
        self.assertEqual(call_input["invocation_num"], 0)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_pre_invocation_role_filtering(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"systemMessage": "Injected context"}), stderr="")
        mock_run.return_value = mock_result
        
        payload = {
            "invocationNum": 1,
            "messages": [
                {"role": "user", "content": "The real user prompt"},
                {"role": "assistant", "content": "The assistant response"}
            ]
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        call_input = json.loads(mock_run.call_args_list[0].kwargs['input'])
        self.assertEqual(call_input["prompt"], "The real user prompt")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_pre_invocation_list_content_coercion(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout="A" * 15000, stderr="")
        mock_run.return_value = mock_result
        
        payload = {
            "invocationNum": 1,
            "messages": [
                {"role": "user", "content": [{"text": "part 1"}, "part 2"]}
            ]
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        call_input = json.loads(mock_run.call_args_list[0].kwargs['input'])
        self.assertEqual(call_input["prompt"], "part 1 part 2")
        # Injected step is capped at 10000 chars
        self.assertEqual(len(out["injectSteps"][0]["ephemeralMessage"]), 10000)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_pre_invocation_messages_array_extraction(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"systemMessage": "Injected context"}), stderr="")
        mock_run.return_value = mock_result
        
        payload = {
            "invocationNum": 1,
            "messages": [
                {"role": "user", "content": "Hello world from messages"}
            ]
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(len(out.get("injectSteps", [])), 2)
        call_input = json.loads(mock_run.call_args_list[0].kwargs['input'])
        self.assertEqual(call_input["prompt"], "Hello world from messages")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_FLAT_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_flat_schema_tolerance(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"decision": "block", "reason": "Flat stop block"}), stderr="")
        mock_run.return_value = mock_result
        
        payload = {"terminationReason": "model_stop"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "continue")
        self.assertEqual(out.get("reason"), "Flat stop block")
        mock_run.assert_called_once()

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_stop_event_block_returns_continue(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"decision": "block", "reason": "Uncommitted work detected"}), stderr="")
        mock_run.return_value = mock_result
        
        payload = {"terminationReason": "model_stop"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "continue")
        self.assertEqual(out.get("reason"), "Uncommitted work detected")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_multi_subagent_fanout_and_deny(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        res1 = MagicMock(returncode=0, stdout=json.dumps({"hookSpecificOutput": {}}), stderr="")
        res2 = MagicMock(returncode=0, stdout=json.dumps({"hookSpecificOutput": {}}), stderr="")
        res3 = MagicMock(returncode=0, stdout=json.dumps({"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": "Agent 2 not permitted"}}), stderr="")
        mock_run.side_effect = [res1, res2, res3, MagicMock()]
        
        payload = {
            "toolCall": {
                "name": "invoke_subagent",
                "args": {
                    "Subagents": [
                        {"TypeName": "agent1", "Workspace": "share", "Prompt": "p1"},
                        {"TypeName": "agent2", "Workspace": "branch", "Prompt": "p2"}
                    ]
                }
            }
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "deny")
        self.assertEqual(out.get("reason"), "[invoke_subagent (agent2)] Agent 2 not permitted")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_invoke_subagent_unrecognized_workspace_not_mapped_to_isolation(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        # Regression guard: Antigravity's Workspace concept ("share",
        # "branch") is not the same enum as Claude Code's `isolation` mode
        # ("worktree"/"remote"). hooks/flag-unassigned-worktree.py gates its
        # warning on the truthiness of `isolation`, so a non-empty but
        # unrecognized Workspace value must NOT surface as a truthy
        # `isolation` -- that would silently suppress the warning for every
        # subagent launch.
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"hookSpecificOutput": {}}), stderr="")
        mock_run.return_value = mock_result

        payload = {
            "toolCall": {
                "name": "invoke_subagent",
                "args": {
                    "Subagents": [
                        {"TypeName": "agent1", "Workspace": "share", "Prompt": "p1"}
                    ]
                }
            }
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "allow")
        call_input = json.loads(mock_run.call_args_list[0].kwargs['input'])
        self.assertIsNone(call_input["tool_input"].get("isolation"))
        # The raw Workspace value must still be preserved somewhere, just
        # not under the `isolation` key.
        self.assertEqual(call_input["tool_input"].get("workspace"), "share")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_invoke_subagent_worktree_workspace_mapped_to_isolation(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        # The positive case: a Workspace value that IS one of Claude Code's
        # recognized isolation modes must still map through.
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"hookSpecificOutput": {}}), stderr="")
        mock_run.return_value = mock_result

        payload = {
            "toolCall": {
                "name": "invoke_subagent",
                "args": {
                    "Subagents": [
                        {"TypeName": "agent1", "Workspace": "worktree", "Prompt": "p1"}
                    ]
                }
            }
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "allow")
        call_input = json.loads(mock_run.call_args_list[0].kwargs['input'])
        self.assertEqual(call_input["tool_input"].get("isolation"), "worktree")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_invoke_subagent_json_string_subagents(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"hookSpecificOutput": {}}), stderr="")
        mock_run.return_value = mock_result
        
        payload = {
            "toolCall": {
                "name": "invoke_subagent",
                "args": {
                    "Subagents": json.dumps([
                        {"TypeName": "agent1", "Workspace": "share", "Prompt": "p1"}
                    ])
                }
            }
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "allow")
        self.assertEqual(mock_run.call_count, 2)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    def test_invoke_subagent_fanout_cap_denial(self, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        subagents = [{"TypeName": f"agent{i}", "Workspace": "share", "Prompt": f"p{i}"} for i in range(55)]
        payload = {
            "toolCall": {
                "name": "invoke_subagent",
                "args": {"Subagents": subagents}
            }
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "deny")
        self.assertIn("exceeded maximum supported fanout limit of 50 subagents", out.get("reason", ""))

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_invoke_subagent_json_dict_string_evaluates_hook(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"hookSpecificOutput": {}}), stderr="")
        mock_run.return_value = mock_result
        
        payload = {
            "toolCall": {
                "name": "invoke_subagent",
                "args": {
                    "Subagents": json.dumps({"TypeName": "agent1", "Workspace": "share", "Prompt": "p1"})
                }
            }
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "allow")
        self.assertEqual(mock_run.call_count, 2)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    def test_invoke_subagent_missing_subagents_denial(self, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        payload = {
            "toolCall": {
                "name": "invoke_subagent",
                "args": {}
            }
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "deny")
        self.assertIn("missing required 'Subagents' argument", out.get("reason", ""))

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    def test_invoke_subagent_non_dict_item_denial(self, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        payload = {
            "toolCall": {
                "name": "invoke_subagent",
                "args": {"Subagents": ["invalid-string-item"]}
            }
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "deny")
        self.assertIn("must be an object", out.get("reason", ""))

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    def test_invoke_subagent_malformed_subagents_list(self, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        payload = {
            "toolCall": {
                "name": "invoke_subagent",
                "args": {"Subagents": "not-a-json-list"}
            }
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "deny")
        self.assertIn("malformed JSON string", out.get("reason", ""))

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_wildcard_and_mcp_matching(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"hookSpecificOutput": {}}), stderr="")
        mock_run.return_value = mock_result
        
        payload = {
            "toolCall": {
                "name": "mcp__github__create_pull_request",
                "args": {"title": "Test PR"}
            }
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        self.assertEqual(mock_run.call_count, 2)
        call_input = json.loads(mock_run.call_args_list[0].kwargs['input'])
        self.assertEqual(call_input["tool_name"], "mcp__github__create_pull_request")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    def test_null_args_in_tool_call(self, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        payload = {"toolCall": {"name": "run_command", "args": None}}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "allow")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_null_tool_call_falls_through_to_termination_reason(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"decision": "block", "reason": "Stop blocked"}), stderr="")
        mock_run.return_value = mock_result
        
        payload = {"toolCall": None, "terminationReason": "model_stop"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "continue")
        self.assertEqual(out.get("reason"), "Stop blocked")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_stop_event_continue_decision(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"decision": "continue", "reason": "Proceed with exit"}), stderr="")
        mock_run.return_value = mock_result
        
        payload = {"terminationReason": "model_stop"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out, {})

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_stop_event_allow_returns_empty_dict(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"decision": "allow"}), stderr="")
        mock_run.return_value = mock_result
        
        payload = {"terminationReason": "model_stop"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out, {})

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_stop_event_warn_only_system_message_surfaced(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        # A warn-only Stop hook (no block/deny decision) must still surface
        # its systemMessage in the top-level response rather than dropping
        # it after only reaching stderr.
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"systemMessage": "Unresolved obligations remain"}), stderr="")
        mock_run.return_value = mock_result

        payload = {"terminationReason": "model_stop"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("systemMessage"), "Unresolved obligations remain")
        self.assertNotIn("decision", out)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_pretooluse_top_level_system_message_surfaced_on_allow(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({
            "systemMessage": "Remember: this directory is protected.",
            "hookSpecificOutput": {}
        }), stderr="")
        mock_run.return_value = mock_result

        payload = {"toolCall": {"name": "run_command", "args": {"CommandLine": "ls"}}}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "allow")
        self.assertNotIn("systemMessage", out)
        # The message should have been logged to stderr instead
        stderr_val = mock_stderr.getvalue()
        self.assertIn("claude-hook-adapter [allow]: Remember: this directory is protected.", stderr_val)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_pretooluse_top_level_system_message_surfaced_on_deny(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({
            "systemMessage": "Writing to /etc is not allowed.",
            "hookSpecificOutput": {
                "permissionDecision": "deny",
                "permissionDecisionReason": "Unauthorized command"
            }
        }), stderr="")
        mock_run.return_value = mock_result

        payload = {"toolCall": {"name": "run_command", "args": {"CommandLine": "rm -rf /etc"}}}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "deny")
        self.assertNotIn("systemMessage", out)
        self.assertIn("Writing to /etc is not allowed.", out.get("reason", ""))

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_pre_invocation_assistant_only_messages_yield_empty_prompt(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        # An assistant-only (or trailing-assistant) messages list must never
        # be substituted for the user's prompt: with no user/human-role
        # entry present, prompt_val stays empty rather than grabbing the
        # last entry regardless of role.
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"systemMessage": "context"}), stderr="")
        mock_run.return_value = mock_result

        payload = {
            "invocationNum": 1,
            "messages": [
                {"role": "assistant", "content": "The assistant's own prior turn"}
            ]
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        call_input = json.loads(mock_run.call_args_list[0].kwargs['input'])
        self.assertEqual(call_input["prompt"], "")

    @patch('os.path.exists', return_value=True)
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_script_key_executes_in_stop(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_exists):
        # extract_hook_list's "script" key support (test_extract_hook_list_
        # supports_script_key) must also be honored by the Stop execution
        # loop, not just by the list-flattening step.
        script_hooks_def = {
            "hooks": {
                "Stop": [{"script": "python3 /path/to/stop-hook.py"}]
            }
        }
        with patch('builtins.open', mock_open(read_data=json.dumps(script_hooks_def))):
            mock_result = MagicMock(returncode=0, stdout=json.dumps({}), stderr="")
            mock_run.return_value = mock_result

            payload = {"terminationReason": "model_stop"}
            mock_stdin.write(json.dumps(payload))
            mock_stdin.seek(0)

            self.adapter.main()

        self.assertEqual(mock_run.call_count, 1)
        self.assertIn("stop-hook.py", mock_run.call_args_list[0].args[0])

    @patch('os.path.exists', return_value=True)
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_script_key_executes_in_pre_invocation(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_exists):
        # extract_hook_list's "script" key support (test_extract_hook_list_
        # supports_script_key) must also be honored by the PreInvocation
        # (UserPromptSubmit) execution loop, not just by the Stop loop
        # covered in test_script_key_executes_in_stop.
        ups_script_hooks_def = {
            "hooks": {
                "UserPromptSubmit": [{"script": "python3 /path/to/prompt-hook.py"}]
            }
        }
        with patch('builtins.open', mock_open(read_data=json.dumps(ups_script_hooks_def))):
            mock_result = MagicMock(returncode=0, stdout=json.dumps({"systemMessage": "context"}), stderr="")
            mock_run.return_value = mock_result

            payload = {"invocationNum": 1, "prompt": "hello"}
            mock_stdin.write(json.dumps(payload))
            mock_stdin.seek(0)

            self.adapter.main()

        self.assertEqual(mock_run.call_count, 1)
        self.assertIn("prompt-hook.py", mock_run.call_args_list[0].args[0])
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("injectSteps"), [{"ephemeralMessage": "context"}])

    # -- Dual-case Subagents lookup ------------------------------------

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_invoke_subagent_lowercase_subagents_key_dispatches(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        # Every sibling arg lookup in this file (Recipient/recipient,
        # name/Name, ...) is dual-case and fail-open; Subagents/subagents
        # must be too, rather than hard-denying a lowercase-only payload.
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"hookSpecificOutput": {}}), stderr="")
        mock_run.return_value = mock_result

        payload = {
            "toolCall": {
                "name": "invoke_subagent",
                "args": {
                    "subagents": [{"typeName": "agent1", "workspace": "share", "prompt": "p1"}]
                }
            }
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "allow")
        self.assertEqual(mock_run.call_count, 2)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    def test_invoke_subagent_empty_list_not_treated_as_missing(self, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        # A present-but-falsy Subagents value (an empty list) must not be
        # treated as absent by the dual-case lookup -- it is a real,
        # explicit "run zero subagents", not a missing argument.
        payload = {
            "toolCall": {
                "name": "invoke_subagent",
                "args": {"Subagents": []}
            }
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "allow")

    # -- matches_tool: invalid regex and empty/absent matcher ----------

    def test_matches_tool_invalid_regex_logs_diagnostic(self):
        buf = io.StringIO()
        with patch('sys.stderr', buf):
            result = self.adapter.matches_tool("[invalid(regex", "SomeTool")
        self.assertFalse(result)
        self.assertIn("invalid matcher pattern", buf.getvalue())
        self.assertIn("[invalid(regex", buf.getvalue())

    def test_matches_tool_empty_or_absent_matcher_matches_all(self):
        # Claude Code's documented PreToolUse semantics: a hook group with
        # no matcher applies to every tool call, the same as an explicit
        # "*" -- not "matches nothing".
        self.assertTrue(self.adapter.matches_tool("", "AnyTool"))
        self.assertTrue(self.adapter.matches_tool(None, "AnyTool"))

    # -- Nested hookSpecificOutput.additionalContext --------------------

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_stop_event_nested_additional_context_surfaced(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        # The documented hook-output shape nests additionalContext under
        # hookSpecificOutput (as the PreToolUse branch reads it); the Stop
        # loop must read that nested form too, not only a top-level one.
        mock_result = MagicMock(returncode=0, stdout=json.dumps({
            "hookSpecificOutput": {"additionalContext": "Unresolved obligations (nested)"}
        }), stderr="")
        mock_run.return_value = mock_result

        payload = {"terminationReason": "model_stop"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("systemMessage"), "Unresolved obligations (nested)")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_pre_invocation_nested_additional_context_injected(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({
            "hookSpecificOutput": {"additionalContext": "Nested context message"}
        }), stderr="")
        mock_run.return_value = mock_result

        payload = {"invocationNum": 1, "prompt": "test"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        out = json.loads(mock_stdout.getvalue())
        # MOCK_HOOKS_DEF's UserPromptSubmit group runs two hooks, and both
        # are mocked to return the same nested-context payload.
        self.assertEqual(
            out.get("injectSteps"),
            [{"ephemeralMessage": "Nested context message"}] * 2,
        )

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_pre_invocation_non_string_additional_context_does_not_crash(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        # Regression guard: a hook returning a non-string
        # additionalContext (a dict here, but a list or a number is the
        # same shape of bug) must not crash the adapter with an uncaught
        # AttributeError from `.encode("utf-8")` on a non-str value.
        # PreInvocation must coerce it to a string, mirroring the
        # str(...) coercion the PreToolUse and Stop branches already
        # apply to their own systemMessage/additionalContext reads, and
        # must still emit valid JSON either way.
        mock_result = MagicMock(returncode=0, stdout=json.dumps({
            "additionalContext": {"nested": "object"}
        }), stderr="")
        mock_run.return_value = mock_result

        payload = {"invocationNum": 1, "prompt": "test"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        out = json.loads(mock_stdout.getvalue())
        self.assertIn("injectSteps", out)
        # MOCK_HOOKS_DEF's UserPromptSubmit group runs two hooks, and both
        # are mocked to return the same non-string additionalContext.
        self.assertEqual(len(out["injectSteps"]), 2)
        for step in out["injectSteps"]:
            self.assertEqual(step["ephemeralMessage"], str({"nested": "object"}))

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_pre_invocation_invalid_json_output_logs_diagnostic_and_falls_back_to_raw_text(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        # Regression guard: the PreInvocation JSON-parse fallback used to be
        # the file's only `except Exception: pass` with no diagnostic. A
        # hook returning non-JSON text must still fall back to using that
        # raw text (unchanged behavior) AND must log a stderr diagnostic,
        # like every sibling parse handler in this file.
        mock_result = MagicMock(returncode=0, stdout="not valid json {", stderr="")
        mock_run.return_value = mock_result

        payload = {"invocationNum": 1, "prompt": "test"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        self.adapter.main()

        out = json.loads(mock_stdout.getvalue())
        self.assertIn("injectSteps", out)
        # MOCK_HOOKS_DEF's UserPromptSubmit group runs two hooks, and both
        # are mocked to return the same non-JSON text.
        self.assertEqual(len(out["injectSteps"]), 2)
        for step in out["injectSteps"]:
            self.assertEqual(step["ephemeralMessage"], "not valid json {")
        self.assertIn("failed to parse PreInvocation hook output", mock_stderr.getvalue())

    def test_default_timeout_applied_at_all_three_call_sites(self):
        # Regression guard for the resolve_cmd_and_timeout() extraction:
        # a hook entry with no "timeout" key must fall back to the same
        # 30-second default at PreToolUse, Stop, and PreInvocation alike,
        # since all three now share one helper.
        no_timeout_hooks_def = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"command": "cmd_pretooluse"}]}
                ],
                "Stop": [
                    {"hooks": [{"command": "cmd_stop"}]}
                ],
                "UserPromptSubmit": [
                    {"hooks": [{"command": "cmd_preinvocation"}]}
                ]
            }
        }
        mock_result = MagicMock(returncode=0, stdout=json.dumps({}), stderr="")

        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(no_timeout_hooks_def))), \
             patch('subprocess.run', return_value=mock_result) as mock_run, \
             patch('sys.stderr', new_callable=io.StringIO):

            with patch('sys.stdin', io.StringIO(json.dumps(
                    {"toolCall": {"name": "run_command", "args": {"CommandLine": "x"}}}))), \
                 patch('sys.stdout', new_callable=io.StringIO):
                self.adapter.main()
            self.assertEqual(mock_run.call_args_list[-1].kwargs['timeout'], 30.0)

            with patch('sys.stdin', io.StringIO(json.dumps(
                    {"terminationReason": "model_stop"}))), \
                 patch('sys.stdout', new_callable=io.StringIO):
                self.adapter.main()
            self.assertEqual(mock_run.call_args_list[-1].kwargs['timeout'], 30.0)

            with patch('sys.stdin', io.StringIO(json.dumps(
                    {"invocationNum": 1, "prompt": "test"}))), \
                 patch('sys.stdout', new_callable=io.StringIO):
                self.adapter.main()
            self.assertEqual(mock_run.call_args_list[-1].kwargs['timeout'], 30.0)

    # -- Configurable caps (env-var overrides) ---------------------------

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    def test_fanout_cap_overridable_via_env_var(self, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        with patch.dict(os.environ, {"AGY_ADAPTER_FANOUT_CAP": "2"}):
            adapter = load_adapter()
        self.assertEqual(adapter.SUBAGENT_FANOUT_CAP, 2)

        subagents = [{"TypeName": f"agent{i}", "Workspace": "share", "Prompt": f"p{i}"} for i in range(3)]
        payload = {
            "toolCall": {
                "name": "invoke_subagent",
                "args": {"Subagents": subagents}
            }
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)

        adapter.main()

        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "deny")
        self.assertIn("exceeded maximum supported fanout limit of 2 subagents", out.get("reason", ""))

    def test_int_env_malformed_value_falls_back_to_default_with_diagnostic(self):
        buf = io.StringIO()
        with patch.dict(os.environ, {"AGY_ADAPTER_FANOUT_CAP": "not-an-int"}):
            with patch('sys.stderr', buf):
                adapter = load_adapter()
        self.assertEqual(adapter.SUBAGENT_FANOUT_CAP, 50)
        self.assertIn("invalid AGY_ADAPTER_FANOUT_CAP", buf.getvalue())

    def test_int_env_missing_value_uses_default_silently(self):
        buf = io.StringIO()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AGY_ADAPTER_MSG_CAP", None)
            with patch('sys.stderr', buf):
                adapter = load_adapter()
        self.assertEqual(adapter.PRE_INVOCATION_MSG_CAP, 20)
        self.assertEqual(adapter.PRE_INVOCATION_MSG_BYTE_CAP, 10000)
        self.assertEqual(adapter.PRE_INVOCATION_TOTAL_BYTE_CAP, 30000)
        self.assertEqual(buf.getvalue(), "")

    # -- Symlink invocation & repo_root resolution (Issue #2681) ---------

    def test_symlink_invocation_resolves_repo_root_to_find_hooks_json(self):
        """Under ~/.gemini/config/plugins/ai-config/... invocation (symlink),
        __file__ must resolve via realpath so hooks/hooks.json is located in the
        real repo checkout, not in the config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_repo = os.path.join(tmpdir, "repo")
            fake_config = os.path.join(tmpdir, "gemini_config")
            
            repo_plugins_dir = os.path.join(fake_repo, "plugins", "ai-config")
            repo_hooks_dir = os.path.join(fake_repo, "hooks")
            os.makedirs(repo_plugins_dir, exist_ok=True)
            os.makedirs(repo_hooks_dir, exist_ok=True)

            config_plugins_dir = os.path.join(fake_config, "plugins")
            os.makedirs(config_plugins_dir, exist_ok=True)

            # Copy actual adapter into fake_repo
            fake_adapter_path = os.path.join(repo_plugins_dir, "claude-hook-adapter.py")
            shutil.copy2(ADAPTER_SCRIPT, fake_adapter_path)

            # Create mock hook script that denies
            mock_deny_path = os.path.join(repo_hooks_dir, "mock-deny.py")
            with open(mock_deny_path, "w", encoding="utf-8") as f:
                f.write(
                    "import sys, json\n"
                    "print(json.dumps({'hookSpecificOutput': {'permissionDecision': 'deny', 'permissionDecisionReason': 'blocked by real repo hook'}}))\n"
                )

            # Create mock hook script for stop that blocks
            mock_stop_path = os.path.join(repo_hooks_dir, "mock-stop.py")
            with open(mock_stop_path, "w", encoding="utf-8") as f:
                f.write(
                    "import sys, json\n"
                    "print(json.dumps({'decision': 'block', 'reason': 'unresolved obligations'}))\n"
                )

            # Create mock hook script for preinvocation
            mock_preinv_path = os.path.join(repo_hooks_dir, "mock-preinv.py")
            with open(mock_preinv_path, "w", encoding="utf-8") as f:
                f.write(
                    "import sys, json\n"
                    "print(json.dumps({'systemMessage': 'injected context from hook'}))\n"
                )

            # Write hooks.json in fake_repo referencing ${CLAUDE_PLUGIN_ROOT}
            hooks_json_path = os.path.join(repo_hooks_dir, "hooks.json")
            with open(hooks_json_path, "w", encoding="utf-8") as f:
                json.dump({
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "Bash",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/mock-deny.py\""
                                    }
                                ]
                            }
                        ],
                        "Stop": [
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/mock-stop.py\""
                                    }
                                ]
                            }
                        ],
                        "UserPromptSubmit": [
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/mock-preinv.py\""
                                    }
                                ]
                            }
                        ]
                    }
                }, f)

            # Create symlink: fake_config/plugins/ai-config -> fake_repo/plugins/ai-config
            symlink_plugin_dir = os.path.join(config_plugins_dir, "ai-config")
            os.symlink(repo_plugins_dir, symlink_plugin_dir)

            symlink_adapter_path = os.path.join(symlink_plugin_dir, "claude-hook-adapter.py")

            # 1. PreToolUse via symlink
            payload_pretool = {
                "toolCall": {
                    "name": "run_command",
                    "args": {"CommandLine": "git push"}
                }
            }
            proc = subprocess.run(
                [sys.executable, symlink_adapter_path],
                input=json.dumps(payload_pretool),
                text=True,
                capture_output=True,
                check=False
            )
            self.assertEqual(proc.returncode, 0, f"Adapter PreToolUse failed: {proc.stderr}")
            self.assertNotIn("hooks.json not found", proc.stderr)
            out = json.loads(proc.stdout)
            self.assertEqual(out.get("decision"), "deny")
            self.assertIn("blocked by real repo hook", out.get("reason", ""))

            # 2. Stop via symlink
            payload_stop = {
                "terminationReason": "model_stop"
            }
            proc_stop = subprocess.run(
                [sys.executable, symlink_adapter_path],
                input=json.dumps(payload_stop),
                text=True,
                capture_output=True,
                check=False
            )
            self.assertEqual(proc_stop.returncode, 0, f"Adapter Stop failed: {proc_stop.stderr}")
            self.assertNotIn("hooks.json not found", proc_stop.stderr)
            out_stop = json.loads(proc_stop.stdout)
            self.assertEqual(out_stop.get("decision"), "continue")
            self.assertIn("unresolved obligations", out_stop.get("reason", ""))

            # 3. PreInvocation via symlink
            payload_preinv = {
                "invocationNum": 1,
                "prompt": "hello"
            }
            proc_preinv = subprocess.run(
                [sys.executable, symlink_adapter_path],
                input=json.dumps(payload_preinv),
                text=True,
                capture_output=True,
                check=False
            )
            self.assertEqual(proc_preinv.returncode, 0, f"Adapter PreInvocation failed: {proc_preinv.stderr}")
            self.assertNotIn("hooks.json not found", proc_preinv.stderr)
            out_preinv = json.loads(proc_preinv.stdout)
            self.assertIn("injectSteps", out_preinv)
            self.assertTrue(any("injected context from hook" in step.get("ephemeralMessage", "") for step in out_preinv.get("injectSteps", [])))

if __name__ == "__main__":
    unittest.main()
