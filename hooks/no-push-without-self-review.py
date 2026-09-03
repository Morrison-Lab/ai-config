#!/usr/bin/env python3
"""PreToolUse guard: require an adversarial self-review before `git push`.

Every self-review this corpus calls for is dispatched to a separate
`adversarial-reviewer` subagent rather than performed inline by the session
that wrote the diff (`shared/workflow/adversarial-self-review.md`). This guard
enforces the pre-push case.

THREE QUESTIONS, NOT ONE
------------------------
**WHO said it.** A transcript-wide search for the verdict phrase cannot work,
for the reason `no-handrolled-verdict-parse.py` documents (ai-config#1297):
this corpus quotes verdict vocabulary constantly. Here it was self-defeating
rather than merely unsound -- a `PreToolUse` deny reason is surfaced back into
the transcript as the blocked call's result, so one blocked push authorized
every retry after it, and `Read`ing any of this repo's prose did the same. So a
verdict is admitted only from the `tool_result` of an `Agent` call whose
`subagent_type` IS the reviewer, and only when that result is not an error.

**WHAT it said.** Restricting provenance does not make a phrase search sound
INSIDE the admitted body, which is the same #1297 failure one layer in: a
review whose closing note quotes the clean verdict it is withholding would be
read as clean. So the verdict is taken from the last line that IS a verdict
line -- anchored at line start, optionally as a heading -- and a quotation
mid-sentence is not one.

**WHAT it was about.** Provenance and content together still let one clean
verdict authorize unlimited later pushes of unrelated work. So the reviewer
states the commit it read as a `Reviewed-Commit: <sha>` line AFTER its verdict,
and this guard resolves what the push would actually ship and compares. That
comparison is the tie between the permission and the code: a later commit, a
`main` merge, a rebase, or a commit made by a subagent in a transcript this
guard cannot see all change what would be shipped and fail it. It also closes
the truncation hole, since a report cut short carries no fingerprint.

Resolving the shipped commits means reading the refspec, not just `HEAD`.
`git push origin other-branch` ships something the reviewer never saw, and an
earlier revision of this guard waved it through while its own docstring claimed
otherwise.

CONSEQUENCES FOR HOW THE REVIEWER IS DISPATCHED
------------------------------------------------
Dispatch it in the FOREGROUND (`run_in_background: false`): a background
dispatch returns an agent id rather than a report, so no verdict ever becomes
that call's result. This is also the Agent tool's own criterion -- the push is
waiting on the answer.

Review AFTER committing, which is where `shared/workflow/ardi.md` already puts
the pause point. A review of uncommitted work names a commit that does not
exist yet.

WHERE IT DELIBERATELY DOES NOT FIRE
------------------------------------
- `git push --dry-run` and `git push --delete` re-head nothing, so there is no
  diff to review. (This is `no-unreviewed-pr.py`'s `_argv_push` rule, reused
  rather than re-derived.)
- A command running `git` through another interpreter (`bash -c "git push"`,
  `ssh host git push`) is one simple command whose argv is not a push. Nothing
  here parses a nested shell.
- A command this guard cannot parse is treated as not-a-push -- the same
  fail-open direction as `main()`'s bare `except`, stated rather than silent: a
  guard that crashed closed would block every push in the session.
- The MCP write tools (`mcp__github__push_files`, `create_or_update_file`,
  `push_files`) commit straight to a remote branch with no local commit to
  fingerprint, so nothing here can check them. They are an open gap, tracked as
  ai-config#1929, not a decision that they are safe.

Authorized override: `ALLOW_UNREVIEWED_PUSH=1`, as an environment assignment on
the pushing command itself.

Scoping it to that command is the whole of the fix. An earlier revision searched
the WHOLE command line -- splitting on `&&`/`;` and testing each segment -- so a
quoted mention of the override anywhere disarmed the guard, and this repo
documents that override in four files. Measured across revisions: with the
second `--allow-unreviewed-push` spelling neutered and only the env spelling
live, three of the four known bypasses still worked. So the second spelling was
not the cause; it is deleted because it was undocumented everywhere and
duplicated a variable that now has one meaning and one placement.

A `:branch` deletion refspec ships nothing, and so passes the commit comparison
-- but it still needs a clean verdict to reach that comparison, unlike
`--dry-run` and `--delete` in the block above, which are never examined at all.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import time

# --- what counts as a verdict ----------------------------------------------

# Anchored at line start, optionally as a Markdown heading. Anchoring is what
# separates a verdict from a sentence quoting one, which a bare `Verdict:`
# search cannot do -- see this module's docstring.
VERDICT_LINE = re.compile(
    r"^[ \t]{0,3}(?:#{1,6}[ \t]*)?Verdict[ \t]*:[ \t]*(?:\*\*)?"
    r"(Ready for merge|Needs (?:more )?work)\b",
    re.I | re.M,
)

# A fenced block is quoted material, so a verdict inside one is an example
# rather than a verdict. Blanking fences before matching is what makes the
# anchoring above mean anything: `> ` is already excluded by the prefix class,
# and four-space indentation by the `{0,3}` bound, but a fence can hold a line
# that is anchored and indented exactly like the real thing.
FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,}).*$", re.M)

# The reviewer's statement of what it read, required to appear AFTER the
# verdict it belongs to: that ordering is what makes a truncated report fail,
# and it is why this is searched forward from the verdict rather than globally.
REVIEWED_COMMIT = re.compile(
    r"\*{0,2}Reviewed-Commit\*{0,2}[ \t]*:[ \t]*\*{0,2}[ \t]*`?([0-9a-fA-F]{7,40})`?",
    re.I,
)

# Matched against an Agent/Task call's `subagent_type` ONLY. An earlier revision
# also matched the call's free-text `prompt`, which any prompt containing the
# word "adversarial" satisfied. A plugin-namespaced name
# (`ai-config:adversarial-reviewer`) is accepted -- the same persona is the same
# reviewer whichever surface registered it.
ADVERSARIAL_AGENT_NAME = re.compile(
    r"\A\s*(?:[\w.-]+[:/])?adversarial[-_ ]?reviewer\s*\Z", re.I
)

# When no dedicated `adversarial-reviewer` persona is registered in the
# environment (e.g. built-in subagents or automated sessions), allow
# fallback subagents whose prompt requests adversarial review.
FALLBACK_AGENT_NAME = re.compile(
    r"\A\s*(?:[\w.-]+[:/])?(?:general[-_ ]?purpose|general|reviewer|code[-_ ]?reviewer|research|self)\s*\Z", re.I
)

REVIEW_PROMPT_RE = re.compile(
    r"\b(?:adversarial[-_ ]?(?:self[-_ ]?)?review|pre[-_ ]?push[-_ ]?review|self[-_ ]?review)\b", re.I
)

AGENT_TOOLS = {"agent", "task", "invoke_subagent", "taskoutput", "task_output", "manage_task"}

OVERRIDE_ENV = re.compile(r"\AALLOW_UNREVIEWED_PUSH=1\Z")

# Degraded mode only, where the shell parser is unavailable and the strict
# argv-scoped check cannot run. Deliberately loose: with no parser this guard
# can only report that it is broken, so a false ALLOW here costs nothing a
# working guard would have caught, while a false DENY has no escape at all --
# a PreToolUse deny is not user-overridable.
DEGRADED_OVERRIDE = re.compile(r"(?:^|[;&|`(\s])ALLOW_UNREVIEWED_PUSH=1\s")

# Options after which no single reviewed commit can describe the push.
# `--branches` is git's own documented alias of `--all` (`git push -h`), so it
# ships every branch while looking like an ordinary unknown option.
PUSH_OPTS_INDETERMINATE = {"--all", "--branches", "--mirror", "--tags",
                           "--follow-tags"}

# `--recurse-submodules` in these modes pushes commits in ANOTHER repository,
# which no fingerprint naming a commit in this one can describe.
SUBMODULE_PUSH_MODES = {"on-demand", "only"}

# The config forms of PUSH_OPTS_INDETERMINATE. Each entry is (key, the flag it
# mirrors, a predicate on the configured value). `{remote}` is filled from the
# resolved remote and the entry is skipped when no remote resolves.
def _is_true(v: str) -> bool:
    return v.strip().lower() in {"true", "yes", "on", "1"}


# (key, the flag it mirrors, a predicate on the value, read-as-boolean).
# The last field matters: a valueless key is true to git and prints empty
# under a plain `--get`, so a boolean entry has to be read with `--bool`.
CONFIG_LIKE_INDETERMINATE_FLAGS = (
    ("remote.{remote}.mirror", "--mirror", _is_true, True),
    ("push.followTags", "--follow-tags", _is_true, True),
    ("push.recurseSubmodules", "--recurse-submodules",
     lambda v: v.strip().lower() in SUBMODULE_PUSH_MODES, False),
)


# --- push detection, borrowed rather than re-derived ------------------------
#
# `no-unreviewed-pr.py`'s detector is shell-parsed rather than regex-matched, so
# it already handles `git -C <dir> push` and `git -c k=v push`, already excludes
# the two push forms that re-head nothing, and is already tested there. A second
# hand-rolled detector would be a DRW finding and would diverge silently
# (ai-config#1920) -- an earlier revision of this file wrote one as a "fallback"
# and it did diverge, on all three of those points. So there is no fallback
# parser: if the sibling cannot be loaded this guard never grades pushes with
# a worse one. It applies only the narrow degraded-mode heuristic in main()
# to decide whether to report the broken installation and deny a command
# whose text looks like a push (ai-config#2981).

def _load_sibling():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "no-unreviewed-pr.py")
    spec = importlib.util.spec_from_file_location("no_unreviewed_pr", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    _SIBLING = _load_sibling()
    _SIBLING_ERROR = None
except Exception as exc:  # covered by orphan_cases() in
                          # test-no-push-without-self-review.py, which runs a
                          # copy of this file in a directory without the sibling
    _SIBLING = None
    _SIBLING_ERROR = str(exc)

# The walk over git's push-option grammar, its tables, and the abbreviation
# resolver live in the sibling and are bound here rather than declared twice
# (ai-config#1935, #1920): the sibling decides whether a command is a push at
# all, and that decision reads values and abbreviations exactly as this
# file's refspec walk must, so one walk keeps the two halves of the decision
# from disagreeing about how git's CLI works. With no sibling the names stay
# unbound: every path that consults them sits behind the deny that a missing
# sibling triggers.
if _SIBLING is not None:
    walk_push_options = _SIBLING.walk_push_options
    resolve_long_opt = _SIBLING.resolve_long_opt
    AMBIGUOUS_OPTION = _SIBLING.AMBIGUOUS_OPTION


def _load_review_payload():
    try:
        from scripts.lib.review_payload import (
            extract_review_payload,
            payload_is_blocking,
        )
        return extract_review_payload, payload_is_blocking
    except ImportError:
        pass
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lib_dir = os.path.join(repo_root, "scripts", "lib")
    path = os.path.join(lib_dir, "review_payload.py")
    if os.path.isfile(path):
        try:
            if lib_dir not in sys.path:
                sys.path.insert(0, lib_dir)
            if repo_root not in sys.path:
                sys.path.insert(0, repo_root)
            spec = importlib.util.spec_from_file_location("scripts.lib.review_payload", path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                extract_fn = getattr(module, "extract_review_payload", None) or getattr(module, "extract_structured_review", None)
                blocking_fn = getattr(module, "payload_is_blocking", None)
                if extract_fn and blocking_fn:
                    return extract_fn, blocking_fn
        except Exception:
            pass
    return None, None


try:
    _extract_review_payload, _payload_is_blocking = _load_review_payload()
except Exception:
    _extract_review_payload, _payload_is_blocking = None, None


ENV_ASSIGNMENT = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*=")


# Wrappers that run the command that follows them, so `git` is not argv[0] even
# though a push is exactly what happens.
COMMAND_WRAPPERS = {"env", "command", "nohup", "time", "exec", "builtin",
                    "sudo", "timeout", "stdbuf", "nice", "ionice", "doas"}

# Shell keywords that can open a simple command. The regex detector this file
# replaced carried these, and dropping them was a REGRESSION rather than a
# simplification: `_simple_commands` splits on `;` and `&&`, so the keyword
# becomes argv[0] of the segment holding the push. `skills/push/SKILL.md`
# prescribes a retry loop, so `do git push ...` is a shape this corpus asks for
# by name.
SHELL_KEYWORDS = {"!", "{", "}", "(", ")", "if", "then", "elif", "else", "fi",
                  "while", "until", "do", "done", "for", "case", "esac"}

# An unexpanded `$GIT`/`${GIT}` program token. shlex leaves it literal, so
# without this the command is not a push as far as argv is concerned.
GIT_VARIABLE = re.compile(r"\A\$\{?GIT\}?\Z")

# A duration argument, so `timeout 5 git push` does not stop the scan at `5`.
# How far past a wrapper to look for the git token. Six covers
# `sudo -u name -H git`, and bounds the scan so an unrelated command
# running git much later on the line is not mistaken for a wrapped push.
WRAPPER_ARG_WINDOW = 6


def _strip_env(argv: list[str]) -> tuple[list[str], list[str]]:
    """Split a simple command's leading env assignments and wrappers off its argv.

    shlex reports `FOO=1 git push` as three tokens, so the sibling's
    `_argv_push` (which requires `argv[0] == "git"`) never sees such a command
    as a push. The same is true of `env git push`, `command git push`, and an
    absolute `/usr/bin/git push`; the last is an ordinary invocation rather than
    an evasion. Splitting here is also what scopes the override to the pushing
    command rather than to any segment of the line.

    Returns (env assignments, argv with `git` first) -- the program token is
    normalized to its basename so the sibling's own check still applies.
    """
    rest = list(argv)
    env: list[str] = []
    after_wrapper = False
    while rest:
        tok = rest[0]
        if ENV_ASSIGNMENT.match(tok):
            env.append(tok)
            rest = rest[1:]
            after_wrapper = False
            continue
        if tok in COMMAND_WRAPPERS:
            after_wrapper = True
            rest = rest[1:]
            continue
        if tok in SHELL_KEYWORDS:
            after_wrapper = False
            rest = rest[1:]
            continue
        # A wrapper's own arguments, so `env -i`, `env -u FOO`, `timeout 5` and
        # `sudo -u someone` do not stop the scan before `git`. Enumerating each
        # wrapper's option grammar would be its own parser, so instead: look
        # ahead a bounded distance for the git token and drop what precedes it.
        # Nothing is consumed unless git is actually found, so a wrapper running
        # something else is left alone.
        if after_wrapper:
            window = rest[1:1 + WRAPPER_ARG_WINDOW]
            hit = next((i for i, t in enumerate(window, start=1)
                        if GIT_VARIABLE.match(t) or os.path.basename(t) == "git"), None)
            if hit is not None:
                rest = rest[hit:]
                continue
        break
    if rest:
        if GIT_VARIABLE.match(rest[0]) or os.path.basename(rest[0]) == "git":
            rest = ["git"] + rest[1:]
    return env, rest


def _depth_segments(command: str):
    """[(depth, segment_text)] -- split on operators, tracking PAREN depth.

    `_simple_commands` deliberately models no nesting, so an earlier revision
    approximated with `nested = "(" in command`, which is wrong twice over: a
    parenthesis inside a quoted string (a commit message reading "fix (typo)")
    discarded a legitimate hint, and `(cd elsewhere && git push)` -- where the
    `cd` DOES apply to the push -- was graded against the wrong repository.
    Depth is the fact that separates those, and it is not derivable from the
    sibling's output, so it is computed here rather than duplicating its parser.
    """
    segs: list[tuple[int, str]] = []
    depth = 0
    cur: list[str] = []
    in_single = in_double = escaped = False
    i, n = 0, len(command)
    while i < n:
        c = command[i]
        if escaped:
            escaped = False
            cur.append(c)
        elif c == "\\" and not in_single:
            escaped = True
            cur.append(c)
        elif c == "'" and not in_double:
            in_single = not in_single
            cur.append(c)
        elif c == '"' and not in_single:
            in_double = not in_double
            cur.append(c)
        elif in_single or in_double:
            cur.append(c)
        elif c in "()":
            segs.append((depth, "".join(cur)))
            cur = []
            depth += 1 if c == "(" else -1
            depth = max(depth, 0)
        elif c in ";&|\n" or command.startswith("&&", i) or command.startswith("||", i):
            segs.append((depth, "".join(cur)))
            cur = []
            if command.startswith(("&&", "||"), i):
                i += 1
        else:
            cur.append(c)
        i += 1
    segs.append((depth, "".join(cur)))
    return [(d, t.strip()) for d, t in segs if t.strip()]


def _blank_shell_redirections(command: str) -> str:
    """Blank unquoted shell redirections while preserving quoted arguments."""
    chars = list(command)
    i, n = 0, len(command)
    in_single = in_double = escaped = False
    while i < n:
        c = command[i]
        if escaped:
            escaped = False
            i += 1
            continue
        if c == "\\" and not in_single:
            escaped = True
            i += 1
            continue
        if c == "'" and not in_double:
            in_single = not in_single
            i += 1
            continue
        if c == '"' and not in_single:
            in_double = not in_double
            i += 1
            continue
        if in_single or in_double:
            i += 1
            continue

        start = i
        if c.isdigit() and (i == 0 or command[i - 1].isspace()
                            or command[i - 1] in ";|&()"):
            while i < n and command[i].isdigit():
                i += 1
            if i >= n or command[i] not in "<>":
                i = start + 1
                continue
        elif c not in "<>" and not (c == "&" and i + 1 < n
                                      and command[i + 1] == ">"):
            i += 1
            continue

        # A herestring's operator and target are both shell syntax; blank
        # them like any redirection (checked before "<<", its prefix).
        if command[i:i + 3] == "<<<":
            i += 3
        # Leave heredocs to the sibling's existing body-aware
        # preprocessing.
        elif command[i:i + 2] == "<<":
            i += 2
            continue

        # Redirections are shell syntax, not git argv (ai-config#2477).
        # Three-character forms first: a fixed two-character window left
        # the third character to be absorbed as a bogus one-character
        # target, letting the real target leak into git argv (#2494
        # review round: &>>, <>, <<<).
        elif command[i:i + 3] == "&>>":
            i += 3
        elif command[i:i + 2] in (">>", ">&", "<&", "&>", "<>", ">|"):
            i += 2
        else:
            i += 1
        while i < n and command[i].isspace():
            i += 1
        quoted = None
        while i < n:
            if quoted:
                if command[i] == quoted:
                    quoted = None
                elif command[i] == "\\" and quoted == '"' and i + 1 < n:
                    i += 1
            elif command[i] in "'\"":
                quoted = command[i]
            elif command[i].isspace() or command[i] in ";|&()":
                break
            elif command[i] == "\\" and i + 1 < n:
                i += 1
            i += 1
        chars[start:i] = " " * (i - start)
    return "".join(chars)


def _resolve_cd_target(rest: list[str], cur_dir: str | None) -> str | None:
    """Resolve the directory after a `cd`, `pushd`, or `popd` command relative to `cur_dir`.

    Returns the new effective directory, or None if cleared / indeterminate.
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


