#!/usr/bin/env python3
"""PreToolUse guard: refuse history reads that a shallow clone answers wrongly.

## The incident

On 2026-11-11 a thread was asked what the 44 working branches of
Morrison-Lab/lds were for. Cloud sessions clone with `--depth`, so the checkout
was shallow, and the session never checked. It then ran:

    git log --reverse --format='%cs %s' origin/main | head -1
    git merge-base origin/main origin/claude/clustering-definition
    git rev-list --count origin/main..origin/<branch>

In a shallow clone each of those answers from the truncated history.
`git log --reverse` called a 2026-11-04 commit main's first. Main actually
begins on 2026-09-04. `git merge-base` found no common ancestor.
`rev-list --count` called whole histories "ahead".
The report told Ezra that 23 branches shared no history with main.
It recommended deleting 41 branches, 12 of which hold commits that are on no
other branch and never had a PR. Ezra said "pause" seconds before the
deletion ran, then: "that was almost a huge mistake" and "make sure that can
never happen again" (ai-config#5323).

## Why a deny, not a warning

The failure is silent: every command above exits 0 and prints a plausible
answer, so nothing downstream can notice. A warning is context that a session
reads past (ai-config#4741). The guard refuses.

## Checking a walk instead of refusing every range

A shallow clone is not wrong about everything. `git log origin/main..HEAD` is
right when HEAD's new commits sit on top of the fetched main, and routine
skills run it in every cloud session. So for a comparison of two commits A
and B (`A..B`, `A...B`, `^A B`, `B --not A`, `merge-base A B`), the guard
reads the fetched graph (`git rev-list --timestamp --parents A B`) and, in
each direction, refuses when:

1. the commits one side has and the other lacks include a cut-off commit
   (from the repository's `shallow` file): that side ran out of history; or
2. the excluded side reaches a cut-off commit, and the commits listed as
   "only on the other side" include one no newer than that cut-off, or a
   parentless one. Such a commit may sit below the cut-off in the full
   history, where the excluded side would have reached it. This is how a
   branch fetched in full after a shallow clone of main makes main's old
   commits look "ahead" (review of ai-config#5323).

Nothing local can see an edge the clone never fetched, so rule 2 judges by
committer date. It is sound unless committer clocks were skewed so that a
commit is older than one of its ancestors. It refuses on a tie, and it
refuses whenever the query fails, times out, or the range names more than
two commits. It also refuses some answers that happen to be right; that is
the conservative direction.

## Checking a walk with no range

A log, rev-list or shortlog with no range lists commits newest first until
its limit. Only a cut-off commit has hidden parents, so no hidden commit can
be listed before a cut-off commit is. The guard lists the same walk with
`git rev-list --max-count=N` and refuses when a cut-off commit appears
anywhere but last place of a full N: from there on, the clone lists fewer or
different commits than the full history would. With no limit, any cut-off
commit refuses. This rule does not depend on dates.

The limit is `-N`, `-n N` or `--max-count=N`, or a pipe straight to
`head [-n] N` when the read is newest first (not `--reverse`, `--count` or
shortlog, where head sees a summary of the whole walk). Any option other
than display options and `--first-parent`, and any path, can make git read
past the limit (`--author`, `--no-merges`, `--skip`, `--topo-order`,
`-- file`), so then the whole walk is checked. This refuses `git log -5`
in a depth-1 clone, where it prints one commit and calls it five.

## What it refuses, in a shallow repository

Walk-checked (refused by the two rules for comparisons):

    git log / rev-list with a range      A..B, A...B, ^A B, B --not A
    git merge-base A B, git cherry U H

Walk-checked (refused by the rule for walks with no range):

    git log / rev-list / shortlog        --reverse, --count, pipes to tail,
                                         wc, awk, grep: each is refused when
                                         its walk reaches the cut-off;
                                         --root and --max-parents=0 always
                                         check the whole walk

Always refused, because the read is of the whole history or has no walk the
guard can check:

    a range with --all, --branches, --tags, --remotes, --glob or --exclude,
    or with an endpoint that starts with "-"
    git merge-base with other arguments  --octopus, --fork-point,
                                         --independent, 3+ commits
                                         (--is-ancestor and --all with two
                                         commits are walk-checked)
    git branch / for-each-ref / tag      with --merged, --no-merged,
                                         --contains, --no-contains, or any
                                         prefix git accepts as one of them
    git for-each-ref %(ahead-behind:..)  ahead/behind counts
    git show-branch, git range-diff      both exit 0 with no common commit
    git bundle create                    a backup missing the cut-off history
    git push that can delete a ref       --delete, -d, :ref, +:ref, --prune,
                                         --mirror, or a prefix of one;
                                         a --dry-run push is allowed

Remote deletion is refused in a shallow clone even when shallowness does not
change what it deletes, because the decision to delete is what a shallow
clone gets wrong. Unshallow first, then delete.

## Which repository

`GIT_DIR=` or `--git-dir`, else `git -C <dir>`, else `env -C <dir>`, else the
`cd` moves earlier in the same call, starting from the hook payload's `cwd`.
A `cd` to a missing directory leaves the directory where it was, as the shell
does after a failed `cd`. A move it cannot resolve (`cd -`, `cd $VAR`) leaves
the directory unknown, and an unknown directory is skipped.
`xargs ... git ...` is read as the git command it runs.
A command inside `bash -c` or `sh -c` is checked from the payload's `cwd`,
and only when the outer command makes no `cd` move, since the nested shell's
starting directory is otherwise unknown (`shell_c_expansions` says why).

## The way out

`git fetch --unshallow`, then run the command again. Where a proxy refuses
that, `git fetch --depth=100000 origin`. For a deliberate read of the shallow
history, prefix that one command with `ALLOW_SHALLOW_HISTORY=1`.

## Fails open

The guard is silent when `shellcmd` cannot load, when the command does not
parse, when `git` is missing, and when the directory is not a repository or
its shallowness cannot be read. A PreToolUse hook that raises blocks the call.

## Not covered

- `eval "git ..."`, commands built from variables, and `git` reached through
  a script file.
- `git blame`, `git log -S` and `--follow`, which `memories/git.md` covers.
- `git status -sb`, `git branch -vv` and `%(upstream:track)`, which compare
  against an upstream and are routine; they are wrong only when the upstream
  forked below the cut-off.
- `mcp__remote-devices__device_bash` and `gh api -X DELETE .../git/refs/...`,
  which act on another machine or through the API.
"""
import json
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.realpath(__file__))
try:
    _LIB = os.path.join(os.path.dirname(_HERE), "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import (simple_commands_with_scope, strip_env, git_subcommand,
                          resolve_cd_target, env_value, shell_c_expansions)
