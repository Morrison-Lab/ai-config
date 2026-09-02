"""Split a shell command string into simple-command argv lists, and classify
each as a `git` invocation.

WHY THIS MODULE EXISTS
----------------------
`_simple_commands` was copied into SEVEN hooks before this module was written:

    hooks/flag-add-a-outside-pathspec.py       hooks/no-clobbering-push.py
    hooks/flag-reset-hard-uncommitted-work.py  hooks/no-delete-branch-under-stacked-pr.py
    hooks/flag-stale-adjacent-comment.py       hooks/no-unreviewed-pr.py
    hooks/warn-nonglobal-substitution.py

The bodies are identical, and so is the heredoc defect `_heredoc_free` fixes
below -- which is the argument for a module rather than an eighth copy. Those
seven are NOT rewired here: migrating seven live guards, three of them denying,
is its own change with its own review, tracked as ai-config#2993. This module
is where the fix landed and where new callers import from.

WHY AN ARGV SPLIT RATHER THAN A REGEX
-------------------------------------
The false positives that matter to a corpus about git workflow are all QUOTING
failures. This repo writes `git commit` and `git push` constantly inside commit
messages, issue bodies, heredocs, and prose, and a line-oriented scan cannot
tell a quoted example from an executed command --
`shared/writing/examples-are-scanned.md` names exactly that hazard, and an argv
split is the "teach the checker about code regions" fix it prescribes. `shlex`
in POSIX mode already knows the quoting rules, so a caller asking "is `git push`
the command word of some simple command" gets the answer without accreting one
regex clause per quoting shape.

THREE LIMITS, ALL INHERITED FROM THE SEVEN COPIES
--------------------------------------------------
The heredoc pre-pass and the newline rewrite run on RAW TEXT, ahead of `shlex`,
so neither knows the quoting rules the paragraph above credits `shlex` with.
State that here rather than letting the argv-split argument imply otherwise --
this docstring is the contract ai-config#2993 will migrate seven live guards
onto, three of them denying.

  * `RX_HEREDOC` is QUOTE-BLIND. A `<<` inside a quoted argument -- a commit
    message that mentions a heredoc, say -- can be treated as a real operator,
    and consuming up to a delimiter then unbalances the quote. `shlex` raises
    `ValueError` and `simple_commands` returns `None`. Measured, writing LF
    for a literal newline:

        simple_commands("git commit -m 'fix a << b'" LF "b=1" LF "git push")
        ->  None

  * The NEWLINE REWRITE is quote-blind for the same reason, so a newline
    INSIDE a quoted argument (a multi-line `-m` message) arrives in the token
    as `;`. The command boundaries are unaffected; the argument's TEXT is not,
    so a caller must never present a rejoined argv as the user's original.

  * WHEN THAT REWRITE CONSUMES THE WHOLE TOKEN, the boundary moves too. This
    is the case the two above do not cover, and the one that breaks the tidy
    "only arguments are affected" reading. The separator test is
    `set(tok) <= _SHELL_OPS`, so an argument that DEQUOTES to nothing but
    separator characters becomes a separator: it disappears from the argv and
    splits the command in half.

        simple_commands("git commit -m 'a' -m '" LF "' && git push")
        ->  [['git', 'commit', '-m', 'a', '-m'], ['git', 'push']]
        simple_commands("git commit -m ';' && git push")
        ->  [['git', 'commit', '-m'], ['git', 'push']]

    A caller can therefore see a command that the shell would not run. For a
    guard this is a FALSE POSITIVE direction, not a false negative: measured,
    no chained push could be hidden this way, but `git commit -m x && echo '"
    LF "' git push` splits so that `git push` -- which is really an argument
    to `echo` -- reads as a command.

The first two fail toward silence or toward a mangled argument. The third does
not fail open, and is stated separately for that reason. Fixing any of them
means a quote-aware pre-scan, which is a real parser and out of scope for an
extraction; ai-config#2993 is where that belongs, alongside migrating the
seven copies.
"""
from __future__ import annotations

import os
import re
import shlex

