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
  M3'' for `git checkout` carrying `-f`/`--force` and NO pathspec: the whole
      tracked working tree is in scope, the same as `reset --hard` (see
      "Forced switches" below)
  M4  `git status --porcelain`, scoped to the whole tree for `reset --hard`
      or to the resolved pathspecs for `checkout`/`restore`, reports at
      least one entry that is NOT untracked (`??`) -- i.e. at least one
      tracked file in scope has a staged or unstaged change relative to
      HEAD, which the command will discard
  M5  a command line nested in a shell's `-c` argument is matched too, via
      `scripts/lib/shellcmd.py`'s `shell_c_expansions`. A nested piece
      contributes only the kinds decided LEXICALLY -- `reset-hard` and
      `checkout-force`, which discard the whole tracked tree wherever they
      run. A `checkout`/`restore` pathspec is not one of them: classifying a
      bare word as a pathspec runs `git rev-parse` in this hook's own
      directory, and for a nested piece that is the wrong repository
      (ai-config#1973 review). A piece that can act only on THIS repository
      takes the ordinary local reading -- M4's status gate included -- rather
      than the unscoped note. That is a wider question than "contains no
      `cd`", which is about the shell's directory: `GIT_DIR=` redirects the
      repository without moving the shell, and `eval` moves the shell without
      a `cd` token. `_may_change_repository` decides it

## Ref-vs-path disambiguation

`git checkout <arg>` is ambiguous on its face: `<arg>` may be a ref (branch,
tag, SHA, `HEAD`, `-` for "previous branch") -- an UNFORCED switch, which git
refuses when it would clobber local changes and otherwise carries them
across -- or a pathspec, which this hook exists to catch. Mirroring git's
own tie-break (a name that is both a ref and a path resolves as the REF) is
the reliable way to tell them apart, so each bare positional argument is
tested with
`git rev-parse --quiet --verify <arg>^{commit}`; only an argument that
demonstrably does NOT resolve as a commit-ish counts as a pathspec.
A `--` separator sidesteps the question entirely -- everything after it is
unambiguously a pathspec, per `git checkout`'s own syntax (`git checkout
[<ref>] [--] <pathspec>...`). `git restore`'s positional operands are always
pathspecs (its ref comes from `-s`/`--source`, never positionally), so no
resolution is needed there.

## Forced switches

`-f`/`--force` removes the refusal that makes an unforced switch safe, and
nothing else about the command announces it. Measured 2026-09-04 on git
2.43.0, over a tree carrying ` M f.txt` and ` M g.txt`: `git checkout other`
left both edits in place, while `git checkout -f other`,
`git checkout --force -b feature`, and `git checkout -f` with no operand at
all each exited 0 with both edits gone. A forced `checkout` that resolves
to no pathspec is scoped to the whole tracked tree, exactly like
`reset --hard`.

`git switch -f`/`--discard-changes` does the same thing and is NOT matched:
`switch` is a fourth command this hook does not read at all, and reading it
would widen the guard past the three it was built for. That gap is named in
the catalogs. (`git switch -f` with no branch operand is a fatal error, so
the gap is the ref-carrying form only.)

Untracked files are deliberately out of scope for all three commands: none
of `reset --hard`, `checkout <path>`, or `restore <path>` can discard a file
git is not already tracking (that is `git clean`'s job), so an untracked
scratch file sitting in the tree is not itself at risk.

The flag lists below are a best-effort read of `git checkout`/`git
restore`'s documented options, not an exhaustive reimplementation of git's
argument parser. An unrecognized `-`-prefixed token is skipped rather than
risking a false pathspec read from its value -- and when that token is a
short cluster ENDING in a value-taking short option (`-qb`, not `-bfixup`),
the value is a SEPARATE next token, which is skipped along with it, rather
than being left to fall through and get misread as a pathspec itself.

Fails OPEN on any parse trouble, on `git status`/`git rev-parse` failing or
timing out, and outside a git repository.
"""
import json
import os
import re
import shlex
import subprocess
import sys

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import shell_c_expansions
except Exception as _exc:  # broken install: degrade to the outer command only
    print(f"flag-reset-hard-uncommitted-work: cannot load "
          f"scripts/lib/shellcmd.py ({_exc}); a discard wrapped in an "
          f"interpreter's -c will not be seen", file=sys.stderr)
    shell_c_expansions = None

RX_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?\n[ \t]*\2\b", re.S)

ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
SHORT_CLUSTER = re.compile(r"-[A-Za-z]+")
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
CHECKOUT_VALUE_SHORTS = "bBt"
RESTORE_VALUE_SHORTS = "s"


def _cluster_forces(tok, value_shorts):
    """Whether short cluster `tok` carries `-f`. A value-taking short option
    swallows the rest of the cluster as its value, so only an `f` before the
    first such letter is `--force` rather than part of that option's value."""
    if not SHORT_CLUSTER.fullmatch(tok):
        return False
    cluster = tok[1:]
    stop = next((i for i, c in enumerate(cluster) if c in value_shorts),
                len(cluster))
    return "f" in cluster[:stop]


def _cluster_value_consumes_next(tok, value_shorts):
    """Whether short cluster `tok` ends in a value-taking short option with
    NO value attached in the same token -- e.g. `-b` in `-qb`, but not the
    `b` in `-bfixup`, where `fixup` is already `-b`'s attached value. When it
    does, that option's value is a SEPARATE next token (`git checkout -qb
    mybranch`), and the caller must skip that token too, or it falls through
    and gets misread as a positional pathspec."""
    if not SHORT_CLUSTER.fullmatch(tok):
        return False
    cluster = tok[1:]
    idx = next((i for i, c in enumerate(cluster) if c in value_shorts), None)
    return idx is not None and idx == len(cluster) - 1


def _checkout_restore_targets(subcommand, args):
    """Positional targets of a `checkout`/`restore` invocation's ARGS (the
    tokens after `git checkout`/`git restore`).

    Returns (pre, post, saw_sep, staged_no_worktree, saw_force). `pre` is
    every non-flag token before a `--` separator (or all of them, if none);
    `post` is every token after one. `staged_no_worktree` (restore only) is
    whether `--staged` appeared without `--worktree` -- that combination
    only rewrites the index, so it carries no risk to the working tree.
    `saw_force` is whether `--force`, or a short cluster whose `f` precedes
    the first value-taking short option in it, if any, appeared before any `--`.

    A short cluster that ENDS in a value-taking short option (`-b`/`-B`/`-t`
    for `checkout`, `-s` for `restore`) with nothing attached after it in the
    same token takes the NEXT token as that option's value, exactly as the
    bare flag would (`-b` in `CHECKOUT_VALUE_FLAGS`) -- so that next token is
    skipped too, whether or not the cluster also carries `-f` (`-fb branch`,
    `-qb branch`). A value-taking short that is NOT last in the cluster has
    its value already attached in the same token (`-bfixup`) and consumes no
    further token.
    """
    value_flags = (CHECKOUT_VALUE_FLAGS if subcommand == "checkout"
                   else RESTORE_VALUE_FLAGS)
    value_shorts = (CHECKOUT_VALUE_SHORTS if subcommand == "checkout"
                    else RESTORE_VALUE_SHORTS)
    pre, post = [], []
    saw_sep = saw_staged = saw_worktree = saw_force = False
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
        if tok == "--force" or _cluster_forces(tok, value_shorts):
            saw_force = True
            # A cluster like `-fb` or `-fB` still ends in a value-taking
            # short (`b`/`B`), whose value is the NEXT token -- skip that
            # too, or it falls through and gets misread as a pathspec.
            i += 2 if _cluster_value_consumes_next(tok, value_shorts) else 1
            continue
        if tok in CHECKOUT_RESTORE_BOOL_FLAGS:
            i += 1
            continue
        if tok in value_flags:
            i += 2
            continue
        if tok.startswith("-") and tok != "-":
            # An unrecognized flag -- see the module docstring. A short
            # cluster ending in a value-taking short (`-qb`) still takes the
            # NEXT token as that option's value; skip it too.
            i += 2 if _cluster_value_consumes_next(tok, value_shorts) else 1
            continue
        pre.append(tok)
        i += 1
    staged_no_worktree = (subcommand == "restore" and saw_staged
                           and not saw_worktree)
    return pre, post, saw_sep, staged_no_worktree, saw_force


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


def _lead_index(argv):
    """Index of ARGV's first real word, past env assignments and lead words.

    `_simple_commands` splits on operators only, so a body's keyword arrives
    attached to the command it heads: `if [ -d w ]; then cd w; git push; fi`
    yields the argv `["then", "cd", "w"]`. Both callers have to look past that
    prefix before the command word means anything -- `offending_here` to find
    the `git`, and `_may_change_repository` to find a `cd`.

    One function rather than the same `while` loop written twice, which is
    what it was until the second caller arrived (ai-config#3645 review round
    3).
    """
    i = 0
    while i < len(argv) and (ASSIGNMENT.match(argv[i])
                             or argv[i] in LEAD_WORDS):
        i += 1
    return i


def offending_here(command, lexical_only=False):
    """The matched destructive-discard invocation in `command`, or None.

    Returns (kind, segment, paths). `kind` is "reset-hard" or
    "checkout-force" (paths is None -- the whole tracked tree is in scope)
    or "checkout"/"restore" (paths is the resolved pathspec list that
    invocation would revert).

    `lexical_only` restricts the answer to the two kinds the TEXT decides on
    its own, and is what a NESTED piece gets. Without it this function reaches
    `_looks_like_path` -> `_resolves_as_ref`, which runs `git rev-parse` in the
    hook's own directory: `sh -c "cd OTHER && git checkout notes.txt"` then
    warns or stays silent according to whether THIS repository happens to
    carry a ref called `notes.txt`, which is a fact about the wrong repository
    (ai-config#1973 review, round 4 finding 3). Relabelling the result
    afterwards did not help, because the resolution had already happened.
    """
    cmds = _simple_commands(command)
    if cmds is None:
        return None
    for argv in cmds:
        rest = argv[_lead_index(argv):]
        if len(rest) < 2 or rest[0] != "git":
            continue
        sub = rest[1]
        if sub == "reset":
            if "--hard" not in rest[2:]:
                continue
            return "reset-hard", " ".join(argv), None
        if sub not in ("checkout", "restore"):
            continue
        (pre, post, saw_sep, staged_no_worktree,
         saw_force) = _checkout_restore_targets(sub, rest[2:])
        if lexical_only:
            # `--force` is decided by the flag alone, so it survives here.
            # Everything below this point needs a repository to resolve a
            # pathspec against, and a nested piece does not have one.
            if sub == "checkout" and saw_force and not staged_no_worktree:
                return "checkout-force", " ".join(argv), None
            continue
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
            if sub == "checkout" and saw_force:
                return "checkout-force", " ".join(argv), None
            continue
        return sub, " ".join(argv), paths
    return None


_CD_WORDS = ("cd", "pushd", "popd")

# Words that move the shell, and tokens that move the REPOSITORY without
# moving the shell. The second group is why this is not a `cd` scan: the
# question a caller asks is which repository the command acts on, and a
# `cd` is only one of the ways that stops being the shell's own directory.
# `no-clobbering-push.py` names the same spellings as `GIT_REPO_OPTS` and
# `GIT_ENV_REDIRECT`; they are restated rather than imported because that
# guard is not importable from here. `GIT_COMMON_DIR=` is the one addition
# over that pair's union, and it redirects the same way.
_REPO_REDIRECT_ENV = ("GIT_DIR=", "GIT_WORK_TREE=", "GIT_COMMON_DIR=")
_REPO_REDIRECT_OPTS = ("--git-dir", "--work-tree")
# `eval` builds its command at run time, so nothing lexical can say where it
# leaves the shell. `source` (and its `.` spelling) runs another file's `cd`s
# in this shell.
_OPAQUE_WORDS = ("eval", "source", ".")


def _may_change_repository(text):
    """True when TEXT might act on a repository other than this directory's.

    NOT a `cd` scan, although a `cd` is the obvious case. The premise "a piece
    containing no `cd` provably starts where the outer command did" is true
    about the SHELL'S DIRECTORY and does not support the conclusion drawn from
    it about the REPOSITORY: `GIT_DIR=/other/.git git reset --hard` never
    moves the shell and discards another repository's work, and
    `eval 'cd /other'` moves the shell with no `cd` token in sight -- the
    token is the whole string, whose basename is `other`. Both took the local
    reading and listed THIS repository's dirty files as what would be lost,
    which is the cross-repository report `NOTE_NESTED_UNSCOPED` exists to
    prevent and calls "worse than silence" (ai-config#3645 pre-merge gate,
    finding 2).

    Deliberately over-reports, and in two ways worth naming so neither reads
    as a bug. A bare `-C` counts although `grep -C 3` is not a git option, and
    unparseable text counts as redirecting. Both cost only the file list.

    What is deliberately NOT over-reported is a `cd`, `eval`, `source` or `.`
    sitting anywhere other than the command word. Those four are only those
    commands when they are being RUN, and reading them positionally made a
    bare `.` path argument -- `git add .` -- look like a `source`.

    The unparseable branch is DEFENSIVE and no case reaches it: `offending`
    calls this only after `shell_c_expansions` has parsed the same text, and
    the two parsers were measured to fail together on every shape tried
    (2026-09-14). It stays because dropping it turns a `None` into a
    `TypeError` that would take the whole guard down.
    """
    cmds = _simple_commands(text)
    if cmds is None:
        return True
    for argv in cmds:
        # A WORD is only `cd` or `source` when it is the command being run.
        # Scanning every token instead matched a bare `.` as the POSIX
        # spelling of `source`, so `sh -c "git add . ; git reset --hard"` --
        # one of the commonest shapes there is -- lost the local reading this
        # shortcut exists to give it, and the docstring's list of accepted
        # over-detections did not name it (ai-config#3645 review round 2).
        #
        # The prefix comes off first, because a body's keyword arrives
        # attached: `then cd /other` splits with `then` at the head, and
        # testing `argv[0]` alone would read that piece as stationary.
        lead = _lead_index(argv)
        if lead < len(argv):
            word = os.path.basename(argv[lead])
            if word in _CD_WORDS or word in _OPAQUE_WORDS:
                return True
        # The REDIRECTION spellings are options and assignments rather than
        # command words, so they really can sit anywhere in an argv -- and
        # `nested_git_dir_option_case` pins one in a sibling command.
        for token in argv:
            if token.startswith(_REPO_REDIRECT_ENV):
                return True
            if token.startswith(_REPO_REDIRECT_OPTS):
                return True
            # `git -C <dir>` reads and writes that directory's repository.
            if token == "-C":
                return True
    return False


def offending(command):
    """`offending_here` over COMMAND and every shell `-c` nested command line.

    This hook compares exact tokens, so an interpreter wrapper bypassed it
    outright: `shlex` collapses the embedded command into ONE opaque token,
    `argv[0]` is the interpreter, and `rest[0] != "git"` rejects it before any
    subcommand is read.

    Measured 2026-09-14 against a deliberately DIRTY tree, which is what the
    check needs -- this hook fires on uncommitted work, so a clean checkout
    makes the bare form silent too and the probe says nothing either way
    (ai-config#1973 records an earlier inconclusive one):

        git reset --hard origin/main            -> warns
        sh -c "git reset --hard origin/main"    -> SILENT
        bash -c "git reset --hard origin/main"  -> SILENT

    Each piece is analysed separately rather than merged, per
    `shell_c_expansions`' own contract: a nested `-c` argument is a different
    shell. Nothing here models shell state, so the separation costs nothing and
    keeps this call site identical in shape to its sibling guards'.

    First hit wins, matching `offending_here`, which returns on the first
    destructive invocation it finds rather than collecting them.
    """
    pieces = [command]
    if shell_c_expansions is not None:
        try:
            pieces = shell_c_expansions(command)
        except Exception as exc:  # never let the descent break the base check
            print(f"flag-reset-hard-uncommitted-work: could not expand nested "
                  f"shells ({exc}); checking the outer command only",
                  file=sys.stderr)
            pieces = [command]
    # A nested piece is answerable only on what the TEXT decides.
    #
    # The comment here used to claim `offending_here` "resolves nothing against
    # a directory". That is false: `_looks_like_path` calls `_resolves_as_ref`,
    # which runs `git rev-parse --verify <arg>^{commit}` in the hook's OWN
    # directory, so whether a `git checkout <word>` reads as a pathspec or as a
    # branch depends on which repository is asked. For a nested piece that
    # repository is the wrong one -- `sh -c "cd OTHER && git checkout
    # feature-x"` reported discarding a tracked file named `feature-x` in THIS
    # repo, for a command that switches branches in the other and discards
    # nothing (ai-config#1973 review, round 2 finding 2).
    #
    # That is the same defect the sibling guard's `deny_only` exists to
    # prevent, and this hook asserted its negation in one sentence while the
    # sibling argued the correct premise at length -- in the same commit.
    #
    # So a nested piece contributes only the kinds decided lexically:
    # `reset-hard` and `checkout-force` discard the whole tracked tree wherever
    # they run, and carry no resolved pathspec. `checkout`/`restore` with a
    # pathspec list do, and are skipped for nested pieces.
    match = offending_here(command)
    if match is not None:
        return match
    for piece in pieces[1:]:
        match = offending_here(piece, lexical_only=True)
        if match is None:
            continue
        # NESTED_UNSCOPED, not the matched kind. The `paths is None` filter
        # this replaces narrowed the classification and left the REPORT alone,
        # and the report is what was wrong: `_tracked_changes` runs
        # `git status` in the hook's own directory whatever piece matched, so
        # `sh -c "cd OTHER && git reset --hard"` listed THIS repo's dirty files
        # as what the command would discard. The classification is
        # directory-dependent too -- `_looks_like_path` resolves a bare word
        # with `git rev-parse` here -- so filtering on its result could not
        # have fixed it either (ai-config#1973 review, round 3, findings 4
        # and 5).
        #
        # A nested piece is worth flagging and not worth enumerating. The
        # caller emits a warning that names the construct and says which
        # repository it cannot see, with no file list.
        #
        # UNLESS the piece provably stays put. The note's own text blames
        # `cd`s the outer shell might have run -- so when neither the outer
        # command nor the piece contains one, that reason does not hold and
        # the guard is entitled to the ordinary local reading, status gate and
        # file list included. Returning `nested-unscoped` regardless made
        # `sh -c "git reset --hard"` warn over a CLEAN tree where the bare
        # form is silent, because the unscoped path returns before the M4
        # status gate runs (ai-config#1973 review, round 4 finding 7,
        # reproduced independently by the @claude review of #3645).
        if (not _may_change_repository(command)
                and not _may_change_repository(piece)):
            return match
        return "nested-unscoped", match[1], None
    return None


NOTE_NESTED_UNSCOPED = """\
A destructive discard is wrapped in a shell's `-c` argument:

    {segment}

This guard cannot list what would be lost. Which repository that nested shell
starts in depends on `cd`s the outer shell runs first, and reading the working
tree from here would name THIS repository's files for a command acting on
another one -- which is worse than silence, because it names a cause and
prescribes a fix.

Before running it, check the target repository yourself:

    git -C <target> status --porcelain

Running the discard in its own Bash call, unwrapped, lets this guard answer
properly."""


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

NOTE_FORCED_SWITCH = (
    "This forced `git checkout` will discard {count} tracked file(s) with "
    "uncommitted changes -- staged or unstaged -- that have nothing "
    "necessarily to do with why this is being run:\n\n"
    "  command:  {segment}\n"
    "  would be discarded:\n{files}\n\n"
    "`-f`/`--force` removes the refusal that makes a plain `git checkout "
    "<ref>` safe: an unforced switch either refuses or carries local "
    "changes across, while a forced one resets every tracked file to the "
    "target and reports only `Switched to branch ...` at exit 0. With no "
    "ref at all (`git checkout -f`), the whole tracked tree is reverted to "
    "HEAD with no output whatsoever.\n\n"
    "If these changes are not meant to be discarded, commit or "
    "`git stash -u` them first.\n\n"
    "`git switch -f` / `--discard-changes` does the same thing and this "
    "hook does not read `git switch` at all -- check that form by hand."
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

    if kind == "nested-unscoped":
        # A destructive discard inside a nested shell. No file list, because
        # this hook cannot know which repository that shell starts in: the
        # answer depends on `cd`s the outer shell ran, and reading `git status`
        # here named THIS repo's dirty files for a command acting on another
        # (ai-config#1973 review, round 3). Naming the construct is what it can
        # honestly do.
        note = NOTE_NESTED_UNSCOPED.format(segment=segment)
        summary = ("A destructive discard is wrapped in a nested shell; this "
                   "guard cannot see which repository it runs in.")
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": note}}))
        print(summary, file=sys.stderr)
        return 0

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
    elif kind == "checkout-force":
        note = NOTE_FORCED_SWITCH.format(
            count=len(changed), segment=segment, files=files)
        summary = (f"Forced `git checkout` will discard {len(changed)} "
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