def _hints_by_position(command: str) -> list[str | None]:
    """One directory hint per push, in order, or [] when structure is unclear.

    A hint is the directory of the last `cd`/`pushd` at or above the push's own
    paren depth. Entering a subshell inherits the enclosing hint; leaving it
    discards whatever was set inside.
    """
    hints: list[str | None] = []
    stack: list[str | None] = [None]
    for depth, text in _depth_segments(command):
        while len(stack) <= depth:
            stack.append(stack[-1])
        del stack[depth + 1:]
        try:
            argv = shlex.split(text)
        except ValueError:
            return []
        if not argv:
            continue
        # Strip FIRST. Push detection three lines below already does, so a
        # `cd` behind a shell keyword (`while true; do cd other; git push`)
        # was invisible here while the push after it was still detected --
        # and that is the retry-loop shape `skills/push/SKILL.md` prescribes,
        # so it is reachable by ordinary use rather than only adversarially.
        _, rest = _strip_env(argv)
        if rest and rest[0] in ("cd", "pushd", "popd"):
            stack[depth] = _resolve_cd_target(rest, stack[depth])
            continue
        if rest and _SIBLING and _SIBLING._argv_push(rest):
            hints.append(stack[depth])
    return hints


# Ways a command points git at a repository other than the one a `-C` scan
# would find. Resolving them means reproducing git's git-dir/work-tree
# precedence, so the guard refuses instead -- see `iter_pushes`.
REPO_REDIRECT_OPTS = {"--git-dir", "--work-tree", "--namespace"}
REDIRECTS_REPO = re.compile(r"\A(?:GIT_DIR|GIT_WORK_TREE|GIT_NAMESPACE)=")

