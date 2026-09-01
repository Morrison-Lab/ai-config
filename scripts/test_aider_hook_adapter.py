#!/usr/bin/env python3
"""Test suite for the Aider hook adapter (`plugins/ai-config/aider-hook-adapter.py`).

Tests markdown chat history parsing, JSONL transcript generation,
PreToolUse / Stop / UserPromptSubmit event dispatch, tool matcher filtering,
fail-open timeout resilience, CLI arguments, and integration with real repository hooks.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
ADAPTER_PATH = ROOT / "plugins" / "ai-config" / "aider-hook-adapter.py"

spec = importlib.util.spec_from_file_location("aider_hook_adapter", ADAPTER_PATH)
assert spec and spec.loader
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class TestAiderMarkdownParsing(unittest.TestCase):
    """Test parsing of various Aider chat history markdown patterns."""

    def test_parse_basic_conversation(self):
        sample_md = """# aider chat started at 2026-08-31 10:00:00

#### Please update the README to add installation instructions.

I'll update README.md with the installation steps.

Applied edit to README.md

I have updated the README.
"""
        turns = adapter.parse_aider_chat_history(sample_md)
        self.assertGreaterEqual(len(turns), 2)
        # First turn is system start
        self.assertEqual(turns[0]["role"], "system")
        self.assertIn("aider chat started", turns[0]["content"])

        # Second turn is user
        self.assertEqual(turns[1]["role"], "user")
        self.assertIn("Please update the README", turns[1]["content"])

        # Third turn is assistant
        self.assertEqual(turns[2]["role"], "assistant")
        self.assertIn("I have updated the README", turns[2]["content"])
        self.assertTrue(any(tc["name"] == "Edit" for tc in turns[2]["tool_calls"]))

    def test_parse_search_replace_block(self):
        sample_md = """#### Fix the typo in src/main.py

src/main.py
<<<<<<< SEARCH
def greet():
    print("helo")
=======
def greet():
    print("hello")
>>>>>>> REPLACE

Done!
"""
        turns = adapter.parse_aider_chat_history(sample_md)
        self.assertEqual(len(turns), 2)
        self.assertEqual(turns[0]["role"], "user")
        self.assertEqual(turns[1]["role"], "assistant")
        self.assertEqual(turns[1]["content"].count(">>>>>>> REPLACE"), 1)
        self.assertTrue(
            any(
                tc["name"] == "Edit" and tc["input"].get("file_path") == "src/main.py"
                for tc in turns[1]["tool_calls"]
            )
        )

    def test_parse_shell_commands_and_commits(self):
        sample_md = """#### Run the tests and commit

> /run pytest tests/

Commit a1b2c3d Fix tests
"""
        turns = adapter.parse_aider_chat_history(sample_md)
        self.assertEqual(turns[0]["role"], "user")
        self.assertEqual(turns[1]["role"], "assistant")
        tool_names = [tc["name"] for tc in turns[1]["tool_calls"]]
        self.assertIn("Bash", tool_names)
        bash_cmds = [tc["input"].get("command", "") for tc in turns[1]["tool_calls"] if tc["name"] == "Bash"]
        self.assertTrue(any("pytest tests/" in c for c in bash_cmds))
        self.assertTrue(any("git commit" in c for c in bash_cmds))

    def test_parse_quotes_style_user_prompts(self):
        sample_md = """# aider chat started at 2026-08-31 12:00:00

> Add helper function

