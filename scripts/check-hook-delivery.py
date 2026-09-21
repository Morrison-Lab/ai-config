#!/usr/bin/env python3
"""Report hooks that exist in this repository but are MISSING from the installed plugin.

WHY THIS EXISTS (ai-config#2439, measured 2026-09-21)
------------------------------------------------------
`hooks/no-binary-file-read.py` merged at 07:33. About one hour and forty
minutes later, a session in this very repository ran `cat` on a Windows
executable and dumped megabytes of machine code into its context -- the exact
mistake that guard was written to prevent. The guard never fired: the file was
on `main`, absent from the working checkout, and absent from every plugin
cache pin. The cache is what actually executes hooks.

**A stale guard is worse than a stale fix, and that is the argument for this
script.** A fix that does not reach a consumer shows up as a bug recurring,
which somebody notices. A guard that does not reach a consumer shows up as
NOTHING: no warning, no error, and the session cannot tell "the guard passed
me" from "the guard was never installed". Its whole value is firing at the
moment of the mistake, so a delivery lag does not degrade it -- it nullifies
it for that window, silently.

WHAT IT ANSWERS
---------------
One question the existing instruments do not:

    which merged hooks is this machine missing?

`install-hooks.py` reports REGISTRATION (is a hook bound to an event), and
`check-hook-catalog.py` checks the README/registration pairing. Both operate
on the repository's own files. Neither compares what is installed against
what exists, so a hook can be correctly written, correctly registered, and
still absent from the thing that runs it.

WHAT IT DELIBERATELY DOES NOT DO
---------------------------------
It does not name a single ACTIVE pin, and an earlier draft of this paragraph
said the active pin was "not reliably derivable here". That was wrong, and
`shared/workflow/keep-checkouts-fresh.md` already documents the derivation:
`~/.claude/plugins/installed_plugins.json` records one entry per install,
each carrying a `scope`, a `projectPath` for a project-scoped one, and the
`installPath` of the pin it is served from. Those install paths are read and
each enumerated pin is labelled INSTALLED with the scopes and projects that
name it, with the entry matching `--project` called out first.

What remains genuinely underivable is narrower: which of several matching
entries the harness prefers when a project-scoped and a user-scoped install
both apply. So the labels report what the file records rather than asserting
one pin executes, and a pin no entry names is labelled as an orphan -- a
garbage-collectable snapshot rather than something to act on. That
distinction is the whole point: reading the newest directory under the cache
identifies nothing, because several pins routinely carry the same commit.

It also does not fetch. It compares the working checkout against installed
pins, so a checkout that is itself behind `origin/main` reports fewer missing
hooks than really are -- which is why the summary prints the checkout's own
position against `origin/main` when git can answer cheaply.

EXIT STATUS
-----------
0   every pin an install record names carries every hook in the checkout
    (or no pins were found, which is not a failure -- a machine may
    legitimately have no plugin install)
1   at least one NAMED pin is missing at least one hook

A gap in an ORPHAN pin -- one no install record names -- is reported and does
not set the status. Such a pin is a garbage-collectable leftover, so failing
on it would make the instrument red on machines where nothing is wrong, which
is the fastest way to get a check ignored.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def repo_hooks(repo):
    """Hook scripts in the checkout, excluding tests and helpers."""
    d = repo / "hooks"
    if not d.is_dir():
        return set()
    out = set()
    for p in sorted(d.iterdir()):
        if p.suffix not in (".py", ".sh"):
            continue
        if p.name.startswith("test-"):
            continue
        out.add(p.name)
    return out


def cache_roots():
    """Installed plugin cache directories for this marketplace, newest first."""
    base = Path.home() / ".claude" / "plugins" / "cache" / "Morrison-Lab" / "ai-config"
    if not base.is_dir():
        return []
    pins = [p for p in base.iterdir() if (p / "hooks").is_dir()]
    pins.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return pins


def install_entries():
    """Installed-plugin records for this marketplace, or [] if unreadable.

    `~/.claude/plugins/installed_plugins.json` is the harness's own record of
    what it installed and from where. Reading it is what turns a list of cache
    directories into an answer about the pin a session is actually served,
    which is the question ai-config#2439 posed and could not answer by hand.
    """
    path = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return []
    plugins = data.get("plugins")
    if not isinstance(plugins, dict):
        return []
    out = []
    for key, entries in plugins.items():
        if "ai-config" not in key:
            continue
        for e in entries or []:
            if isinstance(e, dict) and e.get("installPath"):
                out.append(e)
    return out


def entries_for(pin, entries):
    """The install records naming this pin, exactly as the harness wrote them.

    Matching is on the resolved path rather than the string, because the
    record carries a Windows path with backslashes while `pin` comes from a
    directory walk.
    """
    try:
        target = pin.resolve()
    except Exception:
        target = pin
    out = []
    for e in entries:
        try:
            if Path(e["installPath"]).resolve() == target:
                out.append(e)
        except Exception:
            continue
    return out


def describe_entries(entries, project):
    """One label per pin: which scopes and projects the harness serves from it."""
    if not entries:
        return "ORPHAN -- no install record names this pin"
    mine = [e for e in entries
            if e.get("projectPath") and _same_path(e["projectPath"], project)]
    user = [e for e in entries if e.get("scope") == "user"]
    bits = []
    if mine:
        bits.append("INSTALLED for THIS project")
    if user:
        bits.append("INSTALLED at user scope")
    others = len(entries) - len(mine) - len(user)
    if others > 0:
        bits.append(f"{others} other project install(s)")
    return "; ".join(bits) if bits else f"{len(entries)} install record(s)"


def _same_path(a, b):
    try:
        return Path(a).resolve() == Path(b).resolve()
    except Exception:
        return False


def checkout_position(repo):
    """'behind N' against origin/main, or a note saying it could not be read."""
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "rev-list", "--count", "HEAD..origin/main"],
            capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return "position vs origin/main: unknown (git returned nonzero)"
        n = r.stdout.strip()
        if n == "0":
            return "checkout is level with origin/main"
        return (f"checkout is BEHIND origin/main by {n} commit(s) -- "
                f"hooks merged since are invisible to this comparison")
    except Exception:
        return "position vs origin/main: unknown (git unavailable)"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=str(REPO),
                    help="repository checkout to compare against")
    ap.add_argument("--project", default=os.getcwd(),
                    help="project path whose install record to call out "
                         "(default: the current directory)")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    have = repo_hooks(repo)
    pins = cache_roots()
    entries = install_entries()

    print(f"checkout: {repo}")
    print(f"  {len(have)} hook script(s); {checkout_position(repo)}")

    if not pins:
        print("\nNo installed plugin cache found for Morrison-Lab/ai-config.")
        print("Not a failure: this machine may have no plugin install.")
        return 0

    worst = 0
    orphan_gaps = 0
    named = 0
    for pin in pins:
        installed = {p.name for p in (pin / "hooks").iterdir()
                     if p.suffix in (".py", ".sh") and not p.name.startswith("test-")}
        missing = sorted(have - installed)
        extra = sorted(installed - have)
        records = entries_for(pin, entries)
        named += 1 if records else 0
        label = describe_entries(records, args.project)
        print(f"\npin {pin.name}  ({len(installed)} installed) -- {label}")
        if missing:
            if records:
                worst = 1
            else:
                orphan_gaps += 1
            print(f"  MISSING {len(missing)} hook(s) present in the checkout:")
            for m in missing:
                print(f"    - {m}")
        else:
            print("  carries every hook in the checkout")
        if extra:
            # Not a failure: a pin legitimately predates a removal, and a
            # hook deleted in the checkout is expected to linger in an older
            # pin. Reported so the direction of the gap is visible.
            print(f"  {len(extra)} hook(s) installed but absent from the "
                  f"checkout (older pin, or removed since):")
            for e in extra[:5]:
                print(f"    - {e}")
            if len(extra) > 5:
                print(f"    ... and {len(extra) - 5} more")

    print(f"\ncompared {len(have)} checkout hook(s) against {len(pins)} pin(s), "
          f"{named} of them named by an install record")
    if not entries:
        print("No install records were readable, so every pin above is "
              "labelled ORPHAN on absence of evidence rather than evidence of "
              "absence. Re-run after checking "
              "~/.claude/plugins/installed_plugins.json exists.")
    if worst:
        print("At least one INSTALLED pin is missing a hook that exists in "
              "the checkout.")
        print("A guard that is not installed cannot fire, and reports nothing "
              "when it does not (ai-config#2439).")
    if orphan_gaps:
        print(f"{orphan_gaps} orphan pin(s) are also missing hooks. Not "
              "counted: no install record serves them.")
    return worst


if __name__ == "__main__":
    sys.exit(main())
