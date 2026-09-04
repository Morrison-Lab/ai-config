#!/usr/bin/env python3
"""PreToolUse guard: surface a write-capable `Agent` launch with no `isolation`.

We decided that subagent worktrees are **assigned by the orchestrator** --
`isolation` set on the `Agent` call -- rather than left to each agent to
organize for itself. Then `isolation: "worktree"` reclaimed an agent's worktree
mid-run, and the parameter silently stopped being passed. No decision was made
to stop; the practice simply lapsed, and nothing reported it.

That is the whole reason this is a hook and not a sentence. The lapse changed
no artifact, so no review, test, or lint could see it: the omission lives in a
tool call, which is the one surface none of them inspect. It surfaced only when
the maintainer remembered the decision and asked about it.

What the lapse cost, once: 8 concurrent agents, 7 of which created their own
worktrees and 1 of which took the shared checkout, switched its branch away
from a PR branch being actively pushed to, and left uncommitted work there. A
commit then landed on the wrong PR's branch, so that PR's diff carried a
byte-identical copy of another PR's entire change; separating them took a
history rewrite and a force-push. Nothing failed at the time. The only signal
was `git worktree list`.

## Why this warns rather than denies

Measured over 121 real `Agent` launches in this machine's transcripts, 60 (49%)
are write-capable with no `isolation`. Denying half of all agent launches is
not a proportionate response to a visibility problem, and it would be wrong on
the merits besides:

  - Not every write-capable agent needs a worktree. A single agent editing a
    repo with no concurrent work is fine, and the decision that lapsed was
    "the orchestrator decides", not "everything is isolated".
  - A deny cannot tell "forgot" from "deliberately none", so it would force the
    parameter onto calls that correctly omit it, with no way to say so.
  - The failure being fixed is *invisibility*. A warning at the moment of the
    call fixes that completely. Blocking adds cost without adding visibility.

So this only ever ADDS context. There is no code path in it that denies,
escalates, or auto-approves -- in particular it never emits
`permissionDecision: "allow"`, which would BYPASS the normal permission prompt
and make the harness more permissive than it was without the hook.

Read the 49% as a measurement of the lapse, not a noise forecast: it is high
because the practice stopped, and it falls toward zero as the practice resumes.
It is still the number to weigh before activating this, since a check that
fires constantly trains everyone to ignore it.

## One narrow case now DENIES instead

2026-09-04: an `adversarial-reviewer` launch -- read-only by contract, still
Bash-capable -- ran with no isolation in a checkout that was mid-flight on a
feature branch, and its own git commands switched that checkout to its OWN
branch. A session's next `git commit` and `git push` both landed there
silently (see `flag-stale-branch-mutation.py`, filed against the same
incident). The WARN above did not stop this, because it never fired at all:
`adversarial-reviewer` is in `READ_ONLY` (see "Classifying write-capable"
below), so this exact launch shape is silently exempt from the warning by
design, not merely something an orchestrator talked itself past.

So the escalation below is scoped narrowly rather than by tightening the
WARN's exemption list, which would make it noisy on the common, safe case
(a self-review dispatch on a clean, on-default-branch checkout) that
`READ_ONLY` exists to keep quiet. DENY fires only when ALL of these hold at
launch time, checked live against the repository at the tool's own `cwd`:

  1. no `isolation`, and the launch is Bash-capable -- which, deliberately,
     means EVERY `Agent`/`invoke_subagent` launch this hook can see,
     `READ_ONLY` roles included. A read-only ROLE contract says nothing
     about Bash access, and the incident is the proof: reusing `READ_ONLY`
     here would exempt the exact launch type that caused it.
  2. the session's current branch is NOT the repository's resolved default
     branch (`git symbolic-ref refs/remotes/origin/HEAD`, falling back to
     `git remote show origin`; never a hard-coded `main`).
  3. the session has uncommitted changes to a TRACKED file, or commits on
     the current branch its upstream does not have -- something a stray
     checkout would actually strand.

On the default branch with a clean tree, there is nothing for a stray
checkout to strand, so that stays a WARN -- denying there would be the
misfire README already warns against. On a feature branch with real work in
progress, a branch switch under the session is silently destructive, and the
remedy costs one parameter (`isolation: "worktree"`), so DENY is warranted.

Every git read in the deny path fails toward NOT denying (a non-git `cwd`,
detached `HEAD`, an unresolved default branch, or any `git` error all skip
straight to the WARN above, unchanged) -- same "fail open" posture as the
rest of this hook, just narrowed to the one path that can refuse a launch.

`ALLOW_UNISOLATED_AGENT_LAUNCH=1`, set for the single approved launch (never
exported for the session -- see `no-fable-subagent.py`'s
`FABLE_SUBAGENT_OK=1`, the same convention), clears the deny and falls
through to the WARN above unchanged.

## Classifying write-capable

`subagent_type` is the only reliable signal in the payload; prompt text is not.
Two exemption bases, both contracts rather than tool inventories:
`Explore` and `Plan` are exempt because the harness defines them as read-only
**roles** (it grants neither `Edit`, `Write`, nor `NotebookEdit` to either),
and `adversarial-reviewer` is exempt on the repo-declared persona contract
(its `tools:` line omits Edit/Write, and read-only is instructed discipline
on a harness that over-grants -- ai-config#2281, #2276).
Everything else warns, `claude-code-guide` included.

Be precise about what that exemption rests on, because the shorter reason is
wrong and was stated here in an earlier revision. It is **not** tool
inventory. `Explore` and `Plan` are both granted `Bash`, so on a strict
can-this-touch-a-file test neither would qualify and the allowlist would be
empty. The exemption rests on the declared role contract, and `Bash` is the
hole in that contract --- which is the same heuristic the paragraph below
already owns, rather than a separate weakness.

A **missing** `subagent_type` warns too, and that case is real rather than
theoretical: 3 of the 121 records carry no `subagent_type` at all. Treating an
absent field as "unknown, skip" would have silently exempted every one of them,
which is the shape where a check's pass path and its examined-nothing path look
identical.

The allowlist is a heuristic and its failure direction is stated deliberately:
a project-defined agent named `Explore` that did have write tools would be
wrongly exempted. For a warn-only hook that costs a missed warning, never a
wrong block, which is the right direction for the error to run.

Fails OPEN on any parse trouble. A guard that breaks every agent launch when
its input is malformed costs more than the omission it reports.
"""
import json
import os
import subprocess
import sys

