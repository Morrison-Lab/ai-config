"""Split a shell command string into simple-command argv lists.

Extracted so the git-command guards stop each carrying their own copy.
`hooks/no-clobbering-push.py` and `hooks/flag-reset-hard-uncommitted-work.py`
both grew an identical `_simple_commands`, and this module is that function
plus the `git`-invocation classifier every one of those guards needs next.
Those two are not rewired here -- migrating a live deny guard is its own
change with its own review -- but new callers import from here rather than
adding a fourth copy.

Why an argv split rather than a regex over the raw string: the false positives
that matter to a corpus about git workflow are all QUOTING failures. This repo
writes `git commit` and `git push` constantly inside commit messages, issue
bodies, heredocs, and prose, and a line-oriented scan cannot tell a quoted
example from an executed command -- which is exactly what
`shared/writing/examples-are-scanned.md` names. `shlex` in POSIX mode already
knows the quoting rules, so a caller that asks "is `git push` the command word
of some simple command" gets the answer for free, rather than accreting one
regex clause per quoting shape.
"""
from __future__ import annotations

import re
import shlex

# A heredoc body is data, not commands, so it is blanked before splitting.
# Both the quoted (`<<'EOF'`) and unquoted (`<<EOF`) tags are matched, and
# `<<-` allows the terminator to be tab-indented.
RX_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?\n[ \t]*\2\b", re.S)

# A leading `NAME=value` on a simple command is an env assignment, not the
# command word. `LEAD_WORDS` are the words that can precede a command word
# without being one.
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
LEAD_WORDS = {"then", "do", "else", "!", "time", "sudo", "command", "exec",
              "nohup", "env"}

_SHELL_OPS = set("();|&")

# `git`'s own global options that consume the FOLLOWING token, skipped before
# the subcommand is read so `git -C /repo commit` classifies as `commit`.
# The `--opt=value` inline spellings need no entry: they are one token and the
# generic single-step branch handles them.
GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace",
                  "--exec-path"}


def simple_commands(command):
    """Split `command` into simple-command argv lists; `None` on a parse error.

    Join backslash-continued lines, blank heredoc bodies, turn unquoted
    newlines into `;`, then let `shlex` split and dequote. The returned tokens
    are DEQUOTED, so a quoted `"git push"` arrives as one token inside some
    other command's argv rather than as its own simple command.
    """
    command = re.sub(r"\\\r?\n", " ", command)
    command = RX_HEREDOC.sub("<<", command)
    command = command.replace("\n", ";")
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return None
    cmds, cur = [], []
    for tok in toks:
        if tok and set(tok) <= _SHELL_OPS:
            if cur:
                cmds.append(cur)
                cur = []
        else:
            cur.append(tok)
    if cur:
        cmds.append(cur)
    return cmds


def git_subcommand(argv):
    """`(subcommand, rest, env)` when `argv` is a `git` invocation, else `None`.

    `env` maps the leading `NAME=value` assignments, so a caller can read an
    override prefix without re-scanning. `rest` is everything after the
    subcommand word.

    The subcommand is returned VERBATIM, which is what keeps a caller from
    repeating `no-unshipped-commit.py`'s measured bug: a `\\b` word boundary
    sits happily between `commit` and `-`, so `git commit-tree` and
    `git commit-graph write` both matched a `git\\s+commit\\b` scan. Comparing
    the whole token with `==` cannot make that mistake.
    """
    i, env = 0, {}
    while i < len(argv) and (ASSIGNMENT.match(argv[i]) or argv[i] in LEAD_WORDS):
        if ASSIGNMENT.match(argv[i]):
            name, _, value = argv[i].partition("=")
            env[name] = value
        i += 1
    if i >= len(argv) or argv[i] != "git":
        return None
    i += 1
    while i < len(argv) and argv[i].startswith("-"):
        i += 2 if argv[i] in GIT_VALUE_OPTS else 1
    if i >= len(argv):
        return None  # bare `git`, or global options only
    return argv[i], argv[i + 1:], env
