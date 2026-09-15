#!/usr/bin/env python3
"""PreToolUse guard: a `git push` that could discard another agent's commits.

## The gap this closes

A branch you cut, whose PR you opened, and whose review round you are driving
is the branch you are *least* likely to check before pushing to. Ownership is
the thing that suppresses the check, and the belief is usually wrong:
`shared/workflow/claim-pr.md` already records that the `@claude` agent pushes
to your branch on PR activity, that a second CLI session can pick the same PR
up, and that a human can push to it -- and it carries three separate
procedures for recovering from a push that came back rejected.

Every one of those recoveries runs AFTER the collision. Nothing made the check
happen before the push, and a `git fetch` from earlier in the session is not
evidence about the remote now: it is a measurement, and it expired the moment
somebody else pushed.

`skills/push/SKILL.md` states the pre-push checks well, but a skill only runs
when it is invoked, and a bare `git push` in the middle of an ARDI round never
passes through it. That is the gap a hook closes -- it runs on the command
itself, independent of whether the moment felt like it warranted a check.

## Two behaviours, and why only one of them refuses

**It REFUSES a bare `--force` / `-f`** (deny), because that is the one case
that is decidable from the command text alone and has a remedy that costs one
word. `git push --force-with-lease --force-if-includes` does everything
`--force` does except overwrite a remote tip you have not seen; it is never
the worse choice, and where the remote ref does not exist the lease succeeds
trivially. So the refusal is always satisfiable, and being wrong about it
costs a retype rather than a lost commit.

`ALLOW_FORCE_PUSH=1` is the escape hatch, and it is deliberately not tied to a
worked example. The case that looks like it needs one is not: `memories/git-branches.md`
records `--force-with-lease` failing with `stale info` after a squash-merge with
auto-delete removed the branch, and says the lease is unsatisfiable rather than
violated, so a PLAIN push is the fix and `--force` is unnecessary. That is
consistent with the paragraph above -- where the remote ref does not exist,
there is nothing for any force to overwrite. So the hatch exists for a case this
guard did not foresee, not for a known one.

The refusal also does NOT consult `--force-with-lease`, because `--force`
disables the lease check. Git's documentation for `-f, --force` says so, and
the two wordings in circulation differ enough to be worth attributing:

  upstream master (Documentation/git-push.adoc) --- "This flag disables that
  check, the other safety checks in PUSH RULES below, and the checks in
  `--force-with-lease`."

  the man page shipped with git 2.50.1 --- "when --force-with-lease option is
  used, the command refuses to update a remote ref whose current value does not
  match what is expected. / This flag disables these checks"

So `--force --force-with-lease` is a plain force push, and treating the lease
as clearing the refusal was a bypass rather than a nicety.

**It WARNS on everything else** (`additionalContext`, no `permissionDecision`),
because whether a divergence matters is a judgment this hook cannot make: a
rebase you did on purpose and a parallel session's commits look identical from
here. Per README's "A hook that misfires is worse than a missing one", the
warning path only ever adds context.

## The measurement

The warning is not a transcript heuristic about whether you fetched recently.
It is a fresh reading taken at the moment of the push:

    git ls-remote --heads <remote> <branch>

`ls-remote` is read-only -- it updates no remote-tracking ref and writes
nothing -- so the hook cannot itself change the state it is reporting on.
The reading is then classified:

  - remote ref absent            -> nothing to collide with; silent
  - remote tip == the pushed ref -> already pushed; silent
  - remote tip is an ancestor    -> fast-forward; silent (the common case, so
                                    the hook stays quiet in normal operation)
  - remote tip is NOT an ancestor of the pushed ref -> WARN, say what is at risk

The local side of every comparison above is the ref being PUSHED, which is
`HEAD` only when the refspec says so -- see `_target`'s docstring. The warning
names it explicitly rather than saying "HEAD", because on `git push origin
feature-x` from `main` the two are different branches.

In that last case the hook tries to describe the divergent commits. Whether it
can turns on one thing worth distinguishing in the report:

  - the object IS present locally (a prior fetch brought it): list the commits
    with their authors and dates, so a parallel session is nameable.
  - the object is NOT present locally: that is the sharper signal, not the
    weaker one -- the remote moved since your last fetch and you cannot even
    see what is there. Say exactly that.

## Where the reading is taken

`HEAD` is per-worktree, so WHERE the local ref is resolved is part of the
reading rather than an implementation detail. Resolving it in the session's
own directory made every cross-worktree push report a divergence that did not
exist: a session sitting in one worktree, pushing from another, was told that
its own commits of a few minutes earlier belonged to somebody else, and was
prescribed a `git merge origin/<branch>` that would have merged a branch into
itself (ai-config#2451).

So each push is read in the directory it actually runs in: the payload's
`cwd`, moved by any `cd` earlier in the same compound command, then moved
again by the push's own `git -C`. When a `cd` cannot be resolved statically
--- `cd -`, a directory stack, an unexpanded variable --- the directory is
INDETERMINATE and the reading is declined, because a reading taken in the
wrong repository is worse than no reading at all. That is the same choice
`_target` already makes when the destination is not a single named branch.

A subshell written with PARENTHESES scopes a `cd` to itself, so
`(cd elsewhere && true) && git push` leaves the push in the CALLING directory.
`_simple_commands` therefore labels each simple command with the subshell it
runs in, using the parentheses `shlex` has already separated from quoted text,
and `evaluate` keeps one directory per subshell: a subshell inherits its
caller's directory when it opens, and nothing it does is ever read back out.
Reading a push that sits OUTSIDE those parentheses in `elsewhere` is the
wrong-repository reading of ai-config#2451 again, and this file introduced it
before the parentheses were tracked at all (measured 2026-09-04).

The label is an IDENTITY rather than a nesting depth, which is not a
refinement: two sibling subshells sit at the same depth, so a depth-keyed
directory let the first one's `cd` leak into the second and
`(cd elsewhere && true) && (git push)` read `elsewhere` -- the same
wrong-repository reading, arriving by the very mechanism added to prevent it
(measured 2026-09-04).

Not every `)` closes a subshell, though, and the one that does not is a `case`
PATTERN: `(cd elsewhere && case a in a) git push;; esac)` carries three of
them and opens one subshell. Popping a scope on the pattern's `)` recorded the
push OUTSIDE the parentheses it really runs in, so the `cd` beside it was
dropped and the push was read in the session's own repository --
ai-config#2451's wrong-repository reading once more, and silent rather than
merely misworded wherever the session sits on the remote tip (measured
2026-09-04). `_simple_commands` therefore tracks `case` ... `esac` alongside
the parentheses, the same two words `evaluate`'s region counter already reads
out of `BLOCK_OPEN` / `BLOCK_CLOSE`, and declines to pop for a `)` that closes
a pattern of the innermost case open at the CURRENT depth. A `;;` returns that
case to pattern position, so the second clause's `)` is read as a pattern too.
Every other `)` pops as it always did, which is what closes a subshell nested
inside a case body; keying both tests to the depth the case opened at is what
keeps a deeper one from being read as that case's own.

Pattern position begins at the case's `in` rather than at the `case` keyword,
because the subject between them can itself carry parentheses: in
`case $(echo a) in a) ...` the substitution's own `(` would otherwise be
swallowed as a pattern opener, and the real pattern's `)` would then pop the
enclosing subshell after all (measured 2026-09-04).

A `cd` the shell may never REACH, and one it reaches in a subshell of its
own, are declined as well. Both arrive here looking exactly like an ordinary
`cd`, because `_simple_commands` splits on operators and models neither
short-circuiting nor forking, so applying them read the later push in
`elsewhere` where no shell ever puts it -- ai-config#2451's wrong-repository
warning once more, in each of the shapes below (measured 2026-09-04). Three
things are tracked to decline them, and a fourth decline below has a
different reason.

A compound statement's body runs only when a branch is taken or an iteration
begins, so `evaluate` counts the REGION one opens (`if`, `while`, `until`,
`for`, `select`, `case`) and closes (`fi`, `done`, `esac`), and declines every
`cd` in that body. The region rather than the opening keyword, because a
keyword attaches to a single simple command: `if ...; then echo no;
cd elsewhere; fi` leaves that `cd` carrying no keyword at all, and it was
applied while the one-command body beside it was declined.

The CONDITION such a statement opens is the fourth decline, and the reason is
not the one above: a condition runs in the current shell, so its `cd` really
is reached. What the region cannot do is see it. The condition shares one
argv with the keyword, so `if cd elsewhere; then git push; fi` left that `cd`
unseen and read the push in the session's own repository -- ai-config#2451's
wrong-repository warning, its misattributed commit list and its
branch-into-itself merge included (measured 2026-09-04). `evaluate` tests
that argv's remainder for a `cd` and declines it, rather than resolving it,
because where the shell sits after `fi` depends on whether the condition
succeeded.

Each simple command carries the operator PRECEDING it, which is what tells an
alternative from a chain: a `cd` after `||` runs only when what came before
failed, and a `cd` after `|` is a pipeline element the shell forks.

Each also carries the operator FOLLOWING it, because a fork is invisible from
the operator before: `cd elsewhere & git push` and `cd elsewhere | cat; git
push` both move a directory the pushing shell never sees.

That operator is the FIRST of its punctuation run, and the run is where it
was lost: a newline becomes `;` here, so `cd elsewhere &` at the end of a line
arrives as `&;`, and folding the whole run reported the `;` and discarded the
fork -- the wrong-repository reading arriving through the very clause added
to stop it (measured 2026-09-04). The trailing operator also propagates
BACKWARDS across `&&` and `||`, because a `&` backgrounds the whole AND-OR
list before it rather than the one command it follows: in
`cd elsewhere && make & git push` the `cd` is forked too (measured
2026-09-04, in the one-line and end-of-line spellings alike).

`&&` is deliberately NOT declined, because a `cd` and a later push joined by an
unbroken `&&` chain are reached together: the push runs only if everything
before it succeeded, the `cd` included. That is the shape worth reading
(`git fetch && cd wt && git push`), and declining it would cost the reading
that matters most.

A brace group is the opposite case and needs the opposite treatment: `{ ... ; }`
runs in the CURRENT shell, so a `cd` inside one outlives the closing brace.
`{` and `}` are therefore stripped as lead words rather than counted, which
leaves `{ cd elsewhere; } && git push` reading `elsewhere` -- where a real
shell runs it (measured 2026-09-04).

`--git-dir`, `--work-tree`, and their `GIT_DIR=` / `GIT_WORK_TREE=` env
spellings move the repository a push reads WITHOUT moving the directory, so
resolving the directory alone reads the session's `HEAD` for a push aimed at
another repository -- the same failure by another route (measured 2026-09-04,
in both the `--opt value` and `--opt=value` spellings). They are
DECLINED rather than resolved, which is the answer `pushd` already gets: this
guard reports on one branch in one repository, and honouring them means
threading a repository through every read below rather than a directory.

Where the reading ends up somewhere other than the directory the Bash call
started in, the warning says where, and prefixes each of its remediation
commands with `git -C <that directory>`. The reader's shell is still in the
call's own directory, so a bare `git merge origin/<branch>` handed to it merges
into whatever is checked out THERE -- ai-config#2451's branch-into-itself merge
with the directory axis substituted for the ref one.

The gaps that remain include a premise. The payload's `cwd` is TAKEN to be the
directory this Bash call starts in, and no test here can settle whether it is:
a test supplies that field itself, so `test-no-clobbering-push.py`'s
W10 shows the value is threaded through every read rather than where it came
from
(`shared/workflow/fixtures-are-not-evidence.md`). On one path it measurably is
not the call's directory: `.cursor/hooks/adapt-claude-hooks.py` fills `cwd` in
from `CURSOR_PROJECT_DIR` whenever Cursor supplies none, which is a fixed root.
Where the field is a session or project root, a `cd` from an EARLIER Bash call
--- whose effect persists into this one --- is invisible from here, and the
push is read where the session started rather than where it runs: the
wrong-repository reading of ai-config#2451, arriving by another route. One
measurement settles it, and is worth taking before this paragraph is trusted
either way: a Bash call that `cd`s into a second worktree, a later call
carrying a bare `git push`, and a record of the `cwd` the hook received.

Another gap is an assignment that outlives its own simple command --- a bare
`GIT_DIR=...` command, or `export GIT_DIR=...`, either earlier in this compound
command or in an earlier Bash call. Only the per-command prefix form is
recognized, so the persistent form is invisible here and the reading is taken
in the session's repository rather than declined.

A third is an `&&` chain a `;` then breaks: in `false && cd elsewhere; git
push` the push runs and the `cd` did not, and the paragraph above applies it
anyway. Reaching that shape takes a `cd` guarded by a command that failed, and
a push deliberately run outside the same chain, which is why the reading is
kept rather than declined --- the `&&` shape it would cost is the common one.

A fourth is a function body. `f() { cd elsewhere; }; git push` defines `f`
without running it, and a brace group is transparent by the paragraph above,
so the `cd` is applied to a push the shell runs where the call started
(measured 2026-09-04). Declining it means recognizing a definition's `()` and
then tracking brace depth to find where its body ends, which is more shell
simulation than the shape earns: a definition and a push in one Bash call,
whose body `cd`s and is never called.

When the payload carries no `cwd` at all the fallback is the hook process's own
directory, deliberately, rather than the `CLAUDE_PROJECT_DIR` that
`flag-cd-into-main-checkout.py` prefers: `plugins/ai-config/codex-hook-adapter.py`
runs each hook with its subprocess `cwd` set to the payload's, so the process
directory tracks the call there, while a project root is a fixed point that
cannot be the worktree a push runs in.

## The match condition

  M1  the tool is `Bash` and `tool_input.command` parses into simple commands
  M2  one of those is `git push`, after skipping env assignments, lead words,
      and `git`'s own global options (`-C <dir>`, `-c <cfg>`, `--git-dir=...`).
      Skipping is only about FINDING `push`; `-C` is additionally read back
      out, and `--git-dir` / `--work-tree` additionally decline the reading
  M3  it is not a `--dry-run` / `-n` push (which transfers nothing)
  M4  it is not a `--delete` / `-d` push (branch deletion is
      `skills/clean-branches`' territory, not this guard's)

Deny additionally requires a `--force` or `-f` token and no
`ALLOW_FORCE_PUSH=1` prefix. The prefix is honoured whether it precedes the
push itself or the WRAPPER around it: `ALLOW_FORCE_PUSH=1 bash -c "<push>"`
really sets the variable for the inner `git`, and reading it only from the same
simple command refused a wrapped push with no way to comply
(ai-config#1973 review). An `export ALLOW_FORCE_PUSH=1` in an EARLIER simple
command is honoured too, since an export really does reach every later command
in the same shell; one written after the push is not, since bash has not run
it yet. Deny deliberately does NOT look at `--force-with-lease`, for the
reason given above: `--force` disables the lease check, so the pair is a plain
force push.

  M5  a command line nested in a shell's `-c` argument is matched too, via
      `scripts/lib/shellcmd.py`'s `shell_c_expansions`, and `env -S`'s single
      argument counts as one. A nested piece can only ever produce a REFUSAL,
      never a reading: its starting directory depends on `cd`s in the outer
      shell and is not knowable here, and a reading against the wrong
      repository is what `evaluate`'s Pass 2 already declines to do.

`--mirror` and `--all` are deliberately out of scope: they push ref sets rather
than one branch, so the single-branch reading below would misdescribe them.

Fails OPEN on any parse trouble, outside a git repository, when `git` or the
network is unreachable, and on any `ls-remote` timeout.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import (shell_c_expansions, nested_shell_commands,
                          COMMAND_WRAPPERS)
except Exception as _exc:  # broken install: degrade, do not fail open further
    print(f"no-clobbering-push: cannot load scripts/lib/shellcmd.py ({_exc}); "
          f"a push wrapped in an interpreter's -c will not be seen",
          file=sys.stderr)
    shell_c_expansions = nested_shell_commands = None
    COMMAND_WRAPPERS = frozenset()

RX_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?\n[ \t]*\2\b", re.S)

ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
LEAD_WORDS = {"then", "do", "else", "elif", "!", "time", "sudo", "command",
              "exec", "nohup", "env",
              # A brace group runs in the CURRENT shell rather than forking, so
              # its `cd` outlives the closing brace. Stripping the braces as
              # lead words is what makes `{ cd elsewhere; } && git push` read
              # `elsewhere`; counting them the way parentheses are counted
              # would scope the `cd` to the group and be wrong.
              "{", "}"}

# The words that open and close a compound statement whose body runs only when
# a branch is taken or an iteration begins. A REGION is tracked rather than the
# `then` / `else` / `elif` / `do` keyword, because a keyword attaches to one
# simple command and a body may hold several: in
# `if ...; then echo no; cd elsewhere; fi` the `cd` carries no keyword at all
# (measured 2026-09-04). `elif` opens nothing -- its `if` already did -- and
# `{` / `}` open nothing either, since a brace group runs in the current shell
# whenever the command carrying it runs.
#
# The region covers the BODY. A `cd` in the opening statement's own condition
# shares an argv with the keyword and is declined separately in `evaluate`.
BLOCK_OPEN = {"if", "while", "until", "for", "select", "case"}
BLOCK_CLOSE = {"fi", "done", "esac"}

# The operator BEFORE a `cd` that means the pushing shell may never take its
# effect: `||` runs its right side only when the left one failed, and `|` makes
# the command a pipeline element the shell forks. `&&` is deliberately absent,
# for the reason the module docstring gives.
BRANCH_SEPS = {"||", "|"}

# The operator AFTER a `cd` that forks it into a subshell of its own. A fork is
# invisible from the operator before, so both directions are read.
FORK_SEPS = {"&", "|"}

_SHELL_OPS = set("();|&")

# `ALLOW_FORCE_PUSH=1` counts only as a real env assignment at the start of
# the same simple command, never as a mention of the string elsewhere. Same
# shape as `no-unauthorized-merge.py`'s `ALLOW_MERGE=1` anchor and for the
# same reason: a guard that its own documentation disables is worthless.
OVERRIDE = "ALLOW_FORCE_PUSH"

# `git`'s own global options that consume the following token, skipped before
# `push` is looked for so `git -C /repo push` matches.
GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace",
                  "--exec-path"}

# The two of those that name a REPOSITORY rather than a directory, plus their
# env spellings. `HEAD` is per-repository as well as per-worktree, so either
# one makes the directory an answer to the wrong question.
GIT_REPO_OPTS = {"--git-dir", "--work-tree"}
GIT_ENV_REDIRECT = ("GIT_DIR=", "GIT_WORK_TREE=")

# `git push` long options that consume the FOLLOWING token when written without
# `=`. `--repo` is in here AND is read back out in `_target`, because its value
# IS the remote -- skipping it as a mere value was a defect: `git push --repo
# origin HEAD` was resolved against the current branch's configured remote
# rather than against `origin`.
LONG_VALUE_OPTS = {"--push-option", "--repo", "--receive-pack", "--exec",
                   "--recurse-submodules"}

# Every `git push` short option, taken from `git push -h` rather than guessed:
# -4 -6 -d -f -n -o -q -u -v. Only `-o` consumes a value, and that is what makes
# a cluster like `-fo ci.skip` dangerous: it is accepted bash, it IS a force
# push, and a matcher that does not know `o` swallows a value both misses the
# force and mistakes `ci.skip` for the remote.
SHORT_BOOL = {"4": None, "6": None, "d": "delete", "f": "force",
              "n": "dry_run", "q": None, "u": None, "v": None}
SHORT_VALUE = {"o"}

# Long options this guard cares about, and their negations. EVERY `git push`
# option has a `--[no-]` form, so a positive-only scan is order-blind:
# `git push --dry-run --no-dry-run --force` really does transfer, and reading
# only the `--dry-run` made the guard skip a live force push.
LONG_FLAG = {
    "--force": "force",
    "--dry-run": "dry_run",
    "--delete": "delete",
    "--mirror": "refset",
    "--all": "refset",
    "--branches": "refset",   # `git push -h`: "alias of --all"
}


def _next_sep(sep, ch):
    """The separator a further operator character leaves behind.

    `&&` and `||` are read one character at a time so that a compound operator
    token is recognized wherever `shlex` chooses to break one. A parenthesis
    RESETS the separator rather than becoming one: the first command inside a
    subshell, and the first after one closes, follow no operator of their own.
    """
    if ch in "()":
        return ""
    if ch == "&":
        return "&&" if sep == "&" else "&"
    if ch == "|":
        return "||" if sep == "|" else "|"
    return ch


def _track_case(cases, argv, depth):
    """Open, advance, or close a `case` statement, given one simple command.

    `case` and `esac` reach this the way every other keyword reaches
    `evaluate`'s region counter: as an ordinary word at the head of a simple
    command, behind whatever env assignments and lead words precede it. The
    region answers whether a `cd` sits in a body that may never run, which is
    a different question from the one here -- which `)` characters close a
    PATTERN rather than a subshell -- so the statement is tracked in both
    places rather than one reading the other.

    An entry holds the subshell depth the `case` opened at, whether it stands
    in pattern position, and whether its `in` has been passed. The depth keys
    the parenthesis tests to that case's own level. The third field bounds the
    search for the `in`: a body command can carry that word too (`for f in
    *`), and by then the case has long since passed its own.
    """
    i, _override, _redirected = _lead_prefix(argv)
    if i >= len(argv):
        return
    if argv[i] == "case":
        cases.append([depth, False, False])
    elif argv[i] == "esac" and cases:
        cases.pop()
        return
    if (cases and cases[-1][0] == depth and not cases[-1][2]
            and "in" in argv[i:]):
        cases[-1][1] = True
        cases[-1][2] = True


def _simple_commands(cmd):
    """Split a shell command into `(subshell path, argv, separator)` triples;
    None on error.

    Same construction as `flag-reset-hard-uncommitted-work.py`'s
    `_simple_commands`: join backslash-continued lines, blank heredoc bodies,
    turn unquoted newlines into `;`, then let `shlex` split and dequote.

    The subshell path is this file's own addition, and it costs no second
    parser because `shlex` has already decided which parentheses are
    operators: `git commit -m "fix (typo)"` hands back one token containing
    them, while `(cd /a && true) && git push` hands back `(` and `)` on their
    own (measured 2026-09-04). Tracking those is what stops a subshell's `cd`
    leaking onto a later push.

    The path is a tuple of serial numbers, one per enclosing `(`, so it
    IDENTIFIES the subshell rather than merely counting how deep it sits. A
    depth alone gives two sibling subshells one label, and the first one's
    `cd` then leaks into the second (measured 2026-09-04) --- the leak the
    parentheses were tracked to stop, one shape further along.
    `no-push-without-self-review.py`'s `_depth_segments` counts depth
    character by character, for a caller that needs the segment TEXT rather
    than an argv; it answers the weaker question and neither can be written in
    terms of the other.

    Reading every `)` as a subshell close is what made the path wrong for a
    `case`: its patterns close with the same character, so
    `(cd wt && case a in a) git push;; esac)` popped the parentheses at the
    pattern and recorded the push outside them, losing the `cd` beside it
    (measured 2026-09-04). `_track_case` tracks the statement here as well as
    in `evaluate`'s region counter, and a pattern's `)` pops nothing.

    The separator is the operator immediately BEFORE each simple command, and
    it is what tells a `cd` the shell always reaches from one it may never
    reach: this split knows nothing about short-circuiting, so `cd a || cd b`
    hands back two ordinary `cd` commands (measured 2026-09-04). `evaluate`
    reads it to decline the second rather than apply it.

    The trailing operator is the one immediately AFTER, and it answers a
    question the leading one cannot: `cd a & git push` and `cd a | cat` each
    fork the `cd` into a subshell, and from the operator before it that `cd` is
    indistinguishable from an ordinary one (measured 2026-09-04).

    Two things make that operator survive the shapes a real command is written
    in. It is read as the FIRST operator of its punctuation run rather than
    the run folded down, because a newline becomes `;` here and `cd a &` at
    the end of a line therefore arrives as `&;`. And it propagates BACKWARDS
    across `&&` and `||` within one subshell, because a `&` backgrounds the
    AND-OR list before it rather than its own command alone: in
    `cd a && make & git push` the `cd` is forked too (measured 2026-09-04).
    """
    cmd = re.sub(r"\\\r?\n", " ", cmd)
    cmd = RX_HEREDOC.sub("<<", cmd)
    cmd = cmd.replace("\n", ";")
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return None
    cmds, cur, scopes, opened, sep = [], [], [()], 0, ""
    # The `case` statements still open, innermost last. A case PATTERN closes
    # with the same character a subshell does, so without this
    # `(cd wt && case a in a) git push;; esac)` popped the parentheses at the
    # pattern and read the push in the session's own repository.
    cases = []
    for t in toks:
        if t and set(t) <= _SHELL_OPS:
            trailing = ""
            for ch in t:
                # Only the FIRST operator of a punctuation run is read. A
                # newline becomes `;`, so `cd elsewhere &` at end of line
                # arrives as the single run `&;`, and folding the whole run
                # discarded the `&` that forked the command (measured
                # 2026-09-04).
                if trailing and ch != trailing[-1]:
                    break
                trailing = _next_sep(trailing, ch)
            if cur:
                cmds.append((scopes[-1], cur, sep, trailing))
                _track_case(cases, cur, len(scopes))
                cur = []
                sep = ""
            frozen, prev = False, ""
            for ch in t:
                # A `)` closes a case PATTERN, rather than a subshell, only
                # for the innermost case open at THIS depth and only while
                # that case is in pattern position -- which a `;;` (or a `;&`
                # fallthrough) restores for the clause after it.
                pattern = bool(cases and cases[-1][0] == len(scopes)
                               and cases[-1][1])
                if ch == "(" and not pattern:
                    opened += 1
                    scopes.append(scopes[-1] + (opened,))
                elif ch == ")" and pattern:
                    cases[-1][1] = False
                elif ch == ")" and len(scopes) > 1:
                    scopes.pop()
                elif (ch in ";&" and prev == ";" and cases
                        and cases[-1][0] == len(scopes)):
                    cases[-1][1] = True
                prev = ch
                if ch in "()":
                    sep, frozen = "", False
                elif not frozen:
                    if sep and ch != sep[-1]:
                        frozen = True
                    else:
                        sep = _next_sep(sep, ch)
        else:
            cur.append(t)
    if cur:
        cmds.append((scopes[-1], cur, sep, ""))
    # A `&` backgrounds the whole AND-OR list before it, not only the command
    # it follows, so `cd elsewhere && make & git push` forks the `cd` as well.
    # The trailing operator is therefore propagated backwards across `&&` and
    # `||` inside one subshell: without it that push was read in `elsewhere`,
    # which is ai-config#2451's wrong-repository warning (measured
    # 2026-09-04).
    for i in range(len(cmds) - 1, 0, -1):
        prev, here = cmds[i - 1], cmds[i]
        if here[3] == "&" and prev[3] in ("&&", "||") and prev[0] == here[0]:
            cmds[i - 1] = (prev[0], prev[1], prev[2], "&")
    return cmds


def _lead_prefix(argv):
    """`(index of the first real word, override assigned, git redirected)`.

    Shared with the `cd` scan in `evaluate`, which has to skip the same env
    assignments and shell lead words. `_simple_commands` splits on operators
    only, so a `cd` behind a shell keyword arrives with that keyword still
    attached: `if [ -d w ]; then cd w; git push; fi` yields the argv
    `["then", "cd", "w"]` (measured 2026-09-04). The prefix has to come off
    before the `cd` is visible at all.

    The third element reports a `GIT_DIR=` / `GIT_WORK_TREE=` assignment in
    that prefix rather than merely skipping it, for the reason `_push_argv`
    reads `-C`'s values back out: it moves the repository the push reads, and
    every comparison below is against a ref resolved in one.

    Whether the command sits inside a branch body is NOT reported here, and
    deliberately: a keyword this prefix strips belongs to one simple command,
    while the body it opens may hold several. `evaluate` counts the region
    instead.
    """
    i = 0
    override = False
    redirected = False
    while i < len(argv) and (ASSIGNMENT.match(argv[i]) or argv[i] in LEAD_WORDS):
        if argv[i].startswith(OVERRIDE + "="):
            override = argv[i].split("=", 1)[1].strip() == "1"
        if argv[i].startswith(GIT_ENV_REDIRECT):
            redirected = True
        i += 1
    return i, override, redirected


def _push_argv(argv):
    """The `push`-and-after tokens of a `git push` simple command, whether the
    command was prefixed with the override, and its own `-C` values.
    `(None, False, ())` if this argv is not a `git push`.

    The `-C` values are collected rather than merely skipped because they move
    the directory the push runs in, and `HEAD` is per-worktree -- so
    `git -C <other-worktree> push origin HEAD` resolved against the session's
    own `HEAD` reads an unrelated branch. Git applies each `-C` relative to the
    last, so they are kept in order rather than reduced to the first.

    `--git-dir` and `--work-tree` move the same reading and are NOT resolvable
    the same way, because what they name is a repository rather than a
    directory. A `None` in the returned tuple marks that, and `_push_cwd`
    turns it into the indeterminate answer `cd -` already gets. Both spellings
    are recognized: `--git-dir <dir>` consumes the following token, while
    `--git-dir=<dir>` does not.
    """
    i, override, redirected = _lead_prefix(argv)
    if i >= len(argv) or argv[i] != "git":
        return None, False, ()
    i += 1
    # Skip git's own global options, keeping the `-C` values.
    cdirs = [None] if redirected else []
    while i < len(argv) and argv[i].startswith("-"):
        if argv[i].split("=", 1)[0] in GIT_REPO_OPTS:
            cdirs.append(None)
            i += 2 if argv[i] in GIT_VALUE_OPTS else 1
        elif argv[i] in GIT_VALUE_OPTS:
            if argv[i] == "-C" and i + 1 < len(argv):
                cdirs.append(argv[i + 1])
            i += 2
        else:
            i += 1
    if i >= len(argv) or argv[i] != "push":
        return None, False, ()
    return argv[i + 1:], override, tuple(cdirs)


# `cd` moves the directory a later push runs in; `pushd`/`popd` move it too,
# and this scan does not simulate a directory stack, so they are recognized
# only in order to DECLINE.
CD_WORDS = ("cd", "pushd", "popd")


def _shell_expand(target):
    """`target` with a leading `~` expanded, or `None` for indeterminate.

    Shared by the `cd` scan and the `-C` scan below, because each receives a
    token the SHELL would already have expanded before git ever saw it. A
    `$name` or a command substitution names a directory only a shell can
    produce, and joining it on as a literal path component invents one --
    `git -C "$WT" push` from `/repo` resolving to `/repo/$WT` is a reading
    taken in a directory that exists only if somebody made it (measured
    2026-09-04). A leading `~` is expanded rather than declined, since
    `os.path.expanduser` answers the same question the shell does.
    """
    if "$" in target or "`" in target:
        return None  # unexpanded; resolving it means simulating the shell
    if target.startswith("~"):
        target = os.path.expanduser(target)
        if target.startswith("~"):
            return None  # an unknown user
    return target


def _resolve_cd(argv, cur):
    """The directory `argv` leaves the shell in, or `None` for indeterminate.

    `None` is a real answer rather than a failure: the caller declines the
    reading instead of falling back to the session's own directory, which is
    the substitution this resolution exists to stop.

    Deliberately narrower than `no-push-without-self-review.py`'s
    `_resolve_cd_target`, which resolves the same grammar for a different
    guard. Importing it would give this hook a dependency on a sibling that
    execs a sibling of its own, in a process that starts on every Bash call,
    and the import would fail wherever this file runs as a copy -- including
    this hook's own mutation harness, where the failure would read as a
    behaviour change rather than a missing import. So the forms below are
    resolved the same way and every other form is declined rather than
    guessed.
    """
    if argv[0] != "cd":
        return None  # a directory stack this scan does not simulate
    target = None
    for i, tok in enumerate(argv[1:], start=1):
        if tok == "--":
            target = argv[i + 1] if i + 1 < len(argv) else None
            break
        if tok.startswith("-") and tok != "-":
            continue  # `-P`, `-L`, `-e`, `-@` take no value
        target = tok
        break
    if target is None or target == "-":
        return None  # bare `cd` goes home; `cd -` needs OLDPWD
    target = _shell_expand(target)
    if target is None:
        return None
    if os.path.isabs(target):
        return os.path.normpath(target)
    if cur is None:
        return None
    return os.path.normpath(os.path.join(cur, target))


def _push_cwd(cur, cdirs):
    """Where a push carrying `cdirs` runs, or `None` for indeterminate."""
    for d in cdirs:
        # `--git-dir`/`--work-tree`/`GIT_DIR=` name a repository, which no
        # directory can stand in for -- so the answer is indeterminate.
        if d is None:
            return None
        # A `-C` value reaches git already expanded by the shell, so an
        # unexpanded one is indeterminate for the same reason a `cd`'s is.
        d = _shell_expand(d)
        if d is None:
            return None
        if os.path.isabs(d):
            cur = os.path.normpath(d)
        elif cur is None:
            return None
        else:
            cur = os.path.normpath(os.path.join(cur, d))
    return cur


def _parse_push(rest):
    """Parse a `git push` argument list.

    Returns `(flags, positionals, repo_opt, ok)`.

    `ok` is False when a token could not be classified --- an unrecognized
    short cluster, whose letters might or might not consume the next word. The
    force scan still runs on a not-ok parse (erring toward the refusal, which
    is cheap), while destination resolution does not (erring toward silence,
    since a wrong remote is worse than no remote).
    """
    flags = {"force": False, "lease": False, "dry_run": False,
             "delete": False, "refset": False}
    positionals, repo_opt, ok = [], None, True
    i, end_of_opts = 0, False

    while i < len(rest):
        tok = rest[i]
        i += 1

        if end_of_opts or not tok.startswith("-") or tok == "-":
            positionals.append(tok)
            continue
        if tok == "--":
            end_of_opts = True
            continue

        if tok.startswith("--"):
            name, sep, inline = tok.partition("=")
            negated = name.startswith("--no-")
            base = "--" + name[len("--no-"):] if negated else name

            if base == "--force-with-lease" or name.startswith("--force-with-lease"):
                flags["lease"] = not negated
                continue
            if base in LONG_FLAG:
                flags[LONG_FLAG[base]] = not negated
                continue
            if base in LONG_VALUE_OPTS:
                value = inline if sep else (rest[i] if i < len(rest) else None)
                if not sep:
                    i += 1
                if base == "--repo" and not negated:
                    repo_opt = value
                continue
            continue  # any other long option is a boolean we do not care about

        # A short cluster. Scan left to right; a value-taking letter consumes
        # the cluster's remainder, or the next word when it is the last letter.
        letters = tok[1:]
        for pos, ch in enumerate(letters):
            if ch in SHORT_VALUE:
                if pos == len(letters) - 1:
                    i += 1  # its value is the next word, not the remote
                break
            if ch not in SHORT_BOOL:
                ok = False
                break
            field = SHORT_BOOL[ch]
            if field:
                flags[field] = True

    return flags, positionals, repo_opt, ok


def _git(args, timeout=8, cwd=None):
    """Run a git command in `cwd`; return stdout on success, else None.

    A `cwd` that does not exist raises `FileNotFoundError`, an `OSError`, so a
    stale directory fails open here like every other trouble.
    """
    try:
        out = subprocess.run(["git"] + args, capture_output=True, text=True,
                             timeout=timeout, cwd=cwd)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def _target(positionals, repo_opt, cwd):
    """`(remote, branch, source, on_source)` the push is aimed at, or all-`None`.

    Handles the shapes that occur: a bare `git push`, `git push origin`,
    `git push origin HEAD`, `git push origin <branch>`, `git push -u origin
    HEAD`, `git push origin HEAD:branch`, a leading `+`, and `--repo
    <repository>`.

    `source` is the LOCAL ref being pushed, and it is not always `HEAD`.
    `git push origin feature-x` run while `main` is checked out pushes local
    `feature-x`, so comparing the remote tip against `HEAD` compares it against
    the wrong branch -- silently, and in both directions: a remote commit that
    happens to be an ancestor of `main` reads as a fast-forward while local
    `feature-x` genuinely diverges, which is a false negative in the exact
    situation this guard exists for.

    `on_source` says whether the ref being pushed IS the checked-out one, and
    it is computed by comparing `source` against the resolved head rather than
    by testing `source == "HEAD"`. Those differ: the `"HEAD"` sentinel appears
    only when the refspec omits a source, so `git push origin main` run on
    `main` yields `source == "main"` -- it would fail a sentinel test while
    being the same branch, and the advice would then tell a reader to check out
    the branch they are already on.

    Returns all-`None` rather than a guess whenever the destination is not a
    single named branch --- a wildcard refspec, a deletion refspec, or a
    detached HEAD with nothing to name. A wrong branch here would send
    `ls-remote` at the wrong ref and report on something the push never
    touches, which is worse than reporting nothing.
    """
    head = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    head = head.strip() if head else None
    if head == "HEAD":
        head = None  # detached; no branch to reason about

    # `--repo <repository>` names the remote when no positional one does, so
    # the first positional is then the refspec rather than the remote.
    if repo_opt:
        remote, specs = repo_opt, positionals
    elif positionals:
        remote, specs = positionals[0], positionals[1:]
    else:
        remote, specs = None, []

    if remote is None:
        remote = "origin"
        if head:
            up = _git(["config", "--get", f"branch.{head}.remote"], cwd=cwd)
            if up and up.strip():
                remote = up.strip()

    if not specs:
        return remote, head, "HEAD", True
    if len(specs) > 1:
        return None, None, None, None  # several refspecs; no branch

    spec = specs[0].lstrip("+")
    if ":" in spec:
        src, dst = spec.split(":", 1)
    else:
        src = dst = spec
    if dst.startswith("refs/heads/"):
        dst = dst[len("refs/heads/"):]
    if dst == "HEAD":
        dst = head
    return remote, dst, src, src in ("HEAD", head)


DENY = (
    "This is a bare `git push --force`. It overwrites the remote branch tip "
    "unconditionally -- including commits pushed by another agent since you "
    "last looked.\n\n"
    "  command:  {segment}\n\n"
    "A branch you cut, whose PR you opened, and whose review you are driving "
    "is exactly the branch this happens on: ownership is what suppresses the "
    "check. The `@claude` agent pushes to your branch on PR activity, a "
    "second CLI session can claim the same PR, and a human can push to it -- "
    "`shared/workflow/claim-pr.md` records all three.\n\n"
    "Use the lease instead:\n\n"
    "    git push --force-with-lease --force-if-includes\n\n"
    "`--force-with-lease` refuses when the remote tip is not the one your "
    "remote-tracking ref names. `--force-if-includes` (git 2.30+) is the half "
    "usually left off, and without it the lease is defeatable: the lease "
    "compares against your remote-tracking ref, so ANY background `git fetch` "
    "-- a poller, another tool in the same checkout, a `--recurse-submodules` "
    "fetch -- silently refreshes that ref, and the lease then passes over the "
    "very commits it existed to protect. `--force-if-includes` additionally "
    "checks the remote-tracking tip against the local branch's REFLOG, so a "
    "fetch you never saw no longer satisfies the lease.\n\n"
    "Where the remote ref does not exist, the lease succeeds trivially -- so "
    "this is never the worse command.\n\n"
    "A `stale info` refusal is NOT a reason to force. `memories/git-branches.md` "
    "records that case -- a squash-merge with auto-delete removed the branch "
    "your ref still names -- and states that the lease is unsatisfiable "
    "rather than violated, so `--force` is unnecessary and there is nothing "
    "to race. One read settles it: `git ls-remote --heads origin <branch>`, "
    "where empty output means the next push CREATES the branch, so a plain "
    "push is the fix (or `git fetch --prune` and a retry).\n\n"
    "`ALLOW_FORCE_PUSH=1` (a real env assignment, not a mention) is an escape "
    "valve for a case this guard did not foresee, not a shortcut for a known "
    "one. If you reach for it, say what the lease refused and why forcing is "
    "right -- and if the answer is `stale info`, it is not."
)

WARN_HEAD = (
    "Checked `{remote}/{branch}` just now with `git ls-remote`: its tip is "
    "**{tip}**, which is NOT an ancestor of {srclabel} ({local}){where}.\n\n"
    "  command:  {segment}\n\n"
)

WARN_KNOWN = (
    "{n} commit(s) on the remote are not in what you are about to push:\n\n"
    "{commits}\n\n"
)

WARN_UNKNOWN = (
    "That commit is not in your local object store at all, which is the "
    "sharper signal rather than the weaker one: the remote moved after your "
    "last fetch and you cannot see what is there.\n\n"
)

WARN_TAIL = (
    "Somebody else is driving this branch -- most likely the `@claude` agent "
    "reacting to PR activity, or a second session that claimed the PR. A "
    "plain push will be rejected; a forced one would discard the commits "
    "above.\n\n"
    "Reconcile rather than overwrite:\n\n"
    "{reconcile}\n"
    "Before deciding it is your own earlier work, compare trees and parents -- "
    "`shared/workflow/claim-pr.md` distinguishes an identical merge (reset onto "
    "it) from a differently-resolved one (merge the two commits, never reset)."
)


def _describe(local, tip, cwd, limit=10):
    """Formatted commit list for `local..tip`, or None if the object is absent."""
    if _git(["cat-file", "-e", tip + "^{commit}"], timeout=5, cwd=cwd) is None:
        return None
    out = _git(["log", "--format=    %h  %an, %ar  %s", f"{local}..{tip}"],
               timeout=5, cwd=cwd)
    if out is None:
        return None
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if not lines:
        return None
    shown = lines[:limit]
    text = "\n".join(shown)
    if len(lines) > limit:
        text += f"\n    ... and {len(lines) - limit} more"
    return len(lines), text


def evaluate(command, base_cwd=None, deny_only=False,
             assume_override=False):
    """`('deny', reason)`, `('warn', context)`, or `None`.

    `deny_only` runs Pass 1 and stops: refusals are decidable from the command
    TEXT, while warnings need `git ls-remote` reads against a directory. A
    NESTED piece has no knowable directory, so it gets this.

    `assume_override` treats the caller as having supplied
    `ALLOW_FORCE_PUSH=1`, which is how an override written before a WRAPPER
    reaches the push inside it -- `_lead_prefix` reads an assignment only from
    a simple command's own head, and the nested piece's text does not carry
    the prefix. It DISABLES the deny path, so it is the one argument here that
    changes a verdict rather than narrowing which verdicts are reachable, and
    `evaluate_every_shell` is its only caller.

    `base_cwd` is the directory the Bash call starts in -- the payload's own
    `cwd` -- and a `cd` earlier in the same compound command moves it, as the
    push's own `git -C` moves it again. It is threaded through every read
    below rather than left to the hook process's own directory, because `HEAD`
    is per-worktree and this guard's whole output is a comparison against it.

    A `cd` is scoped to its subshell, so the directory is kept per SUBSHELL
    rather than as one value: a subshell inherits its caller's directory the
    first time a command runs inside it, and nothing it does is read back out.
    Without that, a `cd` inside `(...)` leaked onto every later push in the
    command; keyed on nesting depth instead of on identity, it leaked into the
    next sibling subshell rather than out of the parentheses.

    A `cd` the shell may never REACH, and one it reaches in a subshell of its
    own, are declined rather than applied, which is the answer `cd -` already
    gets. `_simple_commands` splits on operators and models neither
    short-circuiting nor forking, so each arrives as an ordinary `cd` command:
    applying them read `if ...; then cd elsewhere; fi; git push`,
    `cd here || cd elsewhere; git push`, `cd elsewhere & git push` and
    `cd elsewhere | cat; git push` in `elsewhere`, where no shell ever puts
    the push (measured 2026-09-04).

    A compound statement's body is counted as a REGION rather than recognized
    by its keyword, because a keyword attaches to one simple command while a
    body may hold several: with the keyword alone,
    `if ...; then echo no; cd elsewhere; fi` was applied while the
    one-command body beside it was declined (measured 2026-09-04).

    The CONDITION that opens such a statement is declined by its own test,
    because it shares one argv with the keyword and so is never a command the
    region sees: `if cd elsewhere; then git push; fi` read the push in the
    session's own repository (measured 2026-09-04).

    Where the reading ends up in a different directory from `base_cwd`, the
    warning SAYS so and emits its remediation commands with `git -C`, because
    the reader's shell is still in `base_cwd`: a bare `git merge origin/<b>`
    handed to a shell sitting somewhere else merges the wrong branch, which is
    the harm ai-config#2451 reported rather than a wording preference.

    TWO passes over the compound command, deliberately, and the refusal pass
    runs first.

    A single pass returning on the first verdict let a `warn` on an earlier
    push suppress the `deny` a later one deserved:
    `git push origin diverged; git push --force origin mine` returned `warn`,
    which attaches context and does NOT block, so the bare force push ran.
    A refusal blocks the whole Bash call regardless of position, so scanning
    every simple command for one before reporting any warning is both correct
    and cheaper -- the refusal is decided from the command text alone and
    spends no network read.
    """
    cmds = _simple_commands(command)
    if cmds is None:
        return None

    parsed = []
    base = base_cwd or os.getcwd()
    # `subshell path -> directory`. A path is entered ONCE, inheriting its
    # caller's directory as of that moment, and is never revisited after the
    # `)` closes: a later sibling `(` gets a fresh serial number, so it starts
    # from the caller's directory rather than from what its predecessor moved
    # to.
    dirs = {(): base}
    # Subshell paths carrying an exported override, grown as the split is
    # read. Without it the guard was strictly MORE PERMISSIVE for a wrapped
    # push than a bare one: `export ALLOW_FORCE_PUSH=1; bash -c "<push>"` was
    # cleared by `_override_before_wrapper` while
    # `export ALLOW_FORCE_PUSH=1; git push --force origin main` was refused,
    # although bash sets the variable for both (measured `inner=[1]`). An
    # escape hatch that works only once the command is wrapped teaches
    # wrapping (ai-config#3645 pre-merge gate, finding 4).
    exported = []
    # How many compound-statement bodies enclose the command being read. The
    # count is flat rather than per-subshell because these regions nest
    # lexically, in the order the split hands them back.
    region = 0
    for scope, argv, sep, after in cmds:
        for n in range(1, len(scope) + 1):
            dirs.setdefault(scope[:n], dirs[scope[:n - 1]])
        lead, _override, _redirected = _lead_prefix(argv)
        head = argv[lead:]
        if head and head[0] in BLOCK_OPEN:
            # The CONDITION shares this argv with the keyword that opens the
            # region, and it runs in the current shell rather than in the body
            # the region declines -- so `if cd elsewhere; then git push; fi`
            # really does move the push. Leaving it unseen read that push in
            # the session's own repository (measured 2026-09-04). It is
            # DECLINED rather than resolved, because where the shell ends up
            # after `fi` depends on whether the condition succeeded.
            cond = head[1:]
            skip, _o, _r = _lead_prefix(cond)
            if skip < len(cond) and cond[skip] in CD_WORDS:
                dirs[scope] = None
            region += 1
        elif head and head[0] in BLOCK_CLOSE:
            region = max(region - 1, 0)
        if head and head[0] in CD_WORDS:
            if region or sep in BRANCH_SEPS or after in FORK_SEPS:
                dirs[scope] = None
            else:
                dirs[scope] = _resolve_cd(head, dirs[scope])
            continue
        _record_export(exported, scope, argv, sep, after, region)
        rest, override, cdirs = _push_argv(argv)
        if rest is None:
            continue
        override = override or _scope_exported(scope, exported)
        flags, positionals, repo_opt, ok = _parse_push(rest)
        parsed.append((argv, flags, positionals, repo_opt, ok, override,
                       _push_cwd(dirs[scope], cdirs)))

    # Pass 1 -- refusal. Lexical, so no network read, and any command in the
    # compound counts. It is deliberately blind to the directory: `--force` is
    # a force push wherever it runs, so nothing about the refusal depends on
    # resolving one.
    for argv, flags, _pos, _repo, _ok, override, _cwd in parsed:
        if (flags["force"] and not flags["dry_run"] and not override
                and not assume_override):
            return "deny", DENY.format(segment=" ".join(argv))

    # `deny_only` stops here. Pass 1 is lexical and directory-blind, so it is
    # sound for a command whose starting directory is not knowable; Pass 2 is
    # neither, and its own note below says what happens when it reads against
    # the wrong repository. `evaluate_every_shell` passes it for nested pieces.
    if deny_only:
        return None

    # Pass 2 -- the reading. Only reached when nothing is refused.
    for argv, flags, positionals, repo_opt, ok, _override, cwd in parsed:
        segment = " ".join(argv)

        # An indeterminate directory declines the reading rather than falling
        # back to the hook's own. A comparison against the wrong repository is
        # exactly what ai-config#2451 reported, and it is worse than silence:
        # it names a cause and prescribes a merge.
        if cwd is None:
            continue

        # Everything below reports on ONE branch, so anything that is not one
        # ordinary branch push is out of scope rather than guessed at.
        if flags["dry_run"] or flags["delete"] or flags["refset"] or not ok:
            continue

        remote, branch, source, on_source = _target(positionals, repo_opt, cwd)
        if not remote or not branch:
            continue
        # `source` is deliberately NOT tested for emptiness here. An empty
        # source is `git push origin :main`, a deletion, and the `rev-parse
        # --verify` below already declines it (`^{commit}` resolves to
        # nothing). Testing it twice would leave whichever check ran first
        # untestable, which is what the removed wildcard guard did.

        # Resolve the LOCAL side first, before spending a network read.
        #
        # It is the ref being PUSHED, which is `HEAD` only when the refspec
        # says so. Resolving it as `HEAD` unconditionally compared
        # `origin/feature-x` against `main` on any `git push origin
        # feature-x`, and read a remote commit that happened to be an ancestor
        # of `main` as a fast-forward -- a false negative in the exact
        # situation this guard exists for.
        #
        # It doubles as the "is this one ordinary branch" test, which is why
        # there is no separate check for a deletion or wildcard refspec: the
        # source of `origin :main` is empty and the source of
        # `refs/heads/*:refs/heads/*` contains a `*`, and `git rev-parse
        # --verify` resolves neither (measured: both exit 1 with no output).
        local = _git(["rev-parse", "--verify", "--quiet", source + "^{commit}"],
                     timeout=5, cwd=cwd)
        if not local:
            continue  # names no single local ref -- fail open, no network read
        local = local.strip()

        ls = _git(["ls-remote", "--heads", remote, branch], timeout=8, cwd=cwd)
        if not ls or not ls.strip():
            continue  # ref absent remotely, or the read failed -- fail open
        tip = ls.split()[0]

        if tip == local:
            continue

        anc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", tip, local],
            capture_output=True, text=True, timeout=5, cwd=cwd)
        if anc.returncode == 0:
            continue  # plain fast-forward; nothing at risk

        # Name the ref actually compared. Saying "your local HEAD" here was
        # wrong in precisely the case the source-ref fix exists for: on
        # `git push origin feature-x` from `main` it labelled `feature-x`'s
        # tip as HEAD, so a reader would reconcile against the wrong branch.
        srclabel = ("your local HEAD" if source == "HEAD"
                    else f"your local `{source}`")
        # The reading was taken where the PUSH runs, which is not where the
        # READER's shell is when a `cd` or a `-C` moved it. Naming the
        # directory once, and prefixing every remediation command with it, is
        # what makes the advice runnable from the call's own directory:
        # `git merge origin/<branch>` typed there merges into whatever is
        # checked out THERE, which is the branch-into-itself merge of
        # ai-config#2451 with the directory axis substituted for the ref one.
        moved = os.path.realpath(cwd) != os.path.realpath(base)
        where = f", read in `{cwd}`" if moved else ""
        # `shlex.quote`, because a worktree path may carry a space: an
        # unquoted `git -C /home/u/My Worktrees/wt` is read by git as
        # `-C /home/u/My` plus stray arguments, so the advice this block
        # exists to make runnable is not.
        gitc = f"git -C {shlex.quote(cwd)} " if moved else "git "
        body = WARN_HEAD.format(remote=remote, branch=branch, tip=tip[:12],
                                local=local[:12], segment=segment,
                                srclabel=srclabel, where=where)
        described = _describe(local, tip, cwd)
        if described:
            n, commits = described
            body += WARN_KNOWN.format(n=n, commits=commits)
        else:
            body += WARN_UNKNOWN
        # The remediation commands must operate on the ref being pushed, for
        # the same reason the label above does. Emitting
        # `git merge origin/feature-x` while `main` is checked out merges
        # `feature-x`'s remote content INTO `main` -- wrong branch, and
        # destructive, in precisely the scenario this guard exists for.
        if on_source:
            reconcile = (f"    {gitc}fetch origin {branch}\n"
                         f"    {gitc}log --oneline {source}..origin/{branch}\n"
                         f"    {gitc}merge origin/{branch}"
                         "      # or rebase, if the branch is yours alone\n")
        else:
            reconcile = (f"    {gitc}fetch origin {branch}\n"
                         f"    {gitc}log --oneline {source}..origin/{branch}\n"
                         f"    {gitc}checkout {source}"
                         "      # you are not on the branch being pushed\n"
                         f"    {gitc}merge origin/{branch}"
                         "      # or rebase, if the branch is yours alone\n")
        body += WARN_TAIL.format(branch=branch, reconcile=reconcile)
        return "warn", body

    return None


def _override_by_piece(command, _depth=0):
    """Each nested command line in COMMAND, mapped to whether the override reaches it.

    WHY A MAP AND NOT A BOOL
    -----------------------
    This used to be `_override_before_wrapper(command) -> bool`, and
    `evaluate_every_shell` passed that one answer as `assume_override` for
    EVERY nested piece. A prefix assignment is scoped by bash to the single
    command it heads, so one legitimately-authorized wrapped push silently
    authorized an unrelated one in the same compound command:

        ALLOW_FORCE_PUSH=1 sh -c "git push --force origin scratch"
        sh -c "git push --force origin main"                    <- silent

    Real bash sets nothing for the second (`inner=[]`), and the push ran
    unexempted. `shell_c_expansions` returns a flat, deduplicated list with no
    back-reference to the simple command that produced each piece, so the
    caller could not have scoped it (ai-config#3645 review round 4).

    The two arms differ exactly here, which is why flattening them was wrong.
    A PREFIX assignment reaches only the pieces of its own argv. An `export`
    reaches every later command in the same shell, so it reaches their pieces
    too -- verified: `bash -c 'export ALLOW_FORCE_PUSH=1; bash -c "true";
    sh -c "echo inner=[$ALLOW_FORCE_PUSH]"'` prints `inner=[1]`.

    A repeated piece takes the AND of its producers. Two simple commands can
    yield the same text with only one of them authorized, and the refusal is
    the answer that costs a re-spelling rather than a force push.

    WHAT THE PREFIX ARM IS FOR
    --------------------------
    The first version searched the raw text for the assignment anywhere, with
    a comment claiming it "only ever decides whether to carry the author's own
    escape hatch onto a nested piece they wrapped". It decided it for a
    MENTION: a commit message, a shell comment, a heredoc body, a `grep`
    argument. This repository documents the variable by name in `CLAUDE.md`
    and `hooks/README.md`, so quoting it is the ordinary case, and each of
    those silenced the nested refusal on a command that really force-pushes
    (ai-config#1973 review, round 3 finding 3).

    This module already ruled that out 800 lines above, at `OVERRIDE`: "counts
    only as a real env assignment at the start of the same simple command,
    never as a mention of the string elsewhere ... a guard that its own
    documentation disables is worthless."

    So the question is asked of the parsed argv, not of the text. "Some simple
    command" was the earlier answer and was still too loose, by exactly the
    margin that matters: bash scopes a prefix assignment to the one command it
    heads, so `ALLOW_FORCE_PUSH=1 echo hi; sh -c "<push>"` never sets the
    variable for the wrapped `git` -- verified against real bash, which prints
    an empty `inner=[]` -- and yet it cleared the nested refusal
    (ai-config#1973 review, round 4 finding 2). Scoping the map by argv is the
    same fix carried one step further.
    """
    out = {}
    if nested_shell_commands is None or _depth >= _OVERRIDE_PIECE_DEPTH:
        return out
    scoped = _simple_commands(command)
    if scoped is None:
        return out
    exported = []
    # The compound-statement REGION, counted for the same reason `evaluate`
    # counts it: an `export` inside an `if`/`while`/`for`/`case` body may never
    # run. Leaving it out relied on the body's keyword still heading the argv,
    # which holds only while the export is the body's FIRST command -- one
    # `echo` in front detaches it (ai-config#3645 self-review, finding 1).
    region = 0
    for scope, raw, sep, after in scoped:
        argv = list(raw)
        # `env VAR=1 bash -c "<push>"` really does set the variable for the
        # inner `git`, and was refused with no way to comply (round 4 finding
        # 8). A leading wrapper run is skipped so the assignment behind it
        # still reads as a prefix.
        while argv and os.path.basename(argv[0]) in COMMAND_WRAPPERS:
            argv = argv[1:]
        reaches = _prefix_override(argv) or _scope_exported(scope, exported)
        # The pieces come from the UNSTRIPPED argv, because
        # `nested_shell_commands` resolves the program through
        # `command_program`, whose bounded look-ahead handles a wrapper with
        # its own arguments -- `timeout 5 bash -c ...` -- that the `while`
        # strip above cannot. Walking the stripped argv instead made this map
        # disagree with `shell_c_expansions`' own walk, and a piece the map
        # never saw defaulted to no override: deny-preserving, but it meant a
        # verdict reached by accident rather than by the prefix rule, and the
        # clause pinning that rule stopped discriminating.
        for piece in nested_shell_commands(raw):
            out[piece] = out.get(piece, True) and reaches
            for sub, sub_reaches in _override_by_piece(piece, _depth + 1).items():
                out[sub] = out.get(sub, True) and (reaches or sub_reaches)
        lead, _o, _r = _lead_prefix(raw)
        head = raw[lead:]
        if head and head[0] in BLOCK_OPEN:
            region += 1
        elif head and head[0] in BLOCK_CLOSE:
            region = max(region - 1, 0)
        _record_export(exported, scope, raw, sep, after, region)
    return out


# Matches `shell_c_expansions`' own `max_depth`, since the two walks have to
# reach the same set of pieces -- a piece the map never sees defaults to NO
# override, which is deny-preserving but would refuse a legitimate hatch.
_OVERRIDE_PIECE_DEPTH = 3


def _prefix_override(argv):
    """True when a real `ALLOW_FORCE_PUSH=1` heads ARGV as a prefix assignment.

    Only a CONTIGUOUS RUN of assignments from the argv head is a prefix.
    Scanning a window instead found the token wherever it sat, so
    `echo "ALLOW_FORCE_PUSH=1" && sh -c "<push>"` disabled the refusal -- the
    same mention-anywhere hole one step in from the text.
    """
    for index, token in enumerate(argv[:_OVERRIDE_PREFIX_WINDOW]):
        if not ASSIGNMENT.match(token):
            return False
        name, _, value = token.partition("=")
        # `.strip()` and not `.strip("\"'")`, which disagreed with
        # `_lead_prefix`'s test in BOTH directions for the same variable in the
        # same file: shlex has already dequoted, so stripping quote CHARACTERS
        # accepted a value bash sets to `'1'` while rejecting the ` 1 ` that
        # `_lead_prefix` accepts (round 4 finding 12).
        if name == OVERRIDE and value.strip() == "1":
            return True
    return False


def _scope_exported(scope, exported):
    """True when an `export` recorded in EXPORTED reaches a command in SCOPE.

    An export reaches its own shell and every subshell opened underneath it,
    which is exactly "the exporting scope is a PREFIX of this one". Sibling
    subshells carry different serial numbers, so `(1,)` is not a prefix of
    `(2,)` and one sibling's export does not leak into the next.
    """
    return any(scope[:len(done)] == done for done in exported)


# Separators that leave an `export` possibly unexecuted. Wider than
# `evaluate`'s `BRANCH_SEPS`, and deliberately so: the two readers fail in
# OPPOSITE directions. Reading a `cd` that did not run yields an indeterminate
# directory, which declines the reading and is safe; reading an `export` that
# did not run SUPPRESSES A REFUSAL. So `&&` counts here although `evaluate`
# omits it -- `false && export ALLOW_FORCE_PUSH=1` runs nothing. The FORKING
# separators are the same set `evaluate` uses, and are reused rather than
# restated.
_EXPORT_CONDITIONAL_SEPS = {"&&", "||", "|"}


def _record_export(exported, scope, raw, sep, after, region=0):
    """Append SCOPE to EXPORTED when RAW really exports the override there.

    RAW is the unstripped argv, and the wrapper strip happens HERE so both
    callers apply the same rule. It deliberately skips only
    `COMMAND_WRAPPERS`, never a shell KEYWORD: `then export ALLOW_FORCE_PUSH=1`
    arrives with the keyword attached, and stripping it would record an export
    the shell may never reach. `region` is the same guard said explicitly, for
    a body whose keyword has already come off.

    Unlike a prefix assignment, an export reaches every LATER command in the
    same shell:

        $ bash -c 'export ALLOW_FORCE_PUSH=1; bash -c "echo [$ALLOW_FORCE_PUSH]"'
        [1]

    Refusing it left the escape hatch unusable in its most natural spelling,
    with no way to comply (ai-config#1973 review, round 4 finding 8, second
    half; reproduced independently by the @claude review of #3645).

    Honouring it by POSITION ALONE was that fix's own fail-open. It asked "did
    an export appear before this command in the token stream", which is a
    weaker question than "does bash set the variable for it", and two shapes
    cleared a refusal bash never authorized -- each measured with an empty
    `inner=[]` from real bash and the push still executing (ai-config#3645
    pre-merge gate, finding 1):

        ( export ALLOW_FORCE_PUSH=1 ); sh -c "<push>"
        false && export ALLOW_FORCE_PUSH=1; sh -c "<push>"

    So an export counts only when it is UNCONDITIONALLY REACHED, and it then
    covers its own subshell path and everything nested under it.
    """
    argv = list(raw)
    while argv and os.path.basename(argv[0]) in COMMAND_WRAPPERS:
        argv = argv[1:]
    if not argv:
        return
    # RETIRING RUNS FIRST, and unconditionally. Recording an override and
    # never taking it back read `export ALLOW_FORCE_PUSH=1` as permanent, so
    # `export ALLOW_FORCE_PUSH=1; export ALLOW_FORCE_PUSH=0; git push --force`
    # dropped from a refusal to a non-blocking warning while bash ran the push
    # with the variable set to `0` (ai-config#3645 self-review, finding 2).
    #
    # Deliberately unconditional, where RECORDING is guarded: a retirement the
    # shell never reaches costs a refused escape hatch, and a recording the
    # shell never reaches costs a suppressed refusal. Same reasoning as
    # `_EXPORT_CONDITIONAL_SEPS`, applied to the other half of the pair.
    if _retires_override(argv):
        exported[:] = [done for done in exported if scope[:len(done)] != done]
        return
    if os.path.basename(argv[0]) != "export":
        return
    if region or sep in _EXPORT_CONDITIONAL_SEPS or after in FORK_SEPS:
        return
    # No value test here: `_retires_override` above returns True for EVERY
    # value other than `1`, so an `export ALLOW_FORCE_PUSH=<anything else>`
    # has already returned. Repeating the test read as defence in depth and
    # was measured unreachable -- reverting it left the suite at 89/89, which
    # is this branch's own definition of an untested clause.
    for token in argv[1:]:
        if not ASSIGNMENT.match(token):
            continue
        if token.partition("=")[0] == OVERRIDE:
            exported.append(scope)


# Words that put a variable into the environment. Only `export` RECORDS an
# override, because only it is measured; all of them RETIRE one, since the
# retiring direction is the safe one to over-apply.
_EXPORT_WORDS = ("export", "declare", "typeset", "readonly")


def _retires_override(argv):
    """True when ARGV sets the override to something other than `1`, or unsets it.

    A PREFIX assignment is deliberately not one: `ALLOW_FORCE_PUSH=0 echo hi`
    scopes the value to `echo` and leaves the shell's own variable alone, so
    only a command that is NOTHING BUT assignments changes the shell.

    Over-retires across subshell boundaries, which is the safe direction:
    `export ALLOW_FORCE_PUSH=1; ( unset ALLOW_FORCE_PUSH ); git push --force`
    really does leave the parent's variable set, and is refused here. The cost
    is a re-spelling; the cost of the opposite error is an unguarded force
    push.
    """
    word = os.path.basename(argv[0])
    if word == "unset":
        return any(token == OVERRIDE for token in argv[1:])
    if word in _EXPORT_WORDS:
        tokens = argv[1:]
    elif all(ASSIGNMENT.match(token) for token in argv):
        tokens = argv
    else:
        return False
    for token in tokens:
        if not ASSIGNMENT.match(token):
            continue
        name, _, value = token.partition("=")
        if name == OVERRIDE and value.strip() != "1":
            return True
    return False


# How far into a simple command an assignment may sit and still be a prefix.
# `FOO=1 BAR=2 ALLOW_FORCE_PUSH=1 bash -c ...` is three assignments and a
# command; beyond a few the token is not a prefix any more.
_OVERRIDE_PREFIX_WINDOW = 6


def evaluate_every_shell(command, base_cwd=None):
    """`evaluate` over COMMAND, plus a DENY-ONLY pass over each nested shell.

    WHY
    ---
    This guard tokenizes and compares exact tokens, so wrapping the push in an
    interpreter's `-c` argument bypassed it outright: `shlex` collapses the
    embedded command into ONE opaque token, `argv[0]` is the interpreter, and
    every `== "git"` comparison fails immediately. Measured on `main`
    (ai-config#1973): `git push --force origin main` denies, and
    `sh -c "git push --force origin main"` is silently allowed.

    WHY THE NESTED PIECES ARE DENY-ONLY
    -----------------------------------
    A nested `-c` argument is a different shell, and this module's whole output
    is a comparison against a HEAD, so every reading depends on which directory
    that shell starts in. `shell_c_expansions` cannot say: the answer depends
    on the `cd`s the outer shell ran first, which live in the outer analysis.

    Evaluating a nested piece fully anyway did exactly what Pass 2's own note
    warns about. Measured across two repositories: `cd B && sh -c "git push
    origin br0"` produced a warning quoting repository A's commits, about a
    push that is a clean fast-forward in a repository the command never
    touches -- and the mirrored case suppressed a warning that was genuinely
    owed. "A comparison against the wrong repository ... is worse than
    silence: it names a cause and prescribes a merge" is that note, and a
    fabricated one is worse still.

    So a nested piece contributes only what Pass 1 decides: a refusal, which is
    lexical, directory-blind, and true wherever the command runs. `--force` is
    a force push in any directory.

    That also settles the cost. A full `evaluate` per piece spends Pass 2's
    `git ls-remote` reads, each with an 8-second timeout, BEFORE reaching a
    refusal in a later piece -- measured at 11 reads ahead of one deny, where
    the flat path spends none. Pass 1 spends nothing, so the descent adds no
    network work at all.

    WHAT THIS STILL CANNOT SEE
    --------------------------
    A nested push that deserves a WARNING is not warned about, because the
    directory is unknowable. That is a real gap and it is the honest side of
    the trade: the alternative is a warning whose central claim may be false.
    Resolving it needs the `cd` stack and the nested pieces reconciled into one
    analysis, which is ai-config#3178's shape of change rather than this one's.

    A `ssh host "<push>"`, a shell function, an `eval`, and a command built
    from a variable remain invisible, as they are to the reference
    implementation in `hooks/no-empty-promise.py`.
    """
    pieces = []
    if shell_c_expansions is not None:
        try:
            pieces = shell_c_expansions(command)[1:]
        except Exception as exc:  # never let the descent break the base guard
            print(f"no-clobbering-push: could not expand nested shells ({exc}); "
                  f"evaluating the outer command only", file=sys.stderr)
            pieces = []

    # REFUSALS FIRST, across the outer command AND every nested piece, before
    # any reading. `evaluate`'s own docstring states the invariant -- "a
    # refusal blocks the whole Bash call regardless of position, so scanning
    # every simple command for one before reporting any warning is both
    # correct and cheaper" -- and running the full outer `evaluate` first broke
    # it at the outer/nested boundary: a nested refusal was reached only after
    # the outer command's Pass 2 had spent its `git ls-remote` reads, measured
    # at 3 reads (8s timeout each) ahead of one deny (ai-config#1973 review,
    # round 2 finding 3).
    #
    # `ALLOW_FORCE_PUSH=1` written before the WRAPPER really reaches the inner
    # `git`, but `_lead_prefix` reads an override only from the same simple
    # command, so a wrapped push was refused with no way to comply -- the
    # escape hatch this module's docstring calls "the escape hatch" silently
    # stopped working the moment the push was wrapped (round 2 finding 7).
    # Carrying the outer override onto each piece restores it. The reading is
    # deliberately loose, matching this module's existing choice on the same
    # question: "a refused override sends the author looking for a bypass".
    overrides = _override_by_piece(command)
    # The OUTER command is deliberately not in this loop. It used to be, with
    # a `piece is not command` guard keeping the carried override off it --
    # and that guard was unobservable, because the unconditional
    # `evaluate(command, base_cwd)` below re-checks the outer command anyway
    # without the flag, so an over-broad carry could only ever delay the same
    # refusal by one call. Dropping the guard left the suite at 78/78, which
    # is this branch's own definition of an untested clause
    # (ai-config#1973 review, round 4 finding 10).
    #
    # Iterating the nested pieces only removes both the guard and the
    # redundant pass, and says plainly what the loop is for.
    for piece in pieces:
        # An override carried onto a nested piece is passed as a FLAG, not
        # prefixed to the text. `VAR=1 bash -c "a && b"` exports the variable
        # to every command in the piece, while `_lead_prefix` reads one only
        # from a simple command's own head -- so prefixing the piece as a whole
        # exempted the first push and denied the second, with no way to comply
        # (ai-config#1973 review, round 3 finding 7). Rebuilding the text to
        # prefix each simple command means re-serializing a parse, which is the
        # kind of round trip that loses a `&&`.
        refusal = evaluate(piece, base_cwd, deny_only=True,
                           assume_override=overrides.get(piece, False))
        if refusal is not None:
            return refusal

    return evaluate(command, base_cwd)


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
            return {"tool_name": "Bash", "tool_input": {"command": raw_cmd}}, True

    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception as exc:
        print(f"no-clobbering-push: unreadable hook input ({exc})",

              file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0

    if payload.get("tool_name") not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    inp = payload.get("tool_input") or {}
    command = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script")
    if not isinstance(command, str) or not command.strip():
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    try:
        verdict = evaluate_every_shell(command, payload.get("cwd"))
    except Exception as exc:  # fail open on any parse or subprocess trouble
        print(f"no-clobbering-push: could not evaluate command ({exc})",
              file=sys.stderr)
        return 0

    if verdict is None:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    kind, text = verdict
    hso = {"hookEventName": "PreToolUse"}
    if kind == "deny":
        hso["permissionDecision"] = "deny"
        hso["permissionDecisionReason"] = text
    else:
        hso["additionalContext"] = text
    print(json.dumps({"hookSpecificOutput": hso}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
