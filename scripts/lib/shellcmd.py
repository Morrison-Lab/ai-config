"""Split a shell command string into simple-command argv lists, and classify
each as a `git` invocation.

WHY THIS MODULE EXISTS
----------------------
This splitter was copied into EIGHT hooks before the module was written:

    hooks/flag-add-a-outside-pathspec.py       hooks/no-clobbering-push.py
    hooks/flag-reset-hard-uncommitted-work.py  hooks/no-delete-branch-under-stacked-pr.py
    hooks/flag-stale-adjacent-comment.py       hooks/no-unreviewed-pr.py
    hooks/remind-ci-crosscheck-sim-verdict.py  hooks/warn-nonglobal-substitution.py

Derive that set from the CONSTANT, not from the function name:

    grep -rlF '_SHELL_OPS = set("();|&")' hooks/   ->  8 files
    grep -rl  "def _simple_commands"      hooks/   ->  7 files

`remind-ci-crosscheck-sim-verdict.py` spells its copy `simple_commands`, so an
identifier search misses it and a migration keyed on that search would leave
one behind. The loop variable differs between copies too (`t` in some, `tok`
in others), which is why a use-site grep is the wrong query as well.

The bodies are identical, and so is the heredoc defect `_heredoc_free` fixes
below -- which is the argument for a module rather than a ninth copy. Those
eight are NOT rewired here: migrating eight live guards, two of which can
REFUSE (`no-clobbering-push.py` denies, `no-unreviewed-pr.py` blocks; the
other six only add context), is its own change with its own review, tracked
as ai-config#3178 --- not by the closed ai-config#2993, which reported the
defect and shipped this module rather than the migration. This module
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

THREE LIMITS, ALL INHERITED FROM THE EIGHT COPIES
--------------------------------------------------
The heredoc pre-pass and the newline rewrite run on RAW TEXT, ahead of `shlex`,
so neither knows the quoting rules the paragraph above credits `shlex` with.
State that here rather than letting the argv-split argument imply otherwise --
this docstring is the contract ai-config#3178 will migrate eight live guards
onto, two of which can refuse.

  * `RX_HEREDOC_OPEN` is QUOTE-BLIND. A `<<` inside a quoted argument -- a commit
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

    A caller can therefore see a command that the shell would not run:

        git commit -m x && echo '" LF "' git push

    splits so that `git push` -- really an argument to `echo` -- reads as a
    command. That is the FALSE POSITIVE direction.

    IT ALSO RUNS THE OTHER WAY, and the earlier revision of this section said
    it did not. A separator-only token landing between `git` and its
    subcommand ORPHANS the subcommand, hiding a real command. The value of any
    `GIT_VALUE_OPTS` global option is an arbitrary string, so:

        git commit -m wip && git -C '&' push --force origin main
        ->  [..., ['git', 'commit', '-m', 'wip'], ['git', '-C'],
             ['push', '--force', 'origin', 'main']]

    `git_subcommand(['git', '-C'])` returns `None` because `-C` consumes a
    token that is not there, and `['push', ...]` fails the `rest[0] != "git"`
    test. The push is gone. The same hole opens through the newline rewrite
    this limit is named for: `git commit -m x && git -C '" LF "' push` is
    silent too. Both were measured, and the shell really does tokenize them
    that way -- git rejects `&` for not existing as a path, not for being
    malformed.

    Reachability is poor: it needs a path composed only of `();|&` or a bare
    newline, so no real workflow produces one, and every sibling carrying the
    same `_SHELL_OPS` test is equally blind. It is stated because a limits
    section that says "this cannot hide a command from you" is the sentence a
    later reader relies on, and that sentence was wrong.

The first two fail toward silence or toward a mangled argument. The third
fails BOTH ways -- a phantom command and a hidden one -- and is stated
separately for that reason. Fixing any of them
means a quote-aware pre-scan, which is a real parser and out of scope for an
extraction; ai-config#3178 is where that belongs, alongside migrating the
eight copies.
"""
from __future__ import annotations

import os
import re
import shlex

