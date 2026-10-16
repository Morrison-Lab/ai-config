#!/usr/bin/env python3
"""PreToolUse guard: a `git` command that stages every modified tracked path
-- `git commit -a`/`--all`, `git add -u`/`--update`, `git add -A`/`--all`
(`--no-ignore-removal`), or a `git add .`/`git add <dir>` covering a
submodule -- while that submodule's checked-out commit differs from the one
the index pins.

## The incident

2026-10-15, `Morrison-Lab/lds#1026`: `git commit -am "..."` ran in a checkout
whose `latex-macros` submodule sat at a different commit than the index
recorded. `-a` stages every modified TRACKED path, and a submodule whose HEAD
has moved is a modified tracked path (a gitlink, mode 160000). So the commit
carried the intended `CLAUDE.md` edit AND moved the pin from `6e227b6` to the
older `85c285b`. The PR bot flagged it as blocking.

`flag-add-a-outside-pathspec.py` covers `git add -A` and untracked files. It
does not read `git commit -a`, does not read `git add -u` (its M4 clause
exempts `-u` because `-u` never stages an UNTRACKED file), and does not look
at submodules at all. Checked with git 2.x: `git add -u`, `git add -A`,
`git add .` and `git add <dir>` all stage a moved gitlink, as does
`git commit -a`.

## Why a hook rather than a rule

Nothing in the command text says the submodule moved. Whether a pin is about to
change is a fact about the live working tree, which only `git status` at the
moment of the commit can answer -- the same reasoning as the sibling guard.

## Why this warns rather than blocks

A deliberate pin bump (`git commit -am "bump macros"`) is legitimate and is
often exactly what `-a` is for. The hook cannot tell it from an accident, so it
only ADDS context: `additionalContext` and a `systemMessage`, never a
`permissionDecision`. See README's "A hook that misfires is worse than a
missing one".

## The match condition

  M1  the tool is `Bash` and `tool_input.command` parses into simple commands
  M2  one of them is `git`, after skipping leading env-var assignments and
      lead words, and `-C <dir>` / `-c <k=v>` global options; a command line
      inside `bash -c '...'` (or `sh -c`) is read too
  M3  its subcommand is `commit` with `-a`/`--all` (also inside a combined
      short cluster such as `-am`, `-av`, `-sam`; a cluster is read left to
      right and stops at a letter that takes a value, so `-ma` -- message
      "a" -- is NOT `-a`, and also at `S` and `u`, whose values are optional
      and attached, so `-uall` is NOT `-a` while `-S -a` and `-u -a` ARE),
      or `add` with `-u`/`--update`, `-A`/`--all`, or a pathspec that covers
      a submodule from above (`git add .`, `git add <dir>`); a dry run
      (`commit --dry-run`/`--short`/`--porcelain`/`--long`, `add -n`/
      `--dry-run`) stages and commits nothing and is silent. Long options
      may be abbreviated to an unambiguous prefix, as git allows (`--dry`,
      `--upd`); an ambiguous prefix names nothing. Every match in the command
      is checked, not only the first
  M4  the target repository is the `-C` directory (`~` and `$HOME` expanded
      like a `cd`), applied on top of the
      session cwd (`tool_input.Cwd`, else the payload's `cwd`, else the
      hook's own) and of any earlier `cd <dir>` in the same command, scoped
      to its subshell. `cd`, `pushd` and `popd` are resolved by the shared
      `shellcmd.resolve_cd_target` (`-P`/`-L`, `~` and `$HOME` expanded); one
      it cannot name (a bare `popd`, `cd -`, `cd $VAR`, a backtick) makes the
      directory unknown, so a later relative target is skipped (see below).
      A `cd` that is a stage of a pipeline (`cd x | cat`) or a background job
      (`cd x &`) runs in a subshell of its own in bash and moves nothing; when
      the command has one, EVERY directory change in it is ignored and the
      session directory is checked. A nested `bash -c` line starts in the
      session directory when no other line of the command has a `cd`, else
      in an unknown one
  M5  `git status --porcelain=v1 -z -uno` there lists an entry whose worktree
      column is `M` and whose path has mode 160000 in `git ls-files -s`. The
      configured ignore settings decide: with `submodule.<name>.ignore=all` or
      `diff.ignoreSubmodules=all` git leaves the gitlink alone and so does the
      hook (an `--ignore-submodules=` flag would override them). Settings
      given as `git -c key=value` on the command are NOT passed on (measured:
      only `-c diff.ignoreSubmodules=all commit -a` makes git skip the
      gitlink, so the hook warns there although nothing is staged). Every git
      call the hook makes runs with `-c core.fsmonitor=false`, because a
      repository's `core.fsmonitor` program would otherwise run during
      `git status`, before the user approves the command
  M6  the submodule's own HEAD differs from the commit the index pins. A
      submodule with only dirty CONTENT is also reported as ` M` but leaves
      the gitlink unchanged and cannot be swept in, so it stays silent here.
      A pin bump already staged (`M ` with HEAD still equal to the staged
      pin) is silent too, while `MM` (staged, then the submodule moved again)
      warns
  M7  for `git add -u|-A <pathspec>`, only a submodule at or under a pathspec
      counts; an exclude pathspec (`:!x`, `:^x`, `:(exclude)x`) that matches
      the submodule keeps it out whatever else is given, and pathspecs that
      are all excludes mean everything else (checked with git 2.43). Glob
      excludes are matched with fnmatch, which approximates git's. Other
      magic (`:(glob)`, `:(attr:...)`) or a glob include is not evaluated and
      warns; for a plain `git add <pathspec>`, only a pathspec covering the
      submodule from above counts (naming it is how a pin is bumped on
      purpose, and unevaluated magic or a glob include stays silent).
      `:/path` and `:(top)path` are read as `path` from the repository root,
      so `git add :/` covers everything, and `icase` and `literal` are read.
      Relative paths are compared through realpath. `commit -a` takes no
      pathspec (git refuses the combination)

Fails OPEN on any parse trouble, on git failing or timing out, and outside a
git repository. Every git call shares an 8 s deadline, inside the 10 s the
hook gets in hooks.json, and runs with GIT_OPTIONAL_LOCKS=0.

## Documented silent cases

The hook cannot know the target repository, so it says nothing, rather than
check the wrong one, when:

  - the command carries `--git-dir` or `--work-tree`, which name another
    repository than the cwd, `-C` and `cd` resolve to;
  - the target directory is not a directory at match time, which includes
    any `cd` into a directory the command itself creates;
  - an earlier `cd $VAR`, `cd -`, backtick target, `popd` or bare `pushd`
    left the directory unknown, so a later relative `cd ..` or `-C dir` is not
    guessed at (an absolute `git -C /path` after it is still read);
  - a `GIT_DIR=...` or `GIT_WORK_TREE=...` prefix (also after `env`) names
    another repository, like `--git-dir`; an earlier `export GIT_DIR=...;`
    statement or any other redirecting variable is not read;
  - git is not reached as `git` after the shared parser's normalisation
    (`/usr/bin/git` and `timeout 60 git` ARE read): an alias or a shell
    function is not followed;
  - the paths a `--pathspec-from-file` reads are not seen: with `-u`/`-A`
    that reads as no pathspec (the whole repository), and a plain `add` of
    them is silent;
  - a pipeline or background `cd` is detected from the command text, with
    quoted strings blanked; the approximation ignores every `cd` in the
    command, so a `cd` that does take effect beside it is not followed either;
  - a nested `bash -c` line has an unknown directory when any other line of
    the command has a `cd` (before it, after it, or in an intermediate
    `bash -c`), so only an absolute `git -C /path` or `cd /path` inside it is
    read;
  - `eval '...'` and a command built from variables are not read;
  - `env -C dir git ...` and `env --chdir=dir git ...` run elsewhere: the
    hook goes silent on them; other wrappers that change directory are not
    recognised;
  - `git add -N`/`--intent-to-add` and `--renormalize` stage no gitlink and
    are silent (measured, git 2.43);
  - a `cd` inside a subshell `( ... )` is scoped to it, as in the shell, so a
    git command after the subshell runs where the subshell started; a `cd` in
    a `{ ... }` group moves the caller and is followed;
  - the commit names its paths: `git commit <pathspec>` and `git commit -i
    <pathspec>` also commit a moved gitlink covered by a directory pathspec
    (checked: `git commit -m x .` committed `mod`), but they say which paths
    they take, so the hook does not parse commit's positional arguments.
"""
import fnmatch
import json
import os
import re
import subprocess
import sys
import time

