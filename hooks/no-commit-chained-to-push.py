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

    git add -A && git commit -m "..." && git push -u origin my-branch

a refusal of the push loses the commit too. `no-push-without-self-review.py`
and `no-clobbering-push.py` are both registered `PreToolUse` on `Bash`, and
either can refuse. Their refusals speak only about the push, so the message
reads as "the push was blocked" while `git add`, `git commit` and `git push`
all never ran -- the work is still an uncommitted working-tree edit, one
`git checkout -- .` from destruction.

**One shape is currently safe, and it is the one the incident was reported
in**, which is worth stating rather than letting the example imply otherwise.
Both siblings still carry the `_simple_commands` heredoc defect (ai-config#2993,
which `scripts/lib/shellcmd.py` fixes and does not backport), so on

    git add -A && git commit -F - <<'EOF'
    ...
    EOF
    git push -u origin my-branch

neither sibling sees a push at all and neither refuses. Measured 2026-09-02:
this guard denies that call and both siblings return nothing. So for a heredoc
commit, TODAY, nothing would have been lost.

That is a reason to fix #2993, not a reason to exempt the shape. The guard
cannot know which of a changing set of `PreToolUse` guards will refuse a given
push, the exemption would expire the moment #2993 lands, and a rule the author
must apply differently depending on how the commit message is written is not a
rule anyone will follow. What it does change is the CLAIM: neither this
docstring nor the deny message may assert that a sibling would have refused
this particular call.

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
extra tool call.

State the other side of that comparison precisely, because the obvious phrasing
overclaims. The cost of a MISS is not "a discarded commit" on every call --- it
is a discarded commit on the calls where a sibling would in fact have refused,
which is unknowable at match time and, per the heredoc note above, is currently
not all of them. The argument the refusal actually rests on is the asymmetry
between a bounded, certain cost and an unbounded, uncertain one, not a claim
that every chained call is about to lose a commit.

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
  * as the call's LEADING assignment
    (`export ALLOW_COMMIT_AND_PUSH=1 && git commit -m x && git push`).

"Leading" is literal: position zero, followed by a separator. An assignment
further along genuinely sets the variable and is still refused
(`cd /repo && export ALLOW_COMMIT_AND_PUSH=1 && git commit -m x && git push`
denies), which is a deliberate trade -- the raw-text anchor is what makes a
subshell or short-circuited assignment impossible to mistake for a real one,
and no argv-level test can draw that line, because the split discards
connectors. Move the assignment to the front, or prefix the commit or the
push directly.

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
import re
import shlex
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
PreToolUse on Bash and either MAY refuse a push -- and when one does, the
commit never runs either. Whether one would refuse THIS call is not something
this guard checked, and it does not need to be: you cannot know in advance
either, and the set of guards changes. Their refusal names only the push, so it
reads as "the push was blocked" while the change is still an uncommitted
working-tree edit, one `git checkout -- .` from destruction.
`memories/claude-code-hooks.md` records the general mechanism; ai-config#2992
records this instance of it, caught only because an adversarial reviewer
checked whether HEAD had moved.

Split them into two Bash calls. The two commands, re-rendered from the parsed
argv:

    call 1:  {commit}
    call 2:  {push}

Those lines IDENTIFY the commands rather than reproducing them byte for byte:
quoting is normalized, and a newline inside a quoted argument (a multi-line
`-m` message) is shown as `;`. Split your original text rather than pasting
these. Nothing about either command's content needs to change -- only the call
boundary between them.

The commit is then durable before anything can refuse the push, and a refusal
means what it says.