# The harness declares Explore and Plan as read-only ROLES; that contract, not
# their tool inventory, is what the exemption rests on. Both are granted Bash,
# so a strict can-this-touch-a-file test would exempt nothing. See "Classifying
# write-capable" above for why Bash is the hole in the contract rather than a
# separate weakness. Any other value -- and a missing value -- is treated as
# write-capable.
#
# adversarial-reviewer is exempt on the same kind of contract, declared by the
# repo rather than the harness: its persona omits Edit/Write from `tools:` and
# instructs read-only discipline where a harness still grants Write schemas
# (ai-config#2281). Every self-review dispatch is deliberately un-isolated --
# the reviewer reads a diff and returns a report -- so warning on each one
# trains the reader to ignore the warning (ai-config#2276). For a warn-only
# hook the cost runs the safe way: a missed warning on a harness that
# over-grants, never a wrong block.
READ_ONLY = {"Explore", "Plan", "adversarial-reviewer"}

NOTE = (
    "No `isolation` on this Agent launch, and `{subagent_type}` is write-capable.\n\n"
    "We decided subagent worktrees are ASSIGNED by the orchestrator rather than "
    "left to each agent. That practice lapsed once after an unrelated incident, "
    "and the lapse put a commit on the wrong PR's branch.\n\n"
    "Either pass `isolation: \"worktree\"`, or decide deliberately that this one "
    "does not need it and say so. Both are fine; leaving it unmarked is what is "
    "not.\n\n"
    "If you do assign one: brief the agent to stay inside its assigned worktree, "
    "and to push early. A pushed commit survives anything that happens to a "
    "working tree."
)


def _unisolated_subagent_types(payload):
    """Every subagent_type (or unspecified-marker) launched with no
    isolation, WITHOUT the READ_ONLY exemption applied -- the shared parse
    both `unassigned()` (WARN, READ_ONLY-exempt) and `_should_deny()` (DENY,
    deliberately NOT READ_ONLY-exempt -- see its own docstring) build on.

    `[]` means either the launch is isolated, or it is not an Agent-shaped
    launch at all; callers must not conflate the two with "nothing to warn
    or deny", since a caller checking write-capability still needs to know
    the launch happened.
    """
    tname = payload.get("tool_name")
    if tname not in ("Agent", "invoke_subagent"):
        return []

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return []

    if tname == "invoke_subagent":
        subagents = tool_input.get("Subagents")
        if isinstance(subagents, list) and subagents:
            out = []
            for sa in subagents:
                if not isinstance(sa, dict):
                    continue
                ws = sa.get("Workspace")
                if ws in ("branch", "share") or sa.get("isolation"):
                    continue
                stype = sa.get("TypeName") or sa.get("Role") or sa.get("subagent_type")
                out.append(stype or "(unspecified, defaults to write-capable)")
            return out
        ws = tool_input.get("Workspace")
        if ws in ("branch", "share") or tool_input.get("isolation"):
            return []
        stype = tool_input.get("TypeName") or tool_input.get("Role") or tool_input.get("subagent_type")
        return [stype or "(unspecified, defaults to write-capable)"]

    if tool_input.get("isolation"):
        return []

    subagent_type = tool_input.get("subagent_type")
    return [subagent_type or "(unspecified, defaults to write-capable)"]


