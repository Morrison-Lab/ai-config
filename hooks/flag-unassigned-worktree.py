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