# `git commit` short options that consume a value (attached or next token),
# so the rest of a cluster after one of them is that value, not more flags.
# -S and -u take OPTIONAL, attached-only arguments, so they never consume
# the next token and are deliberately absent here.
_COMMIT_VALUE_SHORT = set("mFCct")
_COMMIT_VALUE_LONG = {
    "--message", "--file", "--author", "--date", "--cleanup",
    "--reuse-message", "--reedit-message", "--fixup", "--squash",
    "--template", "--trailer", "--pathspec-from-file",
}
# global options of `git` that consume the next token (checked with git 2.x:
# `--namespace ns` and `--config-env k=ENV` take a separated value;
# `--exec-path[=<path>]` takes an optional ATTACHED one and so must not be
# here, and `--super-prefix` is not a user option at all).
# --git-dir and --work-tree are handled before this set is consulted.
_GIT_VALUE_GLOBAL = {"-C", "-c", "--namespace", "--config-env"}
# `git commit` options that make it a dry run: nothing is committed.
_COMMIT_DRY_RUN = {"--dry-run", "--short", "--porcelain", "--long"}
# Every long option of `git commit` and `git add` (git 2.43, `-h`). git
# accepts an unambiguous prefix of one (`--dry` is `--dry-run`, `--upd` is
# `--update`), so a token is resolved against these lists, not compared whole.
_COMMIT_LONG = _COMMIT_VALUE_LONG | _COMMIT_DRY_RUN | {
    "--quiet", "--verbose", "--reset-author", "--signoff", "--edit",
    "--status", "--gpg-sign", "--all", "--include", "--interactive",
    "--patch", "--only", "--no-verify", "--verify", "--branch",
    "--ahead-behind", "--null", "--amend", "--no-post-rewrite",
    "--post-rewrite", "--untracked-files", "--pathspec-file-nul",
    "--allow-empty", "--allow-empty-message",
}
# `git add` options after which nothing is staged that matters here: a dry
# run, a refresh, `-N` (an empty placeholder for new files) and
# `--renormalize` (tracked files only, never a gitlink; measured, git 2.43).
_STAGES_NOTHING = {"--dry-run", "--refresh", "--intent-to-add",
                   "--renormalize"}
