#!/usr/bin/env python3
"""Tests for scripts/lib/shellcmd.py.

The module is a shell-command classifier used by a DENY guard, so its blind
spots become that guard's silences. Two families carry the weight:

  * QUOTING -- the whole reason this is an argv split. A `git push` inside a
    commit message, a heredoc body, or an `echo` must never be a command word.
  * WRAPPERS -- the whole reason `strip_env` exists. A spelling that
    `hooks/no-push-without-self-review.py` resolves and this module does not is
    a call that guard denies while its partner stays silent, which is precisely
    the failure the partner exists to prevent.

Run:  python3 scripts/test_shellcmd.py
"""
import os
import py_compile
import sys
import tempfile
import time
import warnings

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))

import shellcmd  # noqa: E402

failures = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def descends_to(command, nested):
    """Is `nested` among the command lines the descent reaches from `command`?

    Membership rather than an exact list, because `nested_shell_commands`
    deliberately OVER-DETECTS: when the program is a shell and a `-c`-shaped
    flag is present, every later token is a candidate. A candidate that is not
    a command line costs the caller one scan that finds nothing, while a missed
    one is an unguarded destructive command -- so the contract is "reaches at
    least", not "reaches exactly".
    """
    return nested in shellcmd.shell_c_expansions(command)[1:]


def subs(command):
    """The ordered git subcommands the splitter finds at command positions."""
    cmds = shellcmd.simple_commands(command)
    if cmds is None:
        return None
    out = []
    for argv in cmds:
        parsed = shellcmd.git_subcommand(argv)
        if parsed is not None:
            out.append(parsed[0])
    return out


# ------------------------------------------------------------- splitting

check("plain separators",
      subs("git add -A && git commit -m x; git push"),
      ["add", "commit", "push"])
check("newline separators", subs("git commit -m x\ngit push"),
      ["commit", "push"])
check("backslash continuation is joined",
      subs("git commit \\\n  -m x\ngit push"), ["commit", "push"])
check("subshell parens split", subs("(git commit -m x; git push)"),
      ["commit", "push"])
check("unbalanced quote is a parse error",
      shellcmd.simple_commands('git commit -m "unclosed'), None)
# The heredoc pre-pass and the newline rewrite both run on RAW TEXT, ahead of
# `shlex`, so neither knows the quoting rules. Both limits are documented in
# the module docstring and both fail toward `None` or toward a mangled
# ARGUMENT rather than toward a wrong command boundary. Pinned so a later
# quote-aware rewrite is a visible change rather than a silent one.
# The SYMPTOM here changed when `_heredoc_free` stopped discarding the rest of
# the opener's line, and this case exists to make that visible rather than
# silent. It used to swallow the closing quote too, so `shlex` raised and the
# result was `None`; now the quote survives, the argument parses, and what is
# lost is the text after the unterminated pseudo-heredoc. The DIRECTION is
# unchanged and is the property that matters: both spellings fail OPEN, and
# the hook allows this call either way. Re-pinned rather than restored,
# because restoring it would mean re-introducing the bypass that dropping the
# opener's line caused for a REAL heredoc.
check("a `<<` inside a quoted argument still fails open, now as a mangled "
      "argument rather than a parse error",
      shellcmd.simple_commands("git commit -m 'fix a << b'\nb=1\ngit push"),
      [["git", "commit", "-m", "fix a  << "]])
check("a newline inside a quoted argument arrives in the token as a semicolon",
      shellcmd.simple_commands("git commit -m 'line1\nline2'"),
      [["git", "commit", "-m", "line1;line2"]])
check("but the command boundaries around it are still right",
      subs("git commit -m 'line1\nline2'\ngit push"), ["commit", "push"])
# ... EXCEPT when the rewritten token is nothing BUT separator characters.
# The separator test is `set(tok) <= _SHELL_OPS`, so such an argument becomes
# a separator: it vanishes from the argv and splits the command. Documented as
# the third limit, and pinned here because it is the one that does NOT fail
# open -- a caller can see a command the shell would not run.
check("an argument that dequotes to only a newline is eaten as a separator",
      shellcmd.simple_commands("git commit -m 'a' -m '\n' && git push"),
      [["git", "commit", "-m", "a", "-m"], ["git", "push"]])