Here is the helper function.
"""
        turns = adapter.parse_aider_chat_history(sample_md)
        self.assertEqual(turns[0]["role"], "system")
        self.assertEqual(turns[1]["role"], "user")
        self.assertIn("Add helper function", turns[1]["content"])
        self.assertEqual(turns[2]["role"], "assistant")
        self.assertIn("Here is the helper function", turns[2]["content"])


class TestTranscriptGeneration(unittest.TestCase):
    """Test converting parsed turns into JSONL transcripts."""

    def test_jsonl_output_format(self):
        turns = [
            {"role": "user", "content": "Hello", "tool_calls": [], "tool_results": []},
            {
                "role": "assistant",
                "content": "Running command",
                "tool_calls": [{"id": "call_1", "name": "Bash", "input": {"command": "ls -la"}}],
                "tool_results": [{"tool_use_id": "call_1", "content": "total 0"}],
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "transcript.jsonl"
            res_path = adapter.generate_jsonl_transcript(turns, out_file)
            self.assertEqual(res_path, out_file)
            self.assertTrue(out_file.is_file())

            lines = out_file.read_text(encoding="utf-8").strip().splitlines()
            self.assertGreaterEqual(len(lines), 2)
            parsed_records = [json.loads(line) for line in lines]
            self.assertEqual(parsed_records[0]["type"], "user")
            self.assertEqual(parsed_records[1]["type"], "assistant")
            self.assertEqual(parsed_records[1]["tool_calls"][0]["name"], "Bash")

    def test_temp_transcript_cleaned_up_after_event(self):
        res = adapter.adapt_aider_event(
            event="Stop",
            history_path_or_content="#### hello\n\nworld",
            hooks_manifest={"Stop": []},
        )
        temp_path = Path(res["transcript_path"])
        self.assertFalse(temp_path.exists())


class TestMatcherAndToolHelpers(unittest.TestCase):
    """Test tool matching and path normalization helpers."""

    def test_matches_tool(self):
        self.assertTrue(adapter.matches_tool("*", "Bash"))
        self.assertTrue(adapter.matches_tool(None, "Bash"))
        self.assertTrue(adapter.matches_tool("Bash", "Bash"))
        self.assertFalse(adapter.matches_tool("Bash", "Edit"))
        self.assertTrue(adapter.matches_tool("Bash|Edit", "Edit"))
        self.assertTrue(adapter.matches_tool("mcp__github__.*", "mcp__github__create_issue"))
        self.assertFalse(adapter.matches_tool("mcp__github__.*", "Bash"))

    def test_is_likely_file_path(self):
        self.assertEqual(adapter.is_likely_file_path("path/to/file.py"), "path/to/file.py")
        self.assertEqual(adapter.is_likely_file_path("SKILL.md"), "SKILL.md")
        self.assertEqual(adapter.is_likely_file_path("`scripts/check-links.py`"), "scripts/check-links.py")
        self.assertIsNone(adapter.is_likely_file_path("Done."))
        self.assertIsNone(adapter.is_likely_file_path("OK!"))
        self.assertIsNone(adapter.is_likely_file_path("Here are the changes:"))
        self.assertIsNone(adapter.is_likely_file_path("https://example.com/file.py"))


class TestEventAdaptationAndExecution(unittest.TestCase):
    """Test executing hooks and translating results."""

    def test_adapt_stop_hook_mock(self):
        sample_md = """#### Refactor module