except Exception as _exc:  # broken install: degrade, never block
    print(f"no-history-compare-in-shallow-clone: cannot load "
          f"scripts/lib/shellcmd.py ({_exc}); no guard will run", file=sys.stderr)
    simple_commands_with_scope = None

SHELL_TOOLS = frozenset({"Bash", "bash", "run_command", "execute_command",
                         "terminal", "shell"})
OVERRIDE = "ALLOW_SHALLOW_HISTORY"
CD_WORDS = frozenset({"cd", "pushd", "popd"})
WALK_TIMEOUT = 8

# git's parse-options accepts any prefix of a long option that names exactly
# one option. To decide "is this token one of the dangerous options", the
# token must be a prefix of a dangerous name and of no other option the
# command takes. These are the long options of each command (git 2.43).
REF_FILTERS = ("--merged", "--no-merged", "--contains", "--no-contains")
REF_CMD_OPTS = {
    "branch": REF_FILTERS + (
        "--abbrev", "--all", "--color", "--column", "--copy", "--create-reflog",
        "--delete", "--edit-description", "--force", "--format", "--ignore-case",
        "--list", "--move", "--no-abbrev", "--no-color", "--no-column",
        "--no-track", "--omit-empty", "--points-at", "--quiet",
        "--recurse-submodules", "--remotes", "--set-upstream-to",
        "--show-current", "--sort", "--track", "--unset-upstream", "--verbose"),
    "tag": REF_FILTERS + (
        "--annotate", "--cleanup", "--color", "--column", "--create-reflog",
        "--delete", "--edit", "--file", "--force", "--format", "--ignore-case",
        "--list", "--local-user", "--message", "--no-column", "--no-sign",
        "--omit-empty", "--points-at", "--sign", "--sort", "--trailer",
        "--verify"),
    "for-each-ref": REF_FILTERS + (
        "--count", "--exclude", "--format", "--ignore-case",
        "--include-root-refs", "--omit-empty", "--perl", "--points-at",
        "--python", "--shell", "--sort", "--start-after", "--stdin", "--tcl"),
}
PUSH_DELETERS = ("--delete", "--prune", "--mirror")
PUSH_OPTS = PUSH_DELETERS + (
    "--all", "--branches", "--tags", "--dry-run", "--porcelain", "--force",
    "--force-with-lease", "--force-if-includes", "--repo", "--set-upstream",
    "--thin", "--no-thin", "--quiet", "--verbose", "--progress",
    "--recurse-submodules", "--verify", "--no-verify", "--atomic",
    "--push-option", "--signed", "--ipv4", "--ipv6", "--receive-pack",
    "--exec", "--follow-tags", "--no-signed", "--no-atomic",
)