check("an argument that dequotes to a bare semicolon likewise",
      shellcmd.simple_commands("git commit -m ';' && git push"),
      [["git", "commit", "-m"], ["git", "push"]])
check("a separator-only argument can invent a command (false positive)",
      shellcmd.simple_commands("git commit -m x && echo '\n' git push"),
      [["git", "commit", "-m", "x"], ["echo"], ["git", "push"]])
# ... and it runs the other way too, which an earlier revision of the docstring
# denied. A separator-only VALUE of a `GIT_VALUE_OPTS` global option orphans
# the subcommand, so a real push disappears. Reachability is poor (the path
# must be composed only of `();|&` or a bare newline) and every sibling
# carrying the same `_SHELL_OPS` test is equally blind, but the claim that it
# "cannot hide a command" was false and is now pinned as false.
check("a separator-only -C value orphans the subcommand (hidden command)",
      shellcmd.simple_commands("git commit -m wip && git -C '&' push --force"),
      [["git", "commit", "-m", "wip"], ["git", "-C"],
       ["push", "--force"]])
check("an orphaned subcommand is not classified as a git invocation",
      shellcmd.git_subcommand(["git", "-C"]), None)
check("and its remainder is not either",
      shellcmd.git_subcommand(["push", "--force"]), None)
check("empty input", shellcmd.simple_commands(""), [])

# ------------------------------------------------------------- heredocs
#
# The substitution `" << "` rather than `"<<"` is the load-bearing detail, and
# it is the one every in-tree copy of this splitter still gets wrong. A bare
# `<<` fuses with the newline-derived `;` into a single `<<;` token whose
# character set is not a subset of the separator class, so the separator is
# swallowed and the NEXT command is absorbed into the previous argv. Each case
# below reads as one command under that defect.
check("heredoc body is blanked and the following command survives",
      subs("git commit -F - <<'EOF'\nsee git push\nEOF\ngit push"),
      ["commit", "push"])
check("heredoc then &&",
      subs("git commit -F - <<'EOF'\nmsg\nEOF\n&& git push"),
      ["commit", "push"])
check("unquoted heredoc tag",
      subs("cat <<EOF > /tmp/b\ngit push\nEOF\ngit commit -m x"), ["commit"])
check("<<- tab-indented terminator",
      subs("cat <<-EOF > /tmp/b\ngit push\n\tEOF\ngit commit -m x"),
      ["commit"])
check("a heredoc body's git commands are not command positions",
      subs("cat > /tmp/b <<'EOF'\ngit commit -m x\ngit push\nEOF"), [])

# ONE LINE, TWO HEREDOCS. The shell queues the bodies and reads them back to
# back after the newline, in opener order. Scanning only the first opener and
# emitting the rest of the line verbatim left the second body live, so its
# text was parsed as commands.
check("a second heredoc opened on the same line is also blanked",
      subs("cat <<A > f1 && cat <<B > f2\nbodyA\nA\ngit commit -m x\nB\n"), [])
check("and a git command inside that second body is not a command",
      subs("git commit -m x <<A && git push <<B\na\nA\ngit commit -m y\nB\n"),
      ["commit", "push"])
# THE SAME-LINE BOUND, which is the other half of the loop and fails the other
# way. Collecting delimiters past the opener's own line makes a LATER,
# unrelated heredoc's delimiter queue behind this one, so the first body is
# closed at the wrong terminator and its text goes live. Adversarial review
# found this unpinned: dropping `m.start() < scan_end` left the whole suite
# green while `cat <<A\ngit commit -m x\nA\ncat <<B\nbodyB\nB\n` started
# reporting a commit --- the same false DENY the case above rules out, reached
# from the opposite direction.
check("two heredocs on SEPARATE lines keep their own bodies",
      subs("cat <<A\ngit commit -m x\nA\ncat <<B\nbodyB\nB\n"), [])

# A HERE-STRING carries no body. Matching its second and third `<` as an
# opener blanked everything after it, so a chain written below one was erased
# and the guard went silent -- a false negative, the direction that ships a
# broken push.
check("a here-string is not a heredoc opener",
      subs("cat <<< word\ngit commit -m x\ngit push"), ["commit", "push"])
check("a here-string on a git command likewise",
      subs("git hash-object -w --stdin <<< text\ngit push"), ["hash-object", "push"])

