#!/usr/bin/env python3
"""Check that this repo's hooks are registered with the harness, and repair it.

`bootstrap.sh` symlinks every top-level directory into `~/.claude`, so
`hooks/` lands there with no bootstrap change at all. That gets the *scripts*
onto the machine and stops there: a hook only runs once it is named in
`~/.claude/settings.json`, and bootstrap is a pure symlinker that deliberately
never edits that file. Editing a user's harness config as a side effect of
installing skills is the same objection that kept `git config --global
fetch.prune` out of bootstrap (ai-config#901).

So registration is explicit and opt-in, and lives here rather than in
bootstrap. `scripts/check-install.py` is the sibling for the other half: it
decides whether the installed *files* match the repo, and knows nothing about
`settings.json`.

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
touches a hook it did not add.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "hooks" / "hooks.json"


def claude_dir() -> Path:
    return Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))


def load_manifest() -> list[dict]:
    if not MANIFEST.is_file():
        sys.exit(f"FATAL: manifest not found at {MANIFEST}")
    try:
        data = json.loads(MANIFEST.read_text())
    except json.JSONDecodeError as exc:
        sys.exit(f"FATAL: {MANIFEST} is not valid JSON: {exc}")
    entries = data.get("hooks")
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

    Uses $HOME rather than an absolute path so the same settings.json works on
    every machine this repo is installed on.
    """
    rel = f'"$HOME/.claude/hooks/{entry["script"]}"'
    return rel if entry["script"].endswith(".sh") else f"python3 {rel}"


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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fix", action="store_true",
                    help="register the missing hooks (backs settings.json up first)")
    args = ap.parse_args()

    entries = load_manifest()
    cdir = claude_dir()
    settings_path = cdir / "settings.json"
    settings = load_settings(settings_path)
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
        print("Note --fix only edits settings.json. The scripts themselves are "
              "placed by bootstrap.sh; run scripts/check-install.py --fix if "
              "~/.claude/hooks holds real copies instead of symlinks.")
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
            add_entry(settings, entry)
            added += 1
            print(f"  registered {entry['script']} on {entry['event']}")
        elif status == "stale":
            print(f"  STALE {entry['script']} names a path that does not exist "
                  "-- left alone; fix the install, not settings.json")

    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    print(f"\nadded {added} hook(s) to {settings_path}")
    print("Hooks connect at session start -- restart before expecting them to run.")
    return 0 if added == counts["missing"] else 1


if __name__ == "__main__":
    sys.exit(main())