# Options of log / rev-list that take their value as the next word, so the
# value is never read as a revision (`--author a..b`, `-S x..y`). Measured on
# git 2.43: `--format`, `--pretty`, `--branches`, `--tags` and `--remotes`
# take a value only after `=`, so they are not here (fourth review of
# ai-config#5323).
LOG_VALUE_OPTS = frozenset({
    "-n", "--max-count", "--skip", "--author", "--committer", "--grep",
    "-S", "-G", "--since", "--until", "--after", "--before", "--date",
    "--encoding", "-L", "-O", "--diff-filter", "--output", "--decorate-refs",
    "--decorate-refs-exclude", "--exclude", "--glob",
})
GIT_VALUE_OPTS = ("-c", "--namespace", "--exec-path", "--work-tree")

# Options that add commits to the walk, as revisions do.
REV_SET_OPTS = ("--all", "--branches", "--tags", "--remotes", "--glob", "--exclude")

# Options that change only how each commit is shown, never which commits the
# walk visits or their order. A limited log with only these (and
# --first-parent) lists the same commits as `rev-list --max-count`. Any other
# option (--author, --no-merges, --skip, --topo-order, a path) may make git
# read past the limit, so the whole walk is checked instead.
SHOW_ONLY_OPTS = frozenset({
    "--oneline", "--format", "--pretty", "--abbrev-commit", "--no-abbrev-commit",
    "--abbrev", "--no-abbrev", "--date", "--relative-date", "--decorate",
    "--no-decorate", "--color", "--no-color", "--reverse", "--count",
    "--timestamp", "--parents", "--children", "--stat", "--shortstat",
    "--numstat", "--summary", "--name-only", "--name-status", "--raw",
    "--patch", "--no-patch", "--no-renames", "--encoding", "--expand-tabs",
    "--no-expand-tabs", "--log-size", "--mailmap", "--use-mailmap",
    "--no-mailmap", "--notes", "--no-notes", "--show-signature", "--numbered",
    "--email", "-p", "-u", "-s", "-z",
})

# `git log ... | head [-n N | -N | --lines=N]`: the pipe limits the read.
RX_LOG_TO_HEAD = re.compile(
    r"\bgit\b[^;&\n|]*\b(?:log|shortlog|rev-list)\b[^;&\n|]*"
    r"\|\s*head(?:\s+(?:-n\s*|--lines=|-)(\d+))?\s*(?=$|[|;&)\n])")

DENY = (
    "Refused: `{segment}` reads history that the repository at {repo} does "
    "not have: it is a SHALLOW clone{why}. Such a read still exits 0 and "
    "prints a plausible, wrong answer. On 2026-11-11 one made 23 lds "
    "branches look unrelated to main and nearly deleted 12 branches of "
    "unmerged work (ai-config#5323).\n\n"
    "Fix: `git -C {repo} fetch --unshallow origin` (or, where a proxy refuses "
    "that, `git -C {repo} fetch --depth=100000 origin`), then re-run. "
    "For a deliberate read of the shallow history, prefix that one command "
    "with `ALLOW_SHALLOW_HISTORY=1`."
)


def _is_option(tok, targets, all_opts):
    """True when `tok` names one of `targets`, in full or by a prefix that
    git would accept (one that matches no other option in `all_opts`)."""
    head = tok.split("=", 1)[0]
    if not head.startswith("--") or len(head) < 3:
        return False
    if head in targets:
        return True
    matches = {name for name in all_opts if name.startswith(head)}
    return bool(matches) and matches <= set(targets)