# `<<WORD`, `<<'WORD'`, `<<-"WORD"`, then the body up to a terminator that `<<-`
# allows to be tab-indented. The NEWLINE AFTER the terminator is deliberately
# outside the match -- see `_heredoc_free`.
# The OPENER only. Finding the terminator needs the `-` flag, which a single
# pattern cannot branch on, so `_heredoc_free` scans for it.
#
# The delimiter class is not `\w+`. A shell delimiter is an ordinary word, so
# `END-MSG` and `EOF.1` are legal and common, and `\w` matches neither --- the
# opener then went unrecognized, the body was left as live text, and a heredoc
# merely CONTAINING `git commit && git push` was refused. A false DENY on a
# harmless call is the direction README calls worse than a missing hook.
# The lookbehind is what tells a heredoc from a HERE-STRING. `cat <<< word`
# carries no body, but without the guard the pattern matched its SECOND and
# THIRD `<` as an opener and blanked everything after it as a body -- so a
# `git commit ... && git push` chain written after a here-string was erased
# and the guard went silent. Measured: `cat <<< word` rendered as `cat < << `.
#
# The blank class is `[ \t]` rather than `\s` for grammar fidelity only: POSIX
# lets BLANKS separate `<<` from its delimiter word, and a newline there is a
# syntax error rather than an opener. It fixes no measured defect --- the body
# scan below frames each line from the match's own end, so a straddling match
# corrupts nothing --- and a mutation restoring `\s` kills no case. Read that
# survivor as an unmotivated-by-a-bug change, not as missing coverage.
RX_HEREDOC_OPEN = re.compile(r"(?<!<)<<(-?)[ \t]*(['\"]?)([^\s'\"<>&|;()`$]+)\2")

