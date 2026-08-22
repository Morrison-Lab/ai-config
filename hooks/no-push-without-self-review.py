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

AGENT_TOOLS = {"agent", "task", "invoke_subagent"}

OVERRIDE_ENV = re.compile(r"\AALLOW_UNREVIEWED_PUSH=1\Z")

# Degraded mode only, where the shell parser is unavailable and the strict
# argv-scoped check cannot run. Deliberately loose: with no parser this guard
# can only report that it is broken, so a false ALLOW here costs nothing a
# working guard would have caught, while a false DENY has no escape at all --
# a PreToolUse deny is not user-overridable.
DEGRADED_OVERRIDE = re.compile(r"(?:^|[;&|`(\s])ALLOW_UNREVIEWED_PUSH=1\s")

# Options of `git push` that consume the following token, so a value is never
# mistaken for a refspec.
PUSH_OPTS_WITH_VALUE = {"--repo", "--receive-pack", "--exec", "-o", "--push-option",
                        "--recurse-submodules"}

# Short options that take a value, for the clustered form (`-qo ci.skip`).
SHORT_OPTS_WITH_VALUE = "o"

# Options after which no single reviewed commit can describe the push.
# `--branches` is git's own documented alias of `--all` (`git push -h`), so it
# ships every branch while looking like an ordinary unknown option.
PUSH_OPTS_INDETERMINATE = {"--all", "--branches", "--mirror", "--tags",
                           "--follow-tags"}

# `--recurse-submodules` in these modes pushes commits in ANOTHER repository,
# which no fingerprint naming a commit in this one can describe.
SUBMODULE_PUSH_MODES = {"on-demand", "only"}


# --- push detection, borrowed rather than re-derived ------------------------
#
# `no-unreviewed-pr.py`'s detector is shell-parsed rather than regex-matched, so
# it already handles `git -C <dir> push` and `git -c k=v push`, already excludes
# the two push forms that re-head nothing, and is already tested there. A second
# hand-rolled detector would be a DRW finding and would diverge silently
# (ai-config#1920) -- an earlier revision of this file wrote one as a "fallback"
# and it did diverge, on all three of those points. So there is no fallback: if
# the sibling cannot be loaded this guard says so and denies, rather than
# quietly grading pushes with a worse parser.

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
        if argv[0] in ("cd", "pushd", "popd"):
            arg = argv[1] if len(argv) > 1 else None
            stack[depth] = arg if (arg and not arg.startswith("-")
                                   and argv[0] != "popd") else None
            continue
        _, rest = _strip_env(argv)
        if rest and _SIBLING and _SIBLING._argv_push(rest):
            hints.append(stack[depth])
    return hints


def iter_pushes(command: str):
    """Yield (env, argv, directory) for each `git push` simple command.

    `directory` is the push's own `-C`, else the directory a `cd`/`pushd` put it
    in (subshell scoping respected), else None -- meaning the hook's own cwd.
    Both were previously read off the FIRST git command in the chain, so
    `git -C a status && git -C b push` graded the wrong repository.

    The sibling stays authoritative on WHETHER a command is a push. The
    positional hint list is used only when it agrees with the sibling on how
    many pushes there are; disagreement means this module's structural read and
    the sibling's parse have diverged, and a wrong directory is worse than none.
    """
    if _SIBLING is None:
        return
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
        for i, tok in enumerate(rest[1:-1], start=1):
            if tok == "-C":
                directory = rest[i + 1]
                break
        pushes.append((env, rest, directory))

    hints = _hints_by_position(command)
    if len(hints) != len(pushes):
        hints = [None] * len(pushes)
    for (env, rest, directory), hint in zip(pushes, hints):
        yield env, rest, (directory or hint)


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
    positionals = _push_positionals(argv)
    return None if positionals is None else positionals[1:]  # drop the remote


def _push_positionals(argv: list[str]) -> list[str] | None:
    """The positional arguments after `push` -- remote first; None if indeterminate."""
    try:
        idx = argv.index("push")
    except ValueError:
        return None
    positionals: list[str] = []
    i = idx + 1
    while i < len(argv):
        tok = argv[i]
        if tok.startswith("-") and tok != "-":
            head, _, value = tok.partition("=")
            if head in PUSH_OPTS_INDETERMINATE:
                return None
            if head == "--recurse-submodules" and value in SUBMODULE_PUSH_MODES:
                return None
            if head in PUSH_OPTS_WITH_VALUE and not _:
                if head == "--recurse-submodules" and i + 1 < len(argv) \
                        and argv[i + 1] in SUBMODULE_PUSH_MODES:
                    return None
                i += 2
                continue
            # A clustered short form (`-qo ci.skip`) takes its value from the
            # next token when the cluster ends in a value-taking letter.
            if not tok.startswith("--") and tok[-1] in SHORT_OPTS_WITH_VALUE:
                i += 2
                continue
            i += 1
            continue
        positionals.append(tok)
        i += 1
    return positionals