def _env_chdir(argv):
    """The directory of an `env -C <dir>` / `env --chdir=<dir>` wrapper."""
    if not argv or os.path.basename(argv[0]) != "env":
        return None
    i = 1
    while i < len(argv) and argv[i] != "git":
        tok = argv[i]
        if tok in ("-C", "--chdir") and i + 1 < len(argv):
            return argv[i + 1]
        if tok.startswith("--chdir="):
            return tok.split("=", 1)[1]
        i += 1
    return None


def _unwrap_xargs(argv):
    """`xargs [opts] git ...` -> `git ...`; anything else unchanged."""
    if argv and os.path.basename(argv[0]) == "xargs" and "git" in argv:
        return argv[argv.index("git"):]
    return argv


def _join(base, path):
    path = os.path.expanduser(path)
    if os.path.isabs(path):
        return os.path.normpath(path)
    if base is None:
        return None
    return os.path.normpath(os.path.join(base, path))


def _repo_dir(argv, base):
    """The repository directory one git argv acts on, or None if unknown."""
    chdir = _env_chdir(argv)
    if chdir is not None:
        base = _join(base, chdir)
    env, rest = strip_env(_unwrap_xargs(argv))
    git_dir = env_value(env, "GIT_DIR")
    out = base
    i = 1
    while i < len(rest) and rest[i].startswith("-"):
        tok = rest[i]
        if tok == "-C" and i + 1 < len(rest):
            out = _join(out, rest[i + 1])
            i += 2
        elif tok == "--git-dir" and i + 1 < len(rest):
            git_dir = rest[i + 1]
            i += 2
        elif tok.startswith("--git-dir="):
            git_dir = tok.split("=", 1)[1]
            i += 1
        elif tok in GIT_VALUE_OPTS:
            i += 2
        else:
            i += 1
    if git_dir:
        return _join(out, git_dir)
    return out


def _revisions(rest):
    """The revision words of a log/rev-list/merge-base argv, in order, with
    `--not` kept; stops at `--` and skips separate option values."""
    out = []
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok == "--":
            break
        if tok == "--not":
            out.append(tok)
        elif tok.startswith("-"):
            if tok in LOG_VALUE_OPTS:
                i += 1
        else:
            out.append(tok)
        i += 1
    return out


def _is_range_word(tok, repo):
    if tok == "--not":
        return True
    if tok.startswith("^") and len(tok) > 1:
        return True
    if ".." not in tok:
        return False
    return not _is_path(tok, repo)


def _endpoints(revs):
    """The distinct commits a range names: `A..B`, `A...B`, `^A B` and
    `B --not A` all give [A, B]. An empty side of `..` is HEAD."""
    out = []
    for tok in revs:
        if tok == "--not":
            continue
        tok = tok[1:] if tok.startswith("^") else tok
        sep = "..." if "..." in tok else (".." if ".." in tok else None)
        parts = tok.split(sep, 1) if sep else [tok]
        for part in parts:
            part = part or "HEAD"
            if part not in out:
                out.append(part)
    return out


def _is_path(tok, repo):
    """A word that names a path rather than a revision."""
    if tok.startswith(("./", "../")) or "/../" in tok or tok.endswith("/.."):
        return True
    return bool(repo) and os.path.exists(os.path.join(repo, tok))


