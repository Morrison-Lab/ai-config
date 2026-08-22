#!/usr/bin/env python3
"""Unit tests for scripts/cursor-plugin-enabled.py."""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("cursor-plugin-enabled.py")
spec = importlib.util.spec_from_file_location("cursor_plugin", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

passes = failures = 0


def check(name: str, condition: bool) -> None:
    global passes, failures
    print(f"{'PASS' if condition else 'FAIL'}: {name}")
    passes += condition
    failures += not condition


with tempfile.TemporaryDirectory() as raw:
    root = Path(raw)
    cursor, claude, repo = root / "cursor", root / "claude", root / "repo"
    (repo / "skills" / "ardi").mkdir(parents=True)
    check("empty dirs do not skip skill install",
          mod.skip_reason(cursor, claude, repo) is None)

    local = cursor / "plugins" / "local" / "ai-config"
    local.mkdir(parents=True)
    check("local plugin skips skill install",
          mod.skip_reason(cursor, claude, repo) == "ai-config Cursor plugin is already installed")
    local.rmdir()
    local.parent.rmdir()

    cached = cursor / "plugins" / "cache" / "morrison-lab" / "ai-config" / "abc"
    cached.mkdir(parents=True)
    check("marketplace cache skips skill install",
          "Cursor plugin is already installed" in (mod.skip_reason(cursor, claude, repo) or ""))
    shutil.rmtree(cursor / "plugins")

    listing = cursor / "plugins" / "marketplaces" / "morrison-lab" / "ai-config"
    (listing / "plugins" / "ai-config").mkdir(parents=True)
    (listing / ".cursor-plugin").mkdir()
    (listing / ".cursor-plugin" / "plugin.json").write_text("{}\n", encoding="utf-8")
    check(
        "marketplace catalog clone does not skip skill install",
        mod.skip_reason(cursor, claude, repo) is None,
    )
    shutil.rmtree(cursor / "plugins")

    claude_skills = claude / "skills"
    claude_skills.parent.mkdir(parents=True, exist_ok=True)
    try:
        claude_skills.symlink_to(repo / "skills")
        linked = True
    except OSError:
        linked = False
    if linked:
        check("Claude skill symlink skips Cursor skill install",
              "claude/skills" in (mod.skip_reason(cursor, claude, repo) or "").replace("~/", ""))
        sibling = root / "worktree"
        (sibling / "skills" / "ardi").mkdir(parents=True)
        check(
            "Claude skills into a sibling worktree still skip",
            "claude/skills" in (
                mod.skip_reason(
                    cursor, claude, sibling,
                    repo_roots={sibling.resolve(), repo.resolve()},
                ) or ""
            ).replace("~/", ""),
        )
    else:
        print("SKIP: Claude skill symlink (platform cannot create it)")

    unreadable = cursor / "plugins" / "cache"
    unreadable.mkdir(parents=True)
    try:
        unreadable.chmod(0o000)
        crashed = False
        try:
            found = mod.plugin_installed(cursor)
        except OSError:
            crashed = True
            found = None
        finally:
            unreadable.chmod(0o755)
        check("unreadable cache does not crash plugin_installed",
              (not crashed) and found is False)
    except OSError:
        print("SKIP: unreadable cache (platform cannot chmod)")

print(f"\n{passes} passed, {failures} failed")
raise SystemExit(1 if failures else 0)
