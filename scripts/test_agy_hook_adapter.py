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
import sys
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
    def test_run_command_cwd_fallback_to_repo_root(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
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
        # cwd passed to subprocess.run is repo_root when Cwd is absent
        self.assertTrue(os.path.isabs(mock_run.call_args_list[0].kwargs['cwd']))

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
        # Both the "Bash" and the wildcard "*" matcher groups fire for a
        # run_command call, so the mocked message is forwarded from each.
        self.assertIn("Remember: this directory is protected.", out.get("systemMessage", ""))

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
        self.assertEqual(out.get("systemMessage"), "Writing to /etc is not allowed.")

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
    def test_script_key_executes_in_stop_and_pre_invocation(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_exists):
        # extract_hook_list's "script" key support (test_extract_hook_list_
        # supports_script_key) must also be honored by the execution loops,
        # not just by the list-flattening step.
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

if __name__ == "__main__":
    unittest.main()