def _plain_walk(sub, rest, repo):
    """How a log / rev-list / shortlog with no range walks.

    Returns (limit, walk_opts, revs, filtered): the commit limit or None,
    the revision-set options and --first-parent to hand to rev-list, the
    revision words, and whether anything else (a filter, an ordering option,
    an unknown option, a path) may make git read past the limit."""
    limit, walk_opts, revs, filtered = None, [], [], False
    i = 0
    while i < len(rest):
        tok = rest[i]
        nxt = rest[i + 1] if i + 1 < len(rest) else None
        head = tok.split("=", 1)[0]
        if tok == "--":
            filtered = filtered or i + 1 < len(rest)
            break
        num = None
        if re.fullmatch(r"-\d+", tok):
            num = tok[1:]
        elif sub != "shortlog" and re.fullmatch(r"-n\d+", tok):
            num = tok[2:]
        elif (tok == "--max-count" or (tok == "-n" and sub != "shortlog")) and nxt is not None:
            num = nxt
            i += 1
        elif tok.startswith("--max-count="):
            num = tok.split("=", 1)[1]
        if num is not None:
            if num.isdigit():
                limit = int(num)
            else:
                filtered = True
        elif head in REV_SET_OPTS or tok == "--first-parent":
            walk_opts.append(tok)
            if tok in ("--glob", "--exclude") and nxt is not None:
                walk_opts.append(nxt)
                i += 1
        elif head in SHOW_ONLY_OPTS or (
                sub == "shortlog" and re.fullmatch(r"-[sneci]+|-w[0-9,]*", tok)):
            if tok in LOG_VALUE_OPTS:
                i += 1
        elif tok.startswith("-"):
            filtered = True
            if tok in LOG_VALUE_OPTS:
                i += 1
        elif _is_path(tok, repo):
            filtered = True
        else:
            revs.append(tok)
        i += 1
    return limit, walk_opts, revs, filtered


def _flag(rest, *names):
    for tok in rest:
        if tok == "--":
            break
        if tok.split("=", 1)[0] in names:
            return True
    return False


def _push_can_delete(rest):
    if (_flag(rest, "--dry-run") or "-n" in rest) and not _flag(rest, "--no-dry-run"):
        return False
    for tok in rest:
        if tok == "--":
            continue
        if _is_option(tok, PUSH_DELETERS, PUSH_OPTS):
            return True
        if (tok.startswith("-") and not tok.startswith("--")
                and tok[1:].isalpha() and "d" in tok[1:]):
            return True
        bare = tok[1:] if tok.startswith("+") else tok
        if bare.startswith(":") and len(bare) > 1:
            return True
    return False


