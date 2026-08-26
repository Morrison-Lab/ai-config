#!/usr/bin/env python3
"""Unit tests for scripts/cursor-plugin-enabled.py."""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
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
    check("empty dirs do not skip rule install",
          mod.skip_rules_reason(cursor) is None)

    local = cursor / "plugins" / "local" / "ai-config"
    local.mkdir(parents=True)
    check("local plugin skips skill install",
          mod.skip_reason(cursor, claude, repo) == "ai-config Cursor plugin is already installed")
    check("local plugin skips rule install",
          mod.skip_rules_reason(cursor) == "ai-config Cursor plugin is already installed")
    local.rmdir()
    local.parent.rmdir()

    cached = cursor / "plugins" / "cache" / "morrison-lab" / "ai-config" / "abc"
    cached.mkdir(parents=True)
    check("marketplace cache skips skill install",
          "Cursor plugin is already installed" in (mod.skip_reason(cursor, claude, repo) or ""))
    check("marketplace cache skips rule install",
          "Cursor plugin is already installed" in (mod.skip_rules_reason(cursor) or ""))
    shutil.rmtree(cursor / "plugins")

    listing = cursor / "plugins" / "marketplaces" / "morrison-lab" / "ai-config"
    (listing / "plugins" / "ai-config").mkdir(parents=True)
    (listing / ".cursor-plugin").mkdir()
    (listing / ".cursor-plugin" / "plugin.json").write_text("{}\n", encoding="utf-8")
    check(
        "marketplace catalog clone does not skip skill install",
        mod.skip_reason(cursor, claude, repo) is None,
    )
    check(
        "marketplace catalog clone does not skip rule install",
        mod.skip_rules_reason(cursor) is None,
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
        check("Claude skill symlink does not skip rule install",
              mod.skip_rules_reason(cursor) is None)
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

    unreadable_plugins = cursor / "plugins"
    try:
        unreadable_plugins.chmod(0o000)
        crashed = False
        try:
            found = mod.plugin_installed(cursor)
        except OSError:
            crashed = True
            found = None
        finally:
            unreadable_plugins.chmod(0o755)
        check("unreadable plugins dir does not crash plugin_installed",
              (not crashed) and found is False)
    except OSError:
        print("SKIP: unreadable plugins dir (platform cannot chmod)")

    unreadable_claude = root / "unreadable_claude"
    unreadable_claude.mkdir(parents=True)
    try:
        unreadable_claude.chmod(0o000)
        crashed = False
        try:
            found = mod.claude_skills_serve_repo(unreadable_claude, repo)
        except OSError:
            crashed = True
            found = None
        finally:
            unreadable_claude.chmod(0o755)
        check("unreadable claude dir does not crash claude_skills_serve_repo",
              (not crashed) and found is False)
    except OSError:
        print("SKIP: unreadable claude dir (platform cannot chmod)")

    skills = cursor / "skills"
    sibling = root / "worktree"
    other = root / "other" / "skills" / "ardi"
    (sibling / "skills" / "ardi").mkdir(parents=True, exist_ok=True)
    other.mkdir(parents=True)
    skills.mkdir(parents=True)
    try:
        (skills / "ardi").symlink_to(sibling / "skills" / "ardi")
        (skills / "foreign").symlink_to(other)
        stacked_ok = True
    except OSError:
        stacked_ok = False
    if stacked_ok:
        names = {
            path.name
            for path in mod.stacked_cursor_skill_paths(
                cursor, repo, {repo.resolve(), sibling.resolve()}
            )
        }
        check("sibling-worktree skill link is stacked", "ardi" in names)
        check("foreign skill link is not stacked", "foreign" not in names)
        sibling_rule = sibling / "cursor-rules" / "base.mdc"
        sibling_rule.parent.mkdir(parents=True, exist_ok=True)
        sibling_rule.write_text("x\n", encoding="utf-8")
        foreign_rule = root / "other" / "foreign.mdc"
        foreign_rule.write_text("y\n", encoding="utf-8")
        rules = cursor / "rules"
        rules.mkdir(parents=True)
        (rules / "base.mdc").symlink_to(sibling_rule)
        (rules / "foreign.mdc").symlink_to(foreign_rule)
        (rules / "real.mdc").write_text("leave me\n", encoding="utf-8")
        rule_names = {
            path.name
            for path in mod.stacked_cursor_rule_paths(
                cursor, repo, {repo.resolve(), sibling.resolve()}
            )
        }
        check("sibling-worktree rule link is stacked", "base.mdc" in rule_names)
        check("foreign rule link is not stacked", "foreign.mdc" not in rule_names)
        check("real rule file is not stacked", "real.mdc" not in rule_names)
    else:
        print("SKIP: stacked_cursor_skill_paths (platform cannot create symlink)")

with tempfile.TemporaryDirectory() as raw:
    root = Path(raw)
    cursor, repo = root / "cursor", root / "repo"
    repo.mkdir()

    def run_cli(*cli_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable, str(SCRIPT),
                "--cursor-dir", str(cursor),
                "--repo-root", str(repo),
                *cli_args,
            ],
            capture_output=True, text=True, check=False,
        )

    result = run_cli("--rules")
    check("--rules exits 1 when no plugin", result.returncode == 1)
    (cursor / "plugins" / "local" / "ai-config").mkdir(parents=True)
    result = run_cli("--rules")
    check("--rules exits 0 when plugin is installed", result.returncode == 0)
    check(
        "--rules prints the plugin skip reason",
        "Cursor plugin is already installed" in result.stdout,
    )
    leftover = cursor / "rules" / "000-global-workflow.mdc"
    leftover.parent.mkdir(parents=True)
    rule_src = repo / "cursor-rules" / "000-global-workflow.mdc"
    rule_src.parent.mkdir()
    rule_src.write_text("x\n", encoding="utf-8")
    try:
        leftover.symlink_to(rule_src)
        cli_ok = True
    except OSError:
        cli_ok = False
    if cli_ok:
        result = run_cli("--print-stacked-rules")
        check(
            "--print-stacked-rules lists this repo's leftover rule link",
            str(leftover) in result.stdout,
        )
        check("--print-stacked-rules exits 0", result.returncode == 0)
    else:
        print("SKIP: --print-stacked-rules (platform cannot create symlink)")

print(f"\n{passes} passed, {failures} failed")
raise SystemExit(1 if failures else 0)
