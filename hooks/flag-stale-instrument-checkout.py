#!/usr/bin/env python3
"""PreToolUse warning: an ai-config instrument invoked from a stale checkout.

A repo script consulted to DECIDE something -- `check-pr-fully-clean.py` most
of all -- answers from whatever version happens to be on disk. A clone left on
a detached HEAD, or on a branch nobody fast-forwarded, keeps running it
successfully forever, and nothing in the output names a version.

WHY THIS IS WORTH A GUARD
-------------------------
A stale reading is not merely wrong, it is INDISTINGUISHABLE from the failure
mode the corpus already documents. `fully-clean.md` records that the checker
can report NOT clean over a clean verdict when a review's prose merely
discusses finding vocabulary, and prescribes reading the matched words in
context. A stale checker produces that same output -- so the documented remedy
runs, the words really are innocuous, and the check CONFIRMS the wrong
conclusion. There is no reading of the output that separates the two.

Nor is there a safe direction to guess. Measured 2026-09-02 across three PRs:
the newer checker was STRICTER on one and looser on two, so "my copy is old"
predicts nothing about which way a reading is wrong.

WHY IT WARNS RATHER THAN BLOCKS
-------------------------------
Being behind `origin/main` is not itself an error. A session may be pinned to
an older revision deliberately, may be offline, or may be reading a PR where
the answer does not decide anything. Blocking a read-only diagnostic over a
condition that is usually harmless is how a guard gets switched off, taking
the real cases with it. So this only ever adds a warning line.

It also never fetches. A hook must not make a network call on the critical
path of a tool invocation, so the comparison uses the remote-tracking ref as
it already stands. That makes a false NEGATIVE possible -- a clone whose
`origin/main` is itself stale looks current -- which is the safe direction,
and the message says to fetch.

Fails OPEN and SILENT: any trouble at all prints nothing.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

# Scripts whose answer decides something. A script merely being run is not
# interesting; being run to settle a question is. Keep this list short --
# every addition is a chance to warn about something nobody was deciding on.
DECIDING_SCRIPTS = (
    "check-pr-fully-clean.py",
    "check-links.py",
    "pr-overlap.py",
    "pr-sweep.py",
    "check-context-closure.py",
    "check-stale-records.py",
)


def _git(repo, *args):
    """git in `repo`, or None on any trouble."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def _script_paths(command):
    """Every DECIDING_SCRIPTS path the command line names."""
    found = []
    for name in DECIDING_SCRIPTS:
        # A bare name with no directory tells us nothing about which checkout
        # it came from, so only a path-bearing invocation is actionable.
        for m in re.finditer(r"(\S*/)" + re.escape(name), command):
            found.append(m.group(0))
    return found


def _repo_root(path_str):
    p = Path(path_str).expanduser()
    # The script need not exist (a typo, a not-yet-created file); resolve the
    # nearest existing ancestor instead of giving up.
    for cand in [p.parent, *p.parent.parents]:
        if cand.exists():
            root = _git(cand, "rev-parse", "--show-toplevel")
            return Path(root) if root else None
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not isinstance(command, str) or not command:
        return 0

    seen = set()
    for script_path in _script_paths(command):
        root = _repo_root(script_path)
        if root is None or str(root) in seen:
            continue
        seen.add(str(root))

        # The default branch, derived rather than assumed: a repo whose
        # default is not `main` would otherwise produce a bogus warning.
        head_ref = _git(root, "symbolic-ref", "-q", "refs/remotes/origin/HEAD")
        default = head_ref.rsplit("/", 1)[-1] if head_ref else "main"
        remote = f"origin/{default}"

        if _git(root, "rev-parse", "--verify", "-q", remote) is None:
            continue

        behind = _git(root, "rev-list", "--count", f"HEAD..{remote}")
        if behind is None or behind == "0":
            continue

        name = Path(script_path).name
        print(
            f"The instrument `{name}` is being run from a checkout that is "
            f"{behind} commit(s) behind {remote}.\n\n"
            f"    checkout: {root}\n\n"
            "A stale instrument's output is INDISTINGUISHABLE from the "
            "vocabulary false positive `shared/workflow/fully-clean.md` "
            "documents: the matched words really are innocuous in context, so "
            "reading them confirms the wrong conclusion. And there is no safe "
            "direction to guess -- measured 2026-09-02, the newer checker was "
            "stricter on one PR and looser on two.\n\n"
            "If this answer will decide anything -- a merge, a status report, "
            "a claim that a finding is a false positive -- take the reading "
            "from a worktree that cannot be stale:\n\n"
            f"    git -C {root} fetch origin -q\n"
            f"    git -C {root} worktree add --detach /tmp/aic-now {remote}\n"
            f"    python3 /tmp/aic-now/scripts/{name} <args>\n\n"
            "Run it from inside that worktree rather than copying the file "
            "out: it imports sibling modules, so a lone copy dies on "
            "ModuleNotFoundError.\n\n"
            "This is a reminder, not a refusal. Being behind is often fine.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
