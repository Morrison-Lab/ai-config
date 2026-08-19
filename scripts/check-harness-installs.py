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


def collect_flat(repo_root: Path, source_rel: str, install_dir: Path, harness: str):
    """Classify an individually-linked catalog, including consumer-only paths."""
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
            repo_root,
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
    return sum(counts.get(status, 0) for status in ci.FIXABLE)


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
    codex_dir = Path(args.codex_dir)
    codex_uses_plugin = codex_plugin_enabled(codex_dir / "config.toml")
    codex_entries = [] if codex_uses_plugin else collect_flat(
        repo_root, "codex-skills", codex_dir / "skills", "codex"
    )
    checks = (
        ("Claude", ci.collect(repo_root, Path(args.claude_dir))),
        ("Codex (plugin; wrappers intentionally absent)" if codex_uses_plugin else "Codex", codex_entries),
        ("Gemini", collect_flat(repo_root, "skills", Path(args.gemini_dir) / "skills", "gemini")),
        ("Cursor", collect_flat(repo_root, "cursor-rules", Path(args.cursor_dir) / "rules", "cursor")),
    )
    defects = sum(report(name, entries) for name, entries in checks)
    if defects:
        print(f"\n{defects} repairable entries do not track this repo. Run bootstrap.sh to repair them.")
    return 1 if args.strict and defects else 0


if __name__ == "__main__":
    raise SystemExit(main())