# No `export` alternative here on purpose. `shlex` splits `export FOO=1` into
# TWO tokens, so an `export`-prefixed assignment never reaches this pattern as
# one word -- `strip_env` stops at the `export` token instead, since the
# builtin runs no command. A `(?:export\s+)?` group here was unreachable, and a
# mutation removing it left the suite green, which is how it was found.
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
    Substituting a bare `"<<"` -- what all eight copies of this function do --
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

    THE TERMINATOR IS ANCHORED, and loosely matching it was a false-DENY
    source. The old pattern accepted `[ \t]*<delim>` anywhere, so an indented
    `EOF` INSIDE a body closed the heredoc early and the rest of the body was
    parsed as live commands. The shell is stricter: `<<` requires the
    terminator at column 0, and only `<<-` strips indentation, tabs alone.
    Both spellings are honoured here.

    An unterminated heredoc runs to the end of the input, as the shell reads
    it, so everything after the opener is body.
    """
    out = []
    pos = 0
    while True:
        m = RX_HEREDOC_OPEN.search(command, pos)
        if m is None:
            out.append(command[pos:])
            return "".join(out)
        # ONE LINE MAY OPEN SEVERAL HEREDOCS, and handling only the first
        # was a false DENY. `cat <<A > f1 && cat <<B > f2` queues two bodies;
        # emitting the rest of the opener line verbatim without re-scanning
        # it left B unrecognized, so B's body stayed live text and a
        # `git commit && git push` written inside it was refused. The shell
        # reads the queued bodies back to back after the newline, in opener
        # order, so collect the delimiters across the whole line first and
        # consume the bodies in that order.
        #
        # This predates the opener-line fix below rather than following from
        # it, though it is easy to read the other way round. Checked against
        # `7b54d28`, whose version dropped the opener-line remainder and so
        # lost B's opener with it: the same input leaks the same two commands
        # as live text. Different route, same defect.
        line_end = command.find("\n", m.end())
        scan_end = len(command) if line_end == -1 else line_end
        delims = []
        cursor = pos
        while m is not None and m.start() < scan_end:
            # THE REST OF THE OPENER'S LINE IS NOT BODY, and dropping it was
            # a bypass. A heredoc redirection is one word of a command that
            # can carry more after it --- `git commit -F - <<'EOF' && git
            # push` runs the push, and discarding everything from the opener
            # to the body's first newline discarded that push, so the guard
            # went silent on a real chain. Keep it; only the BODY is blanked.
            out.append(command[cursor:m.start()])
            out.append(" << ")
            delims.append((m.group(1), m.group(3)))
            cursor = m.end()
            m = RX_HEREDOC_OPEN.search(command, cursor)
        out.append(command[cursor:scan_end])
        if line_end == -1:
            return "".join(out)
        out.append("\n")
        pos = line_end + 1
        for dash, delim in delims:
            indent = r"[\t]*" if dash else ""
            # Nothing may follow the delimiter. Bash requires the terminator
            # line to match exactly --- verified directly: a body line
            # `EOF  ` does not close the heredoc, the body continues past it.
            # Accepting trailing whitespace read such a line as the
            # terminator, so the rest of the body was parsed as live commands
            # and a harmless call was refused.
            term = re.compile(r"^" + indent + re.escape(delim) + r"$", re.M)
            hit = term.search(command, pos)
            if hit is None:
                return "".join(out)
            pos = hit.end()


def _comment_free(command):
    """Drop unquoted `#` comments, keeping the newlines that terminate them.

    `simple_commands` turns a newline into `;` so a script's second line is
    seen as its own command. A `#` comment must therefore be removed BEFORE
    that rewrite: afterwards the comment's terminating newline is a `;`, and
    `shlex` -- whose `commenters` is `#` -- discards everything from the `#`
    to the end of the WHOLE input rather than to the end of its line.
    Measured: `git commit -m x # note` followed by `git push` returned no
    commands past the comment, so the guard went silent on exactly the chain
    it exists to refuse.

    THE SCAN IS OVER THE WHOLE COMMAND, NOT PER LINE, and that is the
    correction rather than a detail. A first version reset quote state at
    every newline, which is wrong for the input shape this module's own
    docstring already anticipates: a double-quoted `-m` message spans
    physical lines, so a body line beginning `#` read as an unquoted comment
    and the rest of the command -- closing quote, `&&`, and the push -- was
    deleted with it. That failed OPEN, since `simple_commands` then returns
    `None` and the caller allows.

    A comment begins only where a TOKEN begins: at the start, after
    whitespace, or immediately after a shell operator character. The last is
    not a nicety --- `shlex` starts a new token straight after `&&`, `;`, `|`
    or `)`, so `git commit -m x &&#note` comments out the rest with no space
    anywhere, and a whitespace-only rule leaves that spelling open while
    closing the one beside it.

    Backslash escapes the following character outside single quotes, so it
    consumes that character rather than only itself. Skipping just the
    backslash let `\"` toggle quote state, and an odd number of them before a
    `#` corrupted the balance into the same fail-open deletion.
    """
    single = double = False
    out = []
    i = 0
    n = len(command)
    while i < n:
        ch = command[i]
        if ch == "\\" and not single and i + 1 < n:
            out.append(ch)
            out.append(command[i + 1])
            i += 2
            continue
        if ch == "'" and not double:
            single = not single
        elif ch == '"' and not single:
            double = not double
        elif ch == "#" and not single and not double:
            prev = command[i - 1] if i else ""
            if not prev or prev.isspace() or prev in _SHELL_OPS:
                j = command.find("\n", i)
                if j == -1:
                    break
                i = j
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def simple_commands(command):
    """Split `command` into simple-command argv lists; `None` on a parse error.

    Join backslash-continued lines, blank heredoc bodies, turn unquoted
    newlines into `;`, then let `shlex` split and dequote. The tokens come back
    DEQUOTED, so a quoted `"git push"` arrives as one token inside some other
    command's argv rather than as its own simple command.

    Subshell nesting is FLATTENED here: `(cd /a && ls)` comes back as two
    argv lists indistinguishable from `cd /a && ls`, because the `(` and `)`
    tokens are separators and are dropped with the rest. A caller that models
    shell STATE rather than asking which programs ran needs the distinction,
    since a `cd` inside a subshell moves that subshell and never the parent;
    `simple_commands_with_scope` is the same split with each argv paired with
    the subshell it runs in.
    """
    with_scope = simple_commands_with_scope(command)
    if with_scope is None:
        return None
    return [argv for _scope, argv in with_scope]


def simple_commands_with_scope(command):
    """`simple_commands`, each argv paired with the SUBSHELL IT RUNS IN.

    A scope is the tuple of subshell ids from the caller's own shell down to
    the command, so `(0,)` is the caller's shell and `len(scope) - 1` is the
    nesting depth. Every `(` allocates a FRESH id, so two sibling subshells
    at the same depth carry different scopes and a caller can tell that the
    second inherited from the parent rather than from the first.

    Parens are read one character at a time rather than by net count, because
    a single separator token can both close and open: `shlex` emits `);` and
    `)&&(` as one token each, and only the ordered read gives `)&&(` a new id
    on the far side. The per-token net count this replaced got the depth
    right and the identity wrong.

    `{ ... }` grouping is NOT nesting for this purpose and is not counted: it
    runs in the current shell, so a `cd` inside one does move the caller.
    """
    # ORDER MATTERS, and the natural order is wrong. Joining continuations
    # first lets a heredoc BODY line ending in a backslash eat its own
    # terminator, after which `_heredoc_free` closes at some later occurrence of
    # the delimiter word -- or never -- and everything between is swallowed.
    # Measured: `git commit -F - <<EOF / a \\ / EOF / git push` lost the push
    # entirely, so the guard went silent. A heredoc body is literal text and a
    # backslash in it continues nothing, so it must be removed BEFORE the
    # continuation join runs over what remains.
    command = _heredoc_free(command)
    command = re.sub(r"\\\r?\n", " ", command)
    command = _comment_free(command)
    command = command.replace("\n", ";")
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return None
    cmds, cur, scope, cur_scope, opened = [], [], [0], (0,), 0
    for tok in toks:
        if tok and set(tok) <= _SHELL_OPS:
            if cur:
                cmds.append((cur_scope, cur))
                cur = []
            for ch in tok:
                if ch == "(":
                    opened += 1
                    scope.append(opened)
                elif ch == ")" and len(scope) > 1:
                    scope.pop()
        else:
            if not cur:
                cur_scope = tuple(scope)
            cur.append(tok)
    if cur:
        cmds.append((cur_scope, cur))
    return cmds


def strip_env(argv):
    """`(env, argv_with_git_first)` for one simple command.

    Adapted from `hooks/no-push-without-self-review.py`'s `_strip_env`, which is
    the tested in-repo implementation. Leading env assignments, command
    wrappers, and shell keywords are peeled off, and the program token is
    normalized to its basename -- so `/usr/bin/git push`, `timeout 60 git push`,
    `{ git commit -m x; }`, and `sudo -u me git push` all resolve to a `git`
    first token, as they do for the guard this one is paired against.

    `env` is the list of assignment TOKENS, in order, and never contains an
    `export` word --- a caller trusting otherwise would strip a prefix that
    cannot be present.

    An `export` token STOPS the scan and yields no program, because the
    builtin runs nothing: `export FOO=1 git push` exports three names and
    invokes no git. Peeling it as though it were a wrapper is what made this
    return `git push` for a command that never pushes.
    """
    rest, env, after_wrapper = list(argv), [], False
    while rest:
        tok = rest[0]
        if ENV_ASSIGNMENT.match(tok):
            env.append(tok)
            rest = rest[1:]
            after_wrapper = False
            continue
        # `export` RUNS NOTHING, so it is a stop rather than a peel. It is a
        # builtin whose arguments are names and assignments, so
        # `export FOO=1 git push` exports the three names `FOO`, `git` and
        # `push` and invokes no git at all -- verified against bash, which
        # produced no git output for it. Peeling the word (and then the
        # assignment after it) left `git push` as the command and refused a
        # call that never happens. Nothing after `export` in this simple
        # command can be a git invocation, so return no program at all.
        if tok == "export":
            return env, []
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
    r"""The value assigned to `name` by `env_tokens`, or `None`.

    The LAST assignment wins, as the shell does. Tokens arrive already
    `export`-free, because `strip_env` stops at an `export` token rather than
    peeling it.

    That is not a gap in the `ALLOW_MERGE` escape valve, though
    `hooks/no-unauthorized-merge.py`'s anchor does accept a
    `(?:export\s+)?` prefix. The one-line spelling it accepts runs no command
    at all --- `export ALLOW_MERGE=1 git merge main` exports the names
    `git`, `merge` and `main` --- so there is nothing for an escape valve to
    authorize. The spellings that DO carry the value into a git invocation
    are the bare `ALLOW_MERGE=1 git merge ...` prefix, which arrives here as
    an assignment token, and a separate `export ALLOW_MERGE=1;` statement,
    whose effect on a later simple command is outside what a single argv can
    show.
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


