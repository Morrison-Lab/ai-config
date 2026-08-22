#!/usr/bin/env python3
"""Exit successfully when Cursor already has the ai-config skill catalog.

Cursor can load this repo's skills three ways, and stacking any two doubles
the listing the same way a Claude plugin-plus-symlink install does
(ai-config#1409):

  * a Cursor plugin --- an enabled copy under ``~/.cursor/plugins/cache``
    or a local checkout at ``~/.cursor/plugins/local/ai-config``
    (a marketplace catalog clone is not an install);
  * ``~/.claude/skills`` --- Cursor also discovers Claude/Codex skill
    directories, so a live ``bootstrap.sh`` Claude install already serves
    the catalog;
  * ``~/.cursor/skills`` --- the bare per-skill links this script's caller
    would create.

Bootstrap asks this script whether the first two are already live, and
skips the third when they are.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path


PLUGIN_DIRNAME = "ai-config"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def plugin_installed(cursor_dir: Path) -> bool:
    """True when an ai-config Cursor plugin is actually installed.

    Cursor copies an enabled plugin into ``plugins/local/`` or
    ``plugins/cache/<org>/ai-config/``. ``plugins/marketplaces/`` is only
    the catalog clone: adding a marketplace does not enable the plugin, and
    this repo's tree also contains ``plugins/ai-config`` (Antigravity), so a
    recursive name match there is a false skip.
    """
    plugins = cursor_dir / "plugins"
    local = plugins / "local" / PLUGIN_DIRNAME
    if local.exists():
        return True
    cache = plugins / "cache"
    try:
        if cache.is_dir():
            for org in cache.iterdir():
                if (org / PLUGIN_DIRNAME).exists():
                    return True
    except OSError:
        return False
    return False


def claude_skills_serve_repo(claude_dir: Path, repo_root: Path) -> bool:
    """True when ``<claude_dir>/skills`` already resolves into *repo_root*."""
    skills = claude_dir / "skills"
    repo = repo_root.resolve()
    repo_skills = repo / "skills"
    if not skills.exists():
        return False
    try:
        if skills.is_symlink() or skills.is_dir():
            if _is_relative_to(skills, repo):
                return True
        if skills.is_dir() and not skills.is_symlink():
            return any(
                child.is_symlink() and _is_relative_to(child, repo_skills)
                for child in skills.iterdir()
            )
    except OSError:
        return False
    return False


def _repo_worktrees(repo_root: Path) -> set[Path]:
    """Working trees of *repo_root*, or empty when git cannot answer."""
    spec = importlib.util.spec_from_file_location(
        "check_install", Path(__file__).resolve().parent / "check-install.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.repo_worktrees(repo_root)


def skip_reason(
    cursor_dir: Path,
    claude_dir: Path,
    repo_root: Path,
    repo_roots: set[Path] | None = None,
) -> str | None:
    """Why bootstrap should not link ``~/.cursor/skills``, or None to install.

    *repo_roots* is the worktree-inclusive set ``check-harness-installs.py``
    already computes (ai-config#1729). When omitted, this function derives
    the same union so a Claude catalog that points at a sibling worktree
    still counts as serving this repo.
    """
    if plugin_installed(cursor_dir):
        return "ai-config Cursor plugin is already installed"
    if repo_roots is None:
        repo_roots = {repo_root.resolve()} | _repo_worktrees(repo_root)
    if any(claude_skills_serve_repo(claude_dir, root) for root in repo_roots):
        return "~/.claude/skills already serves this catalog (Cursor loads it)"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--cursor-dir",
        default=os.environ.get("CURSOR_HOME", str(Path.home() / ".cursor")),
    )
    parser.add_argument(
        "--claude-dir",
        default=os.environ.get("CLAUDE_HOME", str(Path.home() / ".claude")),
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parent.parent),
    )
    args = parser.parse_args()
    reason = skip_reason(
        Path(args.cursor_dir), Path(args.claude_dir), Path(args.repo_root)
    )
    if reason is None:
        return 1
    print(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
