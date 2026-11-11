#!/usr/bin/env python3
"""SessionStart: warn when this session's ai-config plugin pin lags the marketplace or origin.

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

It also reads the tip of origin's default branch with one `git ls-remote`
in the clone (ai-config#5309 step 2; #3589, #3149). It does not fetch. The
clone advances only when the marketplace is updated, so in #3149 it was 51
commits behind origin, and a comparison with the clone alone called a pin
that matched it current. When origin answers, a pin that does not contain
origin's tip is reported even when it matches the clone or is ahead of it.
When origin does not answer in time (no network, no remote), the comparison
falls back to the clone and says so on stderr. All origin reads together get
at most 6 seconds, inside the hook's registered 10-second timeout
(AI_CONFIG_REMOTE_BUDGET overrides the 6, for tests).

Origin is not read for a user-scope pin in a cloud session
(CLAUDE_CODE_REMOTE=true) unless AI_CONFIG_NO_AUTO_REFRESH is set, because
there `refresh-stale-plugin-pin-cloud.py` updates the marketplace and the
user-scope pin at the same session start. That hook leaves project and local
pins alone, so origin is still read for those. AI_CONFIG_NO_REMOTE_CHECK=1
turns the origin read off everywhere.

Without an origin reading, a pin that is AHEAD of the clone (the clone, not
the pin, is behind) is not reported. A pin cannot warn about itself: this hook runs only from pins
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
import time
from pathlib import Path

PLUGIN = "ai-config"
DEFAULT_REMOTE_BUDGET = 6.0
_deadline: float | None = None


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


def git(clone: Path, *args: str, quiet: bool = False,
        timeout: float = 5) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(clone), *args],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
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
    return head.startswith(pin) or is_ancestor(clone, head, pin)


def behind(clone: Path, pin: str, head: str) -> str:
    count = git(clone, "rev-list", "--count", f"{pin}..{head}", quiet=True)
    if count is None:
        return "an unknown number of commits (the pin is not in the clone)"
    return f"{count} commit(s)"


def remote_budget() -> float:
    raw = os.environ.get("AI_CONFIG_REMOTE_BUDGET")
    if not raw:
        return DEFAULT_REMOTE_BUDGET
    try:
        return float(raw)
    except ValueError:
        print(f"warn-stale-plugin-pin: AI_CONFIG_REMOTE_BUDGET={raw!r} is not "
              f"a number; using {DEFAULT_REMOTE_BUDGET}", file=sys.stderr)
        return DEFAULT_REMOTE_BUDGET


def refresh_covers(entry: dict) -> bool:
    """True when the cloud refresh hook updates this pin at session start."""
    return (os.environ.get("CLAUDE_CODE_REMOTE") == "true"
            and not os.environ.get("AI_CONFIG_NO_AUTO_REFRESH")
            and entry.get("scope") == "user")


def origin_tip(clone: Path) -> str | None:
    """The tip of origin's default branch, or None when it cannot be read."""
    global _deadline
    if _deadline is None:
        _deadline = time.monotonic() + remote_budget()
    remaining = min(5.0, _deadline - time.monotonic())
    if remaining <= 0.5:
        print(f"warn-stale-plugin-pin: no time left to read origin for "
              f"{clone}; compared with the local clone only", file=sys.stderr)
        return None
    out = git(clone, "ls-remote", "origin", "HEAD", timeout=remaining)
    if not out:
        print(f"warn-stale-plugin-pin: could not read origin's default branch "
              f"for {clone}; compared with the local clone only",
              file=sys.stderr)
        return None
    return out.split()[0]


def is_ancestor(clone: Path, older: str, newer: str) -> bool:
    return git(clone, "merge-base", "--is-ancestor", older, newer,
               quiet=True) is not None


def clone_lags(clone: Path, head: str, tip: str | None) -> bool:
    """True when origin's tip is neither the clone's HEAD nor its ancestor."""
    if tip is None or head == tip:
        return False
    return not is_ancestor(clone, tip, head)


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
        mine = [e for e in entries
                if isinstance(e, dict) and applies(e, here)]
        if not mine:
            continue
        remote = os.environ.get("AI_CONFIG_NO_REMOTE_CHECK") != "1"
        read = remote and not all(refresh_covers(e) for e in mine)
        origin = origin_tip(clone) if read else None
        for entry in mine:
            tip = None if refresh_covers(entry) else origin
            lagging = clone_lags(clone, head, tip)
            pin = entry.get("gitCommitSha") or ""
            has_tip = bool(pin and tip) and (tip.startswith(pin)
                                             or is_ancestor(clone, tip, pin))
            behind_clone = (bool(pin) and not head.startswith(pin)
                            and is_ancestor(clone, pin, head))
            if has_tip and not behind_clone:
                continue
            current = bool(pin) and pin_is_current(clone, pin, head)
            if current and not lagging:
                continue
            scope = entry.get("scope", "?")
            flag = "" if scope == "user" else f" --scope {scope}"
            where = entry.get("projectPath") or "user scope"
            shown = pin[:12] if pin else "no recorded commit"
            if current:
                relation = ("matching" if head.startswith(pin)
                            else "ahead of")
                state = (f"{relation} the marketplace clone at {head[:12]}, "
                         f"which has not been updated: origin's default "
                         f"branch is at {tip[:12]}. ")
            else:
                count = (behind(clone, pin, head) if pin
                         else "an unknown number of commits")
                state = (f"{count} behind the marketplace clone at "
                         f"{head[:12]}"
                         + (f", which itself lags origin at {tip[:12]}. "
                            if lagging else ". "))
            lines.append(
                f"- {key}, {scope} scope ({where}): pinned to {shown}, "
                + state
                + f"Run `claude plugin marketplace update {marketplace}`, then "
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
        "from a cached snapshot older than the marketplace clone or its "
        "origin, so "
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