_ADD_VALUE_LONG = {"--chmod", "--pathspec-from-file"}
_ADD_LONG = _ADD_VALUE_LONG | {
    "--dry-run", "--verbose", "--interactive", "--patch", "--edit", "--force",
    "--update", "--renormalize", "--intent-to-add", "--all",
    "--ignore-removal", "--no-ignore-removal", "--refresh", "--ignore-errors",
    "--ignore-missing", "--sparse", "--pathspec-file-nul",
}


# The shared parser blanks heredoc bodies correctly (a command after
# `<<EOF ... EOF` stays its own command); a private copy did not.
_LIB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
    "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
try:
    from shellcmd import simple_commands_with_scope as _simple_commands
    from shellcmd import resolve_cd_target as _resolve_cd_target
    from shellcmd import strip_env as _strip_env
    from shellcmd import shell_c_expansions as _shell_c_expansions
except Exception as _exc:  # broken install: fail open, like every guard here
    print("flag-commit-a-sweeps-submodule: cannot load "
          f"scripts/lib/shellcmd.py ({_exc}); inert", file=sys.stderr)
    _simple_commands = None


# Environment assignments that name another repository than the cwd does.
_REDIRECT_ENV = ("GIT_DIR", "GIT_WORK_TREE")


def _redirects_git(env_tokens):
    """True if a leading `NAME=value` (or `env NAME=value`) sends git to
    another repository, as `--git-dir`/`--work-tree` would."""
    return any(t.split("=", 1)[0] in _REDIRECT_ENV for t in env_tokens)


