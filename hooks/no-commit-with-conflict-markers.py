#!/usr/bin/env python3
"""PreToolUse guard: DENY a `git commit` whose commit would carry
merge-conflict markers.

## The incident

2026-10-27, during an `ardia` sweep of `Morrison-Lab/lds`: a `main` merge
into lds#1364 left six files conflicted. The agent resolved them with a
helper script that read only its first argument, so five of the six kept
their `<<<<<<< HEAD` / `=======` / `>>>>>>> origin/main` blocks. `git add -A`
and `git commit --no-edit` committed them. The Quarto render then passed,
because Markdown prints the markers as text, and the plugin's push-time
`check-term-links` caught it only incidentally, by flagging a partial link on
one of those lines. Nothing stopped the commit itself.

## What it checks

For each commit-making invocation in the Bash command -- `git commit` (with
`-a`, `--amend`, `-i`, paths, after `git merge`), and `git merge|rebase|
cherry-pick|revert|am --continue` -- in the directory it runs in (the payload
cwd, moved by `cd <dir> &&`, `pushd` and `git -C <dir>`), it runs git's own
detector, `git diff --check`, which reports `leftover conflict marker` on
added lines:

- the index against the base (`git diff --cached --check <base>`), unless
  the commit names paths without `-i` (`--only`, git's default for paths),
  which commits those paths and nothing else that is staged;
- the working tree against the base for the paths the commit takes from the
  working tree: every tracked path under `-a`, the named paths, and the paths
  a `git add` EARLIER IN THE SAME COMMAND will stage. That last one is the
  incident's own shape: `git add -A && git commit` is checked before the add
  runs, so the index alone would read clean. `git diff HEAD` also reads an
  unmerged (`UU`) path's working-tree file, which `--cached` skips.

`<base>` is `HEAD`, or `HEAD^` under `--amend` (the amended commit replaces
HEAD, so markers already in HEAD are part of what it commits); with no HEAD
(the first commit) the index is compared with the empty tree.

## Why it does not trust `--check` alone

git 2.43 flags a lone `=======` line, which is a Markdown setext heading
underline, as a leftover marker (measured 2026-10-27). So a flagged line
counts only when it is

- an opening `<<<<<<<` or closing `>>>>>>>` line, or a diff3 `|||||||` base
  line, none of which is legitimate text; or
- an `=======` line that follows an opening `<<<<<<<` line with no closing
  line between them, read from the content the commit would carry (the
  staged blob, or the working-tree file).

An aider SEARCH/REPLACE block (`<<<<<<< SEARCH` ... `>>>>>>> REPLACE`, which
`scripts/orchestrator/protocols.py` documents) is not a conflict, and its
three lines are exempt. A file that must hold real marker lines raises its
`conflict-marker-size` attribute in `.gitattributes`, git's own mechanism for
this: `--check` then stops flagging seven-character runs. So there is no
escape variable.

## Why it DENIES

A conflict marker in a commit is never intended, and the deny names every
offending file and line, so the fix is mechanical. Unlike the warn-only
staging guards (`flag-commit-a-sweeps-submodule.py`), nothing here is a
judgement call the author could legitimately make the other way.

## Fails open

On a parse failure, a missing sibling or shared parser, a git failure or
timeout, a directory the text does not name (`cd "$X"`, `env -C`),
`--git-dir`/`--work-tree`/`GIT_DIR`, `--pathspec-from-file` (its paths are
unseen, so only the index is checked), `--dry-run`, `-h`, and an interactive
`-p`/`--interactive` commit or add (what it stages is chosen at the prompt).
Untracked files a preceding `git add -A` would stage are not read: a
conflicted file is always tracked.

Command parsing is `flag-commit-a-sweeps-submodule.py`'s, loaded by path,
over `scripts/lib/shellcmd.py`, so an echoed, grepped or heredoc-quoted
`git commit` is inert.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import time


def _load_sibling():
    """`flag-commit-a-sweeps-submodule.py`, whose command-line parsing this
    hook shares. Loaded by path because the filename is not an identifier."""
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                        "flag-commit-a-sweeps-submodule.py")
    if not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location(
        "flag_commit_a_sweeps_submodule", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None
    if getattr(module, "_simple_commands", None) is None:
        return None  # its shared parser failed to load
    return module


_SIB = _load_sibling()
if _SIB is None:
    print("no-commit-with-conflict-markers: cannot load "
          "flag-commit-a-sweeps-submodule.py; inert", file=sys.stderr)

# Subcommands whose `--continue` makes a commit from the index.
_CONTINUES = {"merge", "rebase", "cherry-pick", "revert", "am"}

# Long options after which what is staged is chosen at a prompt.
_INTERACTIVE_LONG = {"--interactive", "--patch"}


class CommitSpec:
    """What one commit-making invocation commits."""

    def __init__(self):
        self.all = False        # -a: every modified tracked path
        self.amend = False
        self.include = False    # -i: named paths ON TOP of the index
        self.paths = []         # named paths
        self.skip = False       # dry run, -h, interactive

    def staged_counts(self):
        """Whether the index is part of the commit: not when paths are
        named without -i (git's default `--only`)."""
        return self.include or not self.paths


def commit_spec(args):
    """A CommitSpec for the arguments after `git commit`."""
    s = CommitSpec()
    i, dashdash = 0, False
    while i < len(args):
        a = args[i]
        if dashdash:
            s.paths.append(a)
        elif a == "--":
            dashdash = True
        elif a in ("-h", "--help"):
            s.skip = True
        elif a.startswith("--"):
            name = _SIB._long_name(a, _SIB._COMMIT_LONG)
            if name == "--all":
                s.all = True
            elif name == "--amend":
                s.amend = True
            elif name == "--include":
                s.include = True
            elif name in _SIB._COMMIT_DRY_RUN or name in _INTERACTIVE_LONG:
                s.skip = True
            # --pathspec-from-file's paths are unseen: only the index is read
            if name in _SIB._COMMIT_VALUE_LONG and "=" not in a:
                i += 1  # value is the next token
        elif a.startswith("-") and a != "-":
            for pos, ch in enumerate(a[1:], start=1):
                if ch == "a":
                    s.all = True
                elif ch == "i":
                    s.include = True
                elif ch == "p":
                    s.skip = True
                elif ch in _SIB._COMMIT_VALUE_SHORT:
                    if pos == len(a) - 1:
                        i += 1  # value is the next token
                    break
                elif ch in "Su":
                    break  # optional attached value: rest of cluster
        else:
            s.paths.append(a)
        i += 1
    return s


def _add_paths(args):
    """What a `git add` will stage, as (whole_tree, paths), or None when it
    stages nothing the commit after it reads (a dry run, a refresh, `-N`) or
    is interactive."""
    for a in args:
        if a == "--":
            break
        if a.startswith("--"):
            if _SIB._long_name(a, _SIB._ADD_LONG) in _INTERACTIVE_LONG | {
                    "--edit"}:
                return None
        elif a.startswith("-") and a != "-" and set(a[1:]) & set("ipe"):
            return None
    found = _SIB.add_kind(args)
    if found is None:
        return None
    _, paths = found
    if not paths:
        return True, []  # `add -A` / `add -u` with no pathspec
    return False, paths


def _scan(command, start):
    """([(segment, target_dir, spec, worktree), ...], moved) for every
    commit-making invocation in the one command line `command`, where
    `worktree` is (whole_tree, paths) for what earlier `git add`s in the same
    directory stage, and `moved` says whether the line changes directory.
    `start` is as in the sibling's `_scan`."""
    cmds = _SIB._simple_commands(command)
    if cmds is None:
        return [], False
    ignore_cd = _SIB._unreachable_cd(command)
    cds = {(0,): start}

    def cd_of(scope):
        while scope not in cds:
            scope = scope[:-1]
        return cds[scope]

    hits, adds, moved = [], {}, False  # adds: target_dir -> [whole, paths]
    for scope, argv in cmds:
        if _SIB._env_chdir(argv):
            continue
        env, rest = _SIB._strip_env(argv)
        cd = cd_of(scope)
        if rest and rest[0] in ("cd", "pushd", "popd"):
            moved = True
            if not ignore_cd:
                cds[scope] = _SIB._move(rest, cd)
            continue
        inv = _SIB._git_invocation(rest)
        if inv is None or _SIB._redirects_git(env):
            continue
        c_dirs, sub, args = inv
        target = cd
        for d in c_dirs:
            target = _SIB._move(["cd", "--", d], target)
        if target is None:
            continue
        if sub in ("add", "stage"):
            staged = _add_paths(args)
            if staged is not None:
                acc = adds.setdefault(target, [False, []])
                acc[0] = acc[0] or staged[0]
                acc[1].extend(staged[1])
            continue
        if sub == "commit":
            spec = commit_spec(args)
        elif sub in _CONTINUES and "--continue" in args:
            spec = CommitSpec()
        else:
            continue
        if spec.skip:
            continue
        acc = adds.get(target, [False, []])
        hits.append((" ".join(argv), target, spec, (acc[0], list(acc[1]))))
    return hits, moved


def commits(command):
    """Every commit-making invocation in `command`, including nested
    `bash -c` lines, read as the sibling's `offending` reads them."""
    if _SIB is None:
        return []
    pieces = _SIB._shell_c_expansions(command)
    scans = [_scan(piece, "") for piece in pieces]
    hits = list(scans[0][0])
    for i, piece in enumerate(pieces[1:], start=1):
        # Another line's `cd` may have moved the shell this one runs in, so
        # only an absolute directory resolves there.
        others_move = any(m for j, (_, m) in enumerate(scans) if j != i)
        hits += _scan(piece, None)[0] if others_move else scans[i][0]
    return hits


# hooks.json gives this hook 10 s; every git call shares one deadline inside
# it, so a slow repository fails open rather than being killed. The tests
# override it with NO_COMMIT_MARKERS_BUDGET_S.
_DEFAULT_BUDGET_S = 8.0
_PER_CALL_S = 5.0
_deadline = None


def _start_budget():
    global _deadline
    try:
        budget = float(os.environ.get("NO_COMMIT_MARKERS_BUDGET_S", ""))
    except ValueError:
        budget = _DEFAULT_BUDGET_S
    _deadline = time.monotonic() + budget


def _git(cwd, *args, ok=(0,)):
    """stdout of `git args` in cwd, or None on any failure, an exit status
    outside `ok`, or a spent deadline. fsmonitor is off and optional locks
    are off, so no repository program runs and the index is never
    rewritten before the user approves the command."""
    if _deadline is None:
        return None
    remaining = _deadline - time.monotonic()
    if remaining <= 0:
        return None
    try:
        out = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-c", "core.quotePath=false",
             "-c", "diff.relative=false", *args],
            cwd=cwd, capture_output=True,
            timeout=min(_PER_CALL_S, remaining),
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode not in ok:
        return None
    return out.stdout.decode("utf-8", "surrogateescape")


