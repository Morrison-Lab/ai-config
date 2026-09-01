#!/usr/bin/env python3
"""PreToolUse guard: `git reset --hard`, `git checkout <path>`, or
`git restore <path>` about to discard tracked, uncommitted work that has
nothing to do with the command itself.

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
  M2  one of those simple commands is `git reset`, `git checkout`, or
      `git restore`, after skipping leading env-var assignments and lead
      words (`sudo`, `time`, `command`, `exec`, `nohup`, `env`, `!`)
  M3  for `git reset`: its arguments include the literal token `--hard` (a
      boolean flag; git accepts no `<ref>` pathspec form together with
      `--hard` at all, so no scoping logic is needed -- a `--hard` reset
      always targets the whole tracked working tree)
  M3' for `git checkout`/`git restore`: the invocation resolves to at least
      one PATHSPEC (see "Ref-vs-path disambiguation" below) and, for
      `restore`, is not `--staged` without `--worktree` (that combination
      only rewrites the index, never the working tree)
  M4  `git status --porcelain`, scoped to the whole tree for `reset --hard`
      or to the resolved pathspecs for `checkout`/`restore`, reports at
      least one entry that is NOT untracked (`??`) -- i.e. at least one
      tracked file in scope has a staged or unstaged change relative to
      HEAD, which the command will discard

## Ref-vs-path disambiguation

`git checkout <arg>` is ambiguous on its face: `<arg>` may be a ref (branch,
tag, SHA, `HEAD`, `-` for "previous branch") -- a safe switch, since git
itself refuses one that would clobber local changes -- or a pathspec, which
this hook exists to catch. Mirroring git's own tie-break (a name that is
both a ref and a path resolves as the REF) is the reliable way to tell them
apart, so each bare positional argument is tested with
`git rev-parse --quiet --verify <arg>^{commit}`; only an argument that
demonstrably does NOT resolve as a commit-ish counts as a pathspec.
A `--` separator sidesteps the question entirely -- everything after it is
unambiguously a pathspec, per `git checkout`'s own syntax (`git checkout
[<ref>] [--] <pathspec>...`). `git restore`'s positional operands are always
pathspecs (its ref comes from `-s`/`--source`, never positionally), so no
resolution is needed there.

Untracked files are deliberately out of scope for all three commands: none
of `reset --hard`, `checkout <path>`, or `restore <path>` can discard a file
git is not already tracking (that is `git clean`'s job), so an untracked
scratch file sitting in the tree is not itself at risk.

The flag lists below are a best-effort read of `git checkout`/`git
restore`'s documented options, not an exhaustive reimplementation of git's
argument parser. An unrecognized `-`-prefixed token is skipped rather than
risking a false pathspec read from its value.

Fails OPEN on any parse trouble, on `git status`/`git rev-parse` failing or
timing out, and outside a git repository.
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


# Boolean (no separate value) flags shared or specific to checkout/restore.
CHECKOUT_RESTORE_BOOL_FLAGS = {
    "-q", "--quiet", "-f", "--force", "-m", "--merge", "-p", "--patch",
    "--progress", "--no-progress", "--overlay", "--no-overlay",
    "--recurse-submodules", "--no-recurse-submodules",
    "--pathspec-file-nul", "--ignore-unmerged", "--ours", "--theirs",
    "--track", "-t",
    # checkout-only
    "--overwrite-ignore", "--no-overwrite-ignore", "--ignore-other-worktrees",
    "--ignore-skip-worktree-bits", "--guess", "--no-guess", "--detach", "-l",
}
# Flags that consume the NEXT token as a value (checked, per subcommand).
CHECKOUT_VALUE_FLAGS = {"-b", "-B", "--orphan"}
RESTORE_VALUE_FLAGS = {"-s", "--source"}


def _checkout_restore_targets(subcommand, args):
    """Positional targets of a `checkout`/`restore` invocation's ARGS (the
    tokens after `git checkout`/`git restore`).

    Returns (pre, post, saw_sep, staged_no_worktree). `pre` is every
    non-flag token before a `--` separator (or all of them, if none);
    `post` is every token after one. `staged_no_worktree` (restore only) is
    whether `--staged` appeared without `--worktree` -- that combination
    only rewrites the index, so it carries no risk to the working tree.
    """
    value_flags = (CHECKOUT_VALUE_FLAGS if subcommand == "checkout"
                   else RESTORE_VALUE_FLAGS)
    pre, post = [], []
    saw_sep = saw_staged = saw_worktree = False
    i = 0
    while i < len(args):
        tok = args[i]
        if saw_sep:
            post.append(tok)
            i += 1
            continue
        if tok == "--":
            saw_sep = True
            i += 1
            continue
        if tok in ("-S", "--staged"):
            saw_staged = True
            i += 1
            continue
        if tok in ("-W", "--worktree"):
            saw_worktree = True
            i += 1
            continue
        if tok in CHECKOUT_RESTORE_BOOL_FLAGS:
            i += 1
            continue
        if tok in value_flags:
            i += 2
            continue
        if tok.startswith("-") and tok != "-":
            i += 1  # an unrecognized flag -- see the module docstring
            continue
        pre.append(tok)
        i += 1
    staged_no_worktree = (subcommand == "restore" and saw_staged
                           and not saw_worktree)
    return pre, post, saw_sep, staged_no_worktree


def _resolves_as_ref(arg):
    """Whether `arg` names a commit-ish (branch, tag, SHA, `HEAD`, ...) in
    this repo. None if git could not even be asked (missing, timeout) --
    the caller treats that the same as "yes, a ref", the same fail-open
    direction `_tracked_changes` takes on an unreachable git."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--quiet", "--verify", f"{arg}^{{commit}}"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.returncode == 0