I will now refactor the code.
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            hist_file = Path(tmpdir) / ".aider.chat.history.md"
            hist_file.write_text(sample_md, encoding="utf-8")

            mock_manifest = {
                "Stop": [
                    {
                        "hooks": [
                            {
                                "command": "python3 -c \"import sys; print('{\\\"decision\\\": \\\"allow\\\"}')\"",
                                "timeout": 5,
                            }
                        ]
                    }
                ]
            }

            out_transcript = Path(tmpdir) / "custom_transcript.jsonl"
            with patch.object(adapter, "load_hooks_manifest", return_value=mock_manifest):
                res = adapter.adapt_aider_event(
                    event="Stop",
                    history_path_or_content=hist_file,
                    cwd=tmpdir,
                    transcript_out=out_transcript,
                )
                self.assertEqual(res["decision"], "allow")
                self.assertIn("transcript_path", res)
                self.assertEqual(res["transcript_path"], str(out_transcript))
                self.assertTrue(out_transcript.is_file())

    def test_adapt_pre_tool_use_block(self):
        mock_manifest = {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "command": "python3 -c \"import sys; print('{\\\"decision\\\": \\\"block\\\", \\\"reason\\\": \\\"Command forbidden\\\"}')\"",
                            "timeout": 5,
                        }
                    ]
                }
            ]
        }
        with patch.object(adapter, "load_hooks_manifest", return_value=mock_manifest):
            res = adapter.adapt_aider_event(
                event="PreToolUse",
                tool_name="Bash",
                tool_input={"command": "rm -rf /"},
            )
            self.assertEqual(res["decision"], "block")
            self.assertIn("Command forbidden", res["reason"])

    def test_user_prompt_submit_warning(self):
        mock_manifest = {
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {
                            "command": "python3 -c \"import sys; print('{\\\"systemMessage\\\": \\\"Reminder: run tests\\\"}')\"",
                            "timeout": 5,
                        }
                    ]
                }
            ]
        }
        with patch.object(adapter, "load_hooks_manifest", return_value=mock_manifest):
            res = adapter.adapt_aider_event(
                event="UserPromptSubmit",
                history_path_or_content="#### Update file",
            )
            self.assertEqual(res["decision"], "allow")
            self.assertIn("Reminder: run tests", res["warnings"])

    def test_hook_timeout_fail_open(self):
        mock_manifest = {
            "Stop": [
                {
                    "hooks": [
                        {
                            "command": "python3 -c \"import time; time.sleep(2)\"",
                            "timeout": 0.1,
                        }
                    ]
                }
            ]
        }
        with patch.object(adapter, "load_hooks_manifest", return_value=mock_manifest):
            res = adapter.adapt_aider_event(
                event="Stop",
                history_path_or_content="#### Test timeout",
            )
            self.assertEqual(res["decision"], "allow")


class TestCLI(unittest.TestCase):
    """Test CLI execution and arguments."""

    def test_cli_parse_only(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("# aider chat started at 2026-08-31 10:00:00\n\n#### hello\n\nHi there!\n")
            f_path = f.name

        try:
            proc = subprocess.run(
                [sys.executable, str(ADAPTER_PATH), "--parse-only", "--history-file", f_path],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertIn("turns", data)
            self.assertEqual(len(data["turns"]), 3)
        finally:
            if os.path.exists(f_path):
                os.unlink(f_path)


class TestRealHooksIntegration(unittest.TestCase):
    """Integration tests running real repo hooks against translated Aider transcripts."""

    def test_no_empty_promise_real_hook_blocks(self):
        # Aider transcript with an undischarged rule promise
        md_history = """# aider chat started at 2026-08-31 10:00:00

#### Please fix the bug.

I have fixed the bug. Going forward I will always verify the return value before returning.
"""
        manifest = {
            "Stop": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "command": f"{sys.executable} ${{CLAUDE_PLUGIN_ROOT}}/hooks/no-empty-promise.py",
                            "timeout": 5,
                        }
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            hist_file = Path(tmpdir) / ".aider.chat.history.md"
            hist_file.write_text(md_history, encoding="utf-8")

            res = adapter.adapt_aider_event(
                event="Stop",
                history_path_or_content=hist_file,
                cwd=tmpdir,
                repo_root=ROOT,
                hooks_manifest=manifest,
            )
            self.assertEqual(res["decision"], "block")
            self.assertIn("no-empty-promise", str(res.get("reason", "")))

    def test_no_empty_promise_real_hook_passes_when_clean(self):
        # Clean assistant reply without empty promises
        md_history = """# aider chat started at 2026-08-31 10:00:00

#### Please fix the bug.

I have fixed the bug by modifying the return check.
"""
        manifest = {
            "Stop": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "command": f"{sys.executable} ${{CLAUDE_PLUGIN_ROOT}}/hooks/no-empty-promise.py",
                            "timeout": 5,
                        }
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            hist_file = Path(tmpdir) / ".aider.chat.history.md"
            hist_file.write_text(md_history, encoding="utf-8")

            res = adapter.adapt_aider_event(
                event="Stop",
                history_path_or_content=hist_file,
                cwd=tmpdir,
                repo_root=ROOT,
                hooks_manifest=manifest,
            )
            self.assertEqual(res["decision"], "allow")


if __name__ == "__main__":
    unittest.main()
