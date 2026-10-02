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

    def run_main(self, *argv, repo=None):
        out = StringIO()
        with redirect_stdout(out):
            code = wire.main([*argv, str(repo or self.repo)])
        return code, out.getvalue()

    def write_settings(self, data):
        (self.repo / ".claude").mkdir(exist_ok=True)
        (self.repo / ".claude/settings.json").write_text(json.dumps(data), encoding="utf-8")

    def settings(self):
        return json.loads((self.repo / ".claude/settings.json").read_text(encoding="utf-8"))

    def read(self, name):
        return (self.repo / name).read_text(encoding="utf-8")

    def test_bare_repo_is_wired_and_idempotent(self):
        self.assertEqual(self.run_main("--check")[0], 1)
        self.assertFalse((self.repo / "AGENTS.md").exists(), "--check wrote a file")
        self.run_main()
        s = self.settings()
        self.assertEqual(s["extraKnownMarketplaces"]["Morrison-Lab"]["source"]["repo"],
                         "Morrison-Lab/ai-config")
        self.assertNotIn("enabledPlugins", s, "plugin enabled without --enable-plugin")
        self.assertEqual(self.read("AGENTS.md"), wire.BLOCK)
        self.assertFalse((self.repo / "CLAUDE.md").exists(), "created a CLAUDE.md")
        code, out = self.run_main("--check")
        self.assertEqual(code, 0, out)

    def test_enable_plugin_opt_in(self):
        self.run_main("--enable-plugin")
        self.assertTrue(self.settings()["enabledPlugins"]["ai-config@Morrison-Lab"])
        self.assertEqual(self.run_main("--check", "--enable-plugin")[0], 0)

    def test_explicit_plugin_choice_is_respected(self):
        self.write_settings({"enabledPlugins": {"ai-config@Morrison-Lab": False}})
        _, out = self.run_main("--enable-plugin")
        self.assertFalse(self.settings()["enabledPlugins"]["ai-config@Morrison-Lab"])
        self.assertNotIn("enable ai-config", out)

    def test_existing_settings_and_marketplace_are_kept(self):
        local = {"source": {"source": "directory", "path": "/src/ai-config"}}
        self.write_settings({"hooks": {"SessionStart": []},
                             "permissions": {"allow": ["Bash(ls)"]},
                             "extraKnownMarketplaces": {"Morrison-Lab": local}})
        self.run_main()
        s = self.settings()
        self.assertEqual(s["permissions"]["allow"], ["Bash(ls)"])
        self.assertIn("SessionStart", s["hooks"])
        self.assertEqual(s["extraKnownMarketplaces"]["Morrison-Lab"], local)

    def test_non_dict_enabled_plugins_does_not_crash(self):
        self.write_settings({"enabledPlugins": ["ai-config@Morrison-Lab"]})
        with self.assertRaises(SystemExit):
            self.run_main("--enable-plugin")
        self.assertEqual(self.run_main()[0], 0)

    def test_agents_and_claude_blocks(self):
        (self.repo / "AGENTS.md").write_text("# Repo rules\n\nUse renv.\n", encoding="utf-8")
        (self.repo / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")
        self.run_main()
        text = self.read("AGENTS.md")
        self.assertTrue(text.startswith("# Repo rules\n\nUse renv.\n\n"), text)
        self.assertEqual(text.count(wire.BEGIN), 1)
        self.assertEqual(self.read("CLAUDE.md"), "# Claude\n\n" + wire.BLOCK)

    def test_claude_md_importing_agents_is_left_alone(self):
        for text in ("@AGENTS.md\n", "# x\n\n@./AGENTS.md\n",
                     "```\nexample\n```\n\n@AGENTS.md\n"):
            (self.repo / "CLAUDE.md").write_text(text, encoding="utf-8")
            self.run_main()
            self.assertEqual(self.read("CLAUDE.md"), text)

    def test_claude_md_mentioning_agents_in_code_gets_block(self):
        (self.repo / "CLAUDE.md").write_text("Use `@AGENTS.md` imports.\n", encoding="utf-8")
        self.run_main()
        self.assertIn(wire.BEGIN, self.read("CLAUDE.md"))

    def test_claude_md_import_inside_fence_gets_block(self):
        for text in ("```\n@AGENTS.md\n```\n", "```\n@AGENTS.md\n"):
            (self.repo / "CLAUDE.md").write_text(text, encoding="utf-8")
            self.run_main()
            self.assertIn(wire.BEGIN, self.read("CLAUDE.md"), repr(text))

    def test_stale_block_is_replaced_in_place(self):
        stale = f"intro\n\n{wire.BEGIN}\nold text\n{wire.END}\n\noutro\n"
        (self.repo / "AGENTS.md").write_text(stale, encoding="utf-8")
        self.run_main()
        text = self.read("AGENTS.md")
        self.assertNotIn("old text", text)
        self.assertTrue(text.startswith("intro\n\n" + wire.BLOCK), text)
        self.assertTrue(text.endswith("outro\n"), text)

    def test_unterminated_block_is_an_error(self):
        broken = f"intro\n\n{wire.BEGIN}\nold text\n"
        (self.repo / "AGENTS.md").write_text(broken, encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.run_main()
        self.assertEqual(self.read("AGENTS.md"), broken)

    def test_r_package_gets_anchored_rbuildignore_entries(self):
        (self.repo / "DESCRIPTION").write_text("Package: x\n", encoding="utf-8")
        (self.repo / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")
        (self.repo / ".Rbuildignore").write_text("^.*\\.Rproj$", encoding="utf-8")
        self.assertEqual(self.run_main("--check")[0], 1)
        self.assertEqual(self.read(".Rbuildignore"), "^.*\\.Rproj$", "--check wrote")
        self.run_main()
        self.assertEqual(self.read(".Rbuildignore"),
                         "^.*\\.Rproj$\n^AGENTS\\.md$\n^CLAUDE\\.md$\n^\\.claude$\n")
        code, out = self.run_main("--check")
        self.assertEqual(code, 0, out)

    def test_rbuildignore_keeps_existing_matches_and_skips_absent_claude_md(self):
        (self.repo / "DESCRIPTION").write_text("Package: x\n", encoding="utf-8")
        (self.repo / ".Rbuildignore").write_text("^\\.claude\n[\n", encoding="utf-8")
        self.run_main()
        # `^\.claude` already covers .claude, `[` does not compile and is
        # skipped, and no CLAUDE.md exists, so only AGENTS.md is added.
        self.assertEqual(self.read(".Rbuildignore"), "^\\.claude\n[\n^AGENTS\\.md$\n")

    def test_rbuildignore_padded_pattern_is_not_a_match(self):
        # R does not trim lines, so "^AGENTS\.md$ " matches nothing there.
        (self.repo / "DESCRIPTION").write_text("Package: x\n", encoding="utf-8")
        (self.repo / ".Rbuildignore").write_bytes(b"^AGENTS\\.md$ \r\n^\\.claude$\r\n")
        self.run_main()
        self.assertEqual((self.repo / ".Rbuildignore").read_bytes(),
                         b"^AGENTS\\.md$ \r\n^\\.claude$\r\n^AGENTS\\.md$\r\n")

    def test_rbuildignore_blank_line_is_not_a_match_all(self):
        # An empty regex matches every path, so R drops blank lines first.
        (self.repo / "DESCRIPTION").write_text("Package: x\n", encoding="utf-8")
        (self.repo / ".Rbuildignore").write_text("^.*\\.Rproj$\n\n", encoding="utf-8")
        self.run_main()
        self.assertEqual(self.read(".Rbuildignore"),
                         "^.*\\.Rproj$\n\n^AGENTS\\.md$\n^\\.claude$\n")

    def test_rbuildignore_matches_case_insensitively(self):
        (self.repo / "DESCRIPTION").write_text("Package: x\n", encoding="utf-8")
        (self.repo / ".Rbuildignore").write_text("^agents\\.md$\n^\\.CLAUDE$\n",
                                                 encoding="utf-8")
        _, out = self.run_main()
        self.assertEqual(self.read(".Rbuildignore"), "^agents\\.md$\n^\\.CLAUDE$\n", out)

    def test_rbuildignore_cr_only_file_keeps_cr(self):
        (self.repo / "DESCRIPTION").write_text("Package: x\n", encoding="utf-8")
        (self.repo / ".Rbuildignore").write_bytes(b"^\\.claude$\r^x\x0c$\r")
        self.run_main()
        self.assertEqual((self.repo / ".Rbuildignore").read_bytes(),
                         b"^\\.claude$\r^x\x0c$\r^AGENTS\\.md$\r")

    def test_rbuildignore_pathological_pattern_is_skipped(self):
        (self.repo / "DESCRIPTION").write_text("Package: x\n", encoding="utf-8")
        nested = "(" * 1000 + ")" * 1000
        (self.repo / ".Rbuildignore").write_text(f"a{{4294967296}}\n{nested}\n",
                                                 encoding="utf-8")
        self.run_main()
        self.assertEqual(self.read(".Rbuildignore"),
                         f"a{{4294967296}}\n{nested}\n^AGENTS\\.md$\n^\\.claude$\n")

    def test_non_utf8_rbuildignore_is_an_error(self):
        (self.repo / "DESCRIPTION").write_text("Package: x\n", encoding="utf-8")
        (self.repo / ".Rbuildignore").write_bytes(b"\xff\n")
        with self.assertRaises(SystemExit) as ctx:
            self.run_main()
        self.assertIn("not UTF-8", str(ctx.exception.code))

    def test_rbuildignore_created_for_package_without_one(self):
        (self.repo / "DESCRIPTION").write_text("Package: x\n", encoding="utf-8")
        self.run_main()
        self.assertEqual(self.read(".Rbuildignore"), "^AGENTS\\.md$\n^\\.claude$\n")

    def test_non_package_gets_no_rbuildignore(self):
        self.run_main()
        self.assertFalse((self.repo / ".Rbuildignore").exists())

    def test_ai_config_and_its_subdirectories_are_skipped(self):
        (self.repo / ".claude-plugin").mkdir()
        (self.repo / ".claude-plugin/marketplace.json").write_text(
            json.dumps({"name": "Morrison-Lab"}), encoding="utf-8")
        sub = self.repo / "skills"
        sub.mkdir()
        for target in (self.repo, sub):
            code, out = self.run_main(repo=target)
            self.assertEqual(code, 0)
            self.assertIn("skip", out)
        self.assertFalse((self.repo / "AGENTS.md").exists())
        self.assertFalse((sub / "AGENTS.md").exists())


if __name__ == "__main__":
    unittest.main()
