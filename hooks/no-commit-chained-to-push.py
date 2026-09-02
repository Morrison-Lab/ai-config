#!/usr/bin/env python3
"""PreToolUse guard: a `git commit` and a `git push` in ONE Bash call.

WHAT HAPPENS
------------
A `PreToolUse` deny rejects the WHOLE tool invocation, before any part of it
runs. `memories/claude-code-hooks.md`'s "A hook's deny rejects the WHOLE call,
so a compound command's setup segments never run either" states the mechanism
and measured it on 2026-08-17 (ai-config#1609, a `git checkout -b` lost to a
punctuation-replace deny). This guard is that mechanism's commit-and-push
instance.

So in this shape:

    git add -A && git commit -F - <<'EOF'
    ...
    EOF
    git push -u origin my-branch

a refusal of the push loses the commit too. `no-push-without-self-review.py`
and `no-clobbering-push.py` are both registered `PreToolUse` on `Bash`, and
either can refuse. Their refusals speak only about the push, so the message
reads as "the push was blocked" while `git add`, `git commit` and `git push`
all never ran -- the work is still an uncommitted working-tree edit, one
`git checkout -- .` from destruction.

Reported 2026-09-02 by a session on this machine that lost a commit this way
and caught it only because an adversarial reviewer independently checked
whether `HEAD` had moved (ai-config#2992). That issue's author states they
verified the MECHANISM from the hook registration and did not reproduce the
lost commit, so the mechanism above is derived and the incident is a report.
The commands in this file's tests are reconstructions of the reported shape,
not a transcript.

WHY IT REFUSES RATHER THAN WARNS
--------------------------------
This is the one decision here worth arguing, because README's "A hook that
misfires is worse than a missing one" pushes hard the other way, and the
sibling `warn-dupe-check-chained-to-create.py` -- the same "two commands in one
call" shape -- deliberately only warns.

The case for the refusal is that it PREVENTS the loss, and the case against a
warning is weaker than it first looks, so both are stated.

A warning is `additionalContext`: it is attached and the call proceeds. If a
sibling guard denies in that same pass, the commit does not happen. Whether the
author is then TOLD depends on something this file cannot establish from a
worktree -- whether a non-denying hook's `additionalContext` is still delivered
when a sibling denies the same call. `memories/claude-code-hooks.md` documents
the whole-call scope of a deny and says nothing about context delivery under
one. Settling it takes ten minutes: register two trivial `PreToolUse` hooks on
`Bash`, one emitting only a sentinel `additionalContext` and one emitting
`permissionDecision: deny`, issue a matching call, and look for the sentinel.
Tracked as part of ai-config#2992.

The refusal does not depend on that answer, which is why it is the choice here.
It stops the chain from reaching the siblings at all, and it is always
satisfiable -- the remedy is to issue the same two commands as two Bash calls.
That is the test `no-clobbering-push.py` applies to its own deny: nothing is
lost by complying, no information is unavailable, and being wrong costs one
extra tool call against a silently discarded commit in the other direction.

ai-config#2992 proposes a DIFFERENT fix: extend the denying guards' own
messages to say a commit in the same chain did not run. That is complementary
rather than superseded, and it has one real advantage over this guard -- it
fires from whichever guard actually refuses, so it cannot miss a shape this
matcher misses, and it covers the non-push publish verbs this guard does not.
It is left open on #2992.

WHAT IT MATCHES
---------------
One Bash `command` whose simple commands include a `git commit` and, LATER in
the same string, a `git push`.

Order matters and is not decoration. Commit-then-push is the hazard: the commit
is the thing that would have been created and was not, and its absence is what
the refusal message hides. Push-then-commit denies the same invocation, but
nothing was created to lose -- the tree is exactly as it was, and the author's
belief about it is correct. Requiring the order drops a class of false positive
at no cost to coverage.

Wrapped and non-literal spellings resolve, because the guard must fire wherever
its siblings would: `timeout 60 git push`, `/usr/bin/git push`, `$GIT push`,
`sudo -u me git push`, `{ git commit -m x; } && git push`. Those come from
`scripts/lib/shellcmd.py`'s `strip_env`, adapted from
`no-push-without-self-review.py`'s own classifier so the two guards agree about
what a push is. A narrower table here would mean the sibling denying a call
this guard stayed silent on, which is the exact failure it exists to prevent.

`git commit-tree` and `git commit-graph write` are NOT `git commit`, and this
matters: `no-unshipped-commit.py` records both as measured bugs of a
`git\\s+commit\\b` scan, because a word boundary sits happily between `commit`
and `-`. The subcommand token is compared whole, so neither can match.

WHAT IT DOES NOT MATCH, AND WHY THAT IS MOST OF THE WORK
--------------------------------------------------------
This corpus quotes git commands constantly -- in commit messages, issue bodies,
PR bodies, fragments, tests, and this docstring. The matcher runs over an ARGV
SPLIT rather than over the raw string, so quoting is handled by `shlex` rather
than by accreting one regex clause per shape:

  * `git commit -m "then git push"` -- the quoted text is ONE dequoted token
    inside the commit's own argv. It is never a command word.
  * a heredoc BODY mentioning either command -- blanked before splitting.
  * `echo 'git commit; git push'` -- `echo` is the command word.

`shared/writing/examples-are-scanned.md` is the general statement of that
hazard, and an argv split is the "teach the checker about code regions" fix it
names.

THE OVERRIDE
------------
`ALLOW_COMMIT_AND_PUSH=1` clears the refusal, in either of the two spellings
that genuinely set the variable for the push:

  * as an assignment prefixing the matched commit or push
    (`ALLOW_COMMIT_AND_PUSH=1 git commit -m x && git push`), or
  * as its own earlier command in the same call
    (`export ALLOW_COMMIT_AND_PUSH=1 && git commit -m x && git push`).

An assignment on some unrelated third command does NOT clear it, and neither
does a mention in a commit message. `export` is accepted because
`no-unauthorized-merge.py`'s `ALLOW_MERGE` anchor accepts it, and an escape
valve that rejects the spelling its own precedent uses is not an escape valve.
`no-clobbering-push.py`'s `ALLOW_FORCE_PUSH` is the stricter precedent and does
not; the looser of the two is taken deliberately, since a refused override
sends the author looking for a bypass.

FAILS OPEN
----------
Malformed stdin, a non-dict payload, a non-string command, an unparseable
command, and a failure to import `scripts/lib/shellcmd.py` all return 0 with
nothing on stdout. A deny guard that cannot establish its own precondition must
not refuse -- see `shared/principles/fail-fast.md` on bounding a fallback. The
import failure additionally prints to stderr, because a missing sibling module
is a broken install rather than an ordinary condition, and ai-config#2981
records a sibling guard failing exactly that way from a worktree.
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
    from shellcmd import env_value, git_subcommand, simple_commands, strip_env
except Exception as _exc:  # broken install; fail open and say so
    print(f"no-commit-chained-to-push: cannot load scripts/lib/shellcmd.py "
          f"({_exc}); not evaluating", file=sys.stderr)
    env_value = git_subcommand = simple_commands = strip_env = None

DENY = """\
A `git commit` and a `git push` are in the SAME Bash call.

    commit:  {commit}
    push:    {push}

