#!/usr/bin/env python3
"""Tests for the Antigravity hook command checker and renderer."""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import agy_hooks  # noqa: E402
from lib.agy_hooks_fixtures import (
    BACKSLASH,
    CHECKER,
    PYTHON_EXE,
    QUOTED_FORM,
    RENDERER,
    UNQUOTED_FORM,
)


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

class TestEnvironmentResolution(unittest.TestCase):
    def test_is_windows(self):
        with patch("os.name", "nt"):
            self.assertTrue(agy_hooks.is_windows())
        with patch("os.name", "posix"), patch("sys.platform", "linux"), patch.dict("os.environ", {}, clear=True):
            self.assertFalse(agy_hooks.is_windows())

    def test_resolve_plugin_dir(self):
        with patch("os.path.expanduser", return_value="C:/Users/u/.gemini/config/plugins/ai-config"):
            self.assertEqual(
                agy_hooks.resolve_plugin_dir(True),
                "C:/Users/u/.gemini/config/plugins/ai-config"
            )

    @patch.dict(os.environ, {"AGY_HOOK_PYTHON": "C:/Custom/Python/python.exe"})
    def test_resolve_python_exe_override(self):
        self.assertEqual(agy_hooks.resolve_python_exe(True), "C:/Custom/Python/python.exe")

    @patch.dict(os.environ, {"AGY_HOOK_PYTHON": "/mingw64/bin/python3.exe"})
    def test_resolve_python_exe_refuses_a_non_native_override(self):
        # An override is likelier than a detected path to come from an MSYS
        # shell, so it is checked rather than trusted.
        with self.assertRaises(ValueError):
            agy_hooks.resolve_python_exe(True)

    @patch.dict(os.environ, {"AGY_HOOK_PYTHON": "py"})
    def test_resolve_python_exe_allows_a_bare_name_override(self):
        self.assertEqual(agy_hooks.resolve_python_exe(True), "py")

    @patch.dict(os.environ, {"AGY_HOOK_PYTHON": "/usr/bin/python3"})
    def test_resolve_python_exe_leaves_a_posix_override_alone(self):
        self.assertEqual(agy_hooks.resolve_python_exe(False), "/usr/bin/python3")

    @patch.dict(os.environ, {}, clear=True)
    @patch("sys.executable", "/mingw64/bin/python.exe")
    @patch("shutil.which", return_value="C:/Python312/python.exe")
    def test_resolve_python_exe_native_path(self, mock_which):
        self.assertEqual(agy_hooks.resolve_python_exe(True), "C:/Python312/python.exe")

    @patch.dict(os.environ, {}, clear=True)
    @patch("sys.executable", "/mingw64/bin/python.exe")
    @patch("shutil.which", return_value="C:/Program Files/Python/python.exe")
    def test_resolve_python_exe_rejects_space(self, mock_which):
        resolved = agy_hooks.resolve_python_exe(True)
        with self.assertRaises(ValueError) as ctx:
            agy_hooks.assert_cmd_safe(resolved, "interpreter")
        self.assertIn("space", str(ctx.exception))

    @patch.dict(os.environ, {}, clear=True)
    @patch("sys.executable", "/mingw64/bin/python.exe")
    @patch("shutil.which", return_value=None)
    def test_resolve_python_exe_no_interpreter_raises(self, mock_which):
        with self.assertRaises(ValueError) as ctx:
            agy_hooks.resolve_python_exe(True)
        self.assertIn("cannot name a Windows interpreter", str(ctx.exception))


class TestInstallLocationOverrides(unittest.TestCase):
    """bootstrap.sh honours GEMINI_CONFIG_HOME and GEMINI_HOME."""

    def test_default_config_dir(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(agy_hooks.gemini_config_dir(), "~/.gemini/config")

    def test_gemini_home_moves_the_config_dir(self):
        with patch.dict(os.environ, {"GEMINI_HOME": "/opt/ag"}, clear=True):
            self.assertEqual(agy_hooks.gemini_config_dir(), "/opt/ag/config")

    def test_gemini_config_home_wins_over_gemini_home(self):
        env = {"GEMINI_HOME": "/opt/ag", "GEMINI_CONFIG_HOME": "/etc/ag"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(agy_hooks.gemini_config_dir(), "/etc/ag")

    def test_staged_manifest_follows_the_override(self):
        with patch.dict(os.environ, {"GEMINI_CONFIG_HOME": "/etc/ag"}, clear=True):
            self.assertEqual(
                agy_hooks.staged_manifest_path(),
                "/etc/ag/plugins/ai-config/hooks.json",
            )

    def test_rendered_plugin_dir_follows_the_override(self):
        with patch.dict(os.environ, {"GEMINI_CONFIG_HOME": "/etc/ag"}, clear=True):
            self.assertEqual(
                agy_hooks.resolve_plugin_dir(windows=False),
                "/etc/ag/plugins/ai-config",
            )


class TestRendererCli(unittest.TestCase):
    """main() is the entry point bootstrap.sh invokes."""

    def run_main(self, argv):
        """Run the CLI with its own output captured, and return the exit code."""
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            return RENDERER.main(argv)

    def test_output_writes_the_rendered_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nested" / "hooks.json"
            rc = self.run_main(["--platform", "posix", "--output", str(out)])
            self.assertEqual(rc, 0)
            self.assertTrue(out.exists())
            self.assertTrue(list(agy_hooks.iter_commands(json.loads(out.read_text()))))

    def test_missing_source_reports_one_line_and_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "absent.json"
            rc = self.run_main(["--platform", "posix", "--source", str(missing)])
            self.assertEqual(rc, 1)

    def test_a_render_failure_writes_no_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "hooks.json"
            missing = Path(tmp) / "absent.json"
            rc = self.run_main(
                ["--platform", "posix", "--source", str(missing), "--output", str(out)]
            )
            self.assertEqual(rc, 1)
            self.assertFalse(out.exists())

if __name__ == "__main__":
    unittest.main()