def resolve_cd_target(rest: list[str], cur_dir: str | None) -> str | None:
    """The directory a `cd`, `pushd`, or `popd` leaves the shell in.

    `rest` is one simple command's argv, `strip_env`-normalized, whose first
    token is `cd`, `pushd`, or `popd`. `cur_dir` is where the shell stood
    before it. `None` comes back when the move is INDETERMINATE rather than
    absent -- `cd -` goes to `OLDPWD`, `popd` pops a stack this scan does not
    simulate, and a `$VAR` target expands at runtime -- so a caller must
    treat `None` as "somewhere I cannot name", never as "unchanged".

    Adapted verbatim from `hooks/no-push-without-self-review.py`'s
    `_resolve_cd_target`, which is the tested in-repo implementation. This is
    a COPY and not a move: that guard still holds its own, because it can
    refuse a push and migrating a deny-capable guard is its own change with
    its own review --- the same call this module's header makes for the eight
    `_simple_commands` copies. The duplication that leaves is tracked as
    ai-config#3177, not by the closed ai-config#2993, whose scope is
    `_simple_commands` and `_strip_env`. New callers import from here.
    """
    cmd_name = rest[0]
    if cmd_name == "popd":
        # `popd -n` suppresses the directory change, leaving cur_dir untouched.
        if any(tok.startswith("-") and "n" in tok and tok != "-" for tok in rest[1:]):
            return cur_dir
        # Without a full dirstack simulation across commands, popd without -n clears the hint.
        return None

    # For `cd` and `pushd`: parse flags and positional directory target.
    i = 1
    target = None
    suppress_chdir = False
    while i < len(rest):
        tok = rest[i]
        if tok == "--":
            # End of options; next token (if present) is the target directory.
            if i + 1 < len(rest):
                target = rest[i + 1]
            break
        if tok == "-":
            # `cd -` switches to OLDPWD, which is indeterminate without shell state.
            return None
        if tok.startswith("+") or (tok.startswith("-") and tok[1:].isdigit()):
            # `pushd +N` or `pushd -N` rotates the directory stack.
            return None
        if tok.startswith("-"):
            # Flags like -P, -L, -e, -@ for cd, or -n for pushd
            if cmd_name == "pushd" and "n" in tok:
                suppress_chdir = True
            i += 1
            continue
        target = tok
        break

    if cmd_name == "pushd" and suppress_chdir:
        # `pushd -n <dir>` rotates/modifies stack without changing current working directory.
        return cur_dir

    if target is None:
        # Bare `cd` or `cd -P` with no directory defaults to $HOME (~).
        # For pushd with no args, it swaps top 2 stack entries (indeterminate -> None).
        if cmd_name == "pushd":
            return None
        target = "~"

    # Expand ~ and ~/path
    if target == "~" or target.startswith("~/"):
        target = os.path.expanduser(target)
    elif target.startswith("$HOME/") or target == "$HOME" or target.startswith("${HOME}/") or target == "${HOME}":
        home = os.path.expanduser("~")
        if target in ("$HOME", "${HOME}"):
            target = home
        elif target.startswith("$HOME/"):
            target = os.path.join(home, target[len("$HOME/"):])
        elif target.startswith("${HOME}/"):
            target = os.path.join(home, target[len("${HOME}/"):])
    elif "$" in target or "`" in target:
        # Unexpanded shell variables/substitutions cannot be resolved statically.
        return None

    if os.path.isabs(target):
        return os.path.normpath(target)
    if cur_dir is not None:
        return os.path.normpath(os.path.join(cur_dir, target))
    return os.path.normpath(target)


