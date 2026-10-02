#!/usr/bin/env python3
"""Tests for scripts/wire-user-config.py (ai-config#4206).

Each case points HOME (and GEMINI_HOME / XDG_CONFIG_HOME) at a fresh temp
directory, so nothing touches the real user config.
"""
import importlib.util
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("wire", HERE / "wire-user-config.py")
wire = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wire)


class WireUserConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        env = {"HOME": str(self.home), "GEMINI_HOME": str(self.home / ".gemini"),
               "XDG_CONFIG_HOME": str(self.home / ".config")}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        which = mock.patch.object(wire.shutil, "which", return_value=None)
        which.start()
        self.addCleanup(which.stop)

    def run_main(self, *argv):
        out = StringIO()
        with redirect_stdout(out):
            code = wire.main(list(argv))
        return code, out.getvalue()

    def settings(self):
        return json.loads((self.home / ".claude/settings.json").read_text())

    def test_fresh_machine_wires_everything_and_is_idempotent(self):
        code, out = self.run_main("--check")
        self.assertEqual(code, 1, out)
        code, out = self.run_main()
        self.assertEqual(code, 0, out)
        s = self.settings()
        self.assertTrue(s["enabledPlugins"]["ai-config@Morrison-Lab"])
        self.assertEqual(s["extraKnownMarketplaces"]["Morrison-Lab"]["source"]["repo"],
                         "Morrison-Lab/ai-config")
        codex = self.home / ".codex/AGENTS.md"
        self.assertTrue(codex.is_symlink())
        self.assertEqual(codex.resolve(), (wire.ROOT / "AGENTS.md").resolve())
        gemini = (self.home / ".gemini/GEMINI.md").read_text()
        self.assertIn(f"@{wire.ROOT / 'AGENTS.md'}", gemini)
        code, out = self.run_main("--check")
        self.assertEqual(code, 0, out)
        before = (self.home / ".gemini/GEMINI.md").read_text()
        self.run_main()
        self.assertEqual((self.home / ".gemini/GEMINI.md").read_text(), before)

    def test_existing_settings_are_preserved(self):
        path = self.home / ".claude/settings.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"model": "opus", "enabledPlugins": {"x@y": True}}))
        self.run_main()
        s = self.settings()
        self.assertEqual(s["model"], "opus")
        self.assertTrue(s["enabledPlugins"]["x@y"])
        self.assertTrue(s["enabledPlugins"]["ai-config@Morrison-Lab"])

    def test_explicit_disable_is_respected(self):
        path = self.home / ".claude/settings.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"enabledPlugins": {"ai-config@Morrison-Lab": False}}))
        code, out = self.run_main()
        self.assertIn("disables the plugin", out)
        self.assertFalse(self.settings()["enabledPlugins"]["ai-config@Morrison-Lab"])

    def test_other_marketplace_copy_counts_as_enabled(self):
        path = self.home / ".claude/settings.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"enabledPlugins": {"ai-config@ai-config": True}}))
        _, out = self.run_main()
        self.assertNotIn("ai-config@Morrison-Lab", self.settings()["enabledPlugins"])
        self.assertIn("ok", out)

    def test_non_plugin_hook_install_blocks_double_registration(self):
        path = self.home / ".claude/settings.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": [
            {"type": "command",
             "command": "\"$HOME/.claude/hooks/inject-local-time.sh\""}]}]}}))
        _, out = self.run_main()
        self.assertIn("fire every hook twice", out)
        self.assertNotIn("enabledPlugins", self.settings())

    def test_foreign_codex_file_is_left_alone(self):
        codex = self.home / ".codex/AGENTS.md"
        codex.parent.mkdir(parents=True)
        codex.write_text("my own rules\n")
        _, out = self.run_main()
        self.assertIn("skip", out)
        self.assertEqual(codex.read_text(), "my own rules\n")

    def test_gemini_block_appends_after_user_content(self):
        gemini = self.home / ".gemini/GEMINI.md"
        gemini.parent.mkdir(parents=True)
        gemini.write_text("# mine\nkeep this\n")
        self.run_main()
        text = gemini.read_text()
        self.assertTrue(text.startswith("# mine\nkeep this\n"), text)
        self.assertEqual(text.count(wire.GEMINI_BEGIN), 1)

    def test_opencode_only_when_installed(self):
        _, out = self.run_main()
        self.assertIn("opencode is not installed", out)
        self.assertFalse((self.home / ".config/opencode").exists())
        (self.home / ".config/opencode").mkdir(parents=True)
        self.run_main()
        config = json.loads((self.home / ".config/opencode/opencode.json").read_text())
        self.assertIn(str(wire.ROOT / "AGENTS.md"), config["instructions"])


if __name__ == "__main__":
    unittest.main()
