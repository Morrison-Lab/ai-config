#!/usr/bin/env python3
"""PreToolUse guard: dispatching a write-capable agent at a dirty worktree.

## The incident

2026-09-07. A round of review findings was fixed in the working tree,
verified, and not committed. An `adversarial-reviewer` was then dispatched
against that worktree, with a brief permitting it to mutate files provided
it restored them. It found the uncommitted changes, read them as stray, and
ran `git checkout -- .`.

The fixes were gone. The next round reported the same findings again, plus a
third: the commit message now claimed a fix its own tree no longer had.

The reviewer behaved reasonably. `git checkout -- .` is the obvious way to
undo scratch edits, and nothing distinguished the orchestrator's uncommitted
work from the agent's own.

## Why a hook rather than a rule

`CLAUDE.md`'s "Subagent worktrees are assigned" section governs which
worktree an agent gets, and `memories/git-worktrees.md` covers checking an
agent's liveness before touching its worktree. Neither covers the reverse:
handing a write-capable agent a tree that already holds your own uncommitted
work.

"Commit before dispatching" is also the shape a rule cannot reach. It is
read at some other moment, and broken at the moment of dispatch, when the
edits feel finished because they are verified.

## The match condition

  M1  the tool is `Agent` or `Task` -- the harness reports a subagent
      dispatch under either name, and registering for only one is a false
      negative that `remind-brief-premises.py` already had and fixed
  M2  the launch is write-capable: `isolation` is not `worktree` (which
      hands the agent a fresh tree of its own) and the prompt does not
      declare the agent read-only
  M3  a candidate path is dirty. Candidates are the session cwd and every
      absolute path named in the prompt -- the second matters because a
      cross-repo dispatch identifies its target that way, and the dispatch
      that lost work named a worktree in a DIFFERENT repository from the
      cwd, which a cwd-only check would have missed.

## Why this warns rather than blocks

Handing an agent a dirty tree is legitimate and common: asking one to review
an uncommitted patch is exactly that, and this corpus's own `ardia` step 2
has workers emit uncommitted patch files by design. A blocking form would
refuse correct work and be switched off, per README's "A hook that misfires
is worse than a missing one".
"""
import json
import os
import re
import subprocess
import sys

# An absolute POSIX path in the prompt. Trailing punctuation is trimmed so a
# path at the end of a sentence still resolves.
RX_ABS_PATH = re.compile(r"(/(?:[\w.@+-]+/)+[\w.@+-]*)")

# Phrases by which a brief declares the agent must not write AT ALL. Matched
# on the prompt, because the tool input carries no capability field a hook
# can read.
#
# Every entry is UNSCOPEABLE on purpose. A bare `do not edit` was here and
# had to go: it matches "do not edit the tests, only the source", a common
# way to narrow what an agent may touch, and reading that as fully read-only
# silenced the guard on exactly the write-capable dispatch it exists for.
# The phrases kept either stand alone (`read-only`) or carry their own
# universal object (`anything`, `any files`, `no changes`).
RX_READ_ONLY = re.compile(
    r"read-only"
    r"|read only"
    r"|do(?:es)? not (?:edit|modify|write|change) any(?:thing| files?)?\b"
    r"|don't (?:edit|modify|write|change) any(?:thing| files?)?\b"
    r"|make no changes"
    r"|without editing any",
    re.I)


def _dirty(path):
    """TRACKED uncommitted changes in `path`, or None when it is not a repo.

    Untracked (`??`) entries are excluded, and the reason is the warning's
    own argument rather than noise-reduction alone: `git checkout -- .`, the
    command that caused the incident, does not touch untracked files at all.
    Warning about a stray `.DS_Store` or a log file would make a claim about
    a destructive command that cannot destroy the thing that triggered it,
    on a very large fraction of ordinary dispatches.

    A `git clean -fd` would destroy untracked work, so this is a real gap
    rather than a non-issue -- but it is a different command with a
    different narrative, and firing on every repo with a stray file is the
    reliable way to get a guard switched off.
    """
    if not os.path.isdir(path):
        return None
    try:
        r = subprocess.run(
            ["git", "-C", path, "status", "--porcelain"],
            capture_output=True, text=True, timeout=STATUS_TIMEOUT_S)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    return [L for L in r.stdout.splitlines()
            if L.strip() and not L.startswith("??")]