# A SHELL specifically, which is a narrower question than "an interpreter".
# Only a shell's `-c` takes a nested COMMAND LINE. `python -c` takes Python
# SOURCE, where `git push` is a syntax error rather than a push, so re-testing
# a Python `-c` argument under shell semantics invents commands nobody ran.
# The distinction is `hooks/no-empty-promise.py`'s, which spent four review
# rounds on this class and is the reference implementation.
#
# Wider than the reference in two ways it was measured to need. `ash` is the
# default shell on Alpine and the busybox applet, and `mksh`/`pdksh` take `-c`
# identically; a bypass guard's coverage is decided by its weakest spelling.
# And a version suffix is an ordinary way to name a binary -- the reference
# allows one for `python[\d.]*` and for no shell, so `/bin/bash-5.2 -c` walked
# past it.
SHELL_PROGRAM = re.compile(
    r"\A(?:[\w.@/-]*/)?(?:ash|bash|dash|ksh|mksh|pdksh|sh|zsh)(?:-?[\d.]+)?\Z",
    re.I)

# `busybox sh -c ...` names the shell in ARGV[1]. The applet is the program as
# far as the kernel is concerned and the shell as far as this question is.
_MULTICALL = re.compile(r"\A(?:[\w.@/-]*/)?busybox\Z", re.I)

# A `-c`-shaped flag hands a command STRING to the shell.
#
# WIDER than the reference implementation's `-[a-z]*c`, which anchors the `c`
# last and so reads `-ec` and misses `-cx`. Short options cluster in any order
# and every shell here spells `-c` as one letter, so a cluster CONTAINING `c`
# sets it: `bash -cx 'git push'` really pushes.
#
# A LOWERCASE `c` is required, and any case is allowed around it. `-C` alone is
# `noclobber`, a different option taking no command, and matching it
# case-insensitively produced a hard refusal on `bash -C <file>`, which runs a
# FILE by that name and pushes nothing. But dropping case-insensitivity from
# the whole cluster went too far the other way: `bash -cC '<cmd>'` really runs
# `<cmd>`, and an all-lowercase cluster arm cannot express "contains a
# lowercase `c`" (ai-config#1973 review, round 2 finding 8).
#
# `--command` was carried over from the reference implementation and removed:
# no shell in SHELL_PROGRAM accepts it (`bash --command x` reports "invalid
# option"), so it only ever produced a false DENY. Reusing a pattern
# structurally without checking that each element transfers is exactly what
# `shared/workflow/check-purpose-before-reusing.md` is about.
#
# `+` is accepted alongside `-` because every shell here spells its `set`
# options both ways.
#
# `-check` is deliberately matched, unlike in the reference implementation:
# bash parses it as `-c -h -e -c -k`, so it really is a `-c`. Over-detecting a
# flag is bounded here because the PROGRAM is checked first AND the scan stops
# at the script operand -- without that second stop, `bash script.sh -c "x"`
# was refused for a `-c` belonging to the script's own argv (round 2 finding
# 5).
DASH_C_FLAG = re.compile(r"\A[-+][A-Za-z]*c[A-Za-z]*\Z")

