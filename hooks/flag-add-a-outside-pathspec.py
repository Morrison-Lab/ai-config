#!/usr/bin/env python3
"""PreToolUse guard: `git add -A`/`--all`/`.`, with untracked files the
command's own exclusion pathspecs do not actually cover.

## The incident

`ucdavis/bcs`'s `CLAUDE.md` bans a bare `git add -A` -- a 2026-07-30 incident
pushed a plaintext SAS credential and real participant identifiers into a PR
because `inst/extdata/reentry/` was untracked and unignored -- and prescribes
`git add -A ':!inst/extdata'` as the sanctioned replacement.

That replacement is narrower than the rule it exists to satisfy. The
exclusion pathspec protects exactly the directory named in it. Any other
untracked file anywhere else in the working tree is still swept in. On
2026-08-09, preparing `ucdavis/bcs#612`, this ran verbatim:

    git add -A ':!inst/extdata'

with two untracked scratch files sitting at the repo root
(`HANDOFF-2026-07-30.md`, `HANDOFF-2026-08-04.md`, left over from earlier
sessions, 304 lines of unrelated prose) -- both went into the commit. Nothing
about the command failed or warned; it did exactly what it says. It was
caught only because two UNRELATED pre-push checks changed verdict afterward
(a punctuation scan and a line-break scan), which is not a designed detector
-- a commit that happened not to trip either one would have shipped clean.

## Why a hook rather than a rule

The sanctioned command is stated in `CLAUDE.md`, was followed to the letter,
and the incident-class recurred anyway on different files, because the
prescribed form only ever excluded one path. A rule that reads "use this
command instead" cannot itself notice that the command's actual coverage,
computed against the LIVE working tree, is narrower than the rule assumes --
that requires running `git status` at the moment of staging, which is exactly
what a `PreToolUse` hook can do and a written rule cannot.

## Why this warns rather than blocks

A bare `git add -A` (or `.`, or `--all`) is frequently exactly right --
staging every real change is the common case, not the exception. What makes
one dangerous is untracked content nobody meant to include, which this hook
cannot distinguish from untracked content that genuinely belongs in the
commit. So it only ever ADDS context: `additionalContext` and a
`systemMessage`, never `permissionDecision`. A blocking guard here would
refuse a large class of legitimate stages and get worked around, per
README's "A hook that misfires is worse than a missing one".

## The match condition

  M1  the tool is `Bash` and `tool_input.command` parses into simple commands
  M2  one of those simple commands is `git add`, after skipping leading
      env-var assignments and lead words (`sudo`, `time`, `command`, `exec`,
      `nohup`, `env`, `!`)
  M3  its arguments amount to "add everything": either `-A`/`--all` with no
      INCLUDING pathspec (git's own whole-repo-scope behaviour), or a bare
      `.`/`./` pathspec (cwd-and-below), computed by `_add_everything`
  M4  `-u`/`--update` alone (no `-A`/`--all`) never triggers this -- it only
      re-stages already-tracked files and can never sweep in an untracked one
  M5  the command's own `:!<path>`/`:(exclude)<path>` arguments are read as
      exclusions and matched by exact-path or path-prefix against `git
      status --porcelain`'s live untracked list; a pathspec containing glob
      metacharacters (`*`, `?`, `[`) is NOT evaluated and excludes nothing,
      which is the SAFE direction (over-warn, never a silent miss)
  M6  scope is whole-repo for `-A`/`--all` with no including pathspec, and
      cwd-and-below (untracked paths not starting with `../`) for a bare `.`
      pathspec -- matching git's own scoping rules for `add`

Fails OPEN on any parse trouble, on `git status` failing or timing out, and
outside a git repository -- consistent with every other guard in this
directory.
"""
import json
import os
import re
import shlex
import subprocess
import sys

RX_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?\n[ \t]*\2\b", re.S)

ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
LEAD_WORDS = {"then", "do", "else", "!", "time", "sudo", "command", "exec",
              "nohup", "env"}

_SHELL_OPS = set("();|&")