# Distinct from None, which means "the hook's own cwd" and is a real answer.
REDIRECTED = object()


# POSIX shlex treats an unquoted backslash as an escape, so
# `git -C C:\Users\foo\AppData\Local\Temp\npwsr-abc push origin main` parses as
# `-C C:UsersfooAppDataLocalTempnpwsr-abc`. The guard then rev-parses `main` in
# a directory that does not exist and reports that `main` could not be resolved
# to a commit --- every allow-case in this hook's suite on Windows 11 /
# Python 3.13 / Git Bash, measured against main at 47e49fd1 (ai-config#2037).
# Recovering the original backslashes after shlex has eaten them is not
# possible. Git accepts forward slashes on Windows, so rewriting the drive
# path before the parse is the recovery. A POSIX path has no drive-letter
# backslash run and is unchanged.
#
# The excluded-character class stops the match at any character a genuine
# path segment cannot plausibly contain: whitespace, the other shell
# separators already excluded, and --- added after ai-config#2325's review
# round --- `#`, `(`, `)`, the two quote characters, a backtick, and `$`.
# Without those five, the match ran through them: an escaped `\#` became an
# unescaped `/#`, which turned the rest of the line into a shlex comment and
# hid a real `git push --all` entirely; an escaped `\)` became a bare `)`,
# which is one of `_simple_commands`'s punctuation_chars and split a chained
# push in two, hiding the second; and with neither a quote character nor
# whitespace excluded, a match starting inside a quoted path ran straight
# through the closing quote into the next argument, turning an unrelated
# `--\all` into `--/all` and degrading a refused indeterminate push into an
# approved bare one. Verified against real bash (not just this module's own
# shlex-based simulation) for all three: `bash -c 'git(){ ...; }; git -C
# C:\a\)b push origin main'` executes a genuine, un-mangled push, and `git -C
# 'C:\repo' push --\all origin` resolves to the argv `--all` on its own,
# unquoted-backslash escaping already turning it into exactly that string
# before this module ever sees the command.
_WIN_PATH_CHARS = r"[^\s\\/;&|<>()#'\"`$]+"
_WIN_DRIVE_PATH = re.compile(r"[A-Za-z]:(?:\\" + _WIN_PATH_CHARS + r")+")

