#!/usr/bin/env python3
"""Test suite for the Antigravity hook adapter (`plugins/ai-config/claude-hook-adapter.py`).

Before this test existed, `test_hooks.py` tested the Claude Code hooks themselves,
but the adapter mapping Antigravity's lifecycle events to those hooks was untested.
This script feeds mock Antigravity payloads into the adapter and asserts that it
parses the payloads correctly, runs the expected underlying hooks via subprocess,
and formats its stdout into the schema Antigravity expects.
"""
import importlib.util
import io
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADAPTER_SCRIPT = os.path.join(ROOT, "plugins", "ai-config", "claude-hook-adapter.py")

def load_adapter():
    spec = importlib.util.spec_from_file_location("claude_hook_adapter", ADAPTER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class TestAgyHookAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = load_adapter()
        
    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_pre_invocation_event(self, mock_run, mock_stderr, mock_stdout, mock_stdin):
        # Mock the underlying hook's execution
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "UMS reminder: do not forget to check X\n"
        mock_run.return_value = mock_result
        
        payload = {"invocationNum": 1, "transcriptPath": "/tmp/transcript.jsonl"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        # Execute
        self.adapter.main()
        
        # Verify output format
        out = json.loads(mock_stdout.getvalue())
        self.assertIn("injectSteps", out)
        self.assertGreaterEqual(len(out["injectSteps"]), 1)
        self.assertIn("UMS reminder: do not forget to check X", out["injectSteps"][0]["ephemeralMessage"])
        
        # Verify it actually called subprocess (the exact command will depend on hooks.json, 
        # but we know it should have called at least one hook for UserPromptSubmit)
        mock_run.assert_called()

    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_stop_event_block(self, mock_run, mock_stderr, mock_stdout, mock_stdin):
        # Mock the underlying hook blocking the stop
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

    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_stop_event_allow(self, mock_run, mock_stderr, mock_stdout, mock_stdin):
        # Mock the underlying hook allowing the stop
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"decision": "allow"})
        mock_run.return_value = mock_result
        
        payload = {"terminationReason": "model_stop"}
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "allow")

    @patch('sys.stdin', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('subprocess.run')
    def test_pre_tool_use_agent(self, mock_run, mock_stderr, mock_stdout, mock_stdin):
        # Mock an Agent hook issuing a warning
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
                    "Subagents": [{"TypeName": "research", "Workspace": "share", "Prompt": "look"}]
                }
            }
        }
        mock_stdin.write(json.dumps(payload))
        mock_stdin.seek(0)
        
        self.adapter.main()
        
        # Verify the Claude payload structure was correctly adapted from Antigravity format
        # The adapter passes json.dumps(claude_payload) to subprocess.run(input=...)
        call_args = mock_run.call_args
        self.assertIsNotNone(call_args)
        kwargs = call_args[1]
        passed_input = json.loads(kwargs['input'])
        
        self.assertEqual(passed_input["tool_name"], "Agent")
        self.assertEqual(passed_input["tool_input"]["subagent_type"], "research")
        self.assertEqual(passed_input["tool_input"]["isolation"], "share")
        
        # Output should allow but print warning to stderr
        out = json.loads(mock_stdout.getvalue())
        self.assertEqual(out.get("decision"), "allow")
        self.assertIn("Warning: isolation mode recommended", mock_stderr.getvalue())

if __name__ == "__main__":
    unittest.main()