_CHECK_LINE = re.compile(r"^(.+):(\d+): leftover conflict marker$")


def _flagged(cwd, cached, base, paths):
    """{path: {line, ...}} that `git diff --check` flags, or None when git
    failed. `--check` exits 2 when it finds a problem."""
    args = ["diff", "--no-ext-diff", "--no-color", "--check"]
    if cached:
        args.append("--cached")
    if base:
        args.append(base)
    if paths is not None:
        args += ["--", *paths]
    out = _git(cwd, *args, ok=(0, 2))
    if out is None:
        return None
    found = {}
    for line in out.splitlines():
        m = _CHECK_LINE.match(line)
        if m:
            found.setdefault(m.group(1), set()).add(int(m.group(2)))
    return found


_MARKER = re.compile(r"^(<{7,}|>{7,}|\|{7,}|={7,})(?:[ \t]+(.*?))?[ \t]*$")


def _marker(text):
    """(kind, label) for a marker line, kind one of `<>|=`; None otherwise."""
    m = _MARKER.match(text.rstrip("\r\n"))
    if not m:
        return None
    return m.group(1)[0], (m.group(2) or "")


def offending_lines(content, flagged):
    """The flagged 1-based line numbers of `content` that are conflict
    markers by the rules in the docstring, with their text."""
    lines = content.splitlines()
    out = []
    open_label = None  # label of the enclosing `<<<<<<<`, None outside one
    for no, text in enumerate(lines, start=1):
        mk = _marker(text)
        kind = mk[0] if mk else None
        bad = False
        if kind == "<":
            open_label = mk[1]
            bad = mk[1] != "SEARCH"
        elif kind == ">":
            bad = not (mk[1] == "REPLACE" and open_label == "SEARCH")
            open_label = None
        elif kind == "|":
            bad = True
        elif kind == "=":
            bad = open_label is not None and open_label != "SEARCH"
        if bad and no in flagged:
            out.append((no, text.rstrip("\r\n")))
    return out


