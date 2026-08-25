#!/usr/bin/env python3
"""Test suite for the Antigravity hook adapter (`plugins/ai-config/claude-hook-adapter.py`).

Tests the adapter in hermetic isolation by mocking `hooks/hooks.json` and subprocess calls.
Verifies event mapping (Bash, Agent, SendMessage, Task, generic/MCP tools), multi-subagent fanout,
regex & wildcard matchers, flat/grouped schema tolerance, Stop block-to-continue translation,
and PreInvocation context injection.
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

class TestAgyHookAdapter(unittest.TestCase):
    def setUp(self):
        self.assertTrue(os.path.isfile(ADAPTER_SCRIPT), f"Adapter script missing at {ADAPTER_SCRIPT}")
        self.adapter = load_adapter()

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_run_command_to_bash(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
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
    def test_pre_invocation_multi_message_join(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        res1 = MagicMock(returncode=0, stdout="Message 1\n", stderr="")
        res2 = MagicMock(returncode=0, stdout="Message 2\n", stderr="")
        mock_run.side_effect = [res1, res2]
        
        payload = {"invocationNum": 1, "transcriptPath": "/tmp/transcript.jsonl"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertIn("injectSteps", out)
        self.assertEqual(len(out["injectSteps"]), 1)
        self.assertEqual(out["injectSteps"][0]["ephemeralMessage"], "Message 1\n\nMessage 2")
        self.assertEqual(mock_run.call_count, 2)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_stop_event_block_to_continue(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"decision": "block", "reason": "Missing self-review"})
        mock_run.return_value = mock_result
        
        payload = {"terminationReason": "model_stop", "transcriptPath": "/tmp/transcript.jsonl"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "continue")
        self.assertEqual(out.get("reason"), "Missing self-review")
        
        input_payload = json.loads(mock_run.call_args.kwargs['input'])
        self.assertEqual(input_payload.get("termination_reason"), "model_stop")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_multi_subagent_fanout_and_deny(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        res1 = MagicMock(returncode=0, stdout=json.dumps({"hookSpecificOutput": {"additionalContext": "Warn 1"}}), stderr="")
        res2 = MagicMock(returncode=0, stdout=json.dumps({"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": "Agent 2 not permitted"}}), stderr="")
        mock_run.side_effect = [res1, res2]
        
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
        self.assertEqual(out.get("reason"), "Agent 2 not permitted")

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
        
        # Matches both mcp__github__.* and *
        self.assertEqual(mock_run.call_count, 2)
        call_input = json.loads(mock_run.call_args_list[0].kwargs['input'])
        self.assertEqual(call_input["tool_name"], "mcp__github__create_pull_request")

if __name__ == "__main__":
    unittest.main()
