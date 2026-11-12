#!/usr/bin/env python3
"""Tests for scripts/retire-leftover-paths.py, each against a temporary Claude home."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("retire", SCRIPTS / "retire-leftover-paths.py")
retire = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(retire)

CATALOG_HOOK = sorted(retire.wire.catalog_scripts())[0]
BACKSLASH = "\\"  # the Windows path separator
REPO_SKILL = sorted(p.name for p in (SCRIPTS.parent / "skills").iterdir() if p.is_dir())[0]
OWN_HOOK = {"type": "command", "command": "python3 /opt/my-own-hook.py"}
CLONE_HOOK = {"type": "command", "command": f"python3 /src/ai-config/hooks/{CATALOG_HOOK}"}


class RetireLeftoverPaths(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.home = root / ".claude"
        self.checkout = root / "checkout"
        project = root / "project"
        for d in (self.home, self.checkout / ".git", self.checkout / "hooks", self.checkout / "skills" / "ums", project):
            d.mkdir(parents=True)
        (self.checkout / "CLAUDE.md").write_text("", encoding="utf-8")
        (self.checkout / "hooks" / "hooks.json").write_text("{}", encoding="utf-8")
        env = {"CLAUDE_HOME": str(self.home), "HOME": str(root), "USERPROFILE": str(root), "CLAUDE_PROJECT_DIR": str(project)}
        self.enterContext(patch.dict(os.environ, env))

    def write_settings(self, enabled=True, hooks=None):
        settings = {"enabledPlugins": {"ai-config@Morrison-Lab": enabled}, "hooks": hooks or {}}
        (self.home / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = retire.main(list(argv))
        return code, out.getvalue()

    def plant_leftovers(self):
        catalog = {"type": "command", "command": f"python3 $HOME/.claude/hooks/{CATALOG_HOOK}"}
        self.write_settings(hooks={"PreToolUse": [{"matcher": "Bash", "hooks": [catalog, OWN_HOOK, CLONE_HOOK]}],
                                   "Stop": [{"hooks": [catalog]}]})
        (self.home / "hooks").mkdir()
        (self.home / "hooks" / CATALOG_HOOK).write_text("old copy", encoding="utf-8")
        (self.home / "shared").symlink_to(self.checkout / "hooks")
        (self.home / "memories").symlink_to(self.checkout / "hooks")
        (self.home / "skills" / REPO_SKILL).mkdir(parents=True)
        (self.home / "skills" / "ums").symlink_to(self.checkout / "skills" / "ums")

    def test_skips_when_plugin_not_enabled(self):
        self.write_settings(enabled=False)
        (self.home / "hooks").mkdir()
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("Not swept", out)
        code, _ = self.run_main("--retire")
        self.assertEqual(code, 2)
        self.assertTrue((self.home / "hooks").is_dir())

    def test_report_only_changes_nothing(self):
        self.plant_leftovers()
        before = (self.home / "settings.json").read_text(encoding="utf-8")
        code, out = self.run_main()
        self.assertEqual(code, 1)
        for expected in (f"retire {self.home / 'hooks'}", f"keep   {self.home / 'memories'}",
                         f"retire {self.home / 'skills' / 'ums'}", f"keep   {self.home / 'skills' / REPO_SKILL}",
                         f"hook entry: python3 $HOME/.claude/hooks/{CATALOG_HOOK}"):
            self.assertIn(expected, out)
        self.assertNotIn(f"{self.home / 'shared'}:", out)
        self.assertEqual((self.home / "settings.json").read_text(encoding="utf-8"), before)
        self.assertFalse((self.home / "ai-config-leftovers").exists())

    def test_retire_moves_aside_and_keeps_the_rest(self):
        self.plant_leftovers()
        code, _ = self.run_main("--retire")
        self.assertEqual(code, 1)
        [backup] = (self.home / "ai-config-leftovers").iterdir()
        self.assertEqual((backup / "hooks" / CATALOG_HOOK).read_text(encoding="utf-8"), "old copy")
        self.assertTrue((backup / "skills" / "ums").is_symlink())
        for gone in ("hooks", "skills/ums"):
            self.assertFalse((self.home / gone).exists(), gone)
        self.assertTrue((self.home / "skills" / REPO_SKILL).is_dir())
        self.assertTrue((self.home / "shared").is_symlink() and (self.home / "memories").is_symlink())
        settings = json.loads((self.home / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["hooks"], {"PreToolUse": [{"matcher": "Bash", "hooks": [OWN_HOOK, CLONE_HOOK]}]})
        self.assertEqual(settings["enabledPlugins"], {"ai-config@Morrison-Lab": True})
        self.assertIn(CATALOG_HOOK, (backup / "settings.json").read_text(encoding="utf-8"))

    def test_unproven_copies_and_jsonc_settings_are_left_alone(self):
        self.write_settings()
        (self.home / "shared").mkdir()
        (self.home / "memories").mkdir()
        (self.home / "hooks").mkdir()
        (self.home / "hooks" / "mine.py").write_text("", encoding="utf-8")
        code, out = self.run_main("--retire")
        self.assertEqual(code, 1)
        self.assertIn(f"keep   {self.home / 'shared'}: a copy", out)
        self.assertIn(f"keep   {self.home / 'hooks'}: not provably", out)
        self.assertIn(f"keep   {self.home / 'memories'}: memories/", out)
        self.assertTrue((self.home / "shared").is_dir())
        (self.home / "settings.json").write_text('// comment' + chr(10) + '{}', encoding="utf-8")
        code, out = self.run_main("--retire")
        self.assertEqual((code, out.startswith("Not swept")), (2, True))
        self.assertTrue((self.home / "hooks" / "mine.py").exists())

    def test_symlinked_settings_are_not_rewritten(self):
        self.plant_leftovers()
        (self.home / "real.json").write_text((self.home / "settings.json").read_text(encoding="utf-8"), encoding="utf-8")
        (self.home / "settings.json").unlink()
        (self.home / "settings.json").symlink_to(self.home / "real.json")
        self.assertEqual(self.run_main("--retire")[0], 2)
        self.assertTrue((self.home / "hooks").is_dir())
        self.assertFalse((self.home / "ai-config-leftovers").exists())

    def test_hook_entries_match_only_the_claude_home_hooks_dir(self):
        windows_style = str(self.home / "hooks").replace("/", BACKSLASH) + BACKSLASH + CATALOG_HOOK
        commands = [f"python3 {d}/{CATALOG_HOOK}" for d in ("~/.claude/hooks", "$HOME/.claude/hooks",
                                                              "${HOME}/.claude/hooks", str(self.home / "hooks"))]
        hooks = [{"command": c} for c in commands + [f"python3 {windows_style}"]]
        settings = {"hooks": {"Stop": [{"hooks": hooks}]}}
        self.assertEqual(len(retire.strip_leftover_hooks(settings, self.home / "hooks")[1]), 5)
        self.assertEqual(retire.strip_leftover_hooks(settings, Path("/elsewhere/hooks"))[1], [])

    def test_empty_directory_is_named_as_such(self):
        self.write_settings()
        (self.home / "hooks").mkdir()
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn(f"retire {self.home / 'hooks'}: an empty directory", out)

    def test_retiring_everything_exits_zero(self):
        self.write_settings()
        (self.home / "hooks").mkdir()
        (self.home / "hooks" / CATALOG_HOOK).write_text("old copy", encoding="utf-8")
        self.assertEqual(self.run_main("--retire")[0], 0)
        self.assertEqual(self.run_main(), (0, f"No leftover delivery paths under {self.home}." + chr(10)))


if __name__ == "__main__":
    unittest.main()
