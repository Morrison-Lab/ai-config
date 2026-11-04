#!/usr/bin/env python3
"""SessionStart: in a cloud session, refresh a stale ai-config plugin pin.

WHY THIS EXISTS
---------------
A cloud container installs the plugin once, when its environment is set up, and a
thread session reuses the container for days. Measured 2026-11-04: a thread's pin
was `7fc3d0d240cb`, installed 2026-11-03T19:43Z, and lacked
`hooks/block-project-memory-write.py` (merged 2026-11-04T00:37Z, #4931), so a
memory write the hook exists to refuse went through.

Nothing refreshed it. A repository's own SessionStart hook (lds's
`.claude/hooks/ai-config-skills.sh`) runs `claude plugin update`, but only when the
session's directory is that repository, and a thread session works from a
directory that is not one. `warn-stale-plugin-pin.py` did not catch it either:
it compares the pin with the local marketplace clone and never fetches, and the
clone was as old as the pin.

WHAT IT DOES
------------
Only when CLAUDE_CODE_REMOTE=true (a local session's `enabledPlugins` handles its
own updates): `claude plugin marketplace update <marketplace>`, then, when a user-scope
pin is not the clone's HEAD, `claude plugin update <plugin>`. It reports the move as
additionalContext and asks for `reloadSkills`. The hooks of this session keep
running from the old snapshot until a restart, as the update's own output says.

Opt out with AI_CONFIG_NO_AUTO_REFRESH=1. It never blocks and always exits 0.
A pin that predates this hook is not refreshed by it: update once by hand.
`AI_CONFIG_PLUGINS_DIR` overrides `~/.claude/plugins` and `AI_CONFIG_CLAUDE_BIN`
the `claude` executable, for tests.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PLUGIN = "ai-config"
TIMEOUT = 100


def plugins_dir() -> Path:
    override = os.environ.get("AI_CONFIG_PLUGINS_DIR")
    return Path(override) if override else Path.home() / ".claude" / "plugins"


def run(*cmd: str) -> bool:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as err:
        print(f"refresh-stale-plugin-pin-cloud: {' '.join(cmd)}: {err}", file=sys.stderr)
        return False
    if out.returncode != 0:
        print(f"refresh-stale-plugin-pin-cloud: {' '.join(cmd)} failed: "
              f"{(out.stderr or out.stdout).strip()}", file=sys.stderr)
    return out.returncode == 0


def head(clone: Path) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def user_pin(root: Path, key: str) -> str | None:
    try:
        record = json.loads((root / "installed_plugins.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    entries = record.get("plugins", {}).get(key) if isinstance(record, dict) else None
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, dict) and entry.get("scope") == "user":
            return entry.get("gitCommitSha") or ""
    return None


def main() -> int:
    if os.environ.get("CLAUDE_CODE_REMOTE") != "true" or os.environ.get("AI_CONFIG_NO_AUTO_REFRESH"):
        return 0
    root = plugins_dir()
    claude = os.environ.get("AI_CONFIG_CLAUDE_BIN", "claude")
    record_path = root / "installed_plugins.json"
    try:
        plugins = json.loads(record_path.read_text(encoding="utf-8")).get("plugins", {})
    except (OSError, ValueError, AttributeError):
        return 0
    for key in sorted(k for k in plugins if k.partition("@")[0] == PLUGIN):
        marketplace = key.partition("@")[2]
        before = user_pin(root, key)
        if before is None or not run(claude, "plugin", "marketplace", "update", marketplace):
            continue
        tip = head(root / "marketplaces" / marketplace)
        if not tip or (before and tip.startswith(before)):
            continue
        if not run(claude, "plugin", "update", key):
            continue
        after = user_pin(root, key) or "unknown"
        json.dump({"hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "reloadSkills": True,
            "additionalContext": (
                f"ai-config plugin refreshed from {before[:12] or 'no recorded commit'} to "
                f"{after[:12]} at session start (it had been installed when the container "
                "was set up). Hooks merged since then run only after a restart; until "
                "then a guard missing here is the stale snapshot, not a bug."),
        }}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
