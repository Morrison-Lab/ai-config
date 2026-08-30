#!/usr/bin/env python3
import os
import sys
import tempfile
import json
import time
import unittest
from unittest.mock import patch

# Import the module to test
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
enforcer = __import__("antigravity_hook_enforcer")

class TestAntigravityHookEnforcer(unittest.TestCase):
    def test_get_hooks(self):
        with tempfile.TemporaryDirectory() as root:
            hooks_dir = os.path.join(root, "hooks")
            os.makedirs(hooks_dir)
            with open(os.path.join(hooks_dir, "hooks.json"), "w") as f:
                json.dump({
                    "hooks": {
                        "Stop": [
                            {"hooks": [{"command": "echo test"}]}
                        ]
                    }
                }, f)
            
            hooks = enforcer.get_hooks(root)
            self.assertEqual(len(hooks), 1)
            self.assertEqual(hooks[0]["command"], "echo test")

    def test_scan_transcripts_triggers_hook(self):
        with tempfile.TemporaryDirectory() as brain_dir:
            # Create a mock transcript directory
            conv_dir = os.path.join(brain_dir, "test_conv", ".system_generated", "logs")
            os.makedirs(conv_dir)
            transcript_path = os.path.join(conv_dir, "transcript.jsonl")
            with open(transcript_path, "w") as f:
                f.write('{"type":"USER_INPUT"}\n')
            
            known_mtimes = {}
            active_transcripts = [transcript_path]
            # Emit both a block and a systemMessage to test both logic paths
            hooks = [{"command": "echo '{\"decision\": \"block\", \"reason\": \"test\", \"systemMessage\": \"warn\"}'"}]
            
            with patch.object(enforcer, 'get_hooks', return_value=hooks):
                with patch.object(enforcer, 'notify') as mock_notify:
                    root = "test_root"
                    
                    # First run initializes
                    enforcer.scan_transcripts(known_mtimes, active_transcripts, root, is_startup=True)
                    self.assertIn(transcript_path, known_mtimes)
                    
                    # Modify transcript and explicitly set mtime in future
                    with open(transcript_path, "a") as f:
                        f.write('{"type":"PLANNER_RESPONSE"}\n')
                    future_time = time.time() + 10
                    os.utime(transcript_path, (future_time, future_time))
                    
                    # Second run should trigger
                    enforcer.scan_transcripts(known_mtimes, active_transcripts, root, is_startup=False)
                    self.assertEqual(mock_notify.call_count, 2)
                    mock_notify.assert_any_call("Agent Hook Violation: guard", "test")
                    mock_notify.assert_any_call("Agent Hook Warning: guard", "warn")

if __name__ == "__main__":
    unittest.main()
