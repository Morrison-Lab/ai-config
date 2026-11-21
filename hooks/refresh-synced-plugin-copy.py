#!/usr/bin/env python3
"""SessionStart: keep the claude.ai-synced ai-config copy current in cloud sessions.

WHY THIS EXISTS
---------------
Every claude.ai cloud or project-thread session gets the account plugin that
claude.ai syncs into `~/.claude/plugins/synced/<bucket>/ai-config/`. That copy
is only as fresh as the account's last Sync. A session whose environment Setup
script installs the marketplace plugin (`ai-config@Morrison-Lab`) loads both
copies; both register their hooks, and a deny from either one wins.

On 2026-11-20 the synced copy predated ai-config#5414 (its
`guard-slide-major-tag.py` had no `_referenced_elsewhere`), so it denied the gha
`v3` slides after gha#2174 and gha#2177 over a brand-new reusable workflow's
`contents: read`, which `main`'s guard allows. The auto-mode classifier then
refused the `ALLOW_BREAKING_SLIDE=1` override, and both slides waited on Ezra
(ai-config#6004). Re-measured 2026-11-21: the synced copy was at about
ai-config#4726 while `main` was past #6054, and the project's environment had
never installed the marketplace plugin, so only the stale copy ran.

WHAT IT DOES
------------
Only when CLAUDE_CODE_REMOTE=true, and only when a synced ai-config copy
exists. It picks a fresh source:

  - this hook's own root, when that is the marketplace plugin;
  - otherwise (it is running from the synced copy itself) the user-scope
    marketplace install recorded in `installed_plugins.json`;
  - and when there is none, it installs `ai-config@Morrison-Lab` first.
    Opt out of that install with AI_CONFIG_NO_SYNCED_INSTALL=1.

It then copies every file of the source over each synced copy whose
`.claude-plugin/plugin.json` names `ai-config`, skipping `.git`. Files only the
synced copy has are kept, because its already-loaded `hooks.json` may still
name them and a missing script would make that hook exit 2, which blocks.

Claude Code runs a hook by executing its command each time, so the synced
copy's hooks run the fresh scripts from the next tool call on. Its `hooks.json`
was read at startup, so a hook added since the account's last Sync runs only
through the marketplace plugin's own registration, from the next session.

Because the synced copy then carries this hook, one Sync (or one environment
that installs the marketplace plugin) is enough: from then on every session
refreshes the synced copy itself, however stale the account's Sync gets.

Opt out entirely with AI_CONFIG_NO_SYNCED_REFRESH=1. It never blocks and always
exits 0. `AI_CONFIG_PLUGINS_DIR` overrides `~/.claude/plugins`,
`AI_CONFIG_CLAUDE_BIN` the `claude` executable, and `CLAUDE_PLUGIN_ROOT` names
the hook's own root, for tests.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN = "ai-config"
MARKETPLACE = "Morrison-Lab"
REPO = "Morrison-Lab/ai-config"
KEY = f"{PLUGIN}@{MARKETPLACE}"
# Up to three sequential calls must fit the hook's 180-second budget in hooks.json.
TIMEOUT = 55


def plugins_dir() -> Path:
    override = os.environ.get("AI_CONFIG_PLUGINS_DIR")
    return Path(override) if override else Path.home() / ".claude" / "plugins"


def plugin_name(root: Path) -> str | None:
    try:
        data = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data.get("name") if isinstance(data, dict) else None


def synced_copies(plugins: Path) -> list[Path]:
    synced = plugins / "synced"
    if not synced.is_dir():
        return []
    return sorted(p for p in synced.glob("*/*")
                  if p.is_dir() and plugin_name(p) == PLUGIN)


def overwrite(source: Path, target: Path) -> int:
    """Copy every file of SOURCE over TARGET, skipping .git; return the count."""
    count = 0
    for path in source.rglob("*"):
        rel = path.relative_to(source)
        if rel.parts and rel.parts[0] == ".git":
            continue
        dest = target / rel
        if path.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            continue
        if path.is_symlink() or not path.is_file():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        count += 1
    return count


def run(*cmd: str) -> bool:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as err:
        print(f"refresh-synced-plugin-copy: {' '.join(cmd)}: {err}", file=sys.stderr)
        return False
    if out.returncode != 0:
        print(f"refresh-synced-plugin-copy: {' '.join(cmd)} failed: "
              f"{(out.stderr or out.stdout).strip()}", file=sys.stderr)
    return out.returncode == 0


def installed_path(plugins: Path) -> Path | None:
    """The user-scope install path of the marketplace plugin, or None."""
    try:
        record = json.loads((plugins / "installed_plugins.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    entries = record.get("plugins", {}).get(KEY) if isinstance(record, dict) else None
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, dict) and entry.get("scope") == "user" and entry.get("installPath"):
            path = Path(entry["installPath"])
            return path if plugin_name(path) == PLUGIN else None
    return None


def install_marketplace_plugin(plugins: Path) -> Path | None:
    """Install the marketplace plugin at user scope; return its path, or None."""
    claude = os.environ.get("AI_CONFIG_CLAUDE_BIN", "claude")
    added = (run(claude, "plugin", "marketplace", "add", REPO)
             or run(claude, "plugin", "marketplace", "update", MARKETPLACE))
    if not added or not run(claude, "plugin", "install", KEY):
        return None
    return installed_path(plugins)


def find_source(plugins: Path) -> tuple[Path | None, bool]:
    """The fresh copy to copy from, and whether this hook installed it."""
    root_env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if root_env:
        root = Path(root_env).resolve()
        if (plugins / "synced") not in root.parents and plugin_name(root) == PLUGIN:
            return root, False
    found = installed_path(plugins)
    if found:
        return found.resolve(), False
    if os.environ.get("AI_CONFIG_NO_SYNCED_INSTALL"):
        return None, False
    installed = install_marketplace_plugin(plugins)
    if installed is None:
        return None, False
    return installed.resolve(), True


def main() -> int:
    if os.environ.get("CLAUDE_CODE_REMOTE") != "true" or os.environ.get("AI_CONFIG_NO_SYNCED_REFRESH"):
        return 0
    plugins = plugins_dir().resolve()
    targets = synced_copies(plugins)
    if not targets:
        return 0
    source, installed = find_source(plugins)
    if source is None:
        return 0
    refreshed = []
    for target in targets:
        if target.resolve() == source:
            continue
        try:
            n = overwrite(source, target)
        except OSError as err:
            print(f"refresh-synced-plugin-copy: {target}: {err}", file=sys.stderr)
            continue
        refreshed.append(f"{target} ({n} files)")
    if not refreshed:
        return 0
    note = ""
    if installed:
        note = (f" It first installed {KEY}, which this environment lacked; "
                "that plugin's own hooks register from the next session.")
    json.dump({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": (
            "ai-config: overwrote the claude.ai-synced ai-config copy with the "
            f"marketplace plugin's files from {source}: " + "; ".join(refreshed)
            + ". Its hooks now run current code, so a deny from a stale synced "
            "guard (ai-config#6004) no longer applies." + note),
    }}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