def _git_invocation(rest):
    """(c_dirs, subcommand, args) for a `git ...` argv, or None.

    `c_dirs` is every `-C <dir>` in order (git applies them cumulatively).
    """
    if not rest or rest[0] != "git":
        return None
    c_dirs = []
    i = 1
    while i < len(rest):
        a = rest[i]
        if a == "-C" and i + 1 < len(rest):
            c_dirs.append(rest[i + 1])
            i += 2
        elif a in ("--git-dir", "--work-tree") or a.startswith(
                ("--git-dir=", "--work-tree=")):
            return None  # names another repository; go silent (docstring)
        elif a in _GIT_VALUE_GLOBAL:
            i += 2
        elif a.startswith("-"):
            i += 1  # --no-pager, -p, --exec-path[=x], ...
        else:
            return c_dirs, a, rest[i + 1:]
    return None


def _long_name(token, known):
    """The option in `known` that the long option `token` (`--dry`,
    `--author=x`) names: an exact match, else the one option it is a prefix
    of, as git resolves it. None when it matches none or several."""
    name = token.split("=", 1)[0]
    if name in known:
        return name
    matches = [k for k in known if k.startswith(name)]
    return matches[0] if len(matches) == 1 else None


def commit_sweeps_all(args):
    """M3 for `git commit`: true if `-a`/`--all` is among the options and
    the commit is not a dry run (`--dry-run`, `--short`, `--porcelain` and
    `--long` all commit nothing; checked with git 2.x). Long options may be
    abbreviated, as git allows."""
    sweeps = dry = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            break
        if a.startswith("--"):
            name = _long_name(a, _COMMIT_LONG)
            if name == "--all":
                sweeps = True
            elif name in _COMMIT_DRY_RUN:
                dry = True
            elif name in _COMMIT_VALUE_LONG and "=" not in a:
                i += 1  # value is the next token
            i += 1
            continue
        if a.startswith("-") and a != "-":
            for pos, ch in enumerate(a[1:], start=1):
                if ch == "a":
                    sweeps = True
                elif ch in _COMMIT_VALUE_SHORT:
                    if pos == len(a) - 1:
                        i += 1  # value is the next token
                    break
                elif ch in "Su":
                    break  # optional attached value (-uall): rest of cluster
            i += 1
            continue
        i += 1
    return sweeps and not dry


def add_kind(args):
    """M3 for `git add`: (kind, pathspecs), or None when nothing is staged
    beyond named paths. kind is "add -u" (`-u`/`--update`), "add -A"
    (`-A`/`--all`) or "add" (only pathspecs, which can still cover a
    submodule: `git add .`); `-n`/`--dry-run` and `--refresh` stage nothing
    (checked with git 2.x), and `--no-ignore-removal` is an alias of `-A`.
    Long options may be abbreviated. The paths `--pathspec-from-file` reads
    are not seen: with `-u`/`-A` that reads as no pathspec (the whole
    repository), and a plain `add` of them is silent."""
    names, letters, paths, dashdash = set(), "", [], False
    i = 0
    while i < len(args):
        a = args[i]
        if dashdash:
            paths.append(a)
        elif a == "--":
            dashdash = True
        elif a.startswith("--"):
            name = _long_name(a, _ADD_LONG)
            names.add(name)
            if name in _ADD_VALUE_LONG and "=" not in a:
                i += 1  # value is the next token
        elif a.startswith("-") and a != "-":
            letters += a[1:]
        else:
            paths.append(a)
        i += 1
    if (names & _STAGES_NOTHING) or "n" in letters or "N" in letters:
        return None
    if "--update" in names or "u" in letters:
        return "add -u", paths
    if "--all" in names or "--no-ignore-removal" in names or "A" in letters:
        return "add -A", paths
    return ("add", paths) if paths else None


