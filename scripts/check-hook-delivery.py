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
2   `--repo` names a directory with no `hooks/` in it

A gap in an ORPHAN pin -- one the install records were READ and found not to
name -- is reported and does not set the status. Such a pin is a
garbage-collectable leftover, so failing on it would make the instrument red
on machines where nothing is wrong, which is the fastest way to get a check
ignored.

That downgrade is conditioned on the records having been readable, and the
condition is the load-bearing half. An unreadable file yields zero records
and would otherwise make every pin look orphaned, turning a completely broken
install into an exit 0 -- a regression this script shipped for one round and
which a test now pins. Where the file cannot be read, the labels are
advisory and any gap fails, exactly as before pins were labelled at all.

Status 2 exists for the same reason: a `--repo` with no `hooks/` used to
yield an empty set, which compares clean against every pin, so a typo'd path
reported success having examined nothing.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class NoHooksDir(Exception):
    """`--repo` names a directory with no `hooks/` in it.

    Raised rather than returned as an empty set, because an empty set compares
    clean against every pin: a typo'd `--repo`, or one aimed at the wrong
    worktree, otherwise reports success having examined nothing. A detector
    that cannot fail is the failure mode this script exists to report.
    """


def repo_hooks(repo):
    """Hook scripts in the checkout, excluding tests and helpers."""
    d = repo / "hooks"
    if not d.is_dir():
        raise NoHooksDir(str(d))
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
    """`(records, readable)` for this marketplace's installs.

    `~/.claude/plugins/installed_plugins.json` is the harness's own record of
    what it installed and from where. Reading it is what turns a list of cache
    directories into an answer about the pin a session is actually served,
    which is the question ai-config#2439 posed and could not answer by hand.

    The second element is the whole reason this returns a pair. An unreadable
    file and a file that genuinely names no pin both yield zero records, and
    they must not have the same consequence: labelling every pin ORPHAN on
    absence of evidence would downgrade every real gap to "not counted" and
    exit 0 on a completely broken install.
    """
    path = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return [], False
    plugins = data.get("plugins") if isinstance(data, dict) else None
    if not isinstance(plugins, dict):
        return [], False
    out = []
    for key, entries in plugins.items():
        if "ai-config" not in key:
            continue
        for e in entries or []:
            if isinstance(e, dict) and e.get("installPath"):
                out.append(e)
    return out, True


def entries_for(pin, entries, warn=None):
    """The install records naming this pin.

    Paths are resolved rather than compared as strings so the match does not
    depend on the harness having written `installPath` in canonical form --
    case, a trailing separator, or a `.` component would otherwise defeat it.
    On Windows both sides already render with backslashes, so separator style
    is NOT what this is for; an earlier comment here said it was, and that was
    wrong.

    A record that cannot be resolved is reported through `warn` rather than
    dropped silently, because a dropped record that was the only one naming
    this pin turns an INSTALLED pin into an ORPHAN -- which now suppresses a
    real failure instead of merely mislabelling it.
    """
    try:
        target = pin.resolve()
    except OSError:
        target = pin
    out = []
    for e in entries:
        try:
            if Path(e["installPath"]).resolve() == target:
                out.append(e)
        except OSError as exc:
            if warn:
                warn(f"  ! could not resolve installPath "
                     f"{e.get('installPath')!r}: {exc}")
    return out


def describe_entries(entries, project):
    """One label per pin: which scopes and projects the harness serves from it."""
    if not entries:
        return "ORPHAN -- no install record names this pin"
    mine = [e for e in entries
            if e.get("projectPath") and _same_path(e["projectPath"], project)]
    user = [e for e in entries if e.get("scope") == "user"]
    # The residual is computed as a set difference rather than by subtracting
    # two lengths. One record can satisfy both predicates -- a user-scoped
    # entry that also carries a matching `projectPath` -- and the arithmetic
    # form then counts it twice, hiding a genuinely different project's
    # install and, with enough overlap, going negative.
    claimed = [e for e in entries if e in mine or e in user]
    others = len(entries) - len(claimed)
    bits = []
    if mine:
        bits.append("INSTALLED for THIS project")
    if user:
        bits.append("INSTALLED at user scope")
    if others > 0:
        bits.append(f"{others} other project install(s)")
    return "; ".join(bits) if bits else f"{len(entries)} install record(s)"


def _same_path(a, b):
    try:
        return Path(a).resolve() == Path(b).resolve()
    except (OSError, TypeError, ValueError):
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
                    help="project path whose install record to call out. It "
                         "must EQUAL a registered projectPath, not merely sit "
                         "under one (default: the current directory)")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    try:
        have = repo_hooks(repo)
    except NoHooksDir as exc:
        print(f"no hooks directory at {exc}", file=sys.stderr)
        print("Nothing to compare: --repo must name an ai-config checkout.",
              file=sys.stderr)
        return 2
    pins = cache_roots()
    entries, readable = install_entries()

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
        warnings = []
        records = entries_for(pin, entries, warn=warnings.append)
        named += 1 if records else 0
        label = describe_entries(records, args.project)
        print(f"\npin {pin.name}  ({len(installed)} installed) -- {label}")
        for w in warnings:
            print(w)
        if missing:
            # An ORPHAN downgrade is only sound when the records were READ and
            # genuinely name no pin. Where they could not be read, every pin
            # looks orphaned, so the old unconditional rule stands and a gap
            # still fails.
            if records or not readable:
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
    if not readable:
        print("~/.claude/plugins/installed_plugins.json could not be read, so "
              "every pin above is labelled ORPHAN on absence of evidence "
              "rather than evidence of absence. Any gap therefore still "
              "fails, exactly as it did before pins were labelled at all.")
    elif not entries:
        print("The install records were read and name no ai-config pin at "
              "all, which is what an uninstalled plugin looks like.")
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
