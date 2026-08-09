#!/usr/bin/env python3
"""PreToolUse guard: `git reset --hard` about to discard tracked, uncommitted
work that has nothing to do with the reset itself.

## The incident

While wiring up gitleaks secret scanning in `ucdavis/bcs#612` on 2026-08-09,
a control experiment planted a synthetic secret in a throwaway commit,
confirmed the scanner caught it, then ran

    git reset --hard <before>

to drop the probe commit. At that same moment the working tree carried
UNRELATED uncommitted edits to `.Rbuildignore` and `NEWS.md` -- ordinary work
in progress, nothing to do with the probe. `reset --hard` reverted both
along with the probe commit, and both had to be redone from scratch.

Nothing about the command warned. It is not a git quirk -- `git reset --hard
<ref>` resetting the ENTIRE working tree (index, staged changes, unstaged
changes to tracked files) to `<ref>` is exactly its documented behaviour. The
mistake was reaching for it in a working tree that held unrelated live
edits, for an operation that never needed to touch that tree at all.

## Why a hook rather than a rule

The auto-mode system reminder already states the general form of this rule
("before any command that could discard uncommitted work ... run `git
status` first and stash"), and it was available in the very session that hit
this. It did not fire, because the moment did not register as the kind of
action the rule covers -- a disposable control experiment felt read-only,
not like "editing files". A rule that has to be recognized as applicable at
the moment of typing is exactly the gap a hook closes: this one runs on the
command itself, independent of whether the moment felt risky.

## Why this warns rather than blocks

`git reset --hard` is frequently exactly what is wanted -- discarding a bad
commit or a failed experiment IS the point, most of the time. What makes one
dangerous is uncommitted work sitting in the same tree that has nothing to
do with the reset, and this hook cannot tell "this working tree happens to
be dirty from something unrelated" from "these changes are the very thing I
meant to discard". So it only ever ADDS context, per README's "A hook that
misfires is worse than a missing one" -- no `permissionDecision`, ever.

## The match condition

  M1  the tool is `Bash` and `tool_input.command` parses into simple commands
  M2  one of those simple commands is `git reset`, after skipping leading
      env-var assignments and lead words (`sudo`, `time`, `command`, `exec`,
      `nohup`, `env`, `!`)
  M3  its arguments include the literal token `--hard` (a boolean flag; git
      accepts no `<ref>` pathspec form together with `--hard` at all, so no
      scoping logic is needed -- a `--hard` reset always targets the whole
      tracked working tree)
  M4  `git status --porcelain` reports at least one entry that is NOT
      untracked (`??`) -- i.e. at least one tracked file has a staged or
      unstaged change relative to HEAD, which `--hard` will discard
      regardless of which ref it resets to, since an uncommitted edit was
      never captured by any commit in the first place

Untracked files are deliberately out of scope: `reset --hard` does not touch
them (that is `git clean`'s job), so an untracked scratch file sitting in
the tree is not itself at risk from this command.

Fails OPEN on any parse trouble, on `git status` failing or timing out, and
outside a git repository.
"""
import json
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

    Same construction as `flag-add-a-outside-pathspec.py`'s
    `_simple_commands` (itself following `no-unreviewed-pr.py`'s pattern):
    join `\\`-continued lines, blank heredoc bodies, turn unquoted newlines
    into `;`, then let `shlex` (punctuation-aware) split and dequote.
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


def offending(command):
    """The matched `git reset --hard ...` segment in `command`, or None."""
    cmds = _simple_commands(command)
    if cmds is None:
        return None
    for argv in cmds:
        i = 0
        while i < len(argv) and (ASSIGNMENT.match(argv[i])
                                  or argv[i] in LEAD_WORDS):
            i += 1
        rest = argv[i:]
        if len(rest) < 2 or rest[0] != "git" or rest[1] != "reset":
            continue
        if "--hard" not in rest[2:]:
            continue
        return " ".join(argv)
    return None


def _tracked_changes():
    """Every path from `git status --porcelain=v1 -z` that is NOT untracked
    -- i.e. has a staged or unstaged change to a tracked file -- or None if
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
    changed = []
    i = 0
    while i < len(records):
        rec = records[i]
        i += 1
        if len(rec) < 3:
            continue
        xy, path = rec[:2], rec[3:]
        if xy != "??":
            changed.append(path)
        if xy[0] in ("R", "C"):
            i += 1  # the rename/copy "from" path is a second NUL-terminated
                     # field, not a change of its own
    return changed


NOTE = (
    "This `git reset --hard` will discard {count} tracked file(s) with "
    "uncommitted changes -- staged or unstaged -- that have nothing "
    "necessarily to do with why this reset is being run:\n\n"
    "  command:  {segment}\n"
    "  would be discarded:\n{files}\n\n"
    "`git reset --hard <ref>` resets the ENTIRE working tree to `<ref>`, "
    "which is exactly its documented behaviour -- it does not distinguish "
    "'the commit I meant to undo' from 'other uncommitted work sitting in "
    "the same tree'. On 2026-08-09 this discarded unrelated edits to "
    "`.Rbuildignore` and `NEWS.md` while resetting away a throwaway probe "
    "commit; both had to be redone.\n\n"
    "If these changes are not meant to be discarded, commit or "
    "`git stash -u` them first. If a destructive experiment does not need "
    "the current working tree at all, run it in a scratch clone or a "
    "throwaway `git worktree add --detach` instead."
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:  # fail open, but say so
        print(f"flag-reset-hard-uncommitted-work: unreadable hook input "
              f"({exc})", file=sys.stderr)
        return 0

    if payload.get("tool_name") != "Bash":
        return 0

    command = (payload.get("tool_input") or {}).get("command")
    if not isinstance(command, str) or not command.strip():
        return 0

    try:
        segment = offending(command)
    except Exception as exc:  # fail open on any parse trouble
        print(f"flag-reset-hard-uncommitted-work: could not parse command "
              f"({exc})", file=sys.stderr)
        return 0

    if segment is None:
        return 0

    changed = _tracked_changes()
    if not changed:
        return 0  # None (git unreachable) or empty (clean tree) -- fail open

    shown = changed[:20]
    files = "\n".join(f"    {p}" for p in shown)
    if len(changed) > len(shown):
        files += f"\n    ... and {len(changed) - len(shown)} more"

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(
                count=len(changed), segment=segment, files=files,
            ),
        },
        "systemMessage": (
            f"`git reset --hard` will discard {len(changed)} tracked "
            "file(s) with uncommitted changes."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
