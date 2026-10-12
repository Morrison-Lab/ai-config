#!/usr/bin/env python3
"""SessionStart: warn when this session's ai-config plugin pin lags the marketplace clone.

WHY THIS EXISTS (ai-config#2439)
--------------------------------
Claude Code runs a plugin's hooks from a per-scope PINNED cache snapshot,
`~/.claude/plugins/cache/<marketplace>/ai-config/<sha>/`, recorded in
`~/.claude/plugins/installed_plugins.json`. The pin does not advance when the
marketplace clone updates, so a merged hook fix can sit unrun for weeks:
measured 2026-08-27 (a project pin 25 days stale), 2026-09-21 (a merged guard
absent from every pin while the session made the exact mistake it guards),
and 2026-10-08 (a user pin of `6a4f97ebfc79` refusing pushes that main had
stopped refusing).

Nothing surfaced the lag. `shared/workflow/keep-checkouts-fresh.md` documents
the manual check and `scripts/check-hook-delivery.py` reports missing hooks,
but both run only when a session already suspects the cache. This hook runs
the comparison at every session start, where the remedy is cheapest.

WHAT IT COMPARES
----------------
Each `ai-config@<marketplace>` entry that applies to this session -- the
`user` scope, and any `project`/`local` scope whose `projectPath` is this
session's directory or an ancestor of it -- against the HEAD of the local
marketplace clone `~/.claude/plugins/marketplaces/<marketplace>`.

It does not fetch. A session-start hook has a short timeout and may have no
network, so the clone itself can lag origin; the warning says to update the
marketplace first for that reason. A clean result therefore means "the pin
matches the local clone", not "the pin matches origin/main".

A pin that is AHEAD of the clone (the clone, not the pin, is behind) is
not reported. A pin cannot warn about itself: this hook runs only from pins
that already contain it, so a pin that predates it stays silent until it is
updated once by hand.

It never blocks and always exits 0. A missing or unreadable record means
there is nothing to compare (no plugin install, or a non-Claude harness), and
that case is reported on stderr rather than as a warning.

`AI_CONFIG_PLUGINS_DIR` overrides `~/.claude/plugins` for tests.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PLUGIN = "ai-config"


def plugins_dir() -> Path:
    override = os.environ.get("AI_CONFIG_PLUGINS_DIR")
    if override:
        return Path(override)
    return Path.home() / ".claude" / "plugins"


def session_dir(payload: dict) -> Path:
    for candidate in (payload.get("cwd"), os.environ.get("CLAUDE_PROJECT_DIR")):
        if candidate:
            return Path(candidate)
    return Path.cwd()


def applies(entry: dict, here: Path) -> bool:
    scope = entry.get("scope")
    if scope == "user":
        return True
    project = entry.get("projectPath")
    if scope not in ("project", "local") or not project:
        return False
    try:
        here.resolve().relative_to(Path(project).resolve())
    except ValueError:
        return False
    return True


def git(clone: Path, *args: str, quiet: bool = False) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(clone), *args],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as err:
        print(f"warn-stale-plugin-pin: git {' '.join(args)} in {clone}: {err}",
              file=sys.stderr)
        return None
    if out.returncode != 0:
        if not quiet:
            print(f"warn-stale-plugin-pin: git {' '.join(args)} in {clone}: "
                  f"{out.stderr.strip()}", file=sys.stderr)
        return None
    return out.stdout.strip()


def pin_is_current(clone: Path, pin: str, head: str) -> bool:
    """True when the pin is HEAD, or HEAD is its ancestor (the clone lags)."""
    if head.startswith(pin):
        return True
    return git(clone, "merge-base", "--is-ancestor", head, pin,
               quiet=True) is not None


def behind(clone: Path, pin: str, head: str) -> str:
    count = git(clone, "rev-list", "--count", f"{pin}..{head}", quiet=True)
    if count is None:
        return "an unknown number of commits (the pin is not in the clone)"
    return f"{count} commit(s)"


def stale_lines(record: dict, here: Path, root: Path) -> list[str]:
    lines = []
    plugins = record.get("plugins", {})
    if not isinstance(plugins, dict):
        print("warn-stale-plugin-pin: installed_plugins.json 'plugins' is "
              "not an object", file=sys.stderr)
        return lines
    for key, entries in sorted(plugins.items()):
        name, _, marketplace = key.partition("@")
        if name != PLUGIN or not marketplace or not isinstance(entries, list):
            continue
        clone = root / "marketplaces" / marketplace
        head = git(clone, "rev-parse", "HEAD")
        if head is None:
            print(f"warn-stale-plugin-pin: no git clone at {clone}; "
                  f"cannot compare {key}", file=sys.stderr)
            continue
        for entry in entries:
            if not isinstance(entry, dict) or not applies(entry, here):
                continue
            pin = entry.get("gitCommitSha") or ""
            if pin and pin_is_current(clone, pin, head):
                continue
            scope = entry.get("scope", "?")
            flag = "" if scope == "user" else f" --scope {scope}"
            where = entry.get("projectPath") or "user scope"
            shown = pin[:12] if pin else "no recorded commit"
            lines.append(
                f"- {key}, {scope} scope ({where}): pinned to {shown}, "
                f"{behind(clone, pin, head) if pin else 'an unknown number of commits'} "
                f"behind the marketplace clone at {head[:12]}. "
                f"Run `claude plugin marketplace update {marketplace}`, then "
                f"`claude plugin update {key}{flag}`"
                + ("" if scope == "user" else " from that directory")
                + "."
            )
    return lines


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            payload = {}
    except (ValueError, OSError):
        payload = {}
    root = plugins_dir()
    path = root / "installed_plugins.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return 0
    except (OSError, ValueError) as err:
        print(f"warn-stale-plugin-pin: cannot read {path}: {err}",
              file=sys.stderr)
        return 0
    if not isinstance(record, dict):
        print(f"warn-stale-plugin-pin: {path} is not a JSON object",
              file=sys.stderr)
        return 0
    lines = stale_lines(record, session_dir(payload), root)
    if not lines:
        return 0
    text = (
        "STALE PLUGIN PIN (ai-config#2439): this session runs ai-config hooks "
        "from a cached snapshot older than the local marketplace clone, so "
        "hook fixes merged since then are NOT running here. A guard that "
        "refuses something already fixed on main is most likely this, not a "
        "live bug.\n"
        + "\n".join(lines)
        + "\nRestart the session afterwards to load the new snapshot."
    )
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": text,
        }
    }, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