# This hook is registered with a 10s timeout in `hooks/hooks.json`, and a
# PreToolUse hook killed on timeout does not deny -- the push simply proceeds.
# So the budget is enforced here rather than left to the harness: one call per
# refspec times a generous per-call timeout would exceed it on a slow repo, and
# the failure would be a silent allow on the one path this guard exists to hold.
# Overridable so the timeout path is testable: it is the one branch whose
# failure direction (allow vs deny) cannot be observed any other way, and a
# mutation turning its refusal into an allow survived an untested suite.
BUDGET_SECONDS = float(os.environ.get("NPWSR_BUDGET_SECONDS", "6.0"))
_DEADLINE = [0.0]


def _rev_parse(directory: str | None, rev: str) -> str | None:
    remaining = _DEADLINE[0] - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("ran out of time resolving what this push would ship")
    args = ["git"] + (["-C", directory] if directory else []) + ["rev-parse", rev]
    try:
        out = subprocess.run(args, capture_output=True, text=True,
                             timeout=min(3.0, remaining))
    except subprocess.TimeoutExpired:
        raise TimeoutError("ran out of time resolving what this push would ship")
    except Exception:
        return None
    if out.returncode != 0:
        return None
    sha = out.stdout.strip()
    return sha.lower() if re.fullmatch(r"[0-9a-f]{40}", sha) else None


def _git_config(directory: str | None, flag: str, key: str) -> str | None:
    args = ["git"] + (["-C", directory] if directory else []) + ["config", flag, key]
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=3)
    except Exception:
        return None
    return out.stdout.strip() or None


def _push_remote(directory: str | None, argv: list[str]) -> str | None:
    """The remote this push acts on, named or not.

    Returning None for a bare `git push` skipped the `remote.<name>.push` check
    in exactly the case it exists for: the command that names nothing is the one
    whose destination is decided entirely by config. So when the command does
    not spell the remote out, resolve the one git would use, in git's own
    precedence order.
    """
    positionals = _push_positionals(argv)
    if positionals:
        return positionals[0]
    branch = _rev_parse_ref(directory, "--abbrev-ref", "HEAD")
    for key in ((f"branch.{branch}.pushRemote",) if branch else ()) + (
            "remote.pushDefault",) + ((f"branch.{branch}.remote",) if branch else ()):
        value = _git_config(directory, "--get", key)
        if value:
            return value
    return "origin"


def _rev_parse_ref(directory: str | None, *args: str) -> str | None:
    cmd = ["git"] + (["-C", directory] if directory else []) + ["rev-parse", *args]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
    except Exception:
        return None
    name = out.stdout.strip()
    return name if out.returncode == 0 and name and name != "HEAD" else None


def shipped_commits(directory: str | None, argv: list[str]) -> tuple[set[str] | None, str]:
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
        named = [t for t in argv if t.partition("=")[0] in PUSH_OPTS_INDETERMINATE
                 or t.partition("=")[0] == "--recurse-submodules"]
        which = f" ({', '.join('`' + t + '`' for t in named)})" if named else ""
        return None, ("this push does not name a single reviewable head" + which)
    if not refspecs:
        # A bare `git push` ships the current branch only under the modern
        # `push.default`. Under `matching` (git's default before 2.0, and still
        # present in long-lived global configs) it ships every branch whose name
        # exists on the remote, and a configured `remote.<name>.push` overrides
        # the question entirely. Measured on git 2.43.0:
        # `git -c push.default=matching push --dry-run origin` reports a branch
        # that is not HEAD. So this is checked rather than assumed.
        default = _git_config(directory, "--get", "push.default")
        if default and default.lower() == "matching":
            return None, "`push.default` is `matching`, so a bare push ships more than HEAD"
        remote = _push_remote(directory, argv)
        if remote and _git_config(directory, "--get-all", f"remote.{remote}.push"):
            return None, (f"`remote.{remote}.push` is configured, so what a bare push "
                          "ships is not simply the current branch")
        head = _rev_parse(directory, "HEAD")
        if head is None:
            return None, "HEAD could not be resolved for the repository being pushed"
        return {head}, ""

    commits: set[str] = set()
    for spec in refspecs:
        src = spec.split(":", 1)[0].lstrip("+")
        if not src:
            continue  # `:branch` deletes a ref and ships nothing
        sha = _rev_parse(directory, f"{src}^{{commit}}")
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


