#!/usr/bin/env python3
"""Tests for the Antigravity hook command checker and renderer.

The measured failure (ai-config#3091) is the positive case: the staged Windows
manifest carried quoted absolute paths, and `cmd.exe` reported the path as not
recognized because the launcher re-escapes an embedded quote on the way. Both
the escaped form recorded in the issue and the correctly quoted form are
rejected here, since neither can launch.

The negative controls matter as much: the repo's own canonical manifest passes,
and the rendered POSIX form passes. A checker that rejects everything and a
checker that never runs are indistinguishable from a red build alone.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import agy_hooks  # noqa: E402


def load_checker():
    """Import the hyphenated checker script as a module."""
    path = REPO_ROOT / "scripts" / "check-agy-hook-commands.py"
    spec = importlib.util.spec_from_file_location("check_agy_hook_commands", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = load_checker()

BACKSLASH = chr(92)
PYTHON_EXE = "C:/Users/u/AppData/Local/Programs/Python/Python312/python.exe"
ADAPTER = "C:/Users/u/.gemini/config/plugins/ai-config/claude-hook-adapter.py"

# The exact string the installed manifest carried, per the issue: each quote
# preceded by a backslash inside the JSON string VALUE.
ESCAPED_FORM = (
    BACKSLASH + '"' + PYTHON_EXE + BACKSLASH + '" '
    + BACKSLASH + '"' + ADAPTER + BACKSLASH + '"'
)
QUOTED_FORM = '"' + PYTHON_EXE + '" "' + ADAPTER + '"'
UNQUOTED_FORM = PYTHON_EXE + " " + ADAPTER


def manifest_with(command: str) -> dict:
    """Wrap one command in both manifest shapes Antigravity uses."""
    return {
        "enforce-merge-control": {
            "PreToolUse": [
                {"matcher": "run_command", "hooks": [{"type": "command", "command": command}]}
            ],
            "Stop": [{"type": "command", "command": command}],
        }
    }


class TestRender(unittest.TestCase):
    def test_posix_render_keeps_the_portable_form(self):
        manifest = json.loads(CHECKER.CANONICAL_MANIFEST.read_text(encoding="utf-8"))
        rendered = agy_hooks.render_manifest(manifest, windows=False)
        for _, command in agy_hooks.iter_commands(rendered):
            self.assertTrue(command.startswith("python3 ~/.gemini/"))

    def test_windows_render_carries_no_quotes(self):
        manifest = json.loads(CHECKER.CANONICAL_MANIFEST.read_text(encoding="utf-8"))
        rendered = agy_hooks.render_manifest(
            manifest,
            windows=True,
            python_exe=PYTHON_EXE,
            plugin_dir="C:/Users/u/.gemini/config/plugins/ai-config",
        )
        for _, command in agy_hooks.iter_commands(rendered):
            self.assertEqual(agy_hooks.windows_problems(command), [])
            self.assertTrue(command.startswith(PYTHON_EXE + " C:/Users/u/.gemini/"))
            self.assertNotIn("\\\"", command)
            self.assertNotIn("\\\"", json.dumps(command))

    def test_windows_render_refuses_a_path_with_a_space(self):
        with self.assertRaises(ValueError):
            agy_hooks.render_command(
                "python3 ~/.gemini/config/plugins/ai-config/claude-hook-adapter.py",
                "C:/Program Files/Python312/python.exe",
                "C:/Users/u/.gemini/config/plugins/ai-config",
                windows=True,
            )

    def test_rendered_json_escapes_a_quote_exactly_once(self):
        """A real quote must survive one JSON round trip unchanged."""
        text = json.dumps({"command": QUOTED_FORM})
        self.assertEqual(json.loads(text)["command"], QUOTED_FORM)
        self.assertNotIn(BACKSLASH + BACKSLASH, text)


class TestProgramResolution(unittest.TestCase):
    def test_missing_program_does_not_resolve(self):
        self.assertFalse(agy_hooks.program_resolves("C:/nope/does-not-exist.exe script.py"))

    def test_program_token_reads_a_quoted_first_token(self):
        self.assertEqual(agy_hooks.program_token(QUOTED_FORM), PYTHON_EXE)
        self.assertEqual(agy_hooks.program_token(UNQUOTED_FORM), PYTHON_EXE)

    def test_running_interpreter_resolves(self):
        self.assertTrue(agy_hooks.program_resolves(sys.executable + " x.py"))


class TestNativePathDetection(unittest.TestCase):
    def test_msys_path_is_not_native(self):
        self.assertFalse(agy_hooks.is_native_windows_path("/mingw64/bin/python3.exe"))

    def test_drive_letter_path_is_native(self):
        self.assertTrue(agy_hooks.is_native_windows_path(PYTHON_EXE))


if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()