# ORDERING: heredoc blanking must run BEFORE the backslash-continuation join.
# A heredoc body is literal text and a backslash in it continues nothing, but
# joining first lets a body line ending in `\` eat its own terminator -- after
# which the heredoc never closes and its body tokens leak out as commands.
# Measured under the wrong order this returns three argv lists, the middle one
# being body text (`['body', 'EOF']`), rather than two.
check("a body line ending in a backslash does not leak body tokens",
      shellcmd.simple_commands(
          "git commit -F - <<'EOF'\nbody \\\nEOF\ngit push"),
      [["git", "commit", "-F", "-", "<<"], ["git", "push"]])
check("that case still finds exactly the two git commands",
      subs("git commit -F - <<'EOF'\nbody \\\nEOF\ngit push"),
      ["commit", "push"])

# ------------------------------------------------------------- quoting

check("a quoted git command is one token, not a command",
      subs('git commit -m "then git push"'), ["commit"])
check("single-quoted likewise",
      subs("git commit -m 'then git push'"), ["commit"])
check("echo of both commands",
      subs("echo 'git commit -m x; git push'"), [])
check("a multi-line quoted body",
      subs('gh issue comment 1 -b "run git commit\nthen git push"'), [])

# ------------------------------------------------------- strip_env / wrappers
#
# Every spelling here is one `hooks/no-push-without-self-review.py` resolves.
# A disagreement between the two is a call that guard denies while a guard
# built on this module stays silent.

def prog(command):
    cmds = shellcmd.simple_commands(command) or []
    return [shellcmd.strip_env(argv)[1][:2] for argv in cmds]


check("env assignment prefix", subs("GIT_PAGER=cat git push"), ["push"])
check("absolute path to git", subs("/usr/bin/git push"), ["push"])
check("unexpanded $GIT", subs("$GIT push"), ["push"])
check("unexpanded ${GIT}", subs("${GIT} push"), ["push"])
check("timeout wrapper", subs("timeout 60 git push"), ["push"])
check("sudo with its own options", subs("sudo -u me -H git push"), ["push"])
check("env wrapper", subs("env git commit -m x"), ["commit"])
check("nice and ionice", subs("nice -n 10 git push"), ["push"])
check("brace group", subs("{ git commit -m x; }"), ["commit"])
check("loop body keyword", subs("for i in 1 2; do git push; done"), ["push"])
check("a wrapper running something else is left alone",
      subs("timeout 60 sleep 5"), [])
check("a wrapper whose git is beyond the window is not claimed",
      subs("sudo -a -b -c -d -e -f -g git push"), [])

# `export` RUNS NOTHING. It is a builtin whose arguments are names and
# assignments, so this exports `FOO`, `git` and `push` and invokes no git ---
# confirmed against bash, which produced no git output. Peeling the word as
# though it were a wrapper resolved the command to `git push` and refused a
# call that never happens.
check("export is a stop, not a wrapper", subs("export FOO=1 git push"), [])
check("a real env prefix on the same line is unaffected",
      subs("FOO=1 git push"), ["push"])
check("and a separate export statement leaves the git command alone",
      subs("export FOO=1; git push"), ["push"])

# ------------------------------------------------------ git_subcommand shape

check("global -C is skipped",
      shellcmd.git_subcommand(["git", "-C", "/r", "commit", "-m", "x"])[0],
      "commit")
check("inline --git-dir= is skipped",
      shellcmd.git_subcommand(["git", "--git-dir=/r/.git", "push"])[0], "push")
check("bare git is not a subcommand",
      shellcmd.git_subcommand(["git"]), None)
check("global options only is not a subcommand",
      shellcmd.git_subcommand(["git", "-C", "/r"]), None)
check("a non-git command", shellcmd.git_subcommand(["echo", "git", "push"]),
      None)
# The reason the subcommand is returned verbatim for an `==` comparison:
# `no-unshipped-commit.py` measured a `git\s+commit\b` scan matching both of
# these, because a word boundary sits between `commit` and `-`.
check("commit-tree is its own subcommand",
      shellcmd.git_subcommand(["git", "commit-tree"])[0], "commit-tree")
check("commit-graph is its own subcommand",
      shellcmd.git_subcommand(["git", "commit-graph", "write"])[0],
      "commit-graph")