# A prompt naming many real repositories would otherwise cost one `git
# status` each, and the hook's own registered budget in hooks.json is 10s.
# The product of these two must stay UNDER that: at 6 candidates x 3s the
# worst case was 18s, so the hook could be killed mid-check and warn about
# nothing -- reintroducing by timeout the silence the cap was added to
# prevent. 3 x 2 = 6s leaves headroom. Missing a warning because the hook
# died is strictly worse than missing the fourth candidate.
# The tool names a subagent dispatch arrives under. See main().
DISPATCH_TOOLS = {"Agent", "Task"}

MAX_CANDIDATES = 3
STATUS_TIMEOUT_S = 2


def candidates(prompt, cwd):
    """Directories this dispatch might hand the agent, nearest first.

    The prompt's paths come first: a cross-repo dispatch names its target
    there, and that is the case a cwd-only check misses.
    """
    out = []
    for m in RX_ABS_PATH.finditer(prompt or ""):
        p = m.group(1).rstrip("/.,;:)\"'`")
        if os.path.isdir(p) and p not in out:
            out.append(p)
    if cwd and os.path.isdir(cwd) and cwd not in out:
        out.append(cwd)
    return out[:MAX_CANDIDATES]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    # Both names, because the harness reports a subagent dispatch either
    # way. `no-fable-subagent.py` and `remind-brief-premises.py` register
    # for both for the same reason, and the latter's own source records
    # Agent-only as a bug it already had: "which meant the Task branch above
    # had never been reachable". Registering for one name is a false
    # negative on the very event this guards.
    if payload.get("tool_name") not in DISPATCH_TOOLS:
        return 0
    ti = payload.get("tool_input")
    if not isinstance(ti, dict):
        return 0

    # ANY isolation value exempts. `worktree` hands the agent a fresh tree
    # of its own and `remote` runs it elsewhere entirely, so in neither case
    # is the orchestrator's uncommitted work reachable. Keying on the
    # specific string `worktree` meant a remote launch drew a warning about
    # a local path it can never touch -- a spurious warning, which is how a
    # guard gets switched off.
    if str(ti.get("isolation") or "").strip():
        return 0

    prompt = str(ti.get("prompt") or "")
    if RX_READ_ONLY.search(prompt):
        return 0

    cwd = payload.get("cwd") or os.getcwd()
    for path in candidates(prompt, cwd):
        lines = _dirty(path)
        if not lines:
            continue
        shown = "\n".join("      " + L for L in lines[:6])
        more = "" if len(lines) <= 6 else f"\n      ... and {len(lines) - 6} more"
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": (
                    "[flag-dispatch-over-uncommitted] This dispatch can write, "
                    f"and {path} holds uncommitted work:\n\n{shown}{more}\n\n"
                    "An agent told it may edit files cannot tell your "
                    "uncommitted changes from its own scratch edits. A review "
                    "agent that was permitted to mutate files 'provided it "
                    "restores them' resolved that by running "
                    "`git checkout -- .`, which destroyed a round of verified "
                    "fixes; the next round then reported them as still "
                    "outstanding, plus a commit message claiming a fix its "
                    "tree no longer had.\n"
                    "Commit first if this work should survive the dispatch. A "
                    "commit is cheap and a lost tree is not.\n"
                    "Disregard this when the dirty tree IS the subject -- "
                    "asking an agent to review an uncommitted patch is exactly "
                    "that, and is why this warns rather than blocks."
                ),
            }
        }))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