# Tokens that may precede the program without changing what runs.
#
# `setsid` is the ONLY addition over COMMAND_WRAPPERS. An earlier version of
# this comment named `sudo` and `stdbuf` as additions too; both are already
# members, and `stdbuf` never appeared in the literal at all (ai-config#1973
# review, round 2 finding 6). The wording had been written against
# `hooks/no-empty-promise.py`'s `_EXEC_PREFIX`, which lists a different set.
_DESCENT_SKIPPABLE = COMMAND_WRAPPERS | {"setsid"}


def command_program(argv):
    """Index of ARGV's program token, for the purpose of finding a SHELL.

    Not a general program resolver, and the summary used to read as one. When
    the wrapper look-ahead finds no shell, this returns the index of the
    wrapper's first ARGUMENT rather than of the program:
    `command_program(["timeout", "5", "git", "push"])` is 1, which is `"5"`.
    That is harmless to the only caller, which rejects a non-shell
    immediately, and would mislead any other.

    Leading `VAR=value` assignments and wrappers are skipped. A wrapper with
    its own arguments (`sudo -u me bash`, `timeout 5 bash`, `env -i bash`) is
    handled by looking ahead a bounded distance for a shell rather than by
    modelling each wrapper's option grammar -- the same trick `strip_env` uses,
    and nothing is consumed unless a shell is actually found.
    """
    index, after_wrapper = 0, False
    while index < len(argv):
        token = argv[index]
        if ENV_ASSIGNMENT.match(token):
            index += 1
            after_wrapper = False
            continue
        # A shell KEYWORD is not the program. `strip_env` has skipped these
        # since the constant was introduced, and its comment says why: the
        # splitter breaks on `;` and `&&`, so the keyword lands at argv[0] of
        # the segment carrying the command. Omitting the same skip here made
        # every keyword-wrapped nesting invisible to the descent --
        # `{ sh -c "git push --force origin main"; }`, `if true; then sh -c
        # "..."; fi` and `for i in 1; do sh -c "..."; done` were each SILENT
        # while their unwrapped forms denied (ai-config#1973 review, round 4
        # finding 1, reproduced independently by the @claude review of #3645).
        if token in SHELL_KEYWORDS:
            index += 1
            after_wrapper = False
            continue
        # Basename first. The membership test used to be an exact string while
        # SHELL_PROGRAM allows a path prefix, so `/bin/sh -c` was followed and
        # `/usr/bin/env bash -c` was not -- measured silent on both guards
        # while really running the push (ai-config#1973 review, round 2).
        if os.path.basename(token) in _DESCENT_SKIPPABLE:
            index += 1
            after_wrapper = True
            continue
        if after_wrapper:
            window = argv[index:index + WRAPPER_ARG_WINDOW]
            hit = next((offset for offset, candidate in enumerate(window)
                        if SHELL_PROGRAM.match(candidate)
                        or _MULTICALL.match(candidate)), None)
            if hit is not None:
                index += hit
        break
    if index < len(argv) and _MULTICALL.match(argv[index]):
        index += 1
    return index


def nested_shell_commands(argv):
    """Every token in ARGV that a shell there might be handed as a command.

    STOP MODELLING THE OPTION GRAMMAR. Three rounds of review found three
    separate holes in it, each a real push executing while both guards stayed
    silent: an operand assumed adjacent to `-c`; an option's VALUE read as the
    script operand (`bash -o pipefail -c`); a `+`-prefixed set option read the
    same way (`bash +x -c`), and a value-taking option AFTER the `-c`
    (`bash -c -O extglob`) whose value was returned as the command. Each fix
    named the next gap in its own comment. `bash --`, `bash -oc` and
    `bash --command` were the over-blocks the same modelling produced.

    The enumeration is not finishable, and it does not have to be, because
    over-detection here is nearly free. A candidate that is not really a
    command line is handed to the caller's own analysis, which finds no `git`
    in it and reports nothing. The cost of a wrong guess is one wasted scan;
    the cost of a missed one is an unguarded destructive command. So when the
    program is a shell and a `-c`-shaped flag appears anywhere in its argv,
    every token after the PROGRAM is a candidate, except the `-c`-shaped
    tokens themselves.

    Stated that precisely because the shorter "EVERY later token" is wrong in
    both directions, and this sentence is the whole specification of the
    design. Tokens BEFORE the flag are candidates too:

        >>> nested_shell_commands(["bash", "-o", "pipefail", "-c", "git push"])
        ['-o', 'pipefail', 'git push']

    and a second `-c` AFTER the flag is not one (round 4 finding 13).

    Returns a list, possibly empty, in argv order.

    What this over-detects, stated rather than discovered later: `bash -- -c
    "<cmd>"` runs no `<cmd>` (the `--` makes `-c` the script name and bash
    exits 127), and `bash script.sh -c "<cmd>"` hands `-c "<cmd>"` to the
    script's own argv. Both are scanned, and both cost only a scan unless the
    token really does carry a gated command -- in which case blocking a command
    that executes nothing is the cheap error.
    """
    split_string = _env_split_string(argv)
    index = command_program(argv)
    if index >= len(argv) or not SHELL_PROGRAM.match(argv[index]):
        return split_string
    rest = argv[index + 1:]
    if not any(DASH_C_FLAG.match(token) for token in rest):
        return split_string
    return split_string + [
        token for token in rest if not DASH_C_FLAG.match(token)]