check("rest is everything after the subcommand",
      shellcmd.git_subcommand(["git", "push", "-u", "origin", "b"])[1],
      ["-u", "origin", "b"])

# ------------------------------------------------------------- env_value

check("plain assignment", shellcmd.env_value(["FOO=1"], "FOO"), "1")
check("absent name", shellcmd.env_value(["BAR=1"], "FOO"), None)
check("empty value is not None",
      shellcmd.env_value(["FOO="], "FOO"), "")
check("the last assignment wins",
      shellcmd.env_value(["FOO=1", "FOO=2"], "FOO"), "2")
check("a name that merely contains the key does not match",
      shellcmd.env_value(["MYFOO=1"], "FOO"), None)
# `export FOO=1` reaches shlex as TWO tokens -- never one -- and the earlier
# reading, that `strip_env` should consume both and carry on to the program
# after them, was wrong about the shell. `export` is a builtin taking names
# and assignments, so nothing after it on that simple command is a program;
# these three cases used to assert `["git", "push"]` and a recorded `FOO=1`,
# which is what made the guard refuse a push that never happens.
check("export yields no program at all",
      shellcmd.strip_env(["export", "FOO=1", "git", "push"])[1], [])
check("and records no assignment, since none takes effect here",
      shellcmd.env_value(shellcmd.strip_env(
          ["export", "FOO=1", "git", "push"])[0], "FOO"), None)
check("the same through a real shlex round trip",
      shellcmd.strip_env(
          (shellcmd.simple_commands("export FOO=1 git push") or [[]])[0])[1],
      [])
check("export of a bare name likewise",
      shellcmd.strip_env(["export", "PATH"])[1], [])
# The spelling that DOES carry a value into a git invocation, kept beside the
# rejected one so the pair reads as a distinction rather than a blanket ban.
check("a bare assignment prefix still resolves to git",
      shellcmd.strip_env(["FOO=1", "git", "push"])[1], ["git", "push"])
check("and still records its value",
      shellcmd.env_value(shellcmd.strip_env(["FOO=1", "git", "push"])[0],
                         "FOO"), "1")

# ------------------------------------------------- resolve_cd_target
#
# A CALLER MUST BE ABLE TO TELL "MOVED SOMEWHERE I CANNOT NAME" FROM
# "DID NOT MOVE". `hooks/no-unshipped-commit.py` attributes a commit to the
# directory the shell stands in, so reading `cd -` as "unchanged" leaves a
# dormant worktree the session merely visited standing as the answer --- the
# false block ai-config#2422 reports. Each indeterminate spelling is pinned
# here rather than left to that hook's own suite.

check("an absolute target is the new directory",
      shellcmd.resolve_cd_target(["cd", "/srv/repo"], "/home/me"), "/srv/repo")
check("a relative target resolves against where the shell stood",
      shellcmd.resolve_cd_target(["cd", "hooks"], "/srv/repo"), "/srv/repo/hooks")
check("`cd -` is indeterminate, not unchanged",
      shellcmd.resolve_cd_target(["cd", "-"], "/srv/repo"), None)
check("`popd` is indeterminate without a simulated stack",
      shellcmd.resolve_cd_target(["popd"], "/srv/repo"), None)
check("`popd -n` moves nothing",
      shellcmd.resolve_cd_target(["popd", "-n"], "/srv/repo"), "/srv/repo")
check("bare `cd` goes home rather than staying put",
      shellcmd.resolve_cd_target(["cd"], "/srv/repo"), os.path.expanduser("~"))
check("`pushd <dir>` moves like `cd`",
      shellcmd.resolve_cd_target(["pushd", "/srv/other"], "/srv/repo"), "/srv/other")
check("an unexpanded variable target is indeterminate",
      shellcmd.resolve_cd_target(["cd", "$WT"], "/srv/repo"), None)

# ------------------------------------------------- subshell nesting depth
#
# `simple_commands` FLATTENS `( ... )`, which is right for a caller asking
# which programs ran and wrong for one modelling the shell's own state: a
# `cd` inside a subshell moves that subshell and dies with it, so the parent
# never left. `(cd /other && git status)` is the routine way to read another
# checkout without leaving your own.
check("a subshell cd is flattened away by simple_commands",
      shellcmd.simple_commands("(cd /a && git status)"),
      [["cd", "/a"], ["git", "status"]])