def _simple_commands(cmd):
    """Split a shell command into simple-command argv lists; None on error.

    Same construction as `no-unreviewed-pr.py`'s `_simple_commands`: join
    `\\`-continued lines, blank heredoc bodies, turn unquoted newlines into
    `;`, then let `shlex` (in punctuation-aware mode) do the real splitting
    and dequoting -- so `':!inst/extdata'` arrives as the literal string
    `:!inst/extdata`, not as an opaque blanked span.
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
    cmds, cur = [], []
    for t in toks:
        if t and set(t) <= _SHELL_OPS:
            if cur:
                cmds.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        cmds.append(cur)
    return cmds


def _pathspec_value(token):
    """(is_exclusion, bare_path) for one `git add` pathspec argument."""
    if token.startswith(":!"):
        return True, token[2:]
    if token.startswith(":(exclude)"):
        return True, token[len(":(exclude)"):]
    m = re.match(r"^:\(exclude(?:,[^)]*)?\)(.*)$", token)
    if m:
        return True, m.group(1)
    return False, token


def _split_add_args(args):
    """(flags, pathspec_tokens) -- everything after a literal `--` is a
    pathspec even if it starts with `-`."""
    flags, paths = [], []
    seen_dashdash = False
    for a in args:
        if not seen_dashdash and a == "--":
            seen_dashdash = True
            continue
        if not seen_dashdash and a.startswith("-") and a != "-":
            flags.append(a)
        else:
            paths.append(a)
    return flags, paths


def _add_everything(args):
    """M3-M6: (scope, exclusion_paths) for an "add everything" invocation,
    or None if `args` is scoped to specific paths (the safe, unflagged case).
    `scope` is "repo" or "cwd"."""
    flags, paths = _split_add_args(args)
    has_all = any(f in ("-A", "--all") for f in flags)
    has_update_only = any(f in ("-u", "--update") for f in flags) and not has_all
    if has_update_only:
        return None  # M4: never stages an untracked file

    includes, excludes = [], []
    for p in paths:
        is_exclusion, val = _pathspec_value(p)
        (excludes if is_exclusion else includes).append(val)

    if has_all and not includes:
        return "repo", excludes
    if any(inc.rstrip("/") in (".", "") for inc in includes):
        return "cwd", excludes
    return None


def offending(command):
    """(matched_segment, scope, exclusions) for the first "add everything"
    `git add` invocation in `command`, or None."""
    cmds = _simple_commands(command)
    if cmds is None:
        return None
    for argv in cmds:
        i = 0
        while i < len(argv) and (ASSIGNMENT.match(argv[i])
                                  or argv[i] in LEAD_WORDS):
            i += 1
        rest = argv[i:]
        if len(rest) < 2 or rest[0] != "git" or rest[1] != "add":
            continue
        result = _add_everything(rest[2:])
        if result is None:
            continue
        scope, excludes = result
        return " ".join(argv), scope, excludes
    return None


def _untracked_files():
    """Every untracked path from `git status --porcelain=v1 -z`, or None if
    `git status` cannot be run (not a repo, git missing, timeout)."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None

    records = out.stdout.split("\0")
    untracked = []
    i = 0
    while i < len(records):
        rec = records[i]
        i += 1
        if len(rec) < 3:
            continue
        xy, path = rec[:2], rec[3:]
        if xy == "??":
            untracked.append(path)
        if xy[0] in ("R", "C"):
            i += 1  # the rename/copy "from" path is a second NUL-terminated
                     # field, never itself an untracked entry
    return untracked


def _repo_relative_cwd():
    """cwd's path relative to the repository's top level -- e.g. "sub" when
    invoked from `<repo>/sub`, or "." at the top level itself. None if this
    is not a git repository.

    `git status --porcelain` reports paths relative to the REPOSITORY ROOT,
    never to cwd, whatever directory it is run from (verified on git
    2.34.1) -- so a cwd-scoped `git add .` needs this to know which of those
    root-relative paths actually fall under cwd; a naive `../`-prefix check
    on the status output itself would never fire, since none of its paths
    ever carry one.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    toplevel = out.stdout.strip()
    if not toplevel:
        return None
    try:
        return os.path.relpath(os.getcwd(), toplevel)
    except ValueError:
        return None  # e.g. different drives on Windows


def _is_excluded(path, excludes):
    for e in excludes:
        e = e.rstrip("/")
        if any(ch in e for ch in "*?["):
            continue  # M5: cannot statically evaluate a glob pathspec
        if path == e or path.startswith(e + "/"):
            return True
    return False


NOTE = (
    "This `git add` stages EVERYTHING under {scope_desc}, and {count} "
    "untracked file(s) are not covered by its own exclusion pathspec(s):\n\n"
    "  command:  {segment}\n"
    "  untracked, not excluded:\n{files}\n\n"
    "An exclusion pathspec like `:!inst/extdata` protects only the path it "
    "names. Any OTHER untracked file in scope still gets staged -- which is "
    "exactly how two unrelated scratch files (`HANDOFF-2026-*.md`) reached a "
    "commit on 2026-08-09 despite following the repo's own sanctioned "
    "`git add -A ':!inst/extdata'` form.\n\n"
    "Run `git status --porcelain` and review every `??` entry before "
    "staging, or add the specific paths you mean instead of sweeping "
    "everything in."
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:  # fail open, but say so
        print(f"flag-add-a-outside-pathspec: unreadable hook input ({exc})",
              file=sys.stderr)
        return 0

    if payload.get("tool_name") not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        return 0

    inp = payload.get("tool_input") or {}
    command = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script")
    if not isinstance(command, str) or not command.strip():
        return 0

    try:
        hit = offending(command)
    except Exception as exc:  # fail open on any parse trouble
        print(f"flag-add-a-outside-pathspec: could not parse command ({exc})",
              file=sys.stderr)
        return 0

    if hit is None:
        return 0

    segment, scope, excludes = hit
    untracked = _untracked_files()
    if untracked is None:
        return 0  # not a repo, git unreachable, or timed out -- fail open

    if scope == "cwd":
        rel = _repo_relative_cwd()
        if rel and rel != ".":
            prefix = rel.rstrip("/") + "/"
            untracked = [p for p in untracked
                        if p == rel or p.startswith(prefix)]

    remaining = [p for p in untracked if not _is_excluded(p, excludes)]
    if not remaining:
        return 0

    scope_desc = "the repository" if scope == "repo" else "the current directory"
    shown = remaining[:20]
    files = "\n".join(f"    ?? {p}" for p in shown)
    if len(remaining) > len(shown):
        files += f"\n    ... and {len(remaining) - len(shown)} more"

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(
                scope_desc=scope_desc, count=len(remaining),
                segment=segment, files=files,
            ),
        },
        "systemMessage": (
            f"`git add` sweeps in {len(remaining)} untracked file(s) its own "
            "exclusion pathspec does not cover."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