def _move(rest, cur):
    """The directory a `cd`, `pushd` or `popd` leaves the shell in, by the
    shared resolver: None when it cannot be named (`cd -`, `popd`, `$VAR`,
    a backtick), `~` expanded. `cur` is None while the directory is unknown,
    and an unknown directory plus a relative move stays unknown."""
    target = _resolve_cd_target(rest, cur)
    if target is None or (cur is None and not os.path.isabs(target)):
        return None
    return target


_CD_WORD = re.compile(
    r"\s*(?:(?:then|do|else|elif|if|while|until|time|!)\s+)*"
    r"(?:cd|pushd|popd)(?![\w./-])")
_QUOTED = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
_SEGMENTS = re.compile(r"&&|\|\||[;\n(){}]")
_PIPE_OR_JOB = re.compile(r"([|&])")


def _unreachable_cd(command):
    """True if a `cd`, `pushd` or `popd` in `command` runs in a subshell of
    its own, so its directory never reaches the commands after it: a stage of
    a pipeline (`cd /x | cat`, which bash forks) or a backgrounded one
    (`cd /x &`). Read from the text with the quoted strings blanked; any such
    form makes the hook ignore EVERY directory change in the command, which
    checks the session directory instead (the warn side)."""
    text = _QUOTED.sub(" ", command)
    text = re.sub(r"[0-9]*[<>]&[0-9-]*|&>>?", " ", text)  # 2>&1, &>f
    for segment in _SEGMENTS.split(text):
        parts = _PIPE_OR_JOB.split(segment)  # piece, op, piece, ...
        stages = parts[0::2]
        ops = parts[1::2]
        for pos, piece in enumerate(stages):
            if not _CD_WORD.match(piece):
                continue
            if "|" in ops:
                return True
            if pos < len(ops) and ops[pos] == "&":
                return True
    return False


def _env_chdir(argv):
    """True for `env -C dir ...` / `env --chdir=dir ...`, which the shared
    parser peels like any lead word although it changes the directory."""
    if os.path.basename(argv[0]) != "env":
        return False
    for a in argv[1:]:
        if a.startswith("--chdir") or a.startswith("-C"):
            return True
        if not a.startswith("-") and "=" not in a:
            break
    return False


def _scan(command, start):
    """[(segment, kind, target_dir, pathspecs), ...] for every
    matching invocation in the one command line `command`, in order, and
    whether it changes directory at all. `start` is the directory the line
    starts in (relative to the session cwd; "" is the session cwd itself, None
    is unknown). `target_dir` is the directory git would run in; an
    invocation whose directory is unknown is left out."""
    cmds = _simple_commands(command)
    if cmds is None:
        return [], False
    ignore_cd = _unreachable_cd(command)
    # Directory per subshell scope: a subshell starts from its parent's
    # directory and a `cd` inside it never reaches the parent. A directory is
    # None once a `cd` goes somewhere the text does not name.
    cds = {(0,): start}

    def cd_of(scope):
        while scope not in cds:
            scope = scope[:-1]
        return cds[scope]

    hits, moved = [], False
    for scope, argv in cmds:
        if _env_chdir(argv):
            continue  # `env -C dir git ...` runs elsewhere; go silent
        env, rest = _strip_env(argv)
        cd = cd_of(scope)
        if rest and rest[0] in ("cd", "pushd", "popd"):
            moved = True
            if not ignore_cd:
                cds[scope] = _move(rest, cd)
            continue
        inv = _git_invocation(rest)
        if inv is None or _redirects_git(env):
            continue
        c_dirs, sub, args = inv
        target = cd
        for d in c_dirs:  # `-C` moves like `cd`, `~` and `$HOME` included
            target = _move(["cd", "--", d], target)
        if target is None:
            continue
        segment = " ".join(argv)
        if sub == "commit" and commit_sweeps_all(args):
            hits.append((segment, "commit -a", target, None))
        elif sub == "add":
            found = add_kind(args)
            if found:
                hits.append((segment, found[0], target, found[1]))
    return hits, moved