check("the scope-aware split keeps the nesting",
      shellcmd.simple_commands_with_scope("(cd /a && git status)"),
      [((0, 1), ["cd", "/a"]), ((0, 1), ["git", "status"])])
check("a cd outside the parens stays in the caller's shell",
      shellcmd.simple_commands_with_scope("cd /r && (cd /a && ls) && git commit"),
      [((0,), ["cd", "/r"]), ((0, 1), ["cd", "/a"]), ((0, 1), ["ls"]),
       ((0,), ["git", "commit"])])
# `{ ... }` runs in the CURRENT shell, so a `cd` inside one does move the
# caller and must not be counted as nesting.
check("brace grouping is not subshell nesting",
      shellcmd.simple_commands_with_scope("f() { cd /a; }"),
      [((0,), ["f"]), ((0,), ["{", "cd", "/a"]), ((0,), ["}"])])
# A DEPTH IS NOT AN IDENTITY. Two sibling subshells sit at the same depth and
# share none of their state, so a caller carrying a per-level directory needs
# the scope-aware split to tell them apart --- `(cd /a) && (git commit` reads
# as `(cd /a && git commit` from the depths alone.
check("sibling subshells get distinct scopes",
      shellcmd.simple_commands_with_scope("(cd /a) && (git commit)"),
      [((0, 1), ["cd", "/a"]), ((0, 2), ["git", "commit"])])
check("one subshell keeps one scope throughout",
      shellcmd.simple_commands_with_scope("(cd /a && git commit)"),
      [((0, 1), ["cd", "/a"]), ((0, 1), ["git", "commit"])])
# `shlex` emits `)&&(` as ONE separator token, whose net paren count is zero
# --- so only the ordered per-character read opens a fresh scope on the far
# side of it.
check("a close-and-open in one token still opens a new scope",
      shellcmd.simple_commands_with_scope("(cd /a)&&(git commit)"),
      [((0, 1), ["cd", "/a"]), ((0, 2), ["git", "commit"])])
check("nesting is a scope path, and the depth is its length",
      shellcmd.simple_commands_with_scope("(cd /a && (cd /b; ls)); cd /c"),
      [((0, 1), ["cd", "/a"]), ((0, 1, 2), ["cd", "/b"]),
       ((0, 1, 2), ["ls"]), ((0,), ["cd", "/c"])])
check("a parse error is None on the scope-aware split too",
      shellcmd.simple_commands_with_scope("git commit -m \'unclosed"), None)

# ------------------------------------------- interpreter descent (#1973)
#
# A hook that compares exact tokens is bypassed outright by an interpreter
# wrapper: `shlex` collapses the embedded command into ONE opaque token, so
# `argv[0]` is the interpreter and every head-token comparison fails. Measured
# on `main`: `git push --force origin main` denies and
# `sh -c "git push --force origin main"` is silently allowed.
#
# The command itself is always first, so a caller can take `[0]` for the
# unchanged outer analysis and treat the rest as additional.
check("the command itself comes back even with nothing nested",
      shellcmd.shell_c_expansions("git push --force origin main"),
      ["git push --force origin main"])
check("a shell's -c argument is a nested command line",
      descends_to('sh -c "git push --force origin main"',
                  "git push --force origin main"), True)
# Only a SHELL's `-c` takes a command line. `python -c` takes Python SOURCE,
# where `git push` is a syntax error rather than a push, so descending into it
# would invent a command nobody ran.
check("a python -c argument is source, not a command line",
      shellcmd.shell_c_expansions('python3 -c "git push --force origin main"'),
      ['python3 -c "git push --force origin main"'])
# WIDER than the reference implementation in hooks/no-empty-promise.py, whose
# `-[a-z]*c` anchors the `c` last and so reads `-ec` and misses `-cx`. Short
# options cluster in any order and `bash -cx 'git push'` really pushes.
check("a -c inside a short-flag cluster still hands over a command line",
      descends_to('bash -cx "git push --force origin main"',
                  "git push --force origin main"), True)
check("assignments and wrappers before the shell do not hide it",
      descends_to('env FOO=1 /bin/bash -c "git push origin main"',
                  "git push origin main"), True)