def _blank_fences(text: str) -> tuple[str, bool]:
    """Blank the contents of fenced code blocks, preserving offsets.

    A SCANNER rather than positional pairing. `zip(fences[0::2], fences[1::2])`
    mis-pairs the moment fences nest -- an outer ````` ```` ````` wrapping an inner
    ````` ``` ````` pairs (outer-open, inner-open) and (inner-close, outer-close),
    leaving the quoted content between the inner fences UNBLANKED. That is the
    ordinary shape whenever a reviewer quotes markdown that itself contains a
    fence, which reviewing this repo requires, and it read a blocking verdict as
    clean. An odd fence count mis-blanked in the other direction, wiping the
    report's own closing verdict and letting an earlier one decide it.

    So: a fence opens with three or more backticks or tildes, and closes only on
    a line of the SAME character that is at least as long.

    An unclosed fence is reported rather than merely blanked, and `parse_report`
    treats such a report as stating no verdict at all. A report whose fencing
    does not resolve is one whose structure cannot be read, and the safe answer
    to "is this clean" is then no. It is also what makes a truncated report
    fail, since truncation mid-block leaves exactly this state.

    Offsets are preserved because `parse_report` searches for the fingerprint
    forward from the verdict's own position.
    """
    out = list(text)
    open_char: str | None = None
    open_len = 0
    blank_from = 0
    for m in FENCE.finditer(text):
        marker = m.group(1)
        char, length = marker[0], len(marker)
        if open_char is None:
            open_char, open_len, blank_from = char, length, m.start()
            continue
        if char == open_char and length >= open_len:
            for i in range(blank_from, m.end()):
                if out[i] != "\n":
                    out[i] = " "
            open_char = None
    if open_char is not None:
        for i in range(blank_from, len(out)):
            if out[i] != "\n":
                out[i] = " "
    return "".join(out), open_char is not None


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
    blanked, unclosed = _blank_fences(text)
    if unclosed:
        return None, None
    matches = list(VERDICT_LINE.finditer(blanked))
    if not matches:
        return None, None
    last = matches[-1]
    verdict = "clean" if last.group(1).lower().startswith("ready") else "needs_work"
    sha = REVIEWED_COMMIT.search(blanked, last.end())
    return verdict, (sha.group(1).lower() if sha else None)


def read_latest_review(transcript_path: str) -> tuple[str | None, str | None, bool]:
    """(verdict, reviewed_commit, saw_reviewer_call) from the transcript.

    Only the reviewer's own call results are consulted, and an errored result is
    skipped -- a failed or interrupted reviewer states no verdict, and
    `fail-fast` forbids letting that look identical to a clean one.
    """
    reviewer_call_ids: set[str] = set()
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

            for b in _iter_blocks(record):
                b_type = b.get("type")

                if b_type == "tool_use":
                    if (b.get("name") or "").lower() not in AGENT_TOOLS:
                        continue
                    inp = b.get("input") or {}
                    sub_type = str(
                        inp.get("subagent_type")
                        or inp.get("subagentType")
                        or inp.get("agent_type")
                        or ""
                    )
                    if ADVERSARIAL_AGENT_NAME.match(sub_type):
                        saw_reviewer_call = True
                        call_id = b.get("id")
                        if isinstance(call_id, str) and call_id:
                            reviewer_call_ids.add(call_id)

                elif b_type == "tool_result":
                    if b.get("tool_use_id") not in reviewer_call_ids:
                        continue
                    if b.get("is_error"):
                        continue
                    found, sha = parse_report(_result_text(b))
                    if found:
                        verdict, reviewed_commit = found, sha

    return verdict, reviewed_commit, saw_reviewer_call


def verify_review(transcript_path: str, directory: str | None,
                  argv: list[str]) -> tuple[bool, str]:
    """(is_clean, reason) -- is there a clean verdict for what this push ships?"""
    if not transcript_path or not os.path.exists(transcript_path):
        return False, "No transcript available to verify the adversarial self-review."

    try:
        verdict, reviewed_commit, saw_reviewer_call = read_latest_review(transcript_path)
    except Exception as e:
        return False, f"Failed reading transcript: {e}"

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
            "The reviewer must end its report with `Reviewed-Commit: <sha>`, after the "
            "verdict; without it nothing ties the verdict to what this push would ship, "
            "and a report cut short before its fingerprint is not a verdict."
        )

    try:
        commits, why = shipped_commits(directory, argv)
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
    "committed diff, address or rebut every finding, and let its report state the "
    "commit it read.\n\n"
    "Only that subagent's own result counts -- this message does not, and neither "
    "does reading a file that quotes a verdict.\n\n"
    "Override by prefixing the push itself with `ALLOW_UNREVIEWED_PUSH=1` when no "
    "verdict can exist for the guard to check: an initial empty PR branch (per "
    "pr-on-claim), a review delivered by a separate CLI rather than a subagent, a "
    "session where the reviewer agent is unregistered or loaded from a stale "
    "definition, or an emergency. Say in your reply that you used it and why."
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


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if (payload.get("tool_name") or "") != "Bash":
            return 0

        cmd = (payload.get("tool_input") or {}).get("command") or ""
        if not cmd:
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
            is_clean, reason = verify_review(
                payload.get("transcript_path") or "", directory, argv
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