# `<<WORD`, `<<'WORD'`, `<<-"WORD"`, then the body up to a terminator that `<<-`
# allows to be tab-indented. The NEWLINE AFTER the terminator is deliberately
# outside the match -- see `_heredoc_free`.
RX_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?\n[ \t]*\2\b", re.S)

# No `export` alternative here on purpose. `shlex` splits `export FOO=1` into
# TWO tokens, so an `export`-prefixed assignment never reaches this pattern as
# one word -- `strip_env` handles the two-token form instead. A
# `(?:export\s+)?` group here was unreachable, and a mutation removing it left
# the suite green, which is how it was found.
ENV_ASSIGNMENT = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*=")

# Wrappers that RUN the command following them, so `git` is not argv[0] even
# though a git command is exactly what executes. Taken from
# `hooks/no-push-without-self-review.py`, which is the tested in-repo
# implementation of this classification; keeping a narrower set here would mean
# a guard silently disagreeing with the guard it is paired against.
COMMAND_WRAPPERS = {"env", "command", "nohup", "time", "exec", "builtin",
                    "sudo", "timeout", "stdbuf", "nice", "ionice", "doas"}

# Shell keywords that can open a simple command. Dropping these is a regression
# rather than a simplification: the splitter below breaks on `;` and `&&`, so
# the keyword becomes argv[0] of the segment holding the git command, and
# `skills/push/SKILL.md` prescribes a retry loop whose body starts with `do`.
SHELL_KEYWORDS = {"!", "{", "}", "(", ")", "if", "then", "elif", "else", "fi",
                  "while", "until", "do", "done", "for", "case", "esac"}

# An unexpanded `$GIT` / `${GIT}` program token; shlex leaves it literal.
GIT_VARIABLE = re.compile(r"\A\$\{?GIT\}?\Z")

# How far past a wrapper to look for the git token. Six covers
# `sudo -u name -H git`, and bounds the scan so an unrelated command running
# git much later on the line is not mistaken for a wrapped one.
WRAPPER_ARG_WINDOW = 6

_SHELL_OPS = set("();|&")

# `git`'s own global options that consume the FOLLOWING token, skipped before
# the subcommand is read so `git -C /repo commit` classifies as `commit`. The
# `--opt=value` inline spellings need no entry: they are one token, and the
# generic single-step branch handles them.
GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace",
                  "--exec-path"}


def _heredoc_free(command):
    """Blank heredoc BODIES, leaving the surrounding shell intact.

    The substitution is `" << "`, with the spaces, and they are load-bearing.
    Substituting a bare `"<<"` -- what all seven copies of this function do --
    leaves `<<` flush against the newline that the caller then rewrites to `;`.
    `shlex` with `punctuation_chars=True` emits that run as the SINGLE token
    `<<;`, whose character set is not a subset of `_SHELL_OPS` (which has no
    `<`), so the separator is swallowed and the following command is absorbed
    into the previous one's argv:

        git commit -F - <<'EOF'      ->  [['git','commit','-F','-',
        msg                                '<<;','git','push']]
        EOF
        git push

    Two commands read as one. Adding `<` to `_SHELL_OPS` is the wrong repair:
    it would split `sort x > out` into two commands as well.
    """
    return RX_HEREDOC.sub(" << ", command)


def simple_commands(command):
    """Split `command` into simple-command argv lists; `None` on a parse error.

    Join backslash-continued lines, blank heredoc bodies, turn unquoted
    newlines into `;`, then let `shlex` split and dequote. The tokens come back
    DEQUOTED, so a quoted `"git push"` arrives as one token inside some other
    command's argv rather than as its own simple command.
    """
    # ORDER MATTERS, and the natural order is wrong. Joining continuations
    # first lets a heredoc BODY line ending in a backslash eat its own
    # terminator, after which `RX_HEREDOC` closes at some later occurrence of
    # the delimiter word -- or never -- and everything between is swallowed.
    # Measured: `git commit -F - <<EOF / a \\ / EOF / git push` lost the push
    # entirely, so the guard went silent. A heredoc body is literal text and a
    # backslash in it continues nothing, so it must be removed BEFORE the
    # continuation join runs over what remains.
    command = _heredoc_free(command)
    command = re.sub(r"\\\r?\n", " ", command)
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