check("descent is recursive and terminates",
      shellcmd.shell_c_expansions('bash -c "bash -c ' + chr(92) + '"git push' + chr(92) + '""'),
      ['bash -c "bash -c ' + chr(92) + '"git push' + chr(92) + '""',
       'bash -c "git push"', "git push"])
# `-c` must be a FLAG TOKEN, not text that merely contains one, or quoting the
# construct in prose would descend into it.
check("quoted prose naming the construct is not descended into",
      shellcmd.shell_c_expansions('echo "sh -c stuff"'), ['echo "sh -c stuff"'])
check("a -c with no operand yields nothing extra",
      shellcmd.shell_c_expansions("sh -c"), ["sh -c"])
# An unparseable piece yields no children and does not discard what was
# already found -- the outer command is still returned.
check("an unbalanced quote does not lose the outer command",
      shellcmd.shell_c_expansions("git commit -m 'unclosed"),
      ["git commit -m 'unclosed"])
# The cap must BITE for the check to mean anything. The first version used
# `"git push"`, which has no nested shell at all, so it returned one piece for
# every max_depth and passed with the bound deleted outright -- a case that
# cannot fail, which is the standard this repo applies to its own tests.
_BS = chr(92)
_Q = chr(34)
_THREE_DEEP = ('bash -c ' + _Q + 'bash -c ' + _BS + _Q + 'bash -c '
               + _BS + _BS + _BS + _Q + 'git push' + _BS + _BS + _BS + _Q
               + _BS + _Q + _Q)
check("depth 1 stops after the first nested command line",
      len(shellcmd.shell_c_expansions(_THREE_DEEP, max_depth=1)), 2)
check("depth 2 reaches the second",
      len(shellcmd.shell_c_expansions(_THREE_DEEP, max_depth=2)), 3)
check("depth 3 reaches all of them",
      len(shellcmd.shell_c_expansions(_THREE_DEEP, max_depth=3)), 4)

# ai-config#1973 review. After `-c`, bash keeps parsing options and takes the
# first non-option OPERAND, so the command string is not necessarily adjacent.
# Each of these really runs the command -- verified directly under bash.
# Three rounds of review found three separate holes in a model of bash's
# option grammar, so there is no model any more: every token after a `-c`-shaped
# flag is a candidate. Both positions of each spelling are covered here.
for _flags, _label in (("-c -x", "a flag after -c"),
                       ("-c --", "an end-of-options marker after -c"),
                       ("-o pipefail -c", "an option VALUE before -c"),
                       ("--rcfile /dev/null -c", "a long option with a value"),
                       ("-O extglob -c", "a shopt option with a value"),
                       ("-eo pipefail -c", "a cluster plus a valued option"),
                       ("+x -c", "a `+`-prefixed set option before -c"),
                       ("-c -o pipefail", "a valued option AFTER -c"),
                       ("-c -O extglob", "a valued shopt option AFTER -c"),
                       ("-c +x", "a `+`-prefixed option AFTER -c")):
    check("the -c operand is found past " + _label,
          descends_to('bash ' + _flags + ' ' + _Q + 'git push' + _Q, "git push"),
          True)

# The PROGRAM is resolved first, and nothing else is considered unless it is a
# shell. A walk-back from the `-c` to the nearest non-flag token returned `sh`
# for the first of these and produced a hard refusal on a command that runs
# nothing.
check("a -c belonging to no command word is not followed",
      shellcmd.shell_c_expansions('echo sh -c ' + _Q + 'git push' + _Q),
      ['echo sh -c ' + _Q + 'git push' + _Q])
check("a -c argument of a non-shell program is not followed",
      shellcmd.shell_c_expansions('printf %s sh -c ' + _Q + 'git push' + _Q),
      ['printf %s sh -c ' + _Q + 'git push' + _Q])
# `-C` is noclobber, which takes no command. Matching the flag
# case-insensitively refused `bash -C <file>`, which runs a FILE by that name.
check("-C is noclobber, not a command flag",
      shellcmd.shell_c_expansions('bash -C ' + _Q + 'git push' + _Q),
      ['bash -C ' + _Q + 'git push' + _Q])

# A bypass guard's coverage is decided by its weakest spelling.
for _shell in ("ash", "mksh", "pdksh", "/bin/bash-5.2", "busybox ash"):
    check(_shell + " takes -c identically",
          descends_to(_shell + ' -c ' + _Q + 'git push' + _Q, "git push"), True)

