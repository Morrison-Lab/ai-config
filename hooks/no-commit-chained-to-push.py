#!/usr/bin/env python3
"""PreToolUse guard: a `git commit` and a `git push` in ONE Bash call.

WHAT HAPPENS
------------
A `PreToolUse` deny rejects the WHOLE tool invocation, before any part of it
runs. So this shape:

    git add -A && git commit -F - <<'EOF'
    ...
    EOF
    git push -u origin my-branch

loses the commit when any guard refuses the push. `no-push-without-self-review.py`
and `no-clobbering-push.py` are both registered `PreToolUse` on `Bash`, and
either can refuse. Their refusals speak only about the push, so the message
reads as "the push was blocked" while the truth is that `git add`, `git commit`
AND `git push` all never ran -- the work is still an uncommitted working-tree
edit, one `git checkout --` from destruction.

Measured 2026-09-02 (ai-config#2992). The commit was recovered only because an
adversarial reviewer independently checked whether `HEAD` had moved, which is
not a step anybody performs after a refusal that appears to be about something
else.

WHY IT REFUSES RATHER THAN WARNS
--------------------------------
This is the one decision in the hook worth arguing, because README's "A hook
that misfires is worse than a missing one" pushes hard the other way, and the
sibling `warn-dupe-check-chained-to-create.py` -- the same "two commands in one
call" shape -- deliberately only warns.

A warning cannot prevent this failure, which is what separates the two cases.
Every `PreToolUse` hook runs in the same pass over the same invocation. A
warning is `additionalContext`: it is attached to the call and the call
proceeds. If a sibling guard denies in that same pass, the commit is already
gone by the time anyone reads the context. So the advisory form does not
mitigate the hazard at all -- it annotates it afterwards. Where a warn cannot
reach the failure, choosing it is not caution, it is a guard that does nothing.

The refusal is also always satisfiable, which is the test
`no-clobbering-push.py` applies to its own deny. The remedy is to issue the
same two commands as two Bash calls. Nothing is lost by doing so, no
information is unavailable, and the cost of being wrong is one extra tool call
-- against a silently discarded commit in the other direction.

WHAT IT MATCHES
---------------
One Bash `command` whose simple commands include a `git commit` and, LATER in
the same string, a `git push`.

Order matters and is not decoration. Commit-then-push is the hazard: the commit
is the thing that would have been created and was not, and its absence is what
the refusal message hides. Push-then-commit denies the same invocation, but
nothing was created to lose -- the tree is exactly as it was, and the author's
belief about it is correct. Requiring the order therefore drops a class of
false positive at no cost to coverage.

`git commit-tree` and `git commit-graph write` are NOT `git commit`, and this
matters: `no-unshipped-commit.py` records both as measured bugs of a
`git\\s+commit\\b` scan, because a word boundary sits happily between `commit`
and `-`. The subcommand token is compared whole, so neither can match.

WHAT IT DOES NOT MATCH, AND WHY THAT IS MOST OF THE WORK
--------------------------------------------------------
This corpus quotes git commands constantly -- in commit messages, issue bodies,
PR bodies, fragments, tests, and this docstring. The matcher runs over an ARGV
SPLIT rather than over the raw string (`scripts/lib/shellcmd.py`), so quoting is
handled by `shlex` rather than by accreting one regex clause per shape:

  * `git commit -m "then git push"` -- the quoted text is ONE dequoted token
    inside the commit's own argv. It is never a command word.
  * a heredoc BODY mentioning either command -- blanked before splitting.
  * `echo 'git commit; git push'` -- `echo` is the command word.

`shared/writing/examples-are-scanned.md` is the general statement of that
hazard, and an argv split is the "teach the checker about code regions" fix it
names.

FAILS OPEN
----------
Malformed stdin, a non-dict payload, a non-string command, an unparseable
command, and a failure to import `scripts/lib/shellcmd.py` all return 0 with
nothing on stdout. A deny guard that cannot establish its own precondition must
not refuse -- see `shared/principles/fail-fast.md` on bounding a fallback. The
import failure additionally prints to stderr, because a missing sibling module
is a broken install rather than an ordinary condition, and #2981 records a
sibling guard failing exactly that way from a worktree.

`ALLOW_COMMIT_AND_PUSH=1`, as a real env assignment at the start of one of the
matched commands rather than a mention anywhere in the text, clears the
refusal. Same anchoring as `ALLOW_FORCE_PUSH` and `ALLOW_MERGE`, and for the
same reason: a guard its own documentation disables is worthless.
"""
from __future__ import annotations

import json
import os
import sys

OVERRIDE = "ALLOW_COMMIT_AND_PUSH"

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import git_subcommand, simple_commands
except Exception as _exc:  # broken install; fail open and say so
    print(f"no-commit-chained-to-push: cannot load scripts/lib/shellcmd.py "
          f"({_exc}); not evaluating", file=sys.stderr)
    git_subcommand = simple_commands = None

DENY = """\
A `git commit` and a `git push` are in the SAME Bash call.

    commit:  {commit}
    push:    {push}

A PreToolUse guard denies the whole invocation, not the offending half. Both
`no-push-without-self-review.py` and `no-clobbering-push.py` are registered
PreToolUse on Bash and either can refuse this push -- and when one does, the
commit never runs either. Their refusal names only the push, so it reads as
"the push was blocked" while the change is still an uncommitted working-tree
edit, one `git checkout --` from destruction.

That is not hypothetical: ai-config#2992 records it happening, caught only
because an adversarial reviewer independently checked whether HEAD had moved.

Split them into two Bash calls:

    call 1:  {commit}
    call 2:  {push}

The commit is durable before anything can refuse the push, and a refusal then
means what it says. Nothing else about the commands needs to change.

`{override}=1`, as a real env assignment leading one of these commands, clears
this refusal for a case the guard did not foresee. Reaching for it means saying
why splitting the call was not possible.
"""


def evaluate(command):
    """`reason` when the call chains a commit into a push, else `None`."""
    if simple_commands is None:
        return None
    cmds = simple_commands(command)
    if not cmds:
        return None

    commit_argv = None
    for argv in cmds:
        parsed = git_subcommand(argv)
        if parsed is None:
            continue
        sub, _rest, env = parsed
        if env.get(OVERRIDE, "").strip() == "1":
            return None
        if sub == "commit" and commit_argv is None:
            commit_argv = argv
        elif sub == "push" and commit_argv is not None:
            return DENY.format(commit=" ".join(commit_argv),
                               push=" ".join(argv), override=OVERRIDE)
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:  # fail open, but say so
        print(f"no-commit-chained-to-push: unreadable hook input ({exc})",
              file=sys.stderr)
        return 0

    if not isinstance(payload, dict):
        return 0

    if payload.get("tool_name") not in ("Bash", "bash", "run_command",
                                        "execute_command", "terminal", "shell"):
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    command = (tool_input.get("command")
               or tool_input.get("cmd")
               or tool_input.get("CommandLine")
               or tool_input.get("script")
               or "")
    if not isinstance(command, str) or not command.strip():
        return 0

    try:
        reason = evaluate(command)
    except Exception as exc:  # fail open on any parse trouble
        print(f"no-commit-chained-to-push: could not evaluate command ({exc})",
              file=sys.stderr)
        return 0

    if reason is None:
        return 0

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            "A `git commit` and a `git push` share one Bash call. A PreToolUse "
            "deny rejects the whole invocation, so a refused push discards the "
            "commit too. Issue them as two separate calls."
        )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
