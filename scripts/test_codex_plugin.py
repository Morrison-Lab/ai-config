#!/usr/bin/env python3
"""Regression tests for scripts/lib/codex_plugin.py."""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from codex_plugin import is_codex_plugin_enabled, clean_stale_codex_wrappers


def test_plugin_detection():
    with tempfile.TemporaryDirectory() as codex_dir, tempfile.TemporaryDirectory() as project_dir:
        # Default: not enabled
        assert not is_codex_plugin_enabled(codex_dir, project_dir)

        # 1. config.toml table enabled = true
        cfg = Path(codex_dir) / "config.toml"
        cfg.write_text('[plugins."ai-config"]\nenabled = true\n', encoding="utf-8")
        assert is_codex_plugin_enabled(codex_dir, project_dir)
        
        # 1b. config.toml table enabled = false (should NOT be enabled)
        cfg.write_text('[plugins."ai-config"]\nenabled = false\n', encoding="utf-8")
        assert not is_codex_plugin_enabled(codex_dir, project_dir)
        cfg.unlink()

        # 2. plugins.json entries
        p_json = Path(codex_dir) / "plugins.json"
        p_json.write_text(json.dumps({"entries": [{"path": "/path/to/ai-config"}]}), encoding="utf-8")
        assert is_codex_plugin_enabled(codex_dir, project_dir)
        p_json.unlink()

        # 3. settings.json enabledPlugins
        s_json = Path(codex_dir) / "settings.json"
        s_json.write_text(json.dumps({"enabledPlugins": {"ai-config": True}}), encoding="utf-8")
        assert is_codex_plugin_enabled(codex_dir, project_dir)

        # 3b. settings.json enabledPlugins false
        s_json.write_text(json.dumps({"enabledPlugins": {"ai-config": False}}), encoding="utf-8")
        assert not is_codex_plugin_enabled(codex_dir, project_dir)
        s_json.unlink()

        # 4. plugins/ai-config directory
        plugin_dir = Path(codex_dir) / "plugins" / "ai-config"
        plugin_dir.mkdir(parents=True)
        assert is_codex_plugin_enabled(codex_dir, project_dir)
        plugin_dir.rmdir()

        # 5. env var override
        orig_env = os.environ.get("CODEX_PLUGIN_ENABLED")
        try:
            os.environ["CODEX_PLUGIN_ENABLED"] = "1"
            assert is_codex_plugin_enabled(codex_dir, project_dir)
            os.environ["CODEX_PLUGIN_ENABLED"] = "0"
            assert not is_codex_plugin_enabled(codex_dir, project_dir)
        finally:
            if orig_env is None:
                os.environ.pop("CODEX_PLUGIN_ENABLED", None)
            else:
                os.environ["CODEX_PLUGIN_ENABLED"] = orig_env


def test_stale_wrapper_cleanup():
    with tempfile.TemporaryDirectory() as codex_dir, tempfile.TemporaryDirectory() as repo_root:
        repo_skills = Path(repo_root) / "codex-skills"
        repo_skills.mkdir(parents=True)
        (repo_skills / "ardi").mkdir()
        (repo_skills / "ardi" / "SKILL.md").write_text("dummy", encoding="utf-8")

        codex_skills = Path(codex_dir) / "skills"
        codex_skills.mkdir(parents=True)

        # Create a symlink pointing into repo codex-skills
        (codex_skills / "ardi").symlink_to(repo_skills / "ardi")
        # Create an unrelated file and unrelated symlink
        (codex_skills / "custom-skill").mkdir()
        (codex_skills / "custom-skill" / "SKILL.md").write_text("custom", encoding="utf-8")

        removed = clean_stale_codex_wrappers(codex_dir, repo_root)
        assert removed == ["ardi"], f"Expected ['ardi'], got {removed}"
        assert not (codex_skills / "ardi").exists()
        assert (codex_skills / "custom-skill").exists()


if __name__ == "__main__":
    test_plugin_detection()
    test_stale_wrapper_cleanup()
    print("PASS: all Codex plugin detection and wrapper cleanup tests passed")