check("a wrapper with its own argument does not hide the shell",
      descends_to('timeout 5 bash -c ' + _Q + 'git push' + _Q, "git push"), True)
check("command_program resolves past assignments and wrappers",
      shellcmd.command_program(["env", "FOO=1", "/bin/bash", "-c", "git push"]), 2)
check("command_program stops at a non-shell head",
      shellcmd.command_program(["echo", "sh", "-c", "git push"]), 0)

# An ENV ASSIGNMENT before the program, with no wrapper to compensate. The
# existing `env FOO=1 /bin/bash -c` case does NOT cover this branch: the
# wrapper look-ahead finds the shell anyway when `env` precedes the
# assignment. Reverting the assignment branch leaves that case green and
# silences the guard on this one (ai-config#1973 review, round 2 finding 4).
check("a bare assignment before the shell does not hide it",
      descends_to('FOO=1 bash -c ' + _Q + 'git push' + _Q, "git push"), True)
check("setsid is skippable",
      descends_to('setsid bash -c ' + _Q + 'git push' + _Q, "git push"), True)
# A wrapper and a shell may BOTH be path-qualified. The membership test used to
# be an exact string while SHELL_PROGRAM allowed a path prefix.
for _wrapper in ("/usr/bin/env", "/usr/bin/nice -n 5", "/bin/nohup"):
    check(_wrapper + " does not hide the shell",
          descends_to(_wrapper + ' bash -c ' + _Q + 'git push' + _Q, "git push"), True)
# The scan must stop at the SCRIPT OPERAND, but not at an option's VALUE.
# ACCEPTED OVER-DETECTION. `bash script.sh -c "<cmd>"` hands `-c "<cmd>"` to
# the script's own argv and runs no `<cmd>`; the descent scans it anyway.
check("a script operand is scanned too, and costs only a scan",
      descends_to('bash script.sh -c ' + _Q + 'git push' + _Q, "git push"), True)
check("an option value does not stop the scan",
      descends_to('bash --rcfile /dev/null -c ' + _Q + 'git push' + _Q, "git push"), True)
check("a cluster ending in a value-taking letter does not stop the scan",
      descends_to('bash -eo pipefail -c ' + _Q + 'git push' + _Q, "git push"), True)
# A cluster CONTAINING a lowercase `c` is a `-c`, whatever case surrounds it.
# Bare `-C` is noclobber and takes no command.
check("a mixed-case cluster containing c still hands over a command line",
      descends_to('bash -cC ' + _Q + 'git push' + _Q, "git push"), True)
check("bare -C is noclobber, not a command flag",
      shellcmd.shell_c_expansions('bash -C ' + _Q + 'git push' + _Q),
      ['bash -C ' + _Q + 'git push' + _Q])
# The `seen` set: a repeated nested string is not queued twice.
check("an identical nested command is not expanded twice",
      shellcmd.shell_c_expansions(
          'bash -c ' + _Q + 'git push' + _Q + ' ; sh -c ' + _Q + 'git push' + _Q),
      ['bash -c ' + _Q + 'git push' + _Q + ' ; sh -c ' + _Q + 'git push' + _Q,
       "git push"])

# `memories/hooks.md` 5.6: a hot-path guard's correctness suite does not
# exercise its performance envelope, so measure adversarial length separately.
# This runs before every Bash call.
_WIDE = " ; ".join(
    ['bash -c ' + _Q + 'git push ' + str(i) + _Q for i in range(2000)])
_start = time.perf_counter()
_pieces = shellcmd.shell_c_expansions(_WIDE)
_elapsed = time.perf_counter() - _start
check("2000 sibling nested shells all expand", len(_pieces), 2001)
check("and do so in under two seconds", _elapsed < 2.0, True)

# ------------------------------------------------- env -S (--split-string)
#
# `env -S` splits ONE argument into a command line and execs it, so
# `env -S 'bash -c "<cmd>"'` really runs that shell -- verified against real
# env, which printed the stubbed command. But the whole invocation is a single
# already-quoted token and `env` is skipped as a bare wrapper, so the descent
# found no shell and the push ran with the guard silent (ai-config#1973 review,
# round 4 finding 5).
check("env -S hands over its argument as a command line",
      descends_to("env -S 'bash -c \"git push --force origin main\"'",
                  'bash -c "git push --force origin main"'), True)