`{override}=1` clears this refusal, either prefixing one of the two commands
above or as the call's LEADING assignment (`export {override}=1 && ...`, at
position zero). An assignment further along the line does not count, even
though the shell would honour it -- move it to the front. It is for a case this
guard did not foresee; reaching for it means saying why the call could not be
split.
"""


# A standalone assignment counts only at the very START of the command text.
# Anywhere else it may not run, or may not persist, and two measured shapes
# cleared the guard while setting nothing at all:
#
#     (ALLOW_COMMIT_AND_PUSH=1); git commit -m x && git push
#         -- a subshell assignment, discarded when the subshell exits
#     false && ALLOW_COMMIT_AND_PUSH=1; git commit -m x && git push
#         -- short-circuited, so it never executes
#
# The argv split cannot see either, because it discards connectors and peels
# `(`/`)` as shell keywords. Anchoring on the raw text sidesteps that entirely:
# a leading assignment is the one position where the shell guarantees the
# variable is set for everything after it.
# The trailing group requires a SEPARATOR, not merely whitespace. Accepting
# any whitespace made `ALLOW_COMMIT_AND_PUSH=1 git status && git commit && git
# push` clear the guard, and that assignment is scoped to `git status` alone --
# it does not persist, so nothing about the push was authorized. That is the
# same scope defect as reading the override off a third command, arriving by a
# different route.
LEADING_OVERRIDE = re.compile(
    r"\A[ \t]*(?:export[ \t]+)?" + OVERRIDE + r"=1[ \t]*(?:;|&&|\|\||\r?\n|\Z)")


def _standalone_override(command):
    """True when the call OPENS with an assignment of the override to 1.

    `export ALLOW_COMMIT_AND_PUSH=1 && ...` and a bare
    `ALLOW_COMMIT_AND_PUSH=1` on the first line both qualify. An assignment
    that appears later, in a subshell, or behind a short-circuit does not --
    see the comment above. An assignment that PREFIXES the commit or the push
    is handled by the per-command check in `evaluate` instead, which is scoped
    to those two commands so a stale prefix on an unrelated `git status`
    cannot disarm the guard.
    """
    return LEADING_OVERRIDE.match(command) is not None


# NO EXEMPTION FOR AN "INERT" COMMIT OR PUSH, and the reason is worth stating
# because a reviewer asked for one and the exemption was written, shipped, and
# then removed.
#
# The request was sound on its face: `git push --dry-run` transfers nothing and
# `git commit --dry-run` creates nothing, and `no-push-without-self-review.py`
# documents that it never examines a dry-run or a deletion -- so denying those
# chains looked like a pure false positive. The exemption was added, and a
# second review measured two ways it went silent on a real loss:
#
#   git commit -m wip && git push --force --delete origin old
#       `no-clobbering-push.py` DENIES this. Its `delete` exemption lives in
#       its reading pass only; its refusal pass tests `force` and `dry_run`
#       and never consults `delete`. So the sibling refuses, the commit is
#       discarded, and the exemption hid it.
#   git commit -m wip && git push --dry-run --no-dry-run --force origin main
#       Every git option has a `--no-` form, so a scan that stops at the first
#       `--dry-run` reads a live force push as inert. `no-clobbering-push.py`
#       carries this exact lesson in its own comments, having been bitten by
#       it, and DENIES this too.
#
# Making the exemption sound means reimplementing git's option grammar --
# last-occurrence-wins, `--no-` negation, short clusters, `--` end-of-options
# -- and then ALSO tracking which pass of which sibling exempts what, since
# those differ per guard and per pass. That is a large, drifting surface whose
# only payoff is not refusing a rare command.
#
# The costs are not comparable. Refusing a chained dry-run costs one extra
# tool call. Missing a chained force-delete costs a silently discarded commit,
# which is the whole failure this guard exists to prevent. So the exemption is
# gone and the false positive is accepted, deliberately.


def evaluate(command):
    """`reason` when the call chains a commit into a later push, else `None`."""
    if simple_commands is None:
        return None
    cmds = simple_commands(command)
    if not cmds:
        return None
    if _standalone_override(command):
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
            # `shlex.join`, never `" ".join`. The argv is DEQUOTED, so a
            # space join re-emits `git commit -m "fix: a b; rm -rf x"` as
            # `git commit -m fix: a b; rm -rf x` -- which commits `fix:` and
            # then runs `rm -rf x`. A guard whose message is more dangerous
            # than the command it refused is worse than no guard, and someone
            # WILL paste a line a refusal printed at them.
            #
            # `shlex.join` makes it injection-safe and not byte-faithful: a
            # newline inside a quoted argument has already become `;` in
            # `simple_commands`, which is quote-blind about the rewrite. The
            # DENY text says so rather than inviting the paste.
            return DENY.format(commit=shlex.join(commit_argv),
                               push=shlex.join(argv), override=OVERRIDE)
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
