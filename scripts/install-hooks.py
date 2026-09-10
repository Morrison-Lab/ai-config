#!/usr/bin/env python3
"""Check that this repo's hooks are registered with the harness, and repair it.

The Claude Code plugin (`.claude-plugin/plugin.json`) is the supported path
on a fresh machine: its loader auto-discovers `hooks/hooks.json` at the
plugin root and registers every hook it names, no separate step needed.

This script covers the non-plugin path instead, and its `--fix` only ever
edits `settings.json` -- it does not place the hook *scripts* onto disk.
`bootstrap.sh` used to symlink `hooks/` into `~/.claude` for that, but no
longer does (see its header comment), so this path currently only helps on a
machine whose `~/.claude/hooks` already holds the scripts some other way
(see [#2352](https://github.com/Morrison-Lab/ai-config/issues/2352)).
Editing a user's harness config as a side effect of installing skills is a
separate concern from placing files, which is the same objection that kept
`git config --global fetch.prune` out of bootstrap (ai-config#901) -- so
registration stays explicit and opt-in here rather than automatic anywhere.

Why hooks at all, given the rules are already written down: each one here
mechanizes a rule that was violated in a session where it was loaded and
readable. The rule is consulted at read time; the violation happens at
composition time, in the closing paragraph of a long message, where no rule is
in view. Prose is necessary and demonstrably not sufficient -- see
ai-config#907 for the three worked cases.

Per `shared/principles/fail-fast.md` this always prints a count. A bare
"nothing to do" would otherwise mean either "all registered" or "examined
nothing", and the second is exactly what a wrong path or an unreadable
settings file produces.

## Statuses

  registered   the event names this hook's command -- it will run
  missing      the repo ships it; settings.json does not name it
  stale        settings.json names the script by a path that no longer exists

Exit code is 0 when everything is registered, 1 otherwise, so it can gate CI.
`--fix` merges the missing entries in, backing the file up first, and never
touches a hook it did not add. It refuses to register a hook whose script is
not on disk, because that registration is itself the outage described below.

## `--check`

The statuses above are all keyed on `hooks/hooks.json`, so they can only speak
about hooks this repo ships, at the path this script would itself write. That
is the narrower of the two questions. `--check` asks the wider one: for every
hook the settings files actually register, does the path in its command
resolve?

It matters because an unresolvable path is not an inert guard. `python3` exits
2 on a file it cannot open, and exit 2 is the `PreToolUse` deny signal, so one
stale absolute path denies every tool call its matcher names -- and from inside
the session that is indistinguishable from the guard legitimately firing. See
[#2392](https://github.com/Morrison-Lab/ai-config/issues/2392) for the two
measured occurrences, the second of which lost `Bash` and `Write`/`Edit`
together and so had no self-repair path left.

`--check` exits 1 when any registered path is missing. A command whose path
interpolates a variable this process cannot expand (`${CLAUDE_PLUGIN_ROOT}` is
set by the plugin loader, not by the shell) is reported as skipped rather than
missing: not checkable here is not the same finding as not present.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from plugin_overlap import enabled_ai_config_plugins  # noqa: E402
from hook_paths import check_settings  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "hooks" / "hooks.json"


def claude_dir() -> Path:
    return Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))


def load_manifest() -> list[dict]:
    """Flatten hooks/hooks.json (native plugin-hooks schema) to a flat entry list.

    The file is the native Claude Code plugin-hooks schema so the plugin loader
    reads it directly: ``hooks`` is an object keyed by event, each value a list
    of groups ``{matcher?, hooks: [{script, timeout, if?, ...}]}``. This
    reconstructs the flat ``{script, event, matcher?, timeout?, if?}`` entries
    the rest of this file consumes. Each hook entry preserves a ``script`` key
    precisely so this needs nothing from the plugin-only ``command`` field.
    """
    if not MANIFEST.is_file():
        sys.exit(f"FATAL: manifest not found at {MANIFEST}")
    try:
        data = json.loads(MANIFEST.read_text())
    except json.JSONDecodeError as exc:
        sys.exit(f"FATAL: {MANIFEST} is not valid JSON: {exc}")
    hooks = data.get("hooks")
    if not isinstance(hooks, dict) or not hooks:
        sys.exit(f"FATAL: {MANIFEST} declares no hooks, or `hooks` is not the "
                 "native object-keyed-by-event schema")
    entries: list[dict] = []
    for event, groups in hooks.items():
        for group in groups:
            matcher = group.get("matcher")
            for hook in group.get("hooks", []):
                script = hook.get("script")
                if not script:
                    sys.exit(f"FATAL: a {event} hook entry in {MANIFEST} has no "
                             "`script` key; install-hooks.py needs it to build "
                             "the settings.json command.")
                entry = {"script": script, "event": event}
                if matcher:
                    entry["matcher"] = matcher
                if hook.get("timeout"):
                    entry["timeout"] = hook["timeout"]
                if hook.get("if"):
                    entry["if"] = hook["if"]
                entries.append(entry)
    if not entries:
        sys.exit(f"FATAL: {MANIFEST} declares no hooks")
    return entries


def load_settings(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        # a malformed settings.json silently disables EVERY setting in it, so
        # this must abort rather than be repaired blind
        sys.exit(f"FATAL: {path} is not valid JSON ({exc}). Fix it by hand "
                 "first -- a broken settings.json disables all of its settings.")


def command_for(entry: dict) -> str:
    """The command string as it appears in settings.json.

    Uses `$HOME/.claude` when that is where the hooks actually live, so the
    same settings.json works on every machine this repo is installed on. When
    CLAUDE_HOME points somewhere else, emit that literal path instead --
    writing `$HOME/.claude` there would register a command that does not exist.
    """
    default = Path.home() / ".claude"
    cdir = claude_dir()
    base = "$HOME/.claude" if cdir.resolve() == default.resolve() else str(cdir)
    rel = f'"{base}/hooks/{entry["script"]}"'
    return rel if entry["script"].endswith(".sh") else f"python3 {rel}"


def enabled_ai_config_plugin(settings: dict) -> str | None:
    """Return the name of an enabled ai-config plugin in this settings.json.

    The plugin loader reads `hooks/hooks.json` directly whenever the plugin is
    enabled, so registering the same hooks here as well double-registers every
    one: the two paths carry different command strings
    (`${CLAUDE_PLUGIN_ROOT}/...` vs `$HOME/.claude/...`), so Claude Code keeps
    both and each hook fires twice.

    Best-effort by design: this inspects only the settings.json this script
    reads, so it catches the common case (plugin enabled in the same file) and
    can miss a project-level enablement. It has no false positives. The
    matching itself lives in `scripts/lib/plugin_overlap.py`; the README
    caveat covers what this cannot see.
    """
    enabled = enabled_ai_config_plugins(settings)
    return enabled[0] if enabled else None


def find_entry(settings: dict, entry: dict) -> dict | None:
    for group in settings.get("hooks", {}).get(entry["event"], []):
        if entry.get("matcher") and group.get("matcher") != entry["matcher"]:
            continue
        for hook in group.get("hooks", []):
            if entry["script"] in hook.get("command", ""):
                return hook
    return None


def classify(settings: dict, entry: dict, hooks_dir: Path) -> str:
    found = find_entry(settings, entry)
    if found is None:
        return "missing"
    if not (hooks_dir / entry["script"]).exists():
        return "stale"
    return "registered"


def add_entry(settings: dict, entry: dict) -> None:
    hook = {"type": "command", "command": command_for(entry)}
    if entry.get("if"):
        hook["if"] = entry["if"]
    if entry.get("timeout"):
        hook["timeout"] = entry["timeout"]

    groups = settings.setdefault("hooks", {}).setdefault(entry["event"], [])
    want_matcher = entry.get("matcher")
    for group in groups:
        if group.get("matcher") == want_matcher:
            group.setdefault("hooks", []).append(hook)   # preserve siblings
            return
    new = {"hooks": [hook]}
    if want_matcher:
        new["matcher"] = want_matcher
    groups.append(new)


def settings_files(cdir: Path) -> list[Path]:
    """The settings files the harness merges, in the order it reads them."""
    return [p for p in (cdir / "settings.json", cdir / "settings.local.json")
            if p.is_file()]


def check_registered_paths() -> int:
    """Report every registered hook whose script path does not resolve.

    Reads the settings files rather than the manifest, so it also sees hooks
    this repo does not ship -- which is the point: the outage is caused by the
    binding, whoever wrote it.
    """
    cdir = claude_dir()
    files = settings_files(cdir)
    if not files:
        print(f"FATAL: no settings.json or settings.local.json under {cdir}, "
              "so nothing is registered and every guard in this corpus is "
              "inert. This is the zero case, not a clean one.")
        return 1

    rows = []
    for path in files:
        for row in check_settings(load_settings(path)):
            row["settings"] = path
            rows.append(row)

    for row in rows:
        if row["status"] != "missing":
            continue
        where = f"{row['event']}/{row['matcher']}" if row["matcher"] else row["event"]
        print(f"  MISSING  {row['path']}")
        print(f"           registered on {where} in {row['settings']}")

    counts = {s: sum(1 for r in rows if r["status"] == s)
              for s in ("ok", "missing", "skipped")}
    print()
    print(f"examined {len(rows)} registered hook command(s) in "
          + ", ".join(str(p) for p in files))
    print(f"  ok={counts['ok']} missing={counts['missing']} "
          f"skipped={counts['skipped']}")
    if not counts["missing"]:
        print()
        print("Every registered hook path resolves.")
        return 0
    print()
    print("A registered path that does not resolve is not an inert guard:")
    print("python3 exits 2 on a file it cannot open, and exit 2 is the")
    print("PreToolUse deny signal, so each line above denies every tool call")
    print("its matcher names. Fix the install or drop the binding; see")
    print("ai-config#2392.")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fix", action="store_true",
                    help="register the missing hooks (backs settings.json up first)")
    ap.add_argument("--check", action="store_true",
                    help="verify every registered hook path resolves, and exit "
                         "non-zero naming the ones that do not")
    args = ap.parse_args()

    if args.check:
        return check_registered_paths()

    entries = load_manifest()
    cdir = claude_dir()
    settings_path = cdir / "settings.json"
    settings = load_settings(settings_path)
    if (plugin := enabled_ai_config_plugin(settings)):
        print(f"WARNING: the '{plugin}' plugin is enabled in {settings_path}; it\n"
              "  already loads these hooks directly. Registering them here too "
              "makes every\n  hook fire twice -- the plugin and settings.json "
              "paths carry different command\n  strings, so Claude Code keeps "
              "both. Use one path, not both (see README).\n")
    hooks_dir = cdir / "hooks"

    rows = [(e, classify(settings, e, hooks_dir)) for e in entries]
    width = max(len(e["script"]) for e in entries)
    for entry, status in rows:
        mark = {"registered": "ok", "missing": "MISSING", "stale": "STALE"}[status]
        print(f"  {mark:<9} {entry['script']:<{width}}  {entry['event']}")

    counts = {s: sum(1 for _, st in rows if st == s)
              for s in ("registered", "missing", "stale")}
    print(f"\nexamined {len(rows)} hook(s) declared in hooks/hooks.json against "
          f"{settings_path}")
    print(f"  registered={counts['registered']} missing={counts['missing']} "
          f"stale={counts['stale']}")

    if not (counts["missing"] or counts["stale"]):
        print("\nAll hooks registered.")
        return 0

    if not args.fix:
        print("\nRe-run with --fix to register the missing hooks.")
        print("Note --fix only edits settings.json and never places the "
              "scripts themselves. On a fresh machine, install the Claude "
              "Code plugin instead (it registers the full catalog with no "
              "separate step); this path only helps if ~/.claude/hooks "
              "already holds the scripts some other way.")
        return 1

    backup = settings_path.with_suffix(f".json.bak-{int(time.time())}")
    if settings_path.is_file():
        shutil.copy2(settings_path, backup)
        print(f"\nbacked up {settings_path} -> {backup}")
    else:
        settings_path.parent.mkdir(parents=True, exist_ok=True)

    added = 0
    for entry, status in rows:
        if status == "missing":
            script = hooks_dir / entry["script"]
            if not script.exists():
                print(f"  REFUSED {entry['script']} -- no script at {script}.")
                print("          Registering it would deny every tool call its "
                      "matcher names,")
                print("          since python3 exits 2 on a missing file and "
                      "exit 2 is the")
                print("          PreToolUse deny signal (#2392).")
                continue
            add_entry(settings, entry)
            added += 1
            print(f"  registered {entry['script']} on {entry['event']}")
        elif status == "stale":
            print(f"  STALE {entry['script']} names a path that does not exist "
                  "-- left alone; fix the install, not settings.json")

    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    print(f"\nadded {added} hook(s) to {settings_path}")
    print("Hooks connect at session start -- restart before expecting them to run.")
    # a stale entry is still broken after --fix, and --fix deliberately does not
    # touch it, so it must keep the exit code non-zero. Without the stale term
    # a stale-only run returns 0 == 0 and reports success over broken hooks --
    # the pass-path-equals-failure-path shape this file's own docstring cites.
    return 0 if added == counts["missing"] and counts["stale"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