check("the attached short form is read too",
      descends_to("env -Sbash\\ -c\\ x", "bash -c x") or
      descends_to("env '-Sbash -c x'", "bash -c x"), True)
check("--split-string is the same flag",
      descends_to("env --split-string 'bash -c \"git push --force\"'",
                  'bash -c "git push --force"'), True)
check("the attached long form is read too",
      descends_to("env '--split-string=bash -c \"git push --force\"'",
                  'bash -c "git push --force"'), True)
check("S inside a short cluster counts, as env reads it",
      descends_to("env -vS 'bash -c \"git push --force\"'",
                  'bash -c "git push --force"'), True)
check("a path-spelled env is still env",
      descends_to("/usr/bin/env -S 'bash -c \"git push --force\"'",
                  'bash -c "git push --force"'), True)
check("an ordinary env wrapper is unaffected",
      descends_to("env FOO=1 bash -c 'git push --force'", "git push --force"),
      True)
check("-S on a non-env program hands over nothing",
      shellcmd.nested_shell_commands(["echo", "-S", "bash -c x"]), [])

# The `env` is looked for in a window from the head, not at argv[0] alone.
# Testing only the head asked whether `env` was TYPED first rather than
# whether it RUNS, and every one of these words is already in
# `COMMAND_WRAPPERS`: `command env -S "bash -c '<push>'"` really executes
# (measured) and both guards were silent on it, while the bare `env -S`
# spelling denied (ai-config#3645 pre-merge gate, finding 3).
for _wrapper in ("command", "sudo", "nohup", "exec"):
    check(f"a {_wrapper} before env -S still hands over the command line",
          descends_to(f"{_wrapper} env -S 'bash -c \"git push --force\"'",
                      'bash -c "git push --force"'), True)
check("an env -S past the wrapper window is not searched for",
      shellcmd.nested_shell_commands(
          ["a", "b", "c", "d", "e", "f", "g", "env", "-S", "bash -c x"]), [])

# ------------------------------------------------- source-level hygiene
#
# THIS MODULE QUOTES REGEX SOURCE IN ITS PROSE, so a docstring can carry an
# escape sequence Python reads as invalid --- `(?:export\s+)?` did, in
# `env_value`. The remedy is a raw docstring, and the reason it needs a test
# rather than care is that the failure is INVISIBLE on some interpreters and
# not others: Python 3.11 raises `DeprecationWarning`, which is silent by
# default, while 3.12 and later raise `SyntaxWarning`, which prints on every
# cold-cache import. So a maintainer on 3.11 sees nothing while CI prints the
# warning on every run, and the deprecation ends in a hard `SyntaxError`.
# Asserting on the warning CATEGORY would inherit that split, so this compiles
# the file and reads the message instead.
with warnings.catch_warnings(record=True) as _w:
    warnings.simplefilter("always")
    py_compile.compile(shellcmd.__file__, cfile=os.path.join(
        tempfile.mkdtemp(), "probe.pyc"), doraise=True)
    _escapes = [f"line {x.lineno}: {x.message}" for x in _w
                if "invalid escape" in str(x.message)]
check("the module compiles with no invalid escape sequences", _escapes, [])

# native_path: Git Bash drive paths become paths native git.exe can open.
# Measured on Windows before the helper existed: `git -C /c/Users/x ...` exited
# 128 ("cannot change to '/c/Users/x'"), which made the push guards refuse a
# reviewed cross-repo push or fail open.
for given, want in (
    ("/c/Users/x", "C:/Users/x"),
    ("/C/a b/c", "C:/a b/c"),
    ("/cygdrive/d/work", "D:/work"),
    ("/c", "C:/"),
    ("/c/", "C:/"),
    ("/tmp/x", "/tmp/x"),     # MSYS root, not a drive: unknowable, unchanged
    ("/cc/x", "/cc/x"),       # a two-letter first segment is not a drive
    ("C:/x", "C:/x"),         # already native
    ("rel/x", "rel/x"),
    (None, None),
):
    check(f"native_path({given!r}) on Windows", shellcmd.native_path(given, True), want)
check("native_path leaves /c/... alone off Windows",
      shellcmd.native_path("/c/Users/x", False), "/c/Users/x")

if failures:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