def unassigned(payload):
    """Return the subagent_type to warn about, or None to stay silent."""
    tname = payload.get("tool_name")
    if tname not in ("Agent", "invoke_subagent"):
        return None

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None

    if tname == "invoke_subagent":
        subagents = tool_input.get("Subagents")
        if isinstance(subagents, list) and subagents:
            for sa in subagents:
                if isinstance(sa, dict):
                    ws = sa.get("Workspace")
                    if ws in ("branch", "share") or sa.get("isolation"):
                        continue
                    stype = sa.get("TypeName") or sa.get("Role") or sa.get("subagent_type")
                    if stype in READ_ONLY:
                        continue
                    return stype or "(unspecified, defaults to write-capable)"
            return None
        ws = tool_input.get("Workspace")
        if ws in ("branch", "share") or tool_input.get("isolation"):
            return None
        stype = tool_input.get("TypeName") or tool_input.get("Role") or tool_input.get("subagent_type")
        if stype in READ_ONLY:
            return None
        return stype or "(unspecified, defaults to write-capable)"

    if tool_input.get("isolation"):
        return None

    subagent_type = tool_input.get("subagent_type")
    if subagent_type in READ_ONLY:
        return None

    return subagent_type or "(unspecified, defaults to write-capable)"


# ------------------------------------------------------------------ escalation
#
# 2026-09-04: the WARN above fired -- silently exempted, in fact, since the
# launch was `adversarial-reviewer` and READ_ONLY exempts it entirely -- and
# the orchestrator reasoned "the agent is read-only, it makes no commits".
# That reasoning is wrong: a read-only ROLE (no Edit/Write grant, or
# instructed reviewer discipline) still gets Bash, which is the exact hole
# this module's own docstring already names, and the agent used it to run
# git commands that switched the shared checkout to its own branch mid-run.
#
# So this escalation deliberately does NOT reuse `unassigned()`'s READ_ONLY
# exemption -- `_unisolated_subagent_types()` above is the un-exempted parse
# for exactly that reason. Escalating a check that still exempts the
# incident's own launch type would fix nothing.
#
# DENY fires only on the narrow conjunction where a stray checkout is
# actually destructive: no isolation, off the repository's OWN default
# branch (resolved live, never hard-coded `main`), and either uncommitted
# tracked changes or commits the upstream does not have -- something for a
# switch to strand. On the default branch with a clean tree there is
# nothing to strand, so that stays a WARN, per the "misfires are worse than
# a missing hook" doctrine: DENY is reserved for the case a wrong guess
# actually destroys work.
#
# Every git read below fails toward NOT denying: a non-git cwd, a detached
# HEAD, an unresolved default branch, or a `git` invocation that errors all
# skip the deny path and fall through to the WARN above, unchanged from
# today. Denying on an uncertain read would be worse than the omission this
# guard exists to report.

OVERRIDE_ENV = "ALLOW_UNISOLATED_AGENT_LAUNCH"

DENY = (
    "This Agent launch has no `isolation`, `{subagent_type}` is Bash-capable "
    "(READ-ONLY ROLES ARE NOT EXEMPT HERE -- see below), the session is on "
    "`{branch}`, NOT the repository's default branch (`{default}`), and the "
    "session has {stranded} that a stray checkout would strand.\n\n"
    "2026-09-04: an `adversarial-reviewer` launch -- read-only by contract, "
    "still Bash-capable -- ran git commands that switched this exact checkout "
    "to its own branch mid-run, and the orchestrator's reasoning at the time "
    "(\"it's read-only, it makes no commits\") is precisely the reasoning "
    "this DENY exists to override: a read-only role can still run "
    "`git checkout`, and that is all it takes to strand work.\n\n"
    "On the default branch with a clean tree there would be nothing to "
    "strand, and this would only warn. Here there is.\n\n"
    "Pass `isolation: \"worktree\"` -- one parameter -- and brief the agent to "
    "stay inside its assigned worktree and never run `git checkout`/"
    "`git switch` in the primary checkout.\n\n"
    "If this specific launch is genuinely safe despite the above, set "
    f"`{OVERRIDE_ENV}=1` for THIS command only (never export it for the "
    "session) and say why."
)