# `env -S` / `--split-string` takes ONE argument and splits it into a command
# line itself, so `env -S 'bash -c "<cmd>"'` really execs that shell -- but the
# whole invocation is a single already-quoted token, and `command_program`
# skips `env` as a bare wrapper and then finds no shell. The descent never
# reached it, and `env -S 'bash -c "git push --force origin main"'` ran the
# push while the guard stayed silent (ai-config#1973 review, round 4 finding 5,
# reproduced independently by the @claude review of #3645).
#
# Both spellings, attached and detached, and `-vS` style clusters: `env` reads
# `-S` anywhere in a short cluster.
_ENV_PROGRAM = re.compile(r"\A(?:[\w.@/-]*/)?env\Z")
_SPLIT_STRING_ATTACHED = re.compile(r"\A(?:-[A-Za-z]*S|--split-string=)(.+)\Z")
_SPLIT_STRING_BARE = re.compile(r"\A(?:-[A-Za-z]*S|--split-string)\Z")


def _env_split_string(argv):
    """The command lines `env -S` would split out of ARGV, in argv order.

    Over-detects on purpose, like the rest of this module: a token that is not
    really a command line costs one wasted scan, while a missed one is an
    unguarded destructive command.

    The `env` is looked for in a WINDOW from the head rather than at `argv[0]`
    alone. Testing only the head asked whether `env` was typed first, which is
    a different question from whether `env` runs: every one of `command`,
    `sudo`, `nohup` and `exec` is already in `COMMAND_WRAPPERS`, which
    `command_program` skips two functions up, so the module knew those words
    were transparent while this function did not -- and `command env -S "bash
    -c '<push>'"` ran the push with both guards silent, where the bare `env -S`
    spelling denied (ai-config#3645 pre-merge gate, finding 3).

    A window rather than a wrapper-by-wrapper skip, for the reason
    `nested_shell_commands` gives at length: the enumeration is not finishable
    and does not have to be, because a wrong guess costs one scan of a token
    that carries no gated command.
    """
    start = next((position for position, token
                  in enumerate(argv[:1 + WRAPPER_ARG_WINDOW])
                  if _ENV_PROGRAM.match(os.path.basename(token))), None)
    if start is None:
        return []
    out = []
    for position, token in enumerate(argv[start + 1:], start=start + 1):
        attached = _SPLIT_STRING_ATTACHED.match(token)
        if attached:
            out.append(attached.group(1))
        elif _SPLIT_STRING_BARE.match(token) and position + 1 < len(argv):
            out.append(argv[position + 1])
    return out