def _looks_like_path(arg):
    """True only when `arg` demonstrably does NOT resolve as a ref -- the
    one case git itself (and this hook) reads as a pathspec rather than a
    branch switch."""
    return _resolves_as_ref(arg) is False


def offending(command):
    """The matched destructive-discard invocation in `command`, or None.

    Returns (kind, segment, paths). `kind` is "reset-hard" (paths is None
    -- the whole tracked tree is in scope) or "checkout"/"restore" (paths
    is the resolved pathspec list that invocation would revert).
    """
    cmds = _simple_commands(command)
    if cmds is None:
        return None
    for argv in cmds:
        i = 0
        while i < len(argv) and (ASSIGNMENT.match(argv[i])
                                  or argv[i] in LEAD_WORDS):
            i += 1
        rest = argv[i:]
        if len(rest) < 2 or rest[0] != "git":
            continue
        sub = rest[1]
        if sub == "reset":
            if "--hard" not in rest[2:]:
                continue
            return "reset-hard", " ".join(argv), None
        if sub not in ("checkout", "restore"):
            continue
        pre, post, saw_sep, staged_no_worktree = _checkout_restore_targets(
            sub, rest[2:])
        if staged_no_worktree:
            continue
        if sub == "restore":
            paths = pre + post
        elif saw_sep:
            paths = post
        elif not pre:
            paths = []
        elif pre[0] == "-":
            paths = pre[1:]
        elif len(pre) == 1:
            paths = pre if _looks_like_path(pre[0]) else []
        else:
            paths = pre if _looks_like_path(pre[0]) else pre[1:]
        if not paths:
            continue
        return sub, " ".join(argv), paths
    return None


def _tracked_changes(paths=None):
    """Every path from `git status --porcelain=v1 -z`, optionally scoped to
    `paths`, that is NOT untracked -- i.e. has a staged or unstaged change
    to a tracked file -- or None if `git status` cannot be run (not a repo,
    git missing, timeout)."""
    try:
        cmd = ["git", "status", "--porcelain=v1", "-z"]
        if paths:
            cmd += ["--", *paths]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
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


NOTE_RESET_HARD = (
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

NOTE_PATH_DISCARD = (
    "This `git {subcommand}` will discard {count} tracked file(s) with "
    "uncommitted changes -- staged or unstaged -- that have nothing "
    "necessarily to do with why this is being run:\n\n"
    "  command:  {segment}\n"
    "  would be discarded:\n{files}\n\n"
    "`git checkout <path>` / `git restore <path>` revert the named path(s) "
    "to the INDEX, not to 'the state before whatever I was just doing' -- "
    "any edit made since the last `git add` is destroyed, silently, with "
    "no output and exit 0. On 2026-08-21 this destroyed a comment written "
    "after the last `git add`, while reverting an unrelated deliberate "
    "test mutation.\n\n"
    "If these changes are not meant to be discarded, commit or "
    "`git stash -u` them first."
)


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
        print(f"flag-reset-hard-uncommitted-work: unreadable hook input ({exc})",

              file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0

    if payload.get("tool_name") not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    inp = payload.get("tool_input") or {}
    command = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script")
    if not isinstance(command, str) or not command.strip():
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    try:
        match = offending(command)
    except Exception as exc:  # fail open on any parse trouble
        print(f"flag-reset-hard-uncommitted-work: could not parse command "
              f"({exc})", file=sys.stderr)
        return 0

    if match is None:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0
    kind, segment, paths = match

    sim_dirty = os.environ.get("SIMULATE_DIRTY")
    if sim_dirty is not None:
        changed = [f.strip() for f in sim_dirty.split(",") if f.strip()]
    else:
        changed = _tracked_changes(paths)
    if not changed:
        return 0  # None (git unreachable) or empty (clean tree) -- fail open

    shown = changed[:20]
    files = "\n".join(f"    {p}" for p in shown)
    if len(changed) > len(shown):
        files += f"\n    ... and {len(changed) - len(shown)} more"

    if kind == "reset-hard":
        note = NOTE_RESET_HARD.format(
            count=len(changed), segment=segment, files=files)
        summary = (f"`git reset --hard` will discard {len(changed)} "
                   "tracked file(s) with uncommitted changes.")
    else:
        note = NOTE_PATH_DISCARD.format(
            subcommand=kind, count=len(changed), segment=segment, files=files)
        summary = (f"`git {kind}` will discard {len(changed)} tracked "
                   "file(s) with uncommitted changes.")

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": note,
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = summary
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