A PreToolUse guard denies the whole invocation, not the offending half. Both
`no-push-without-self-review.py` and `no-clobbering-push.py` are registered
PreToolUse on Bash and either can refuse this push -- and when one does, the
commit never runs either. Their refusal names only the push, so it reads as
"the push was blocked" while the change is still an uncommitted working-tree
edit, one `git checkout -- .` from destruction. `memories/claude-code-hooks.md`
records the general mechanism; ai-config#2992 records this instance of it,
caught only because an adversarial reviewer checked whether HEAD had moved.

Split them into two Bash calls:

    call 1:  {commit}
    call 2:  {push}

The commit is durable before anything can refuse the push, and a refusal then
means what it says. Nothing else about the commands needs to change.

`{override}=1` clears this refusal, either prefixing one of the two commands
above or as its own earlier command (`export {override}=1 && ...`). It is for a
case this guard did not foresee; reaching for it means saying why the call could
not be split.
"""


def _standalone_override(cmds):
    """True when some simple command in the call just sets the override.

    `export ALLOW_COMMIT_AND_PUSH=1` and a bare `ALLOW_COMMIT_AND_PUSH=1` are
    both real assignments that persist for the rest of the call, so both count.
    A command that ASSIGNS the override and then runs something is handled by
    the per-command check instead, and only for the commit and the push --
    reading it off any third command would let a stale prefix on an unrelated
    `git status` silently disarm the guard.
    """
    for argv in cmds:
        env, rest = strip_env(argv)
        if rest:
            continue  # it ran something; not a bare assignment
        if env_value(env, OVERRIDE) == "1":
            return True
    return False


def evaluate(command):
    """`reason` when the call chains a commit into a later push, else `None`."""
    if simple_commands is None:
        return None
    cmds = simple_commands(command)
    if not cmds:
        return None
    if _standalone_override(cmds):
        return None

    commit_argv = None
    for argv in cmds:
        parsed = git_subcommand(argv)
        if parsed is None:
            continue
        sub, _rest, env = parsed
        if sub not in ("commit", "push"):
            continue
        if env_value(env, OVERRIDE) == "1":
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
