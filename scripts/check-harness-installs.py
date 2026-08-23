#!/usr/bin/env python3
"""Audit ai-config's Claude, Codex, Gemini, and Cursor consumer installs.

This complements ``check-install.py``, whose repair workflow deliberately
models Claude Code's merge-into-a-preseeded-directory installation.  The
other harnesses install a flat catalog of individually linked entries, so a
single read-only audit can use the same entry classifier without pretending
their layouts are identical.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_check_install():
    spec = importlib.util.spec_from_file_location("check_install", ROOT / "scripts" / "check-install.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ci = load_check_install()


def codex_plugin_enabled(config: Path) -> bool:
    spec = importlib.util.spec_from_file_location(
        "codex_plugin_enabled", ROOT / "scripts" / "codex-plugin-enabled.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.ai_config_plugin_enabled(config)


def cursor_skill_catalog_served(
    cursor_dir: Path, claude_dir: Path, repo_root: Path,
    repo_roots: set[Path] | None = None,
) -> bool:
    """True when a Cursor plugin or Claude catalog already serves this repo."""
    spec = importlib.util.spec_from_file_location(
        "cursor_plugin_enabled", ROOT / "scripts" / "cursor-plugin-enabled.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.skip_reason(
        cursor_dir, claude_dir, repo_root, repo_roots
    ) is not None


def catalog_leftovers(entries):
    """Keep on-disk Cursor skill entries when a plugin/catalog already serves.

    ``missing`` is expected in that state (bootstrap did not link
    ``~/.cursor/skills``). Leftover ``ok`` links are the stacked-catalog
    hazard (ai-config#1409), so they become ``stacked`` rather than staying
    healthy. ``stale`` / ``foreign`` leftovers stay as themselves.
    """
    leftovers = []
    for entry in entries:
        if entry.status == "missing":
            continue
        if entry.status == "ok":
            leftovers.append(ci.Entry(
                entry.group, entry.name, "stacked",
                entry.repo_path, entry.install_path,
                detail="plugin or Claude catalog already serves this skill",
            ))
        else:
            leftovers.append(entry)
    return leftovers


def collect_flat(repo_root: Path, source_rel: str, install_dir: Path, harness: str,
                 repo_roots: set[Path] | None = None):
    """Classify an individually-linked catalog, including consumer-only paths.

    `repo_roots` is the set of checkouts a symlink may point into and still
    count as tracking this repo. These catalogs are installed by the same
    `bootstrap.sh` run as the Claude ones, so they carry the same worktree
    hazard (ai-config#1729): a link into a sibling worktree is not misdirected.
    Defaults to `{repo_root}`, preserving the pre-worktree behaviour.
    """
    if repo_roots is None:
        repo_roots = {repo_root}
    source = repo_root / source_rel
    if not install_dir.is_dir():
        return []
    names = {entry.name for entry in source.iterdir()} if source.is_dir() else set()
    names |= {entry.name for entry in install_dir.iterdir()}
    return [
        ci.classify(
            source / name if (source / name).exists() else None,
            install_dir / name,
            harness,
            name,
            repo_roots,
        )
        for name in sorted(names)
        if name not in ci.IGNORED_NAMES
    ]


def report(harness: str, entries) -> int:
    if not entries:
        print(f"{harness}: no consumer directory -- nothing installed to check")
        return 0
    counts = {}
    for entry in entries:
        counts[entry.status] = counts.get(entry.status, 0) + 1
    print(f"\n{harness}:")
    ci.summarize(entries, counts)
    return sum(counts.get(status, 0) for status in (*ci.FIXABLE, "stacked"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--claude-dir", default=os.environ.get("CLAUDE_HOME", str(Path.home() / ".claude")))
    parser.add_argument("--codex-dir", default=os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    parser.add_argument("--gemini-dir", default=os.environ.get("GEMINI_HOME", str(Path.home() / ".gemini")))
    parser.add_argument("--cursor-dir", default=os.environ.get("CURSOR_HOME", str(Path.home() / ".cursor")))
    parser.add_argument("--strict", action="store_true", help="exit 1 when a repairable defect is found")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    # Union, never substitute: an empty result (git missing, not a repo) leaves
    # the original single-root behaviour untouched. See check-install.py's
    # module docstring for why no worktree is privileged as "the" install source.
    repo_roots = {repo_root} | ci.repo_worktrees(repo_root)
    codex_dir = Path(args.codex_dir)
    cursor_dir = Path(args.cursor_dir)
    claude_dir = Path(args.claude_dir)
    codex_uses_plugin = codex_plugin_enabled(codex_dir / "config.toml")
    cursor_uses_catalog = cursor_skill_catalog_served(
        cursor_dir, claude_dir, repo_root, repo_roots
    )
    codex_entries = [] if codex_uses_plugin else collect_flat(
        repo_root, "codex-skills", codex_dir / "skills", "codex", repo_roots
    )
    cursor_skill_raw = collect_flat(
        repo_root, "skills", cursor_dir / "skills", "cursor", repo_roots
    )
    cursor_skill_entries = (
        catalog_leftovers(cursor_skill_raw) if cursor_uses_catalog else cursor_skill_raw
    )
    checks = (
        ("Claude", ci.collect(repo_root, claude_dir, repo_roots)),
        ("Codex (plugin; wrappers intentionally absent)" if codex_uses_plugin else "Codex", codex_entries),
        ("Gemini", collect_flat(repo_root, "skills", Path(args.gemini_dir) / "skills", "gemini", repo_roots)),
        (
            "Cursor skills (plugin/catalog leftovers)"
            if cursor_uses_catalog
            else "Cursor skills",
            cursor_skill_entries,
        ),
        (
            "Cursor rules",
            collect_flat(
                repo_root, "cursor-rules", cursor_dir / "rules", "cursor", repo_roots
            ),
        ),
    )
    defects = sum(report(name, entries) for name, entries in checks)
    if defects:
        print(f"\n{defects} repairable entries do not track this repo. Run bootstrap.sh to repair them.")
    return 1 if args.strict and defects else 0


if __name__ == "__main__":
    raise SystemExit(main())
