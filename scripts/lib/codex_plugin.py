#!/usr/bin/env python3
"""Detect whether Codex plugin is enabled, and manage Codex wrappers vs plugin.

Codex can load ai-config skills through either its plugin or individual wrapper
symlinks in ~/.codex/skills. Enabling both doubles the catalog and exhausts the
skill context budget. This module ensures only one route is active.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]


def is_codex_plugin_enabled(codex_dir: Path | str, project_dir: Path | str = ".") -> bool:
    """Return True if Codex plugin for ai-config is enabled in user/project config or environment."""
    env_override = os.environ.get("CODEX_PLUGIN_ENABLED")
    if env_override is not None:
        return env_override.strip() in {"1", "true", "TRUE", "yes", "YES"}

    codex_path = Path(codex_dir).expanduser().resolve()
    project_path = Path(project_dir).resolve()

    # Check ~/.codex/config.toml and ./.codex/config.toml
    config_paths = [
        codex_path / "config.toml",
        project_path / ".codex" / "config.toml",
    ]

    for p in config_paths:
        if not p.is_file():
            continue
        content = p.read_text(encoding="utf-8", errors="ignore")
        if tomllib is not None:
            try:
                data = tomllib.loads(content)
                plugins = data.get("plugins")
                if isinstance(plugins, dict):
                    ai_cfg = plugins.get("ai-config")
                    if isinstance(ai_cfg, dict) and ai_cfg.get("enabled") is not False:
                        return True
                    if ai_cfg is True:
                        return True
                elif isinstance(plugins, list) and "ai-config" in plugins:
                    return True
            except Exception:
                pass
        # Fallback text parsing for toml when tomllib is absent
        if "ai-config" in content:
            # Check for table header [plugins."ai-config"] or [plugins.ai-config]
            if re.search(r'\[plugins\.(?:"ai-config"|\'ai-config\'|ai-config)\]', content):
                # Unless explicitly disabled
                match = re.search(r'\[plugins\.(?:"ai-config"|\'ai-config\'|ai-config)\].*?(?:enabled\s*=\s*(true|false))', content, re.DOTALL)
                if match:
                    if match.group(1).lower() == "true":
                        return True
                else:
                    return True
            # Check for plugins list
            if re.search(r'plugins\s*=\s*\[[^\]]*["\']ai-config["\']', content):
                return True

    # Check JSON settings / plugins
    json_paths = [
        codex_path / "plugins.json",
        codex_path / "settings.json",
        project_path / ".codex" / "plugins.json",
        project_path / ".codex" / "settings.json",
    ]
    for p in json_paths:
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                entries = data.get("entries") or []
                if isinstance(entries, list):
                    for entry in entries:
                        if isinstance(entry, dict) and "ai-config" in str(entry.get("path", "")):
                            return True
                enabled_plugins = data.get("enabledPlugins") or {}
                if isinstance(enabled_plugins, dict):
                    if any("ai-config" in k and v for k, v in enabled_plugins.items()):
                        return True
        except Exception:
            continue

    # Check plugin directory ~/.codex/plugins/ai-config
    plugin_dir = codex_path / "plugins" / "ai-config"
    if plugin_dir.exists():
        return True

    return False


def clean_stale_codex_wrappers(codex_dir: Path | str, repo_root: Path | str) -> list[str]:
    """Remove symlinks in ~/.codex/skills/ pointing into repo's codex-skills/."""
    codex_skills = Path(codex_dir).expanduser().resolve() / "skills"
    repo_wrappers = Path(repo_root).resolve() / "codex-skills"
    removed = []
    if not codex_skills.is_dir():
        return removed

    for child in codex_skills.iterdir():
        if child.is_symlink():
            try:
                target = child.resolve()
                if target.is_relative_to(repo_wrappers.resolve()):
                    child.unlink()
                    removed.append(child.name)
            except (OSError, ValueError):
                continue
    return removed