def offending(command):
    """[(segment, kind, target_dir, pathspecs), ...] for every
    matching invocation in `command`, including the command lines of nested
    `bash -c '...'` shells, in order.

    A nested line starts in the session directory when no OTHER line of the
    command (the outer text, or another nested line) changes directory, else
    in an unknown one, because the text does not tie that `cd` to this shell
    (`bash -c "cd r && bash -c 'git commit -am x'"`, or a `cd` after the
    `bash -c`). Only an absolute `git -C /path` or `cd /path` is read there."""
    if _simple_commands is None:
        return []
    pieces = _shell_c_expansions(command)
    scans = [_scan(piece, "") for piece in pieces]
    hits = list(scans[0][0])
    for i, piece in enumerate(pieces[1:], start=1):
        # Another line's `cd` may have moved the shell this one runs in.
        others_move = any(m for j, (_, m) in enumerate(scans) if j != i)
        hits += _scan(piece, None)[0] if others_move else scans[i][0]
    return hits


# hooks.json gives this hook 10 s. Every git call shares one deadline inside
# that, so a slow repository fails open here rather than being killed by the
# harness. FLAG_COMMIT_A_BUDGET_S overrides the total (the tests use 0).
_DEFAULT_BUDGET_S = 8.0
_PER_CALL_S = 5.0
_deadline = None


def _start_budget():
    global _deadline
    try:
        budget = float(os.environ.get("FLAG_COMMIT_A_BUDGET_S", ""))
    except ValueError:
        budget = _DEFAULT_BUDGET_S
    _deadline = time.monotonic() + budget


def _git(cwd, *args):
    """stdout of `git args` in cwd, or None on any failure or when the
    shared deadline is spent. Optional locks are off so a read-only status
    never rewrites the index under a concurrent git."""
    if _deadline is None:
        return None  # main() starts the budget; no budget, no git call
    remaining = _deadline - time.monotonic()
    if remaining <= 0:
        return None
    try:
        out = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", *args], cwd=cwd,
            capture_output=True,
            timeout=min(_PER_CALL_S, remaining),
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    # A tracked file name need not be UTF-8 (`ls-files -z` and `status -z`
    # emit it raw): surrogateescape keeps it round-trippable instead of
    # raising UnicodeDecodeError out of the hook.
    return out.stdout.decode("utf-8", "surrogateescape")


def modified_submodules(cwd):
    """(found, toplevel) where found lists (path, pinned_sha, head_sha) for
    each submodule whose gitlink would change if every modified tracked path
    were staged; None if git cannot be run here."""
    # `-uno` skips the untracked scan, which `-a`/`-u` never stage anyway and
    # which dominates the time in a large tree. No `--ignore-submodules`
    # override: it would also override `submodule.<name>.ignore=all` and
    # `diff.ignoreSubmodules=all`, which make `commit -a` and `add -u` leave
    # the gitlink alone (checked with git 2.43), so the configured values must
    # decide. A submodule with only dirty content is reported as ` M` too;
    # the HEAD-versus-pin comparison below tells the two apart.
    status = _git(cwd, "status", "--porcelain=v1", "-z", "-uno")
    top = _git(cwd, "rev-parse", "--show-toplevel")
    # ONE index read for every gitlink, rather than a query per modified path:
    # a large sweep would otherwise spend the whole deadline and fail open
    # exactly when the sweep is big.
    # Run from the root: from a subdirectory it would list only that subtree,
    # with paths relative to it, while status paths are root-relative.
    if status is None or top is None:
        return None
    top = top.strip()
    index = _git(top, "ls-files", "-s", "-z")
    if index is None:
        return None
    gitlinks = {}
    for entry in index.split("\0"):
        meta, _, entry_path = entry.partition("\t")
        fields = meta.split()
        if len(fields) == 3 and fields[0] == "160000":
            gitlinks[entry_path] = fields[1]
    records = status.split("\0")
    found = []
    i = 0
    while i < len(records):
        rec = records[i]
        i += 1
        if len(rec) < 4:
            continue
        xy, path = rec[:2], rec[3:]
        if xy[0] in ("R", "C"):
            i += 1
        if xy[1] != "M":
            continue
        pinned = gitlinks.get(path)  # only a gitlink (mode 160000) counts
        if pinned is None:
            continue
        head = _git(os.path.join(top, path), "rev-parse", "HEAD")
        if head is None:
            continue
        head = head.strip()
        if head != pinned:
            found.append((path, pinned, head))
    return found, top


