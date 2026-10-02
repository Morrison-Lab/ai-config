#!/usr/bin/env python3
"""Tests for scripts/wire-repo-config.py (ai-config#4206)."""
import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("wire_repo", HERE / "wire-repo-config.py")
wire = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wire)


class WireRepoConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)

    def run_main(self, *argv):
        out = StringIO()
        with redirect_stdout(out):
            code = wire.main([*argv, str(self.repo)])
        return code, out.getvalue()

    def settings(self):
        return json.loads((self.repo / ".claude/settings.json").read_text())

    def test_bare_repo_is_wired_and_idempotent(self):
        self.assertEqual(self.run_main("--check")[0], 1)
        self.assertFalse((self.repo / "AGENTS.md").exists(), "--check wrote a file")
        self.run_main()
        s = self.settings()
        self.assertTrue(s["enabledPlugins"]["ai-config@Morrison-Lab"])
        self.assertEqual(s["extraKnownMarketplaces"]["Morrison-Lab"]["source"]["repo"],
                         "Morrison-Lab/ai-config")
        self.assertEqual((self.repo / "AGENTS.md").read_text(), wire.BLOCK)
        code, out = self.run_main("--check")
        self.assertEqual(code, 0, out)

    def test_existing_settings_and_agents_are_kept(self):
        (self.repo / ".claude").mkdir()
        (self.repo / ".claude/settings.json").write_text(json.dumps(
            {"hooks": {"SessionStart": []}, "permissions": {"allow": ["Bash(ls)"]}}))
        (self.repo / "AGENTS.md").write_text("# Repo rules\n\nUse renv.\n")
        self.run_main()
        s = self.settings()
        self.assertEqual(s["permissions"]["allow"], ["Bash(ls)"])
        self.assertIn("SessionStart", s["hooks"])
        text = (self.repo / "AGENTS.md").read_text()
        self.assertTrue(text.startswith("# Repo rules\n\nUse renv.\n\n"), text)
        self.assertEqual(text.count(wire.BEGIN), 1)

    def test_explicit_plugin_choice_is_respected(self):
        (self.repo / ".claude").mkdir()
        original = {"enabledPlugins": {"ai-config@Morrison-Lab": False},
                    "extraKnownMarketplaces": {"Morrison-Lab": {"source": {}}}}
        (self.repo / ".claude/settings.json").write_text(json.dumps(original))
        self.run_main()
        self.assertEqual(self.settings(), original)

    def test_stale_block_is_replaced_in_place(self):
        stale = f"intro\n\n{wire.BEGIN}\nold text\n{wire.END}\n\noutro\n"
        (self.repo / "AGENTS.md").write_text(stale)
        self.run_main()
        text = (self.repo / "AGENTS.md").read_text()
        self.assertNotIn("old text", text)
        self.assertTrue(text.startswith("intro\n\n" + wire.BLOCK), text)
        self.assertTrue(text.endswith("outro\n"), text)

    def test_ai_config_itself_is_skipped(self):
        (self.repo / ".claude-plugin").mkdir()
        (self.repo / ".claude-plugin/marketplace.json").write_text(
            json.dumps({"name": "Morrison-Lab"}))
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("skip", out)
        self.assertFalse((self.repo / "AGENTS.md").exists())


if __name__ == "__main__":
    unittest.main()
