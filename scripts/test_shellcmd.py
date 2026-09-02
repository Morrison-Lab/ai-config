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
import sys

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
check("a `<<` inside a quoted argument can unbalance the quote and fail open",
      shellcmd.simple_commands("git commit -m 'fix a << b'\nb=1\ngit push"),
      None)
check("a newline inside a quoted argument arrives in the token as a semicolon",
      shellcmd.simple_commands("git commit -m 'line1\nline2'"),
      [["git", "commit", "-m", "line1;line2"]])
check("but the command boundaries around it are still right",
      subs("git commit -m 'line1\nline2'\ngit push"), ["commit", "push"])
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
# `export FOO=1` reaches shlex as TWO tokens -- never one -- so `strip_env`
# must consume both, and `env_value` must never need to strip an `export `
# prefix from a token. Both halves are asserted, because a mutation removing
# the (unreachable) prefix handling from `ENV_ASSIGNMENT` left the suite green.
check("export split across two tokens leaves git as the program",
      shellcmd.strip_env(["export", "FOO=1", "git", "push"])[1],
      ["git", "push"])
check("export split across two tokens still records the assignment",
      shellcmd.env_value(shellcmd.strip_env(
          ["export", "FOO=1", "git", "push"])[0], "FOO"), "1")
check("an export-prefixed assignment survives a real shlex round trip",
      shellcmd.env_value(shellcmd.strip_env(
          (shellcmd.simple_commands("export FOO=1 git push") or [[]])[0])[0],
          "FOO"), "1")
check("export with no assignment after it is not consumed as one",
      shellcmd.strip_env(["export", "PATH"])[1], ["export", "PATH"])

if failures:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
