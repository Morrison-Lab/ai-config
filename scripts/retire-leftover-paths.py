#!/usr/bin/env python3
"""Report the leftover ai-config delivery paths on this machine, and retire them on request.

Step 3 of ai-config#5309; docs/delivery-paths.md lists the leftovers. A plain run
only reports. `--retire` reports, then moves each `retire` path into
~/.claude/ai-config-leftovers/<UTC time>/, and removes the settings.json hook
entries that run catalog hooks from ~/.claude/hooks after copying the old file
there; moving them back undoes it, even after a failed move. `keep` items need a person and are never
touched. It reuses doctor.py's leftover tests and wire-user-config.py's hook-entry
test. It sweeps nothing when no settings file enables the plugin (exit 0, or 2 with --retire), since
a ~/.claude copy may then be the only install.

Exit status: 0 when nothing is left, 1 when an item remains, 2 when a file could
not be read or --retire was refused.
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import re
import shutil
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import doctor  # noqa: E402

_spec = importlib.util.spec_from_file_location("wire_user_config", SCRIPTS / "wire-user-config.py")
wire = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wire)


def provenance(path: Path) -> str | None:
    """Why `path` is provably ai-config's, or None: a link into a checkout, or only repo names."""
    if path.name == "memories":  # ~/.claude/CLAUDE.md may import from it, and nothing replaces it (#2352)
        return None
    if path.is_symlink():
        return doctor.describe_path(path) if doctor.points_into_ai_config(path) else None
    ours = {p.name for p in (doctor.REPO_ROOT / path.name).iterdir()}
    foreign = sorted(p.name for p in path.iterdir() if p.name not in ours) if path.is_dir() else ["?"]
    return None if foreign else "a copy holding only names from this repo"


def path_items(home: Path) -> list[tuple[str, Path, str]]:
    """(action, path, reason) for each leftover path under `home`."""
    items = []
    for name in doctor.LEFTOVER_NAMES:
        path = home / name
        if not (path.is_symlink() or path.exists()):
            continue
        if name in doctor.DOCUMENTED_MANUAL_LINKS and path.is_symlink() and doctor.points_into_ai_config(path):
            continue
        if name in doctor.DOCUMENTED_MANUAL_LINKS and not path.is_symlink():
            items.append(("keep", path, "a copy: replace it with a symlink into a checkout (README.md)"))
            continue
        why = provenance(path)
        items.append(("retire", path, why) if why else
                     ("keep", path, "not provably ai-config's, or memories/, which a CLAUDE.md may import"))
    linked, doubled = doctor.find_skill_leftovers(home)
    items += [("retire", s, doctor.describe_path(s)) for s in linked]
    return items + [("keep", s, "shares a name with an ai-config skill; it may be your own")
                    for s in doubled]


def strip_leftover_hooks(settings: dict, hooks_dir: Path) -> tuple[dict, list[str]]:
    """Return settings without catalog hooks run from `hooks_dir`, and the removed commands."""
    if not isinstance(settings.get("hooks"), dict):
        return settings, []
    scripts = wire.catalog_scripts()
    anchors = [hooks_dir.as_posix()]  # commands are matched with backslashes turned into slashes
    if hooks_dir == Path.home() / ".claude" / "hooks":  # Path.home() also works where HOME is unset (Windows)
        anchors += ["$HOME/.claude/hooks", "${HOME}/.claude/hooks", "~/.claude/hooks"]
    pattern = re.compile("(?:" + "|".join(map(re.escape, anchors)) + ")/(?:"
                         + "|".join(map(re.escape, scripts)) + r")(?![\w.~-])")

    def leftover(hook):
        return wire.leftover_hook(hook, scripts) and bool(pattern.search(hook["command"].replace(chr(92), "/")))

    removed, kept_events = [], {}
    for event, groups in settings["hooks"].items():
        if not isinstance(groups, list):
            kept_events[event] = groups
            continue
        kept_groups = []
        for group in groups:
            hooks = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(hooks, list):
                kept_groups.append(group)
                continue
            removed += [h["command"] for h in hooks if leftover(h)]
            if any(not leftover(h) for h in hooks):
                kept_groups.append({**group, "hooks": [h for h in hooks if not leftover(h)]})
        if kept_groups:
            kept_events[event] = kept_groups
    return {**settings, "hooks": kept_events}, removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--retire", action="store_true", help="after reporting, retire the `retire` items")
    args = parser.parse_args(argv)
    home = doctor.claude_home()
    enabled, source, error = doctor.resolve_plugin_enabled(home)
    settings_path = home / "settings.json"
    settings = wire.load_json(settings_path)
    if error is not None or settings is None:
        bad = source if error else settings_path  # the settings file that failed to parse
        print(f"Not swept: {bad} is not readable as plain JSON.")
        return 2
    if not enabled:
        print("Not swept: no settings file enables the ai-config plugin, so ~/.claude may hold the only install.")
        return 2 if args.retire else 0

    items = path_items(home)
    stripped, commands = strip_leftover_hooks(settings, home / "hooks")
    items += [("retire", settings_path, f"hook entry: {c}") for c in commands]
    for action, path, reason in items:
        print(f"{action:6} {path}: {reason}")
    if not items:
        print(f"No leftover delivery paths under {home}.")
        return 0
    if not args.retire:
        print("Reported only. Rerun with --retire to move the `retire` items aside.")
        return 1
    if commands and settings_path.is_symlink():
        print(f"Refused: {settings_path} is a symlink, and rewriting it would detach it.")
        return 2

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = home / "ai-config-leftovers" / stamp
    if any(action == "retire" for action, _, _ in items):
        backup.mkdir(parents=True)
    if commands:
        shutil.copy2(settings_path, backup / "settings.json")
        wire.write_json(settings_path, stripped)
        print(f"edited {settings_path}: removed {len(commands)} hook {'entry' if len(commands) == 1 else 'entries'}; old file in {backup}")
    for action, path, _ in items:
        if action == "retire" and path != settings_path:
            target = backup / path.relative_to(home)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(target))
            print(f"moved  {path} -> {target}")
    return 1 if any(action == "keep" for action, _, _ in items) else 0


if __name__ == "__main__":
    sys.exit(main())