class _Repo:
    """Per-repository facts, each read once per hook run."""

    def __init__(self):
        self._shallow = {}

    def cutoff(self, repo):
        """The set of cut-off commits, empty if the repo is not shallow,
        or None if that cannot be read."""
        if repo in self._shallow:
            return self._shallow[repo]
        result = None
        try:
            flag = subprocess.run(
                ["git", "-C", repo, "rev-parse", "--is-shallow-repository",
                 "--git-common-dir"],
                capture_output=True, text=True, timeout=5)
            if flag.returncode == 0:
                lines = flag.stdout.split("\n")
                if lines[0].strip() == "false":
                    result = set()
                elif lines[0].strip() == "true" and len(lines) > 1:
                    common = _join(repo, lines[1].strip())
                    with open(os.path.join(common, "shallow"), encoding="utf-8") as fh:
                        result = {line.strip() for line in fh if line.strip()}
                    if not result:
                        result = None
        except Exception:
            result = None
        self._shallow[repo] = result
        return result

    @staticmethod
    def pair_unsafe(repo, a, b, cutoff):
        """Why comparing commits `a` and `b` may be wrong here, or None.

        Reads the fetched graph once (`rev-list --timestamp --parents a b`)
        and checks each direction, X excluded and Y included, with
        OUT = reach(Y) - reach(X):

        1. OUT holds a cut-off commit: Y's side ran out of history, so the
           answer is missing whatever lies below it.
        2. reach(X) holds a cut-off commit, and OUT holds a commit no newer
           than the newest such cut-off, or a parentless commit: that commit
           may be a hidden ancestor of X's cut-off, which X's side would have
           excluded with full history. (A branch fetched in full after a
           shallow clone of main brings main's old commits back through the
           branch, and only their age can show they sit below main's cut-off.)

        Rule 2 assumes a commit is not older than its ancestors, which holds
        unless committer clocks were skewed. It refuses rather than allows when
        the dates tie. Any failure of the query refuses.
        """
        if a.startswith("-") or b.startswith("-"):
            return "a revision that starts with '-' cannot be checked"
        try:
            ids = subprocess.run(
                ["git", "-C", repo, "rev-parse", a + "^{commit}", b + "^{commit}"],
                capture_output=True, text=True, timeout=5)
            shas = ids.stdout.split()
            if ids.returncode != 0 or len(shas) != 2:
                return "the revisions could not be resolved, so the walk was not checked"
            res = subprocess.run(
                ["git", "-C", repo, "rev-list", "--timestamp", "--parents",
                 shas[0], shas[1], "--"],
                capture_output=True, text=True, timeout=WALK_TIMEOUT)
        except Exception:
            return "the walk query failed or timed out"
        if res.returncode != 0:
            return "the walk query failed"
        when, parents = {}, {}
        for line in res.stdout.split("\n"):
            fields = line.split()
            if len(fields) < 2:
                continue
            when[fields[1]] = int(fields[0])
            parents[fields[1]] = fields[2:]

        def reach(start):
            seen, todo = set(), [start]
            while todo:
                sha = todo.pop()
                if sha in seen or sha not in parents:
                    continue
                seen.add(sha)
                todo.extend(parents[sha])
            return seen

        side = {shas[0]: reach(shas[0]), shas[1]: reach(shas[1])}
        for x, y in ((shas[0], shas[1]), (shas[1], shas[0])):
            out = side[y] - side[x]
            if out & cutoff:
                return "one side's walk runs into the cut-off"
            cut_x = side[x] & cutoff
            if not cut_x:
                continue
            newest = max(when[c] for c in cut_x)
            for sha in out:
                if when[sha] <= newest or not parents[sha]:
                    return ("the walk lists commits as old as the cut-off, which "
                            "may sit below it in the full history")
        return None

    @staticmethod
    def walk_unsafe(repo, revs, walk_opts, limit, cutoff):
        """Why a walk with no range may be wrong here, or None.

        Lists the walk with `rev-list` (at most `limit` commits). Only a
        cut-off commit has hidden parents, so no hidden commit can be listed
        before a cut-off commit is. The walk is wrong when it lists a cut-off
        commit anywhere but last place of a full `limit`: past that point the
        clone lists fewer, or different, commits than the full history."""
        if not revs and not any(o.split("=", 1)[0] in REV_SET_OPTS for o in walk_opts):
            revs = ["HEAD"]
        cmd = ["git", "-C", repo, "rev-list"]
        if limit is not None:
            cmd.append(f"--max-count={limit}")
        cmd += walk_opts + ["--end-of-options"] + revs + ["--"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True,
                                 timeout=WALK_TIMEOUT)
        except Exception:
            return "the walk query failed or timed out"
        if res.returncode != 0:
            return "the walk could not be checked"
        for n, sha in enumerate(res.stdout.split()):
            if sha in cutoff and (limit is None or n < limit - 1):
                return "the walk reaches the cut-off"
        return None


def _verdict(sub, rest, repo, cutoff, head_limit):
    """A short reason string when this git command must be refused, else None."""
    walk = _Repo.pair_unsafe
    if sub in ("log", "rev-list", "shortlog"):
        revs = _revisions(rest)
        if any(_is_range_word(tok, repo) for tok in revs):
            # A range bounds the walk, so --reverse or --max-parents inside a
            # range that checks out reads only fetched history.
            if _flag(rest, *REV_SET_OPTS):
                return "; a range combined with --all/--branches/--tags/--remotes cannot be checked"
            ends = _endpoints(revs)
            if len(ends) != 2:
                return "; a range with " + str(len(ends)) + " endpoints cannot be checked"
            why = walk(repo, ends[0], ends[1], cutoff)
            return "; " + why if why else None
        limit, walk_opts, wrevs, filtered = _plain_walk(sub, rest, repo)
        if (head_limit is not None and sub != "shortlog"
                and not _flag(rest, "--reverse", "--count")):
            limit = head_limit if limit is None else min(limit, head_limit)
        if filtered:
            # A filter or path can make git read past the limit.
            limit = None
        why = _Repo.walk_unsafe(repo, wrevs, walk_opts, limit, cutoff)
        if why and filtered:
            why += " (a filter or path makes git walk past any limit)"
        elif why and limit is None:
            why += " (the read has no limit)"
        return "; " + why if why else None
    if sub in ("merge-base", "cherry"):
        revs = [tok for tok in _revisions(rest) if tok != "--not"]
        opts = [t for t in rest if t.startswith("--")]
        if sub == "merge-base" and any(t not in ("--is-ancestor", "--all") for t in opts):
            return "; merge-base " + " ".join(opts) + " cannot be checked"
        if len(revs) == 1 and sub == "cherry":
            revs = [revs[0], "HEAD"]
        if len(revs) != 2:
            return "; " + sub + " with " + str(len(revs)) + " commits"
        why = walk(repo, revs[0], revs[1], cutoff)
        return "; " + why if why else None
    if sub in ("branch", "for-each-ref", "tag"):
        if any(_is_option(tok, REF_FILTERS, REF_CMD_OPTS[sub]) for tok in rest):
            return "; --merged/--contains filters walk into the cut-off"
        if sub == "for-each-ref" and any("ahead-behind" in tok for tok in rest):
            return "; ahead-behind counts walk into the cut-off"
        return None
    if sub in ("show-branch", "range-diff"):
        return "; " + sub + " exits 0 with no common commit"
    if sub == "bundle" and rest and rest[0] == "create":
        return "; the bundle would lack the cut-off history"
    if sub == "push" and _push_can_delete(rest):
        return "; deleting a remote ref is refused until the history is complete"
    return None