# Pathspec magic the hook evaluates: `:!x` and `:^x` (exclude), `:/x` (from
# the repository root) and `:(exclude,top,icase,literal)x`. Any other magic
# (`attr`, `glob`, `from-file`, ...) is not evaluated.
_SHORT_MAGIC = re.compile(r"^:([!^/]+):?(.*)$", re.S)
_LONG_MAGIC = re.compile(r"^:\(([^)]*)\)(.*)$", re.S)
_EVALUATED = {"exclude", "top", "icase", "literal"}
_GLOB = "*?["


def _parse_pathspec(p):
    """(exclude, top, icase, literal, body), or None for a pathspec carrying
    magic the hook does not evaluate. A plain path is (False, False, False,
    False, p)."""
    if not p.startswith(":"):
        return False, False, False, False, p
    short = _SHORT_MAGIC.match(p)
    if short:
        flags, body = short.groups()
        return ("!" in flags or "^" in flags), "/" in flags, False, False, body
    long_form = _LONG_MAGIC.match(p)
    if long_form:
        words = {w for w in long_form.group(1).split(",") if w}
        if words <= _EVALUATED:
            return ("exclude" in words, "top" in words, "icase" in words,
                    "literal" in words, long_form.group(2))
    return None


def _rel(spec, real_cwd, real_top):
    """The pathspec's path relative to the repository root, lowercased for
    `icase`."""
    _, top, icase, _, body = spec
    if top:
        rel = os.path.normpath(body or ".")
    else:
        if os.name == "nt":
            body = body.replace("\\", "/")  # Windows separators only
        rel = os.path.relpath(os.path.normpath(os.path.join(real_cwd, body)),
                              real_top)
        if os.name == "nt":
            rel = rel.replace("\\", "/")
    return rel.lower() if icase else rel


def _has_glob(spec, rel):
    return not spec[3] and any(ch in rel for ch in _GLOB)


def _matches(spec, rel, sub_path):
    """Does the pathspec (path `rel`) match the submodule at `sub_path` as
    that path or a directory above it? A glob is matched with fnmatch, which
    approximates git's."""
    sub = sub_path.lower() if spec[2] else sub_path
    if _has_glob(spec, rel):
        prefixes = [sub[:i] for i, ch in enumerate(sub) if ch == "/"] + [sub]
        return any(fnmatch.fnmatchcase(x, rel) for x in prefixes)
    return rel == "." or sub == rel or sub.startswith(rel + "/")


def _under_pathspecs(sub_path, pathspecs, cwd, top, sweeping):
    """M7: does a pathspec given from `cwd` stage the submodule at `sub_path`
    (repo-root relative, `top` the repo root)?

    An exclude pathspec (`:!x`, `:^x`, `:(exclude)x`) that matches the
    submodule keeps it out whatever else is given (checked with git 2.43:
    `git add -u mod ':!mod'` stages nothing). Pathspecs that are all excludes
    mean everything else.

    `sweeping` is `add -u`/`-A`: no pathspec means the whole repo, a pathspec
    naming the submodule itself counts, and magic the hook does not evaluate,
    a glob include, or `--pathspec-from-file` warns. A plain `git add
    <pathspec>` counts only a pathspec that covers the submodule from above
    (`.`, a parent directory, `:/`): naming the submodule is how a pin bump is
    staged on purpose, and unevaluated magic or a glob include there stays
    silent. Both sides go through realpath, so a symlinked cwd cannot make
    the relative path miss."""
    if not pathspecs:
        return sweeping
    real_cwd, real_top = os.path.realpath(cwd), os.path.realpath(top)
    parsed = [_parse_pathspec(p) for p in pathspecs]
    for spec in parsed:
        if spec and spec[0] and _matches(
                spec, _rel(spec, real_cwd, real_top), sub_path):
            return False
    includes = [s for s in parsed if not (s and s[0])]
    if not includes:
        return True  # only excludes: git takes `.` as the include
    for spec in includes:
        rel = None if spec is None else _rel(spec, real_cwd, real_top)
        if spec is None or _has_glob(spec, rel):
            if sweeping:
                return True
            continue
        if _matches(spec, rel, sub_path) and (sweeping or rel != sub_path):
            return True
    return False


