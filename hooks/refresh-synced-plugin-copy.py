#!/usr/bin/env python3
"""SessionStart: overwrite a stale claude.ai-synced ai-config copy with this plugin's files.

WHY THIS EXISTS
---------------
A claude.ai cloud or project-thread session loads two copies of ai-config when
its environment installs the marketplace plugin:

  - the marketplace plugin (`ai-config@Morrison-Lab`), which the environment's
    Setup script installs and `refresh-stale-plugin-pin-cloud.py` keeps current;
  - the account plugin claude.ai syncs into
    `~/.claude/plugins/synced/<bucket>/ai-config/`, which is only as fresh as the
    account's last manual Sync.

Both register their hooks, and a deny from either one wins. On 2026-11-20 the
synced copy predated ai-config#5414 (its `guard-slide-major-tag.py` had no
`_referenced_elsewhere`), so it denied the gha `v3` slides after gha#2174 and
gha#2177 over a brand-new reusable workflow's `contents: read`, which `main`'s
guard allows. The auto-mode classifier then refused the
`ALLOW_BREAKING_SLIDE=1` override, and both slides waited on Ezra
(ai-config#6004). Re-measured 2026-11-21: the synced copy was at about
ai-config#4726 while `main` was past #6054.

WHAT IT DOES
------------
Only when CLAUDE_CODE_REMOTE=true and this hook runs from a copy that is NOT
itself under `plugins/synced/`: for each synced directory whose
`.claude-plugin/plugin.json` names `ai-config`, it copies every file of this
plugin's root over the synced copy, skipping `.git`. Files only the synced copy
has are kept, because its already-loaded `hooks.json` may still name them and a
missing script would make that hook exit 2, which blocks.

Claude Code runs a hook by executing its command each time, so the synced
copy's hooks run the fresh scripts from the next tool call on. Its `hooks.json`
was read at startup, so a hook added since the account's last Sync still runs
only through this plugin's own registration, which is enough.

Opt out with AI_CONFIG_NO_SYNCED_REFRESH=1. It never blocks and always exits 0.
`AI_CONFIG_PLUGINS_DIR` overrides `~/.claude/plugins` and `CLAUDE_PLUGIN_ROOT`
names the source, for tests.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

PLUGIN = "ai-config"


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


def main() -> int:
    if os.environ.get("CLAUDE_CODE_REMOTE") != "true" or os.environ.get("AI_CONFIG_NO_SYNCED_REFRESH"):
        return 0
    root_env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not root_env:
        return 0
    source = Path(root_env).resolve()
    plugins = plugins_dir().resolve()
    if (plugins / "synced") in source.parents or plugin_name(source) != PLUGIN:
        return 0
    refreshed = []
    for target in synced_copies(plugins):
        if target.resolve() == source:
            continue
        try:
            n = overwrite(source, target)
        except OSError as err:
            print(f"refresh-synced-plugin-copy: {target}: {err}", file=sys.stderr)
            continue
        refreshed.append(f"{target} ({n} files)")
    if refreshed:
        json.dump({"hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                "ai-config: overwrote the claude.ai-synced ai-config copy with the "
                f"marketplace plugin's files from {source}: " + "; ".join(refreshed)
                + ". Its hooks now run current code, so a deny from a stale synced "
                "guard (ai-config#6004) no longer applies."),
        }}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
