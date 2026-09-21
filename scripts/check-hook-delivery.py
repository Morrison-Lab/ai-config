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
It does not decide which cache pin is ACTIVE. That is chosen by the harness
from `settings.json` and is not reliably derivable here, so reporting a pin
as "the" one would be a guess presented as a finding. It reports every pin it
finds and says what each is missing, leaving the reader to recognise a pin
that is behind.

It also does not fetch. It compares the working checkout against installed
pins, so a checkout that is itself behind `origin/main` reports fewer missing
hooks than really are -- which is why the summary prints the checkout's own
position against `origin/main` when git can answer cheaply.

EXIT STATUS
-----------
0   every pin carries every hook in the checkout (or no pins were found,
    which is not a failure -- a machine may legitimately have no plugin
    install)
1   at least one pin is missing at least one hook
"""

import argparse
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
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    have = repo_hooks(repo)
    pins = cache_roots()

    print(f"checkout: {repo}")
    print(f"  {len(have)} hook script(s); {checkout_position(repo)}")

    if not pins:
        print("\nNo installed plugin cache found for Morrison-Lab/ai-config.")
        print("Not a failure: this machine may have no plugin install.")
        return 0

    worst = 0
    for pin in pins:
        installed = {p.name for p in (pin / "hooks").iterdir()
                     if p.suffix in (".py", ".sh") and not p.name.startswith("test-")}
        missing = sorted(have - installed)
        extra = sorted(installed - have)
        print(f"\npin {pin.name}  ({len(installed)} installed)")
        if missing:
            worst = 1
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

    print(f"\ncompared {len(have)} checkout hook(s) against {len(pins)} pin(s)")
    if worst:
        print("At least one pin is missing a hook that exists in the checkout.")
        print("A guard that is not installed cannot fire, and reports nothing "
              "when it does not (ai-config#2439).")
    return worst


if __name__ == "__main__":
    sys.exit(main())