# What each kind stages, for the message.
_STAGES = {
    "commit -a": "every modified tracked path",
    "add -u": "every modified tracked path",
    "add -A": "every change",
    "add": "every change",
}

NOTE = (
    "This `git {kind}` stages {stages}{scope}, and {count} "
    "submodule(s) here sit at a different commit than the index pins, so "
    "{which} commit would MOVE the pin(s):\n\n"
    "  command:  {segment}\n"
    "  submodule (pinned -> checked out):\n{lines}\n\n"
    "On 2026-10-15 `git commit -am` did exactly this in Morrison-Lab/lds#1026: "
    "it carried a `CLAUDE.md` edit and moved `latex-macros` from 6e227b6 to an "
    "older 85c285b, and the PR bot flagged it as blocking.\n\n"
    "If the pin bump is intended, carry on. Otherwise stage only what you "
    "mean (`git add <paths>`), commit with paths (`git commit -- <paths>`), "
    "or check the submodule out at the pinned commit first "
    "(`git submodule update <path>`, after checking that the submodule's "
    "own commits are pushed or on a branch: the update detaches HEAD and "
    "can leave unpushed commits reachable only through the reflog)."
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
        print(f"flag-commit-a-sweeps-submodule: unreadable hook input ({exc})",
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

    if payload.get("tool_name") not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        return quiet()

    inp = payload.get("tool_input")
    inp = inp if isinstance(inp, dict) else {}
    command = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script")
    if not isinstance(command, str) or not command.strip():
        return quiet()

    try:
        hits = offending(command)
    except Exception as exc:  # fail open on any parse trouble
        print(f"flag-commit-a-sweeps-submodule: could not parse command ({exc})",
              file=sys.stderr)
        return 0

    # Every match is checked: one that is filtered out (a pathspec that
    # excludes the submodule, a missing directory) must not hide a later one.
    # The directory the command runs from is the payload's, not this
    # process's: tool_input.Cwd, then the payload's `cwd`, then ours.
    base = next((c for c in (inp.get("Cwd"), payload.get("cwd"))
                 if isinstance(c, str) and c), None) or os.getcwd()
    state = {}  # cwd -> modified_submodules(cwd), one status per repository
    for segment, kind, target, pathspecs in hits:
        cwd = os.path.normpath(os.path.join(base, target))
        if not os.path.isdir(cwd):
            continue
        if cwd not in state:
            state[cwd] = modified_submodules(cwd)
        if not state[cwd]:
            continue
        subs, top = state[cwd]
        if pathspecs is not None:
            subs = [s for s in subs
                    if _under_pathspecs(s[0], pathspecs, cwd, top,
                                        kind != "add")]
        if subs:
            return warn(segment, kind, pathspecs, subs)
    return quiet()


def warn(segment, kind, pathspecs, subs):
    """Print the warning for `subs` and return the exit status."""
    lines = "\n".join(f"    {p}: {a[:7]} -> {b[:7]}" for p, a, b in subs)
    # Only `commit -a` commits what it stages; the `add` forms leave the pin
    # moved for the NEXT commit.
    which = "this" if kind == "commit -a" else "the next"
    scope = f" under {', '.join(pathspecs)}" if pathspecs else ""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(
                kind=kind, stages=_STAGES[kind], scope=scope,
                count=len(subs), segment=segment, lines=lines,
                which=which),
        },
        "systemMessage": (
            f"`git {kind}` would stage a moved pin, so {which} commit "
            f"would move it"
            + f" ({len(subs)} submodule(s)): "
            + ", ".join(p for p, _, _ in subs) + "."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
