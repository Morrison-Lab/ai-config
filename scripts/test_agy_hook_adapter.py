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
    def test_invoke_subagent_json_dict_string_warning(self, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
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
        self.assertIn("Subagents argument is not a list: dict", mock_stderr.getvalue())

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    def test_invoke_subagent_malformed_subagents_list(self, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        payload = {
            "toolCall": {
                "name": "invoke_subagent",
                "args": {"Subagents": "not-a-list"}
            }
        }
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
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"decision": "continue", "reason": "Native continue"}), stderr="")
        mock_run.return_value = mock_result
        
        payload = {"terminationReason": "model_stop"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "continue")
        self.assertEqual(out.get("reason"), "Native continue")

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

if __name__ == "__main__":
    unittest.main()
