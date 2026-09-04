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
import warnings

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))

import shellcmd  # noqa: E402

failures = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


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

if failures:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