def shell_c_expansions(command, max_depth=3):
    """`command` first, then every command line reachable via a shell's `-c`.

    WHY THIS EXISTS
    ---------------
    A hook that tokenizes and compares exact tokens is bypassed outright by
    wrapping the gated command in an interpreter's `-c` argument. `shlex`
    collapses the embedded command into ONE opaque token, so `argv[0]` is the
    interpreter and every head-token comparison fails immediately.

    Measured on `main` (ai-config#1973): `git push --force origin main` fed to
    `hooks/no-clobbering-push.py` denies, and `sh -c "git push --force origin
    main"` produces no output and is silently allowed. That is the direction
    `shared/principles/fail-fast.md` calls the dangerous one -- a silent
    discharge rather than an over-warn.

    HOW TO USE IT
    -------------
    Analyse each returned string SEPARATELY. Do not concatenate their argv
    lists: a nested `-c` argument is a DIFFERENT SHELL, so its `cd` moves that
    shell and not the caller's.

    A caller that resolves anything against a WORKING DIRECTORY must go
    further than that, and `hooks/no-clobbering-push.py` records what happens
    when it does not: this function cannot tell a nested shell what directory
    it starts in, because that depends on the `cd`s the outer shell ran first.
    A verdict that depends on a directory is therefore unsound for a nested
    piece, and evaluating one anyway fabricated a warning quoting an unrelated
    repository's commits. Use nested pieces only for verdicts decidable from
    the command TEXT.

    THE FAILURE DIRECTION INVERTS WHEN THIS IS COPIED INTO A GUARD
    --------------------------------------------------------------
    In `hooks/no-empty-promise.py`, where this descent was extracted from, each
    give-up point fails CLOSED -- the worst case is a promise that does not
    discharge. In a guard the identical give-up point fails OPEN. So the limits
    below are not the reference's limits with a different label on them; they
    are holes, and each one is a command that runs while the guard is silent.

    LIMITS
    ------
    A shell function, an `eval`, a command assembled from a variable, a remote
    command sent by `ssh`, a `-c` operand built by expansion, and any shell not
    in SHELL_PROGRAM all yield nothing extra.

    So does an interpreter that SHELLS OUT rather than taking a command line:
    `python3 -c "import os; os.system('git push --force origin main')"` and
    `perl -e "system(q(...))"` run the push and yield nothing here. That is
    deliberate -- a Python `-c` argument is SOURCE, and reading it as shell
    once made a bare path inside it look like an execution -- but it is named
    because the issue this closes is titled around an interpreter's `-c`, and
    a reader could otherwise take the silence for coverage (round 4
    finding 9).

    So does a wrapper chain longer than `WRAPPER_ARG_WINDOW` tokens --
    `sudo -u me -H -E -i -n bash -c "<push>"` measured silent -- and a wrapper
    the set does not know, such as `flock /tmp/x bash -c` or
    `git bisect run sh -c`. `bash -s` reads its script from stdin, which is not
    in the argv at all. Each of these is a HOLE rather than a design boundary,
    and they are named here because the previous version of this section listed
    only the first group and so read as exhaustive (ai-config#1973 review,
    round 2 finding 9).

    So does a `-c` nested more than `max_depth` levels deep. Measured at the
    default of 3: one, two and three levels of `bash -c` reach the push, four
    and five do not. It is listed among the holes rather than only under
    BOUNDS below, because a reader auditing coverage reads the enumerated
    list and a cap named elsewhere as a performance knob does not register as
    a bypass (ai-config#3645 pre-merge gate, finding 8).

    BOUNDS
    ------
    `max_depth` and the `seen` set bound the walk, and neither is what makes it
    terminate. The operand is NOT always a substring of its parent, which this
    paragraph claimed until round 2 of ai-config#1973's review: `simple_commands`
    returns DEQUOTED tokens, so `bash -c "git commit -m \\"x\\""` yields
    `git commit -m "x"`, which its parent does not contain. What is true, and
    is what makes the recursion finite, is that dequoting never lengthens and
    the program plus its `-c` are always consumed, so each operand is strictly
    shorter than the text it came from. The bounds cap work on adversarial
    input rather than preventing a loop. `max_depth` is nonetheless a real
    hole, and it is named as one in LIMITS above: raising it is nearly free
    for the `deny_only`, network-free lexical pass both guards run, and the
    default stays at 3 only because nothing has yet been measured past it.

    An unparseable piece yields no children and does not discard the pieces
    already found.
    """
    found = [command]
    seen = {command}
    frontier = [(command, 0)]
    while frontier:
        text, depth = frontier.pop(0)
        if depth >= max_depth:
            continue
        argvs = simple_commands(text)
        if argvs is None:
            continue  # unparseable: no children, and the rest still stands
        for argv in argvs:
            for nested in nested_shell_commands(argv):
                if nested in seen:
                    continue
                seen.add(nested)
                found.append(nested)
                frontier.append((nested, depth + 1))
    return found


# `/c/...` (Git Bash / MSYS) or `/cygdrive/c/...` (Cygwin): a drive letter as
# the first path segment. Group 1 is the letter, group 2 the remainder.
_RX_POSIX_DRIVE = re.compile(r"\A/(?:cygdrive/)?([A-Za-z])(?=/|\Z)(.*)\Z", re.S)


def native_path(path, is_windows=None):
    """PATH in a form native Windows `git.exe` and `subprocess` can open.

    A hook's command text comes from the Bash tool, which on Windows is Git
    Bash, so a `cd` or `git -C` target is spelled `/c/Users/...`. The hook
    itself runs under native Windows Python and calls native `git.exe`, and
    neither reads that form: measured, `git -C /c/Users/x rev-parse HEAD`
    exits 128 with "cannot change to '/c/Users/x'", and
    `subprocess.run(..., cwd="/c/Users/x")` raises `NotADirectoryError`
    (WinError 267). A push guard that resolves a push in that directory then
    either refuses a reviewed push or fails open, depending on the guard.

    Only the drive-letter forms are rewritten (`/c/x` and `/cygdrive/c/x`
    become `C:/x`). Other absolute MSYS paths (`/tmp`, `/usr`) map to the
    Git install's own root, which this cannot know, so they are returned
    unchanged. Off Windows the path is always returned unchanged, since
    `/c/...` is then an ordinary directory. `None` passes through.
    """
    if path is None:
        return None
    if is_windows is None:
        is_windows = os.name == "nt"
    if not is_windows:
        return path
    match = _RX_POSIX_DRIVE.match(path)
    if not match:
        return path
    return f"{match.group(1).upper()}:{match.group(2) or '/'}"