def _content(cwd, top, path, staged):
    """The text the commit would carry for `path` (relative to the top
    level): the staged blob, or the working-tree file. None if unreadable."""
    if staged:
        return _git(cwd, "show", f":{path}")
    try:
        with open(os.path.join(top, path), "rb") as fh:
            return fh.read().decode("utf-8", "surrogateescape")
    except OSError:
        return None


def check(cwd, spec, worktree):
    """[(path, line, text), ...] of conflict-marker lines the invocation
    would commit in `cwd`, sorted; empty when clean or undecidable."""
    top = _git(cwd, "rev-parse", "--show-toplevel")
    if top is None:
        return []
    top = top.strip()
    base = None
    if spec.amend and _git(cwd, "rev-parse", "-q", "--verify",
                           "HEAD~1^{commit}") is not None:
        base = "HEAD^"
    elif _git(cwd, "rev-parse", "-q", "--verify", "HEAD^{commit}") is not None:
        base = "HEAD"

    # Each source is (staged?, flagged-map).
    sources = []
    if spec.staged_counts():
        found = _flagged(cwd, True, base, None)
        if found:
            sources.append((True, found))
    whole, add_paths = worktree
    if spec.all:
        whole = True
    paths = list(add_paths) + list(spec.paths)
    if whole or paths:
        # With no HEAD, plain `git diff --check` reads the working tree
        # against the index, which is the closest available base.
        found = _flagged(cwd, False, base, None if whole else paths)
        if found:
            sources.append((False, found))

    hits = set()
    for staged, found in sources:
        for path, nums in found.items():
            content = _content(cwd, top, path, staged)
            if content is None:
                continue
            for no, text in offending_lines(content, nums):
                hits.add((path, no, text))
    return sorted(hits)