def _git(cwd, args, timeout=8):
    try:
        out = subprocess.run(["git", "-C", cwd] + args, capture_output=True,
                             text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def _current_branch(cwd):
    """The checked-out branch, or None (detached HEAD, non-git cwd, or a
    failed read -- all three must fail toward NOT denying)."""
    out = _git(cwd, ["branch", "--show-current"])
    if out is None:
        return None
    branch = out.strip()
    return branch or None


def _default_branch(cwd):
    """The repository's OWN default branch, resolved live -- never `main`
    hard-coded, per `memories/preferences.md`'s measured
    `fatal: invalid reference: origin/main` failure on a repo whose default
    is named otherwise."""
    out = _git(cwd, ["symbolic-ref", "refs/remotes/origin/HEAD"])
    if out:
        ref = out.strip()
        prefix = "refs/remotes/origin/"
        if ref.startswith(prefix):
            return ref[len(prefix):]
    # Fallback for a clone where the local origin/HEAD ref was never set
    # (e.g. `git clone --single-branch`): ask the remote directly.
    out = _git(cwd, ["remote", "show", "origin"])
    if out:
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("HEAD branch:"):
                branch = line.split(":", 1)[1].strip()
                if branch and branch != "(unknown)":
                    return branch
    return None


def _has_dirty_tracked(cwd):
    """True when a TRACKED file has uncommitted changes (staged or not).
    Untracked files are excluded -- a stray checkout does not strand a file
    git has never committed."""
    out = _git(cwd, ["status", "--porcelain"])
    if out is None:
        return False
    for line in out.splitlines():
        if line and not line.startswith("??"):
            return True
    return False


def _has_unpushed_commits(cwd):
    """True when the current branch has commits its upstream lacks. False
    (not None) when there is no upstream at all -- an unconfigured upstream
    is a separate problem this hook does not adjudicate, and treating it as
    'unknown, don't deny' vs 'stranded, deny' is a judgment call the DENY
    path should not make on an ambiguous read."""
    out = _git(cwd, ["rev-list", "--count", "@{u}..HEAD"])
    if out is None:
        return False
    out = out.strip()
    return out.isdigit() and int(out) > 0


def _should_deny(payload, cwd):
    """Return the DENY message, or None to fall through to the WARN above."""
    if os.environ.get(OVERRIDE_ENV) == "1":
        return None

    types = _unisolated_subagent_types(payload)
    if not types:
        return None  # isolated, or not an Agent-shaped launch at all

    branch = _current_branch(cwd)
    if not branch:
        return None  # detached HEAD, non-git cwd, or the read failed

    default = _default_branch(cwd)
    if not default:
        return None  # could not resolve; fail toward WARN only

    if branch == default:
        return None  # nothing for a stray checkout to strand

    dirty = _has_dirty_tracked(cwd)
    unpushed = _has_unpushed_commits(cwd)
    if not dirty and not unpushed:
        return None  # clean tree, nothing unpushed -- nothing to strand

    stranded = " and ".join(
        label for label, present in
        (("uncommitted tracked changes", dirty), ("unpushed commits", unpushed))
        if present
    )
    return DENY.format(subagent_type=types[0], branch=branch, default=default,
                       stranded=stranded)


def _read_payload() -> tuple[dict, bool]:
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw_cmd = positional[0].strip()
            if raw_cmd.startswith("{") and raw_cmd.endswith("}"):
                try:
                    return json.loads(raw_cmd), True
                except Exception:
                    pass
            return {"tool_name": "Agent", "tool_input": {"subagent_type": raw_cmd}}, True

    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception as exc:
        print(f"flag-unassigned-worktree: unreadable hook input ({exc})",

              file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0

    cwd = payload.get("cwd") or os.getcwd()

    try:
        deny_reason = _should_deny(payload, cwd)
    except Exception as exc:  # fail toward WARN, never crash the launch
        print(f"flag-unassigned-worktree: could not evaluate deny condition ({exc})",
              file=sys.stderr)
        deny_reason = None

    if deny_reason is not None:
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": deny_reason,
            },
        }
        print(json.dumps(out))
        return 0

    subagent_type = unassigned(payload)
    if subagent_type is None:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    note = NOTE.format(subagent_type=subagent_type)

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": note,
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            f"Agent launch without `isolation` (subagent_type: {subagent_type}). "
            "Assign a worktree or decide deliberately not to."
        )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
