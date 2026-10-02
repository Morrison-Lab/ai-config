#!/usr/bin/env python3
"""Tests for scripts/wire-user-config.py (ai-config#4206).

Each case points HOME (and CODEX_HOME, GEMINI_HOME, XDG_CONFIG_HOME) at a
fresh temp directory and clears CLAUDE_CODE_REMOTE, so nothing touches the
real user config and a remote test runner behaves like a local machine.
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
AGENTS = (wire.ROOT / "AGENTS.md").resolve()


def line(out, label):
    return next(row for row in out.splitlines() if row.startswith(label))


class WireUserConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_REMOTE"}
        env.update({"HOME": str(self.home), "CODEX_HOME": str(self.home / ".codex"),
                    "GEMINI_HOME": str(self.home / ".gemini"),
                    "XDG_CONFIG_HOME": str(self.home / ".config")})
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        which = mock.patch.object(wire.shutil, "which", return_value=None)
        which.start()
        self.addCleanup(which.stop)

    def run_main(self, *argv):
        out = StringIO()
        with redirect_stdout(out):
            code = wire.main(list(argv))
        return code, out.getvalue()

    def write_settings(self, data):
        path = self.home / ".claude/settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def settings(self):
        return json.loads((self.home / ".claude/settings.json").read_text(encoding="utf-8"))

    def test_fresh_machine_wires_everything_and_is_idempotent(self):
        code, out = self.run_main("--check")
        self.assertEqual(code, 1, out)
        self.assertFalse((self.home / ".claude").exists(), "--check wrote a file")
        code, out = self.run_main()
        self.assertEqual(code, 0, out)
        s = self.settings()
        self.assertTrue(s["enabledPlugins"]["ai-config@Morrison-Lab"])
        self.assertEqual(s["extraKnownMarketplaces"]["Morrison-Lab"]["source"]["repo"],
                         "Morrison-Lab/ai-config")
        codex = self.home / ".codex/AGENTS.md"
        self.assertEqual(Path(os.path.realpath(codex)), AGENTS)
        gemini = (self.home / ".gemini/GEMINI.md").read_text(encoding="utf-8")
        self.assertIn(f"@./{wire.GEMINI_LINK}", gemini)
        self.assertEqual(Path(os.path.realpath(self.home / ".gemini" / wire.GEMINI_LINK)),
                         AGENTS)
        code, out = self.run_main("--check")
        self.assertEqual(code, 0, out)
        before = gemini
        self.run_main()
        self.assertEqual((self.home / ".gemini/GEMINI.md").read_text(encoding="utf-8"),
                         before)

    def test_existing_settings_are_preserved_including_non_ascii(self):
        self.write_settings({"model": "opus", "note": "café",
                             "enabledPlugins": {"x@y": True}})
        self.run_main()
        s = self.settings()
        self.assertEqual(s["model"], "opus")
        self.assertTrue(s["enabledPlugins"]["x@y"])
        self.assertTrue(s["enabledPlugins"]["ai-config@Morrison-Lab"])
        raw = (self.home / ".claude/settings.json").read_text(encoding="utf-8")
        self.assertIn("café", raw)

    def test_explicit_disable_is_respected(self):
        self.write_settings({"enabledPlugins": {"ai-config@Morrison-Lab": False}})
        _, out = self.run_main()
        self.assertIn("disables the plugin", line(out, "Claude Code"))
        self.assertFalse(self.settings()["enabledPlugins"]["ai-config@Morrison-Lab"])

    def test_mixed_explicit_entries_are_left_alone(self):
        original = {"enabledPlugins": {"ai-config@Morrison-Lab": False,
                                       "ai-config@ai-config": True}}
        self.write_settings(original)
        _, out = self.run_main()
        self.assertTrue(line(out, "Claude Code").split()[2] == "ok", out)
        self.assertEqual(self.settings(), original)

    def test_other_marketplace_copy_counts_as_enabled(self):
        self.write_settings({"enabledPlugins": {"ai-config@ai-config": True}})
        _, out = self.run_main()
        self.assertNotIn("ai-config@Morrison-Lab", self.settings()["enabledPlugins"])
        self.assertEqual(line(out, "Claude Code").split()[2], "ok", out)

    def test_remote_container_is_left_to_the_account_sync(self):
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_REMOTE": "true"}):
            _, out = self.run_main()
            self.assertIn("skip  remote container", line(out, "Claude Code"))
            self.assertFalse((self.home / ".claude/settings.json").exists())
            (self.home / ".claude/plugins/synced/org_x/ai-config").mkdir(parents=True)
            _, out = self.run_main()
        self.assertIn("ok    plugin already loads", line(out, "Claude Code"))

    def test_project_scoped_install_does_not_count(self):
        plugins = self.home / ".claude/plugins"
        plugins.mkdir(parents=True)
        (plugins / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {
            "ai-config@Morrison-Lab": [{"scope": "project", "projectPath": "/x"}]}}),
            encoding="utf-8")
        self.run_main()
        self.assertTrue(self.settings()["enabledPlugins"]["ai-config@Morrison-Lab"])

    def test_malformed_settings_values_do_not_abort(self):
        self.write_settings({"enabledPlugins": ["x"], "hooks": ["y"]})
        code, out = self.run_main()
        self.assertEqual(code, 0, out)
        self.assertIn("Gemini CLI", out)

    def test_unterminated_gemini_block_is_reported_not_doubled(self):
        gemini = self.home / ".gemini/GEMINI.md"
        gemini.parent.mkdir(parents=True)
        broken = f"# mine\n{wire.GEMINI_BEGIN}\n"
        gemini.write_text(broken, encoding="utf-8")
        _, out = self.run_main()
        self.assertIn("skip  ValueError", line(out, "Gemini CLI"))
        self.assertEqual(gemini.read_text(encoding="utf-8"), broken)

    def test_synced_plugin_on_disk_is_not_doubled(self):
        (self.home / ".claude/plugins/synced/org_x/ai-config").mkdir(parents=True)
        _, out = self.run_main()
        self.assertIn("account plugin sync", line(out, "Claude Code"))
        self.assertFalse((self.home / ".claude/settings.json").exists())

    def test_non_plugin_hook_install_blocks_double_registration(self):
        self.write_settings({"hooks": {"UserPromptSubmit": [{"hooks": [
            {"type": "command",
             "command": "\"$HOME/.claude/hooks/inject-local-time.sh\""}]}]}})
        _, out = self.run_main()
        self.assertIn("fire every hook twice", line(out, "Claude Code"))
        self.assertNotIn("enabledPlugins", self.settings())

    def test_foreign_codex_file_is_left_alone(self):
        codex = self.home / ".codex/AGENTS.md"
        codex.parent.mkdir(parents=True)
        codex.write_text("my own rules\n", encoding="utf-8")
        _, out = self.run_main()
        self.assertIn("skip", line(out, "Codex"))
        self.assertEqual(codex.read_text(encoding="utf-8"), "my own rules\n")

    def test_dangling_codex_link_is_repointed(self):
        codex = self.home / ".codex/AGENTS.md"
        codex.parent.mkdir(parents=True)
        codex.symlink_to(self.home / "moved-away/AGENTS.md")
        _, out = self.run_main()
        self.assertIn("link", line(out, "Codex"))
        self.assertEqual(Path(os.path.realpath(codex)), AGENTS)

    def test_gemini_block_appends_after_user_content(self):
        gemini = self.home / ".gemini/GEMINI.md"
        gemini.parent.mkdir(parents=True)
        gemini.write_text("# mine\nkeep this\n", encoding="utf-8")
        self.run_main()
        text = gemini.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# mine\nkeep this\n"), text)
        self.assertEqual(text.count(wire.GEMINI_BEGIN), 1)

    def test_one_failing_step_does_not_stop_the_rest(self):
        failing = mock.Mock(side_effect=OSError("no symlinks"))
        steps = tuple((label, failing if label == "Codex" else step)
                      for label, step in wire.STEPS)
        with mock.patch.object(wire, "STEPS", steps):
            code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("OSError: no symlinks", line(out, "Codex"))
        self.assertTrue((self.home / ".gemini/GEMINI.md").exists())

    def test_opencode_only_when_installed(self):
        _, out = self.run_main()
        self.assertIn("not installed", line(out, "opencode"))
        self.assertFalse((self.home / ".config/opencode").exists())
        config_dir = self.home / ".config/opencode"
        config_dir.mkdir(parents=True)
        stale = str(self.home / "old-checkout/AGENTS.md")
        (config_dir / "opencode.json").write_text(
            json.dumps({"instructions": ["mine.md", stale]}), encoding="utf-8")
        self.run_main()
        config = json.loads((config_dir / "opencode.json").read_text(encoding="utf-8"))
        self.assertEqual(config["instructions"], ["mine.md", str(wire.ROOT / "AGENTS.md")])

    def test_opencode_jsonc_is_not_shadowed(self):
        config_dir = self.home / ".config/opencode"
        config_dir.mkdir(parents=True)
        (config_dir / "opencode.jsonc").write_text("{}\n", encoding="utf-8")
        _, out = self.run_main()
        self.assertIn("opencode.jsonc", line(out, "opencode"))
        self.assertFalse((config_dir / "opencode.json").exists())


if __name__ == "__main__":
    unittest.main()
