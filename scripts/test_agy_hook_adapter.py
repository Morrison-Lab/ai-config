#!/usr/bin/env python3
"""Test suite for the Antigravity hook adapter (`plugins/ai-config/claude-hook-adapter.py`).

Tests the adapter in hermetic isolation by mocking `hooks/hooks.json` and subprocess calls.
Verifies event mapping, multi-subagent fanout, regex matchers, Stop block-to-continue translation,
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
                        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/test-prompt.py\"",
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
                        "timeout": 10
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
        self.adapter = load_adapter()

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_pre_invocation_event(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "UMS reminder: do not forget to check X\n"
        mock_run.return_value = mock_result
        
        payload = {"invocationNum": 1, "transcriptPath": "/tmp/transcript.jsonl"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertIn("injectSteps", out)
        self.assertEqual(len(out["injectSteps"]), 1)
        self.assertEqual(out["injectSteps"][0]["ephemeralMessage"], "UMS reminder: do not forget to check X")
        mock_run.assert_called_once()

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

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_multi_subagent_fanout(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "hookSpecificOutput": {
                "additionalContext": "Warning: isolation mode recommended"
            }
        })
        mock_run.return_value = mock_result
        
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
        
        # Verify subprocess.run was called for BOTH subagents
        self.assertEqual(mock_run.call_count, 2)
        call_inputs = [json.loads(c[1]['input']) for c in mock_run.call_args_list]
        self.assertEqual(call_inputs[0]["tool_input"]["subagent_type"], "agent1")
        self.assertEqual(call_inputs[1]["tool_input"]["subagent_type"], "agent2")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_HOOKS_DEF))
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_mcp_regex_matching(self, mock_run, mock_stderr, mock_stdout, mock_stdin, mock_file, mock_exists):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"hookSpecificOutput": {}})
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
        
        mock_run.assert_called_once()
        call_input = json.loads(mock_run.call_args[1]['input'])
        self.assertEqual(call_input["tool_name"], "mcp__github__create_pull_request")

if __name__ == "__main__":
    unittest.main()