def _git_parse(argv):
    """`git_subcommand` of one simple command, reading through `xargs`."""
    _env, rest = strip_env(argv)
    unwrapped = _unwrap_xargs(rest) if rest else rest
    return git_subcommand(unwrapped if unwrapped is not rest else argv)


def _evaluate_line(command, base_cwd, repos):
    cmds = simple_commands_with_scope(command)
    if cmds is None:
        return None
    heads = RX_LOG_TO_HEAD.findall(command)
    reads = [argv for _scope, argv in cmds
             if (_git_parse(argv) or ("",))[0] in ("log", "rev-list", "shortlog")]
    # Only an unambiguous pipe counts: one log read, piped straight to head.
    head_limit = int(heads[0] or 10) if len(heads) == 1 and len(reads) == 1 else None
    dirs = {(): base_cwd}
    for scope, argv in cmds:
        for n in range(1, len(scope) + 1):
            dirs.setdefault(scope[:n], dirs[scope[:n - 1]])
        _env, rest = strip_env(argv)
        if rest and rest[0] in CD_WORDS:
            target = resolve_cd_target(rest, dirs[scope])
            if target is None or os.path.isdir(target):
                dirs[scope] = target
            continue
        parsed = _git_parse(argv)
        if parsed is None:
            continue
        sub, sub_rest, env = parsed
        if env_value(env, OVERRIDE) == "1" or env_value(_env, OVERRIDE) == "1":
            continue
        repo = _repo_dir(argv, dirs[scope])
        if repo is None or not os.path.isdir(repo):
            continue
        cutoff = repos.cutoff(repo)
        if not cutoff:
            continue
        why = _verdict(sub, sub_rest, repo, cutoff, head_limit)
        if why is not None:
            return "deny", DENY.format(segment=" ".join(argv), repo=repo, why=why)
    return None


def _has_cd(command):
    for _scope, argv in simple_commands_with_scope(command) or []:
        _env, rest = strip_env(argv)
        if rest and rest[0] in CD_WORDS:
            return True
        if _env_chdir(argv) is not None:
            return True
    return False


def evaluate(command, base_cwd):
    """`('deny', reason)` or `None`."""
    if simple_commands_with_scope is None:
        return None
    repos = _Repo()
    verdict = _evaluate_line(command, base_cwd, repos)
    if verdict:
        return verdict
    if _has_cd(command):
        return None
    for nested in list(shell_c_expansions(command))[1:]:
        verdict = _evaluate_line(nested, base_cwd, repos)
        if verdict:
            return verdict
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") not in SHELL_TOOLS:
        return 0
    inp = payload.get("tool_input")
    inp = inp if isinstance(inp, dict) else {}
    command = inp.get("command")
    if not isinstance(command, str) or not command.strip():
        return 0
    cwd = payload.get("cwd")
    try:
        if not isinstance(cwd, str) or not os.path.isabs(cwd):
            cwd = os.getcwd()
        verdict = evaluate(command, cwd)
    except Exception as exc:  # fail open
        print(f"no-history-compare-in-shallow-clone: could not evaluate ({exc})",
              file=sys.stderr)
        return 0
    if verdict is None:
        return 0
    _kind, text = verdict
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": text}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