_SHOW = 20

NOTE = (
    "Refused: this commit would carry merge-conflict markers.\n\n"
    "  command:  {segment}\n"
    "  in:       {cwd}\n"
    "  markers (file:line):\n{lines}\n\n"
    "On 2026-10-27 a helper script that read only its first argument left "
    "five of six conflicted files unresolved during a `main` merge into "
    "Morrison-Lab/lds#1364, and `git add -A && git commit --no-edit` "
    "committed the markers; the render passed because Markdown prints them "
    "as text.\n\n"
    "Resolve every block (keep what each side added, hunk by hunk), then "
    "confirm with `git diff --cached --check` (and `git diff HEAD --check` "
    "for files you have yet to stage) before committing again. A file that "
    "legitimately holds marker lines sets a larger `conflict-marker-size` "
    "for its path in `.gitattributes`."
)


def deny(segment, cwd, hits):
    lines = "\n".join(f"    {p}:{n}: {t}" for p, n, t in hits[:_SHOW])
    if len(hits) > _SHOW:
        lines += f"\n    ... and {len(hits) - _SHOW} more"
    files = sorted({p for p, _, _ in hits})
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": NOTE.format(
                segment=segment, cwd=cwd, lines=lines),
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            f"Refused a commit carrying {len(hits)} conflict-marker line(s) "
            f"in {len(files)} file(s): {', '.join(files[:5])}"
            + (" ..." if len(files) > 5 else "") + "."
        )
    print(json.dumps(out))
    return 0


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
        print(f"no-commit-with-conflict-markers: unreadable hook input ({exc})",
              file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    _start_budget()
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0

    def quiet():
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    if payload.get("tool_name") not in ("Bash", "bash", "run_command",
                                        "execute_command", "terminal", "shell"):
        return quiet()
    inp = payload.get("tool_input")
    inp = inp if isinstance(inp, dict) else {}
    command = (inp.get("command") or inp.get("CommandLine") or inp.get("cmd")
               or inp.get("script"))
    if not isinstance(command, str) or "commit" not in command and (
            "--continue" not in command):
        return quiet()

    try:
        found = commits(command)
    except Exception as exc:  # fail open on any parse trouble
        print(f"no-commit-with-conflict-markers: could not parse command ({exc})",
              file=sys.stderr)
        return 0

    base = next((c for c in (inp.get("Cwd"), payload.get("cwd"))
                 if isinstance(c, str) and c), None) or os.getcwd()
    for segment, target, spec, worktree in found:
        cwd = os.path.normpath(os.path.join(base, target))
        if not os.path.isdir(cwd):
            continue
        try:
            hits = check(cwd, spec, worktree)
        except Exception as exc:  # fail open
            print(f"no-commit-with-conflict-markers: check failed ({exc})",
                  file=sys.stderr)
            continue
        if hits:
            return deny(segment, cwd, hits)
    return quiet()


if __name__ == "__main__":
    sys.exit(main())