# A quoted span, single or double, matched so it can be skipped rather than
# rewritten. Real bash (confirmed by execution, not just read) already keeps
# a single-quoted backslash literal and a double-quoted one is only special
# before `$` `` ` `` `"` `\` or a newline --- so a quoted Windows path never
# had the backslash-eating bug this function exists to fix, and rewriting it
# anyway makes the guard verify a directory bash never asked for: on POSIX,
# `C:\repo` and `C:/repo` are two unrelated paths, not two spellings of one.
_QUOTED_SPAN = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")


def _posixize_windows_paths(command: str) -> str:
    """Rewrite an UNQUOTED `C:\\Users\\...` to `C:/Users/...`.

    Confined to text outside quotes; see `_QUOTED_SPAN` and `_WIN_DRIVE_PATH`
    above for why both restrictions are load-bearing rather than tidiness.
    """
    def rewrite(segment: str) -> str:
        return _WIN_DRIVE_PATH.sub(lambda m: m.group(0).replace("\\", "/"), segment)

    out = []
    pos = 0
    for m in _QUOTED_SPAN.finditer(command):
        out.append(rewrite(command[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(rewrite(command[pos:]))
    return "".join(out)


def iter_pushes(command: str):
    """Yield (env, argv, directory) for each `git push` simple command.

    `directory` is the push's own absolute `-C`, else the push's relative `-C`
    resolved within the directory a `cd`/`pushd` put it in (subshell scoping
    respected), else the `cd`/`pushd` directory, else None -- meaning the hook's
    own cwd. Both were previously read off the FIRST git command in the chain, so
    `git -C a status && git -C b push` graded the wrong repository.

    The sibling stays authoritative on WHETHER a command is a push. The
    positional hint list is used only when it agrees with the sibling on how
    many pushes there are; disagreement means this module's structural read and
    the sibling's parse have diverged, and a wrong directory is worse than none.

    `directory` is the sentinel REDIRECTED when the command points git at a
    repository this scan will not resolve. `--git-dir`/`--work-tree`, and their
    `GIT_DIR`/`GIT_WORK_TREE` environment forms, all send the push to another
    repository while leaving nothing for a `-C` scan to find, so the guard
    resolved HEAD in its OWN cwd and graded the wrong repo. Measured against
    two throwaway repos, the hook's cwd being repoA and the verdict naming
    repoA's HEAD:

        git --git-dir=repoB/.git --work-tree=repoB push origin main  -> allowed
        GIT_DIR=repoB/.git git push origin main                      -> allowed

    while the `-C` spelling of the same push was correctly denied. Resolving
    them properly means reproducing git's own git-dir/work-tree precedence, so
    this refuses instead, which is the direction the rest of the module takes
    when it cannot describe what a push ships.

    `-C` is also CHAINED by git -- each is applied relative to the last -- so
    the first one is not the answer when several appear (ai-config#1977).

    Windows drive paths are rewritten to forward slashes before either parser
    runs, so `_simple_commands` and `_hints_by_position` see the same command.
    """
    if _SIBLING is None:
        return
    # Join line-continuations BEFORE posixize. Otherwise a Windows CRLF
    # continuation (`\` + `\r\n`) is swallowed into the drive path (`/` + CR),
    # the leftover newline becomes `;`, and a real `git push` is no longer
    # detected --- fail-open. Measured on this change: `git -C C:\Users\...\`
    # plus CRLF plus `push origin main` yielded zero pushes after posixize
    # and one push (mangled directory, fail-closed) without it. `\r` is also
    # excluded from the path class so a stray CR cannot extend the match even
    # if this join were skipped. The sibling's `_simple_commands` runs the
    # identical `re.sub` again on its own copy of the command; that second
    # pass is a no-op once this one has already run, not a second parser to
    # keep in sync, so there is nothing left here for a future change to miss.
    command = re.sub(r"\\\r?\n", " ", command)
    command = _posixize_windows_paths(command)
    command = _blank_shell_redirections(command)
    cmds = _SIBLING._simple_commands(command)
    if not cmds:
        return
    pushes = []
    for argv in cmds:
        if not argv:
            continue
        env, rest = _strip_env(argv)
        if not rest or not _SIBLING._argv_push(rest):
            continue
        directory = None
        if any(REDIRECTS_REPO.match(tok) for tok in env):
            directory = REDIRECTED
        else:
            i = 1
            while i < len(rest) - 1:
                tok = rest[i]
                if tok == "-C" and i + 1 < len(rest):
                    # Chained: each -C is relative to the accumulated path.
                    directory = os.path.join(directory or "", rest[i + 1]) \
                        if directory not in (None, REDIRECTED) else rest[i + 1]
                    i += 2
                    continue
                head = tok.partition("=")[0]
                if head in REPO_REDIRECT_OPTS:
                    directory = REDIRECTED
                    break
                i += 1
        pushes.append((env, rest, directory))

    hints = _hints_by_position(command)
    if len(hints) != len(pushes):
        hints = [None] * len(pushes)
    for (env, rest, directory), hint in zip(pushes, hints):
        effective_dir = directory
        if effective_dir is REDIRECTED:
            yield env, rest, REDIRECTED
            continue
        if effective_dir is None:
            effective_dir = hint
        elif hint is not None and not os.path.isabs(effective_dir):
            # When -C is relative and an in-command cd/pushd established a working
            # directory, git applies -C relative to that directory.
            effective_dir = os.path.normpath(os.path.join(hint, effective_dir))
        yield env, rest, effective_dir


def has_allow_override(env: list[str]) -> bool:
    """True if the PUSHING command carries the override as an env assignment.

    Scoped to that command's own environment prefix, deliberately. A previous
    revision searched the whole command line, so `git push && echo
    'ALLOW_UNREVIEWED_PUSH=1'` -- or a commit message quoting this repo's own
    documentation of the override -- disarmed the guard.
    """
    return any(OVERRIDE_ENV.match(tok) for tok in env)


def push_refspecs(argv: list[str]) -> list[str] | None:
    """The refspecs a `git push` argv would ship; None if indeterminate.

    An empty list means the push names no refspec. What THAT ships is a
    `push.default` question rather than a fact about the command, which
    `shipped_commits` asks git rather than assuming.
    """
    # `positionals[0]` is dropped as the remote even when `--repo` supplied
    # one. `--repo` does NOT turn the positionals into refspecs -- an explicit
    # positional repository OVERRIDES it, which is git's documented "if both
    # are specified, the command-line argument takes precedence". Measured on
    # git 2.43.0, since a review of this line read it the other way and called
    # it a bypass:
    #
    #   git push --dry-run --repo=origin evil main
    #     -> fatal: 'evil' does not appear to be a git repository
    #   git push --dry-run --repo=origin main
    #     -> fatal: 'main' does not appear to be a git repository
    #   git push --dry-run --repo=/nonexistent origin main
    #     -> succeeds, pushing via `origin`; /nonexistent is never contacted
    #
    # So `--repo=origin main` is a BARE push to the repository named `main`,
    # and resolving it through push.default rather than through `main` is
    # correct. Regression rows: grep CASES and config_cases() for --repo.
    positionals = _push_positionals(argv)
    return None if positionals is None else positionals[1:]  # drop the remote


def _push_positionals(argv: list[str]) -> list[str] | None:
    """The positional arguments after `push` -- remote first; None if indeterminate."""
    return None if (parsed := _parse_push(argv)) is None else parsed[0]


def _parse_push(argv: list[str]) -> tuple[list[str], str | None] | None:
    """(positionals after `push`, the --repo value); None if indeterminate.

    `--repo` is read HERE rather than by a separate scan of argv, because the
    guards that make this walk correct are exactly the ones such a scan lacks.
    An earlier revision scanned raw argv for `--repo` and was permissive twice
    over, measured on git 2.43.0 against a repo whose `remote.pushDefault` was
    `alpha` and whose `remote.alpha.push` shipped every branch:

        git push --repo=zzz --no-repo   -> git pushes to alpha; the scan said zzz
        git push -o --repo=zzz          -> `--repo=zzz` is -o's VALUE, not an
                                           option; git pushes to alpha

    Both turned a correctly-refused push into an allowed one. This walk already
    classifies option values, so resolving `--repo` inside it cannot disagree
    with that classification -- but only for the spellings its tables know,
    which is why every long option is put through `resolve_long_opt` first. An
    earlier revision skipped that and `--pu --repo=X` walked straight back into
    the same hole, `--pu` being `--push-option`. `--no-repo` clears the value,
    as it does for git, and the last occurrence wins. The tokens come from the
    sibling's `walk_push_options`, the one walk both hooks read git's push
    grammar through (ai-config#1935).
    """
    try:
        idx = argv.index("push")
    except ValueError:
        return None
    positionals: list[str] = []
    repo: str | None = None
    for kind, head, value in walk_push_options(argv[idx + 1:]):
        if kind == "positional":
            positionals.append(head)
            continue
        if kind == "short":
            continue
        if head is AMBIGUOUS_OPTION:
            return None
        if head in PUSH_OPTS_INDETERMINATE:
            return None
        if head == "--recurse-submodules" and value in SUBMODULE_PUSH_MODES:
            return None
        if head == "--no-repo":
            repo = None
        elif head == "--repo":
            repo = value
    return positionals, repo


# This hook is registered with a 10s timeout in `hooks/hooks.json`, and a
# PreToolUse hook killed on timeout does not deny -- the push simply proceeds.
# So the budget is enforced here rather than left to the harness: one call per
# refspec times a generous per-call timeout would exceed it on a slow repo, and
# the failure would be a silent allow on the one path this guard exists to hold.
# Overridable so the timeout path is testable: it is the one branch whose
# failure direction (allow vs deny) cannot be observed any other way, and a
# mutation turning its refusal into an allow survived an untested suite.
BUDGET_SECONDS = float(os.environ.get("NPWSR_BUDGET_SECONDS", "6.0"))
PER_CALL_SECONDS = 3.0
_DEADLINE = [0.0]


def _run_git(directory: str | None, env: list[str], *args: str) -> str | None:
    """Run one git command inside the shared budget; None if it failed.

    EVERY git call goes through here, deliberately. An earlier revision budgeted
    only `_rev_parse` and let `_git_config`/`_rev_parse_ref` carry their own
    hardcoded timeouts, so the bare-push resolution path could spend six
    unbudgeted subprocess calls -- eighteen seconds against a ten-second
    PreToolUse timeout -- before reaching the one call that enforced the budget.
    A hook killed on timeout does not deny, so that reopened the silent allow
    this budget exists to prevent, on the newest path rather than the oldest.

    Sharing one helper is what makes that unrepeatable: a future call site
    cannot forget to check the deadline, because there is nowhere else to run
    git from.

    `env` is the PUSHING command's environment prefix, and it is required for
    the same reason. git takes config from the environment as well as from
    `-c` and from files: `GIT_CONFIG_COUNT` with `GIT_CONFIG_KEY_<n>` and
    `GIT_CONFIG_VALUE_<n>` is a documented override equivalent to `-c`. This
    process does not carry those, so a subprocess run under the hook's own
    environment reads different config than the push will. Measured on git
    2.43.0, with nothing on disk:

        GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=remote.origin.mirror \
        GIT_CONFIG_VALUE_0=true git push origin

    ships every branch, including an unreviewed one, while the guard allowed
    it. Enumerating that one variable would have been the fourth patch to the
    same class, so the overlay is applied wholesale instead: every git call
    runs under the environment the push will run under, which covers env-based
    overrides this file does not know about. `GIT_DIR` and friends are refused
    upstream rather than forwarded, since those redirect the repository.
    """
    remaining = _DEADLINE[0] - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("ran out of time resolving what this push would ship")
    cmd = ["git"] + (["-C", directory] if directory else []) + list(args)
    try:
        overlay = dict(os.environ)
        for assignment in env:
            key, sep, value = assignment.partition("=")
            if sep:
                overlay[key] = value
        out = subprocess.run(cmd, capture_output=True, text=True, env=overlay,
                             timeout=min(PER_CALL_SECONDS, remaining))
    except subprocess.TimeoutExpired:
        raise TimeoutError("ran out of time resolving what this push would ship")
    except Exception:
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _rev_parse(directory: str | None, env: list[str], rev: str) -> str | None:
    sha = _run_git(directory, env, "rev-parse", rev)
    return sha.lower() if sha and re.fullmatch(r"[0-9a-f]{40}", sha) else None


def _config_overrides(argv: list[str]) -> list[str]:
    """The pushing command's own `-c key=value` tokens, to forward to `git config`.

    `git -c remote.origin.mirror=true push` is process-local, so a separate
    `git config --get` subprocess cannot see it. Measured on git 2.43.0 with
    NO on-disk config: that command ships every branch, including an unreviewed
    one, while the guard's config read returned nothing.

    `--config-env=KEY=VAR` names an environment variable rather than a value,
    and this process may not carry it, so it is not forwardable. `main` refuses
    a push carrying one instead.
    """
    out: list[str] = []
    i = 1
    while i < len(argv) and argv[i] != "push":
        tok = argv[i]
        if tok == "-c" and i + 1 < len(argv):
            out += ["-c", argv[i + 1]]
            i += 2
            continue
        if tok.startswith("-c") and len(tok) > 2:
            out += ["-c", tok[2:]]
        i += 1
    return out


def _has_config_env(argv: list[str]) -> bool:
    """True if the command carries `--config-env`, which cannot be forwarded."""
    for tok in argv:
        if tok == "push":
            return False
        if tok == "--config-env" or tok.startswith("--config-env="):
            return True
    return False


def _git_config(directory: str | None, flag: str, key: str,
                argv: list[str], env: list[str],
                as_bool: bool = False) -> str | None:
    """A config value as the PUSHING git would see it.

    Two ways a plain `git config --get` reads something git does not.

    A valueless key is TRUE to git's boolean parser and prints EMPTY here, so
    `[remote "origin"]` + a bare `mirror` line read as unset. `--bool --get`
    normalizes it. Measured on git 2.43.0:

        git config --file t --get      remote.origin.mirror  -> '' (exit 0)
        git config --file t --bool --get remote.origin.mirror -> 'true'

    And an inline `git -c key=value push` is process-local to that invocation,
    so a separate `git config` subprocess never sees it. `--config-env` is not
    forwardable -- it names an environment variable this process may not carry
    -- and is refused upstream instead.

    `argv` is REQUIRED, and the overrides are derived here rather than passed
    in, because an optional `overrides=` parameter is exactly what a call site
    forgets. One did: `_push_remote`'s fallback chain read
    `remote.pushDefault` without them, so `git -c remote.pushDefault=alpha -c
    remote.alpha.push=... push` sent the real push to `alpha` while the guard
    resolved the literal `origin` and checked the wrong remote's keys. Every
    read now goes through this one function and cannot omit them.
    """
    args = _config_overrides(argv) + ["config"]
    if as_bool:
        args.append("--bool")
    return _run_git(directory, env, *args, flag, key) or None


def _push_remote(directory: str | None, argv: list[str],
                 env: list[str]) -> str | None:
    """The remote this push acts on, named or not.

    Returning None for a bare `git push` skipped the `remote.<name>.push` check
    in exactly the case it exists for: the command that names nothing is the one
    whose destination is decided entirely by config. So when the command does
    not spell the remote out, resolve the one git would use, in git's own
    precedence order.

    `--repo=<remote>` supplies the remote for a push that names no positional
    one, so it has to be consulted BEFORE that config chain -- reading it as a
    bare push resolved the wrong remote and skipped the `remote.<name>.push`
    check on a command that does ship other refs. Measured on git 2.43.0, in a
    repo whose `remote.other.push` is `refs/heads/*:refs/heads/*`:

        git push --dry-run --repo=other
          -> * [new branch]  feature -> feature      (an unreviewed ref)
             * [new branch]  main -> main

    while `git push other` was already refused. The positional still wins over
    `--repo` when both appear, which is git's documented precedence and is why
    it is checked first.
    """
    parsed = _parse_push(argv)
    if parsed is None:
        return None
    positionals, repo = parsed
    if positionals:
        return positionals[0]
    if repo:
        return repo
    branch = _rev_parse_ref(directory, env, "--abbrev-ref", "HEAD")
    for key in ((f"branch.{branch}.pushRemote",) if branch else ()) + (
            "remote.pushDefault",) + ((f"branch.{branch}.remote",) if branch else ()):
        value = _git_config(directory, "--get", key, argv, env)
        if value:
            return value
    return "origin"


def _rev_parse_ref(directory: str | None, env: list[str], *args: str) -> str | None:
    name = _run_git(directory, env, "rev-parse", *args)
    return name if name and name != "HEAD" else None


def shipped_commits(directory: str | None, argv: list[str],
                    env: list[str]) -> tuple[set[str] | None, str]:
    """(commits this push would ship, reason-if-unknown).

    None means the guard cannot tell -- `--all`, `--mirror`, an unresolvable
    ref -- which is a refusal rather than a pass, since an unknown payload is
    exactly what a review cannot have covered.
    """
    try:
        refspecs = push_refspecs(argv)
    except Exception:
        return None, "its arguments could not be parsed"
    if refspecs is None:
        named = [t for t in argv if resolve_long_opt(t.partition("=")[0]) in PUSH_OPTS_INDETERMINATE
                 or t.partition("=")[0] == "--recurse-submodules"]
        which = f" ({', '.join('`' + t + '`' for t in named)})" if named else ""
        return None, ("this push does not name a single reviewable head" + which)
    # These apply whether or not the push names a refspec, so the loop cannot
    # live in the bare-push branch alone -- the equivalent command-line flag is
    # refused on both paths. Measured: with `push.recurseSubmodules=on-demand`,
    # `git push origin main` was ALLOWED while
    # `git push --recurse-submodules=on-demand origin main` was refused, and
    # real git reports `Pushing submodule` for the former.
    remote_for_config = _push_remote(directory, argv, env)
    for key, mirrors, verdict, as_bool in CONFIG_LIKE_INDETERMINATE_FLAGS:
        if "{remote}" in key:
            # `--mirror` cannot be combined with refspecs (git refuses it), so
            # its config form only decides anything on the bare-push path.
            if refspecs or not remote_for_config:
                continue
            key = key.format(remote=remote_for_config)
        value = _git_config(directory, "--get", key, argv, env, as_bool)
        if value and verdict(value):
            return None, (f"`{key}` is set, which does what `{mirrors}` does "
                          "without naming it on the command line")
    if not refspecs:
        # A bare `git push` ships the current branch only under the modern
        # `push.default`. Under `matching` (git's default before 2.0, and still
        # present in long-lived global configs) it ships every branch whose name
        # exists on the remote, and a configured `remote.<name>.push` overrides
        # the question entirely. Measured on git 2.43.0:
        # `git -c push.default=matching push --dry-run origin` reports a branch
        # that is not HEAD. So this is checked rather than assumed.
        default = _git_config(directory, "--get", "push.default", argv, env)
        if default and default.lower() == "matching":
            return None, "`push.default` is `matching`, so a bare push ships more than HEAD"
        remote = remote_for_config
        if remote and _git_config(directory, "--get-all",
                                  f"remote.{remote}.push", argv, env):
            return None, (f"`remote.{remote}.push` is configured, so what a bare push "
                          "ships is not simply the current branch")
        head = _rev_parse(directory, env, "HEAD")
        if head is None:
            return None, "HEAD could not be resolved for the repository being pushed"
        return {head}, ""

    commits: set[str] = set()
    for spec in refspecs:
        src = spec.split(":", 1)[0].lstrip("+")
        if not src:
            continue  # `:branch` deletes a ref and ships nothing
        sha = _rev_parse(directory, env, f"{src}^{{commit}}")
        if sha is None:
            hint = ("; a shell variable cannot be expanded here, so push `HEAD` "
                    "(`git push -u origin HEAD`) when you mean the current branch"
                    if "$" in src or "`" in src else "")
            return None, f"`{src}` could not be resolved to a commit{hint}"
        commits.add(sha)
    return commits, ""


# --- transcript reading -----------------------------------------------------

def _result_text(block: dict) -> str:
    """Flatten a tool_result block's payload into one searchable string.

    A subagent's report arrives as `content`, which is a plain string in some
    transports and a list of content blocks in others. Reading only one shape
    returns "" for the other, and an empty string is indistinguishable from a
    report that stated no verdict.
    """
    parts: list[str] = []
    content = block.get("content")
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for sub in content:
            if isinstance(sub, str):
                parts.append(sub)
            elif isinstance(sub, dict):
                parts.append(str(sub.get("text") or sub.get("content") or ""))
    for key in ("output", "text"):
        val = block.get(key)
        if isinstance(val, str):
            parts.append(val)
    return "\n".join(p for p in parts if p)


def _iter_blocks(record: dict):
    message = record.get("message")
    blocks = message.get("content") if isinstance(message, dict) else record.get("content")
    if isinstance(blocks, str):
        blocks = [{"type": "text", "text": blocks}]
    elif not isinstance(blocks, list):
        blocks = []
    for b in blocks:
        if isinstance(b, dict):
            yield b
    if "tool_calls" in record and isinstance(record["tool_calls"], list):
        for tc in record["tool_calls"]:
            if isinstance(tc, dict):
                args = tc.get("args") or tc.get("input") or (tc.get("function") or {}).get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                yield {
                    "type": "tool_use",
                    "id": tc.get("id") or str(id(tc)),
                    "name": tc.get("name") or (tc.get("function") or {}).get("name") or "",
                    "input": args if isinstance(args, dict) else {},
                }


def _blank_quoted_regions(text: str) -> tuple[str, bool]:
    """Blank fenced code AND HTML comments in one render-faithful pass.

    Two sequential linear passes cannot be correct in both directions: with
    fences first, a fence that swallows a comment's opener leaves the
    comment interior live (a spoofed verdict "hidden" there decides the
    report), and a fence that swallows only the true closer makes the
    comment pass pair the opener with a later decoy arrow, exposing
    whatever follows the decoy (both measured in the #2479 review rounds).
    Comments first fails the mirror cases. CommonMark resolves the
    ambiguity by ORDER: whichever construct opens first swallows the
    other's markers until its own closer, so this scanner walks the text
    once and enters whichever region begins next -- a fence per FENCE's
    dialect (closing only on a same-character, at-least-as-long BARE
    marker: positional pairing mis-pairs the moment fences nest, e.g. an
    outer 4-tick fence quoting an inner 3-tick pair), or a comment at
    ``<!--``
    (closing only at the first literal ``-->``, fence markers inside
    swallowed, matching how a renderer treats an open comment). The
    blanked region is then exactly what a renderer hides, and any live
    verdict line is one a reader of the rendered report would see.

    An unclosed fence or comment at end of text reports True, and
    parse_report fails the report closed: a structure that cannot be
    resolved is a verdict that cannot be read, and truncation mid-region
    leaves exactly this state. Offsets are preserved throughout.
    """
    out = list(text)
    n = len(text)

    def blank(a: int, b: int) -> None:
        for i in range(a, b):
            if out[i] != "\n":
                out[i] = " "

    pos = 0
    while pos < n:
        fence = FENCE.search(text, pos)
        comment_at = text.find("<!--", pos)
        if fence is None and comment_at == -1:
            break
        if comment_at == -1 or (fence is not None
                                and fence.start() < comment_at):
            open_char = fence.group(1)[0]
            open_len = len(fence.group(1))
            close = None
            for m in FENCE.finditer(text, fence.end()):
                marker = m.group(1)
                # A CLOSING fence is bare: CommonMark allows an info string
                # after an OPENER only, so a candidate with non-whitespace
                # trailing text is fenced content, not a closer -- reading
                # it as one exposed everything after it as live text
                # (#2479 review rounds).
                if (marker[0] == open_char and len(marker) >= open_len
                        and not text[m.end(1):m.end(0)].strip()):
                    close = m
                    break
            if close is None:
                blank(fence.start(), n)
                return "".join(out), True
            blank(fence.start(), close.end())
            pos = close.end()
        else:
            close_at = text.find("-->", comment_at + 4)
            if close_at == -1:
                blank(comment_at, n)
                return "".join(out), True
            blank(comment_at, close_at + 3)
            pos = close_at + 3
    return "".join(out), False


def parse_report(text: str) -> tuple[str | None, str | None]:
    """(verdict, reviewed_commit) from one reviewer report.

    The verdict is the LAST verdict LINE, and the fingerprint is the first one
    after it. Both halves matter: taking the last verdict anywhere lets a
    closing sentence that quotes the other verdict decide the report, and
    taking the fingerprint from anywhere lets a fingerprint quoted in the
    findings stand in for the report's own.
    """
    # BOTH searches run against the blanked text. Blanking only the verdict
    # search left the asymmetry that mattered: a fenced example whose
    # illustrative fingerprint happened to name the current HEAD was found
    # first and stood in for the report's real one, which named the older
    # commit actually reviewed -- so the push of an unreviewed commit was
    # allowed by the very comparison this guard is built around.
    # Fences and HTML comments are blanked in ONE interleaving-aware pass:
    # a commented-out "Verdict:" line must not decide the report
    # (ai-config#2413), and neither may a spoofed verdict exposed by a
    # fence/comment straddle in either direction (#2479 review rounds) --
    # see _blank_quoted_regions for why two sequential passes cannot be
    # correct.
    blanked, unresolved = _blank_quoted_regions(text)
    if unresolved:
        return None, None
    matches = list(VERDICT_LINE.finditer(blanked))
    if not matches:
        return None, None
    last = matches[-1]
    verdict = "clean" if last.group(1).lower().startswith("ready") else "needs_work"
    sha = REVIEWED_COMMIT.search(blanked, last.end())
    if verdict == "clean" and _extract_review_payload is not None and _payload_is_blocking is not None:
        try:
            payload = _extract_review_payload(text)
            if _payload_is_blocking(payload):
                verdict = "needs_work"
        except Exception:
            pass
    return verdict, (sha.group(1).lower() if sha else None)




def _is_reviewer_record(record: dict) -> bool:
    """True if this transcript record is attributed to the adversarial reviewer."""
    candidates: list[str] = []
    for k in ("attributionAgent", "agent_type", "subagent_type", "subagentType",
              "TypeName", "Role", "agent", "name", "persona"):
        val = record.get(k)
        if isinstance(val, str) and val:
            candidates.append(val)
        elif isinstance(val, dict):
            for sub_k in ("name", "TypeName", "Role", "type"):
                sub_val = val.get(sub_k)
                if isinstance(sub_val, str) and sub_val:
                    candidates.append(sub_val)
    msg = record.get("message")
    if isinstance(msg, dict):
        for k in ("attributionAgent", "agent_type", "subagent_type", "subagentType",
                  "TypeName", "Role", "agent", "name", "persona", "role"):
            val = msg.get(k)
            if isinstance(val, str) and val and val.lower() not in (
                "user", "assistant", "system", "tool", "model", "planner"
            ):
                candidates.append(val)
    return any(ADVERSARIAL_AGENT_NAME.match(c) for c in candidates)


def read_latest_review(transcript_path: str) -> tuple[str | None, str | None, bool]:
    """(verdict, reviewed_commit, saw_reviewer_call) from the transcript.

    Only the reviewer's own call results and attributed subagent reports are
    consulted, and an errored result on the dispatch itself is skipped -- a failed
    or interrupted reviewer states no verdict, and `fail-fast` forbids letting that
    look identical to a clean one. Transient tool call errors during a subagent's
    exploration (e.g. bash command syntax retry) do not invalidate an otherwise
    clean final review verdict.
    """
    reviewer_call_ids: set[str] = set()
    reviewer_task_ids: set[str] = set()
    saw_reviewer_call = False
    verdict: str | None = None
    reviewed_commit: str | None = None

    with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except Exception:
                continue
            if not isinstance(record, dict):
                continue

            is_assistant = (
                record.get("source") == "MODEL"
                or record.get("type") == "assistant"
                or (isinstance(record.get("message"), dict) and record["message"].get("role") == "assistant")
            )

            record_is_reviewer = _is_reviewer_record(record)
            if record_is_reviewer:
                saw_reviewer_call = True
                content_text = _result_text(
                    record.get("message") if isinstance(record.get("message"), dict) else record
                )
                if content_text:
                    found, sha = parse_report(content_text)
                    if found:
                        verdict, reviewed_commit = found, sha

            for b in _iter_blocks(record):
                b_type = b.get("type")

                if b_type == "tool_use":
                    tool_name = (b.get("name") or "").lower()
                    call_id = b.get("id")
                    inp = b.get("input") or {}

                    if tool_name in AGENT_TOOLS:
                        sub_types = []
                        for k in ("subagent_type", "subagentType", "agent_type", "TypeName", "name", "Role"):
                            if inp.get(k):
                                sub_types.append(str(inp.get(k)))
                        if isinstance(inp.get("Subagents"), list):
                            for sa in inp["Subagents"]:
                                if isinstance(sa, dict):
                                    for k in ("TypeName", "Role", "name"):
                                        if sa.get(k):
                                            sub_types.append(str(sa.get(k)))

                        prompt = str(inp.get("prompt") or inp.get("Prompt") or inp.get("instruction") or inp.get("description") or "")

                        is_adversarial = any(ADVERSARIAL_AGENT_NAME.match(st) for st in sub_types)
                        is_fallback = bool(
                            sub_types
                            and any(FALLBACK_AGENT_NAME.match(st) for st in sub_types)
                            and REVIEW_PROMPT_RE.search(prompt)
                        )

                        if is_adversarial or is_fallback:
                            saw_reviewer_call = True
                            if isinstance(call_id, str) and call_id:
                                reviewer_call_ids.add(call_id)
                        elif tool_name in ("taskoutput", "task_output", "manage_task"):
                            task_id = str(inp.get("task_id") or inp.get("TaskId") or inp.get("id") or "")
                            if task_id and task_id in reviewer_task_ids:
                                if isinstance(call_id, str) and call_id:
                                    reviewer_call_ids.add(call_id)
                    elif tool_name == "send_message" and record_is_reviewer:
                        msg_text = str(inp.get("Message") or inp.get("message") or "")
                        if msg_text:
                            found, sha = parse_report(msg_text)
                            if found:
                                verdict, reviewed_commit = found, sha

                elif b_type == "tool_result":
                    call_id = b.get("tool_use_id")
                    if call_id in reviewer_call_ids:
                        # Check if this result launched a background task with an ID
                        res_text = _result_text(b)
                        try:
                            res_data = json.loads(res_text)
                            if isinstance(res_data, dict):
                                tid = res_data.get("task_id") or res_data.get("conversationId") or res_data.get("id")
                                if tid:
                                    reviewer_task_ids.add(str(tid))
                        except Exception:
                            tid_match = re.search(r"\b(?:task[-_ ]?id|conversationId)[:=]\s*[`\"']?([\w-]+)", res_text, re.I)
                            if tid_match:
                                reviewer_task_ids.add(tid_match.group(1))

                        if not b.get("is_error"):
                            found, sha = parse_report(res_text)
                            if found:
                                saw_reviewer_call = True
                                verdict, reviewed_commit = found, sha

                # Genuine task notifications from tracked background reviewer dispatches
                origin = record.get("origin")
                is_task_notification = (
                    isinstance(origin, dict)
                    and origin.get("kind") in ("task-notification", "task_notification")
                )
                if is_task_notification and not is_assistant and not b.get("is_error"):
                    origin_task_id = str(origin.get("taskId") or origin.get("task_id") or "")
                    sender_id = str(record.get("sender") or "")
                    if (
                        (origin_task_id and origin_task_id in reviewer_task_ids)
                        or (sender_id and sender_id in reviewer_task_ids)
                    ):
                        text = str(b.get("text") or b.get("content") or "")
                        found, sha = parse_report(text)
                        if found:
                            saw_reviewer_call = True
                            verdict, reviewed_commit = found, sha

    return verdict, reviewed_commit, saw_reviewer_call


def verify_review(transcript_path: str, directory: str | None,
                  argv: list[str], env: list[str]) -> tuple[bool, str]:
    """(is_clean, reason) -- is there a clean verdict for what this push ships?"""
    saw_reviewer_call = False
    verdict: str | None = None
    reviewed_commit: str | None = None

    if transcript_path and os.path.exists(transcript_path):
        try:
            verdict, reviewed_commit, saw_reviewer_call = read_latest_review(transcript_path)
        except Exception as e:
            return False, f"Failed reading transcript: {e}"

    if not transcript_path and not saw_reviewer_call:
        return False, "No transcript available to verify the adversarial self-review."

    if not saw_reviewer_call:
        return False, (
            "No `adversarial-reviewer` subagent was dispatched in this session.\n"
            "Dispatch it against your committed diff and address its findings before pushing."
        )

    if verdict is None:
        return False, (
            "An `adversarial-reviewer` subagent was dispatched, but no verdict came back "
            "as that call's own result.\n"
            "Dispatch it in the foreground (`run_in_background: false`) so its report "
            "returns as the tool result -- a background dispatch returns an agent id, "
            "which carries no verdict, and an errored result carries none either."
        )

    if verdict == "needs_work":
        return False, (
            "The latest adversarial self-review returned a blocking verdict.\n"
            "Address, rebut, or defer every finding, commit, and re-dispatch the reviewer."
        )

    if not reviewed_commit:
        return False, (
            "The clean verdict does not say which commit it read.\n"
            "The reviewer must state `Reviewed-Commit: <full sha>` on its own line "
            "immediately after the verdict; the JSON payload may follow it, and "
            "nothing else should. Without the line nothing ties the verdict to what "
            "this push would ship, and a report cut short before its fingerprint is "
            "not a verdict."
        )

    try:
        commits, why = shipped_commits(directory, argv, env)
    except TimeoutError as e:
        return False, (
            f"This guard {e}.\n"
            "It refuses rather than letting the push through unchecked; re-run once the "
            "repository is responsive, or use the override and say so."
        )
    if commits is None:
        return False, (
            f"Cannot determine which commits this push would ship: {why}.\n"
            "A clean verdict covers the commit it names, so a push whose payload cannot "
            "be resolved is not covered by it."
        )
    if not commits:
        return True, "This push ships no commits (a ref deletion)."

    unreviewed = sorted(c for c in commits if not c.startswith(reviewed_commit))
    if unreviewed:
        return False, (
            f"The clean verdict is for commit {reviewed_commit}, but this push would ship "
            f"{', '.join(c[:12] for c in unreviewed)}.\n"
            "A push ships commits, so whatever differs -- a later commit, a `main` merge, "
            "a rebase, or a branch other than the reviewed one -- is unreviewed. "
            "Re-dispatch the reviewer against what you are actually pushing."
        )

    return True, f"Clean adversarial self-review verified at {reviewed_commit}."


DENY_TAIL = (
    "\n\nStanding rule: every self-review is an adversarial review by a separate "
    "subagent. Dispatch `adversarial-reviewer` in the foreground against your "
    "committed diff (or dispatch a fallback reviewer subagent such as `general-purpose` "
    "or `self` with an adversarial review prompt when the persona is unregistered), "
    "address or rebut every finding, and let its report state the commit it read.\n\n"
    "Only that reviewer's own result or report counts -- this message does not, "
    "and neither does reading a file that quotes a verdict.\n\n"
    "Override by prefixing the push itself with `ALLOW_UNREVIEWED_PUSH=1` when no "
    "verdict can exist for the guard to check: an initial empty PR branch (per "
    "pr-on-claim), an auto-mode session where no subagent tool exists, "
    "or an emergency. In auto mode, if the permission classifier denies the env "
    "prefix, request a Bash permission rule. "
    "Say in your reply that you used the override and why."
)


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"git push blocked by the pre-push self-review policy:\n{reason}{DENY_TAIL}"
            ),
        }
    }))


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
        print(f"no-push-without-self-review: unreadable hook input ({exc})",

              file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0
    try:
        if (payload.get("tool_name") or "") not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
            if is_dry_run:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
            return 0

        inp = payload.get("tool_input") or {}
        cmd = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script") or ""
        if not cmd:
            if is_dry_run:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
            return 0

        if _SIBLING is None:
            # Only reached once a push-shaped command is plausible, so a broken
            # install does not deny every Bash call -- but it does deny rather
            # than grade pushes with a detector this file refuses to duplicate.
            # A degraded-mode heuristic rather than a second parser: it decides
            # only whether to SAY the guard is broken, never whether a command
            # is a push. Narrow enough that `git commit -m "push the button"`
            # and `grep push` do not trip it.
            #
            # The override is honoured here too: denying a push that carries it,
            # under a message saying the override works, is a session-wide
            # lockout with no escape.
            if DEGRADED_OVERRIDE.search(cmd):
                return 0
            if re.search(
                r"(?:^|[;&|`(\s])(?:[\w./-]*/)?git"
                r"(?:\s+(?:-C\s+\S+|-c\s+\S+|--(?:git-dir|work-tree|namespace)[= ]\S+|-\S+))*"
                r"\s+push\b", cmd):
                deny(
                    "This guard could not load its push detector from "
                    f"`no-unreviewed-pr.py` ({_SIBLING_ERROR}), so it cannot tell whether "
                    "this command pushes."
                )
            return 0

        _DEADLINE[0] = time.monotonic() + BUDGET_SECONDS
        for env, argv, directory in iter_pushes(cmd):
            if has_allow_override(env):
                continue
            if _has_config_env(argv):
                deny("this push carries `--config-env`, whose value comes from "
                     "an environment variable this guard cannot read, so what "
                     "the push ships cannot be determined")
                return 0
            if directory is REDIRECTED:
                deny("this push points git at another repository "
                     "(`--git-dir`/`--work-tree`/`GIT_DIR`/`GIT_WORK_TREE`), "
                     "so a verdict naming a commit in this one cannot cover it")
                return 0
            is_clean, reason = verify_review(
                payload.get("transcript_path") or "", directory, argv, env
            )
            if not is_clean:
                deny(reason)
                return 0
        return 0
    except Exception:
        # Fail open, deliberately and in the same direction as the parse-failure
        # rule in the docstring: a guard that crashed closed would block every
        # push in the session, which is a worse failure than missing one review.
        return 0


if __name__ == "__main__":
    sys.exit(main())