def strip_env(argv):
    """`(env, argv_with_git_first)` for one simple command.

    Adapted from `hooks/no-push-without-self-review.py`'s `_strip_env`, which is
    the tested in-repo implementation. Leading env assignments, command
    wrappers, and shell keywords are peeled off, and the program token is
    normalized to its basename -- so `/usr/bin/git push`, `timeout 60 git push`,
    `{ git commit -m x; }`, and `sudo -u me git push` all resolve to a `git`
    first token, as they do for the guard this one is paired against.

    `env` is the list of assignment TOKENS, in order, including any `export`
    prefix.
    """
    rest, env, after_wrapper = list(argv), [], False
    while rest:
        tok = rest[0]
        if ENV_ASSIGNMENT.match(tok):
            env.append(tok)
            rest = rest[1:]
            after_wrapper = False
            continue
        if tok == "export" and len(rest) > 1 and ENV_ASSIGNMENT.match(rest[1]):
            rest = rest[1:]  # `export FOO=1` split by shlex into two tokens
            continue
        if tok in COMMAND_WRAPPERS:
            after_wrapper = True
            rest = rest[1:]
            continue
        if tok in SHELL_KEYWORDS:
            after_wrapper = False
            rest = rest[1:]
            continue
        # A wrapper's own arguments, so `env -i`, `timeout 5` and `sudo -u me`
        # do not stop the scan before `git`. Enumerating each wrapper's option
        # grammar would be its own parser, so instead look ahead a bounded
        # distance for the git token and drop what precedes it. Nothing is
        # consumed unless git is actually found, so a wrapper running something
        # else is left alone.
        if after_wrapper:
            window = rest[1:1 + WRAPPER_ARG_WINDOW]
            hit = next((i for i, t in enumerate(window, start=1)
                        if GIT_VARIABLE.match(t) or os.path.basename(t) == "git"),
                       None)
            if hit is not None:
                rest = rest[hit:]
                continue
        break
    if rest and (GIT_VARIABLE.match(rest[0]) or os.path.basename(rest[0]) == "git"):
        rest = ["git"] + rest[1:]
    return env, rest


def env_value(env_tokens, name):
    """The value assigned to `name` by `env_tokens`, or `None`.

    The LAST assignment wins, as the shell does. Tokens arrive already
    `export`-free: `strip_env` consumes the `export` word separately, because
    `shlex` splits `export FOO=1` into two tokens and never into one.

    The `export` spelling still has to WORK, since
    `hooks/no-unauthorized-merge.py`'s `ALLOW_MERGE` anchor accepts it and an
    escape valve that rejects its own precedent's spelling is not an escape
    valve. `strip_env` is where that support lives.
    """
    value = None
    for tok in env_tokens:
        key, sep, val = tok.partition("=")
        if sep and key == name:
            value = val
    return value


def git_subcommand(argv):
    """`(subcommand, rest, env)` when `argv` is a `git` invocation, else `None`.

    `env` is the leading assignment tokens, so a caller can read an override
    prefix scoped to THIS command rather than to any segment of the line.
    `rest` is everything after the subcommand word.

    The subcommand is returned VERBATIM for the caller to compare with `==`,
    which is what keeps a caller from repeating `no-unshipped-commit.py`'s
    measured bug: a `\\b` word boundary sits happily between `commit` and `-`,
    so a `git\\s+commit\\b` scan matched `git commit-tree` and
    `git commit-graph write`.
    """
    env, rest = strip_env(argv)
    if not rest or rest[0] != "git":
        return None
    i = 1
    while i < len(rest) and rest[i].startswith("-"):
        i += 2 if rest[i] in GIT_VALUE_OPTS else 1
    if i >= len(rest):
        return None  # bare `git`, or global options only
    return rest[i], rest[i + 1:], env
