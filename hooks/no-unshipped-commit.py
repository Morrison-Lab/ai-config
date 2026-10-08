#!/usr/bin/env python3
"""Stop-hook guard: a successful commit must be pushed before reporting done."""
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

# The shell's working directory is not this hook's to model: `cd`, `pushd`,
# `popd`, `cd -`, a bare `cd`, `~` and `$HOME` targets, and a relative target
# resolved against wherever the shell already stood are all handled by
# `scripts/lib/shellcmd.py`, whose `resolve_cd_target` is the tested in-repo
# implementation this file would otherwise re-derive. A broken install fails
# OPEN: the directory the shell stands in simply goes untracked, which costs
# attribution for a commit whose own call names no directory and can never
# invent one.
try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import (native_path, resolve_cd_target, simple_commands_with_scope,
                          strip_env)
except Exception as _exc:  # broken install; fail open and say so
    print(f"no-unshipped-commit: cannot load scripts/lib/shellcmd.py "
          f"({_exc}); not tracking the shell's directory", file=sys.stderr)
    native_path = resolve_cd_target = simple_commands_with_scope = strip_env = None

# `(?![\w-])`, not `\b`. A word boundary sits happily between `commit` and
# `-`, because `-` is a non-word character -- so `git\s+commit\b` matched
# `git commit-tree`, plumbing that writes a commit object and moves no ref.
# There is nothing to push, by construction, so the call that used it never
# contained a `git push`, `pending` was never cleared, and every later Stop in
# the session blocked on a fully-pushed branch (ai-config#1963, measured while
# driving #1947). `git commit-graph write` is the second instance, and the one
# people actually run.
#
# ai-config#2727 moved the DECISION to repository state. The transcript scan
# kept needing one clause per gap (the two above, plus #1806's heredocs and
# #2365's env prefixes), and the gap class was open-ended: a commit dropped
# on review advice -- `git reset --hard HEAD~1`, a rebase that drops it --
# leaves `pending` set with no commit left to push, so every later Stop
# blocked on a fully-pushed branch, three times consecutively in the measured
# session. The transcript scan now only decides WHETHER to look (a real
# `git commit` ran this session); the ANSWER is `git rev-list --count
# @{u}..HEAD`, which is immune to every reconstruction gap at once and needs
# no new clause per gap, per shared/workflow/algorithmatize-checks.md.
#
# PUSH carries the same guard for symmetry rather than as a second repair:
# `git push` has no hyphenated plumbing sibling today, so that half prevents
# the mirror bug instead of fixing a live one.
# `_ENV` tolerates leading NAME=value assignments before the command word.
# Without it, `ALLOW_UNREVIEWED_PUSH=1 git push` -- the sibling pre-push
# guard's own documented override spelling -- was invisible to PUSH, so a
# session whose every push carried the prefix was told on every Stop that a
# commit was never pushed, and only a literal no-op `git push` silenced it
# (ai-config#2365, #2395: three identical blocks on one shipped commit).
# The two guards' interaction guaranteed the loop: one required the prefix,
# the other could not see prefixed pushes.
_ENV = r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
_GIT_FLAGS = (
    r"(?:"
    r"-[Cc]\s*\S+\s+|"
    r"-[a-bd-zA-BD-Z0-9_][a-zA-Z0-9_-]*(?:=\S*)?\s+|"
    r"--[a-zA-Z0-9_][a-zA-Z0-9_-]*(?:=\S*)?\s+"
    r")*"
)
COMMIT = re.compile(r"(?:^|[;&|\n])\s*" + _ENV + r"git\s+" + _GIT_FLAGS + r"commit(?![\w-])", re.MULTILINE)
PUSH = re.compile(r"(?:^|[;&|\n])\s*" + _ENV + r"git\s+" + _GIT_FLAGS + r"push(?![\w-])", re.MULTILINE)
CREATE = re.compile(r"(?:^|[;&|\n])\s*" + _ENV + r"gh\s+pr\s+create\b", re.MULTILINE)

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from git_cmd import (  # type: ignore[no-redef]
        _ENV as _GIT_ENV,
        _GIT_FLAGS as _GIT_CMD_FLAGS,
        COMMIT as _GIT_COMMIT,
        CREATE as _GIT_CREATE,
        PUSH as _GIT_PUSH,
    )
    _ENV, _GIT_FLAGS = _GIT_ENV, _GIT_CMD_FLAGS
    COMMIT, PUSH, CREATE = _GIT_COMMIT, _GIT_PUSH, _GIT_CREATE
except Exception as _exc:  # fallback to inline definitions; log why
    print(f"no-unshipped-commit: cannot load scripts/lib/git_cmd.py "
          f"({_exc}); using fallback regexes", file=sys.stderr)

# A heredoc body redirected INTO A FILE is text, not commands: `cat > x <<'EOF'
# ... EOF` writes the lines rather than running them. A corpus about git
# workflow quotes git commands inside issue and PR bodies constantly, and a
# line-oriented scan cannot tell a quoted example from an executed one --
# shared/writing/examples-are-scanned.md states exactly this, and names
# teaching the checker about quoted regions as the fix where we own it.
#
# Measured on ai-config#1806: filing an issue whose body quoted
# `pr-on-claim.md`'s own start-commit mechanic armed this guard, and the same
# command's `gh issue create` did not disarm it, so a fully-pushed session was
# told to push.
#
# ONLY the file-redirect form is stripped. `bash <<'EOF' ... EOF` genuinely
# executes its body, so a heredoc this does not recognise as a file write
# keeps arming the guard -- the unrecognised case fails toward the old
# behaviour rather than toward a hole.
# `(?<!<)` rejects the second `<` of a `<<<` HERESTRING. Without it,
# `cat <<< hello` parses as a heredoc with tag `hello`; a herestring has no
# body and no terminator line, so the terminator search runs off the end of
# the command and swallows EVERY remaining line -- unbounded trailing text,
# not one heredoc body. `cat <<< "$v" > /tmp/out` is an ordinary way to write
# a literal to a file, so this is reachable rather than contrived.
HEREDOC_START = re.compile(r"(?<!<)(<<(-?))\s*(['\"]?)([A-Za-z_]\w*)\3")
# Both tests below run against the pipeline/list SEGMENT that owns the
# heredoc, never the whole line. Scoping is the whole game here: on a whole
# line, `cat <<'EOF' | bash` finds `cat` and a redirect and calls an executed
# heredoc "data", and `cat notes > /tmp/x; bash <<'EOF'` does the same across
# a `;`. Both hide a real commit, which is the failure this guard exists to
# prevent.
SEPARATOR = re.compile(r"\|\||&&|[;&|]")
# A redirect to a file, within the owning segment. Necessary, not sufficient.
REDIRECT = re.compile(r"[12]?>>?\s*\S")
# The owning segment's command word must WRITE its heredoc rather than run it.
WRITER = re.compile(r"^\s*(?:cat|tee)\b")


def _owning_segment(line, start):
    """The pipeline/list segment containing the heredoc token.

    Separators inside quotes are not honoured. That is deliberate: a
    mis-split can only ever make the segment look LESS like a plain
    `cat`/`tee` write, so the guard keeps arming -- the safe direction.
    """
    cuts = [0] + [m.end() for m in SEPARATOR.finditer(line)] + [len(line)]
    for lo, hi in zip(cuts, cuts[1:]):
        if lo <= start.start() < hi:
            return line[lo:hi]
    return line


def _terminates(line, tag, dash):
    """Match bash's heredoc terminator rule exactly."""
    return (line.lstrip("\t") if dash else line) == tag


def strip_quoted(command):
    """Drop heredoc bodies written to a file rather than executed."""
    lines = command.split("\n")
    kept, i = [], 0
    while i < len(lines):
        line = lines[i]
        start = HEREDOC_START.search(line)
        segment = _owning_segment(line, start) if start else ""
        if (start and WRITER.search(segment)
                and REDIRECT.search(HEREDOC_START.sub("", segment))):
            kept.append(line)
            dash, tag = start.group(2), start.group(4)
            i += 1
            # Drop the body AND the terminator: neither is executed, and the
            # terminator line carries nothing this scans for. Keeping it was
            # an equivalent mutant -- no assertion could pin it, so it was
            # untestable code rather than tested code.
            # bash's real termination rule, not `.strip()`. A plain `<<TAG`
            # terminates only on a line equal to TAG with NO surrounding
            # whitespace; `<<-TAG` strips leading TABS only. `.strip()` was
            # looser than both, so an indented decoy `  EOF` ended the strip
            # early and exposed body text -- including a quoted `git push`,
            # which then discharged a genuinely pending commit.
            while i < len(lines) and not _terminates(lines[i], tag, dash):
                i += 1
            i += 1
            continue
        kept.append(line)
        i += 1
    return "\n".join(kept)



GIT_C_CMD = re.compile(
    r"(?:^|[;&|\n])\s*" + _ENV + r"git\s+-C\s+([^\s;&|]+)",
    re.MULTILINE
)
# Calls that MOVE HEAD, as opposed to merely naming a branch. Matched for
# their own sake rather than for the names they carry: `git checkout -`
# switches back and names nothing, and a switch that names nothing still has
# to supersede the branch a commit would otherwise inherit (ai-config#2422).
#
# It is the ONLY source of the names a commit may inherit, and it replaces
# them rather than adding to them. An earlier revision read those from a
# wider pattern that matched `git branch` too, so
# `git branch -d agy-dormant` --- the cleanup this issue's own report
# describes performing on a squash-merged leftover --- made that branch the
# one the next commit was attributed to, and a `git branch -d` git refuses as
# unmerged left the session blocked on a branch it never committed to. A
# branch only ever passed to `git branch` was never committed on.
#
# Three near-misses are excluded, because supersession CLEARS the carried
# branch and clearing on a call that moved nothing loses the switched-branch
# attribution ai-config#2737 added. `git branch feature` creates without
# switching. `git worktree add <path> <branch>` creates a second checkout and
# leaves this one exactly where it stood, so it belongs beside `git branch`
# rather than here --- and so does its `-b` form, which names a branch in a
# checkout this shell is not standing in. `git checkout -p` stages
# hunks interactively and switches nothing, so the argument list is read
# rather than only the command word.
#
# `git switch --detach` IS a move and stays included: it detaches HEAD at the
# current commit, so a commit after it lands on no branch at all and must not
# inherit the one the shell left.
#
# `(?![\w-])`, not `\b`, for the same reason COMMIT carries it: a word
# boundary sits happily before a hyphen, so `checkout\b` matches
# `git checkout-index`, plumbing that copies files out of the index and moves
# HEAD nowhere. The group must stay optional-whitespace to reach a bare
# `git checkout`, which is what makes the guard necessary here.
SWITCH_CMD = re.compile(
    r"(?:^|[;&|\n])\s*" + _ENV + r"git\s+(?:checkout|switch)(?![\w-])\s*([^;&|\n]*)",
    re.MULTILINE
)
PATCH_FLAGS = {"-p", "--patch"}
# The bare `--` token, which ends the options and makes everything after it a
# PATHSPEC. `git checkout -- README.md` and `git checkout main -- README.md`
# both restore a file into the working tree and move HEAD nowhere, so neither
# may clear the carried branch --- and a path restore is far commoner in this
# corpus's own workflows than the patch and plumbing forms above it.
#
# The bare `git checkout README.md` form, with no `--`, is NOT decidable from
# the command text: git resolves it as a ref when one exists and as a path
# otherwise, and `README.md` and `feature/x.y` are both legal branch names.
# It is therefore left reading as a switch, which clears the carried branch
# and names one no worktree holds --- so the guard falls silent rather than
# blocking on a branch the session never committed to. That is the direction
# ai-config#2422 requires: a missed block costs a reminder, a false block
# costs every Stop in the session.
PATHSPEC_SEP = "--"
# A cheap pre-filter for `shell_dir_after`. Parsing every call's argv would
# run `shlex` twice per Bash call across a whole transcript, and a Stop hook
# has to answer promptly; a command carrying none of these three words moves
# the shell nowhere, so the parse has nothing to find. `(?![\w-])` again, so
# `cdate` and `cd-into` do not arm it.
DIR_MOVE = re.compile(r"(?:^|[;&|\n(]|\s)(?:cd|pushd|popd)(?![\w-])", re.MULTILINE)


def _moves_head(args):
    """Whether a `git checkout`/`git switch` argument list actually moves HEAD.

    The single gate `branches_after` consults before REPLACING the carried
    branch: a form that moves supersedes whatever was carried even when it
    names nothing, and a form that does not move must leave the carry alone.
    An earlier revision asked that question in two places --- one deciding
    whether to clear, the other deciding what replaces --- and they read
    different patterns, so a command counted as naming a branch was never
    counted as clearing one. One caller is what makes that unrepresentable
    rather than merely unlikely.
    """
    if any(a in PATCH_FLAGS for a in args):
        return False
    return PATHSPEC_SEP not in args


# Appended by `shell_dir_after` so the parse reports the subshell the TEXT
# ENDS IN. `simple_commands_with_scope` pairs each command with its own scope
# and says nothing about the separators that follow the last one, so
# `(cd /a && git status)` and `(cd /a && ` are otherwise indistinguishable:
# the first ends back in the parent shell, the second inside the subshell
# where whatever follows it runs. A marker word invokes nothing and is never
# a `cd`, so it only ever reports.
END_MARKER = "__no_unshipped_commit_end__"


def _scope_dir(dirs, scope, cur_dir):
    """The directory subshell `scope` stands in, entering it if it is new.

    A subshell inherits its parent's directory AT THE MOMENT IT OPENS, which
    is what recording it lazily --- on the scope's first command --- gets
    right: every `cd` the parent ran before the `(` has already been folded
    into the parent's entry, and every `cd` it runs after the `)` comes later
    and cannot reach a scope that is already closed.
    """
    if scope not in dirs:
        dirs[scope] = (cur_dir if len(scope) == 1
                       else _scope_dir(dirs, scope[:-1], cur_dir))
    return dirs[scope]


_RX_WIN_DRIVE_PATH = re.compile(r"([A-Za-z]:\\[^;&|\n\r]+)")


def shell_dir_after(text, cur_dir, parent_only=False):
    """The directory the shell stands in WHERE `text` ENDS, given `cur_dir`,
    or, with `parent_only`, the caller's own shell wherever `text` stopped.

    `None` means INDETERMINATE, never "unchanged": `cd -`, `popd`, a `$VAR`
    target, and an unparseable command each move the shell somewhere this
    scan cannot name, so nothing after them may inherit the directory they
    left. That is the whole of ai-config#2422's directory half --- a session
    that visits a dormant foreign worktree and then returns must not attribute
    its own later commit to the worktree it visited.

    One directory per SUBSHELL, keyed on the scope
    `simple_commands_with_scope` reports rather than on nesting depth alone:
    a subshell inherits its parent's directory on descent, its own moves die
    with it on ascent, and the parent's survives both. Depth alone cannot
    say that much, because two SIBLING subshells share a depth --- so keying
    on it let `(cd /other-worktree && git status) && (git commit -m mine`
    carry the first subshell's move into the second and attribute the commit
    to a checkout it never ran in, which is ai-config#2422's own false-block
    failure on a different spelling.
    """
    if simple_commands_with_scope is None or not DIR_MOVE.search(text):
        return cur_dir
    # The marker goes on its own line, so a heredoc terminator ending `text`
    # stays a terminator rather than becoming `EOF __no_unshipped_commit_end__`
    # and swallowing the rest of the call. When it is swallowed anyway,
    # `end_scope` stays the caller's own shell and the parent's directory is
    # the answer, which is what this function returned before scopes existed.
    parse_text = text
    if "\\" in text:
        parse_text = _RX_WIN_DRIVE_PATH.sub(lambda m: m.group(1).replace("\\", "/"), text)
    argvs = simple_commands_with_scope(parse_text + chr(10) + END_MARKER)
    if argvs is None:
        return None
    dirs, end_scope = {}, (0,)
    for scope, argv in argvs:
        here = _scope_dir(dirs, scope, cur_dir)
        if argv == [END_MARKER]:
            end_scope = scope
            break
        _, rest = strip_env(argv)
        if rest and rest[0] in ("cd", "pushd", "popd"):
            target = resolve_cd_target(rest, here)
            if target and native_path is not None:
                target = native_path(target)
            dirs[scope] = target
    return _scope_dir(dirs, (0,) if parent_only else end_scope, cur_dir)


def absolute_dir(path):
    """`path` when it names a directory absolutely, else None.

    A relative target resolved against an unknown starting directory comes
    back as the literal the user typed (`hooks`), which no worktree path can
    be compared against. Dropping it is the honest answer.
    """
    return path if path and (os.path.isabs(path) or bool(re.match(r"^[A-Za-z]:[/\\]", path))) else None


def extract_named_paths(command):
    """Directories a `git -C <dir>` NAMES without moving the shell into them.

    `-C` points the command at a repository while leaving the shell where it
    stood, so a `-C` the COMMIT ITSELF carries attributes that commit on its
    own and needs no carrying forward. Where the shell IS standing is tracked
    separately by `shell_dir_after`, because a `cd` persists across tool calls
    while this function sees one call.

    Callers attributing a commit pass the committing git invocation rather
    than the whole call, so that only a `-C` the commit carries counts --- see
    `scan_transcript`. `git worktree add <path>` is deliberately not read
    here: it creates a checkout without moving the shell into it, so a commit
    beside it lands where the shell already stood, and the only routes into
    the new checkout --- a `cd` into it, or a `-C` naming it on the commit ---
    are each already covered above.
    """
    paths = set()
    for m in GIT_C_CMD.finditer(command):
        p = m.group(1).strip("\"'").strip()
        if p:
            paths.add(p)
    return paths


def _switch_target(args):
    """Branch names a head-moving `git checkout`/`git switch` leaves HEAD on.

    An empty set is a real answer, not a miss: `git checkout -` moves away
    while naming nothing, and `branches_after` reads that emptiness as the
    supersession ai-config#2422 requires.

    `git checkout [<tree-ish>] -- <paths>` restores files and moves HEAD
    nowhere, so it names no branch this scan may carry --- reading the
    pathspec as one replaced the real carried branch with a filename and lost
    the switched-branch attribution ai-config#2737 added. `_moves_head` is
    what excludes it, and the patch forms beside it, before this runs.
    """
    branches = set()
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg in ("-b", "-B", "-c", "-C", "-d", "-D", "-m", "-M", "--create", "--orphan"):
            continue
        if arg.startswith("-"):
            if arg in ("-t", "--track", "--recurse-submodules", "--set-upstream-to", "-u"):
                skip_next = True
            continue
        if arg == "--":
            continue
        b = arg
        if b.startswith("refs/heads/"):
            b = b[len("refs/heads/"):]
        if not b.startswith("-") and not b.startswith("@"):
            branches.add(b)
    return branches


def branches_after(text, cur_branches):
    """The branches a commit after `text` may sit on, given `cur_branches`.

    The branch-side twin of `shell_dir_after`, and folded the same way: each
    head-moving command is applied IN SOURCE ORDER, replacing the set rather
    than adding to it, so the command the text ends on is the one that
    decides. Unioning every match instead left the inspect-then-return route
    ai-config#2422 reports open whenever both halves sat in one text ---
    `git checkout agy-dormant && git log -1 && git checkout -` still yielded
    the dormant branch, because the named checkout outvoted the `-` that
    superseded it. The same union claimed `main` off the
    `git checkout main && git pull --ff-only && git checkout -b fix/x`
    opening this corpus writes constantly, so a local `main` sitting ahead of
    its upstream blocked every Stop over a branch nothing was committed on.

    A move that names nothing empties the set, which is the supersession
    itself.

    `git worktree add -b <name>` is NOT a source here, and adding it was a
    false-attribution bug of exactly the kind this issue exists to remove: it
    creates the branch in a SECOND checkout and leaves this shell's HEAD
    where it stood, so a commit beside it lands on whatever the shell was
    already on. Contributing the name additively also made it permanent ---
    nothing but a later head-moving switch removes it --- so a conductor
    session that creates several subagent worktrees, this corpus's own
    standard shape, had its Stop blocked by any subagent's unpushed commit.
    The session's own route into such a checkout is a `cd` into it or a
    `-C` naming it on the commit, and `shell_dir_after` and
    `extract_named_paths` already attribute both.
    """
    branches = set(cur_branches)
    for m in SWITCH_CMD.finditer(text):
        args = m.group(1).split()
        if _moves_head(args):
            branches = _switch_target(args)
    return branches


def unwrap_command(cmd):
    if not isinstance(cmd, str):
        return ""
    if cmd.startswith('"'):
        try:
            return json.loads(cmd)
        except Exception:
            # Handle truncated JSON strings by unescaping manually
            cmd = cmd[1:]
            if cmd.endswith('"'):
                cmd = cmd[:-1]
            return cmd.replace('\\n', '\n').replace('\\"', '"')
    return cmd

def _timestamp_key(record):
    """A record's own timestamp, or None when it carries none that parses."""
    stamp = record.get("timestamp")
    if not isinstance(stamp, str) or not stamp:
        return None
    try:
        return datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def bash_calls(path):
    """Every Bash tool call in the transcript, in CHRONOLOGICAL order.

    File order is not time order. A context compaction replays earlier
    records, appending them BELOW newer ones while they keep their original
    timestamps, so a replayed `cd` can land after a commit it never preceded
    and claim it --- the "last X in the transcript" unsoundness
    `memories/claude-code-transcripts.md` names, which fails silently because
    every record parses correctly and the reader simply holds the wrong one.
    Every piece of carried state below is position-keyed, so the ordering is
    fixed once, here, rather than defended at each use.

    Calls are sorted by each record's own timestamp, stably, and ONLY when
    all of them carry one that parses and compares. A mix of stamped and
    unstamped records has no total order to impose, and neither do aware and
    naive stamps together, so file order stands in both cases rather than a
    guessed one.
    """
    calls = []
    with open(path, encoding="utf-8", errors="ignore") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            tool_calls = []
            if record.get("type") == "assistant" or record.get("role") == "assistant":
                blocks = (record.get("message") or {}).get("content") or record.get("content") or []
                if isinstance(blocks, list):
                    for block in blocks:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            tool_calls.append((block.get("name") or "", block.get("input") or {}))
            if record.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or record.get("source") == "MODEL" or "tool_calls" in record:
                for tc in record.get("tool_calls") or []:
                    if isinstance(tc, dict):
                        name = tc.get("name") or (tc.get("function") or {}).get("name") or ""
                        args = tc.get("args") or tc.get("input") or (tc.get("function") or {}).get("arguments") or {}
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                args = {"command": args}
                        tool_calls.append((name, args if isinstance(args, dict) else {}))
            for name, inp in tool_calls:
                if name not in {"Bash", "bash", "run_command", "terminal", "execute_command", "shell"}:
                    continue
                calls.append((_timestamp_key(record), len(calls), inp))
    if calls and all(call[0] is not None for call in calls):
        try:
            calls.sort(key=lambda call: (call[0], call[1]))
        except TypeError:
            calls.sort(key=lambda call: call[1])
    return [call[2] for call in calls]


def scan_transcript(path):
    """Return (saw_commit, pending, commit_branches, commit_paths).

    `saw_commit` is whether a real `git commit` ran at all --- the gate that
    decides whether repository state is worth consulting, so a session that
    never committed is not blocked for commits it did not make. `pending` is
    the last committed-but-never-discharged command, by the same scan.

    `commit_branches` and `commit_paths` are scoped to the tool calls that
    actually COMMITTED, not to every branch and directory the session
    happened to visit (ai-config#2422). Visiting is not committing: a
    session that runs `cd /other-tool-worktree && git status` to inspect a
    dormant Antigravity or Cursor worktree used to make that worktree
    relevant, so a leftover branch there --- typically one whose PR already
    squash-merged, leaving local commits no remote carries --- blocked every
    Stop for a debt the session never incurred and often could not safely
    discharge. The payload `cwd` stays relevant on its own, so the ordinary
    single-checkout case is unaffected.

    A commit is attributed to the state the shell was in WHEN IT RAN, which
    is what makes both halves narrow. EVERY commit in a call is attributed
    that way, not only the first, so `cd /a && git commit -m x && cd /b &&
    git commit -m y` claims both checkouts. The directory is the one `cd`
    calls EARLIER IN THE SAME CALL leave the shell in, over the
    harness-recorded working directory of that call, over the directory
    carried from the previous call --- so `git commit -m x && cd /elsewhere`
    attributes where the shell stood, not where it ends up. The branch is the
    one the LAST head-moving command earlier in the same call named, and
    otherwise the branch carried forward: both axes fold their moves in
    source order, so neither reports a state the shell had already left.
    A `git -C <dir>` on the committing invocation ITSELF names the repository
    the commit runs in and attributes on its own. A `git -C` elsewhere in the
    same call does not, whether it precedes the commit or follows it: it
    reads another repository without running the commit there, and
    `git commit -m x && git -C /elsewhere log -1` used to report /elsewhere
    --- the `cd`-after-the-commit misattribution spelled with a different
    flag. `git worktree add <path>` likewise creates a checkout without
    moving the shell into it, so a commit beside it lands where the shell
    already stood --- on neither axis, the `-b` form included: the path it
    creates is not a commit path, and the branch it creates is not a commit
    branch, until a `cd` into that checkout or a `-C` naming it on the commit
    says the commit ran there.

    Both carried values are SUPERSEDED by a move that names nothing, whether
    it stands in its own call or precedes the commit inside one: `git
    checkout -` and `cd -` move away while yielding no name, and `popd` and a
    bare `cd` do too, so inspecting a dormant worktree or branch and then
    returning leaves the dormant one unattributed in either spelling
    (ai-config#2422). Attribution is per commit rather than per
    session, so a later checkout away --- the switched-branch case
    ai-config#2737 added --- still reports the branch that holds the commit,
    while a checkout no commit followed reports nothing.
    """
    saw, pending, commit_branches, commit_paths = False, None, set(), set()
    # The shell's running state, awaiting a commit to claim it. `cur_dir` is
    # a single resolved absolute path rather than a set of raw literals,
    # because the shell stands in exactly one directory; None means the last
    # move went somewhere this scan cannot name.
    recent_branches, cur_dir = set(), None
    try:
        for inp in bash_calls(path):
            harness_dirs, harness_cwd = set(), None
            for key in ("cwd", "workdir", "Cwd", "WorkingDirectory", "path"):
                val = inp.get(key)
                if isinstance(val, str) and val:
                    harness_dirs.add(val)
                    if harness_cwd is None:
                        harness_cwd = val
            command = str(inp.get("command") or inp.get("cmd") or inp.get("CommandLine") or inp.get("script") or "")
            command = unwrap_command(command)
            scanned = strip_quoted(command)
            start_dir = harness_cwd or cur_dir
            # EVERY commit in the call, not only the first: a call can commit
            # in one worktree, move, and commit in another, and attributing
            # only the first left the second unclaimed --- so an unshipped
            # commit went unreported and the Stop was allowed.
            for commit in COMMIT.finditer(scanned):
                saw = True
                pending = command
                before = scanned[:commit.start()]
                # The commit's OWN match span, which runs from the start of
                # its git invocation through the `commit` word, so a `git -C`
                # it carries is inside it and every other one in the call is
                # outside it.
                invocation = scanned[commit.start():commit.end()]
                commit_paths |= harness_dirs | extract_named_paths(invocation)
                commit_dir = absolute_dir(shell_dir_after(before, start_dir))
                if commit_dir:
                    commit_paths.add(commit_dir)
                # Supersession applies WITHIN the call as well as between
                # calls, and is decided by the LAST head-moving command
                # before the commit rather than by all of them at once:
                # `git checkout agy-dormant && git log -1 && git checkout -
                # && git commit -m mine` ends on a move that names nothing,
                # so the inspected branch is cleared rather than inherited
                # (ai-config#2422).
                commit_branches |= branches_after(before, recent_branches)
            # The carried state is updated AFTER the commit is attributed, so
            # `git commit -m x && git checkout -` reports the branch the
            # commit landed on rather than the one the call ended on.
            recent_branches = branches_after(scanned, recent_branches)
            cur_dir = absolute_dir(shell_dir_after(scanned, start_dir, parent_only=True))
            if pending and (PUSH.search(scanned) or CREATE.search(scanned)):
                pending = None
    except Exception:
        return saw, pending, commit_branches, commit_paths
    return saw, pending, commit_branches, commit_paths


def pending_commit(path):
    return scan_transcript(path)[1]


def _default_branch_ref(cwd):
    """`origin/<default>` for `cwd`, or None when it cannot be resolved.

    Prefers `origin/HEAD` --- the remote's own configured default, set by
    `git remote set-head origin -a` or an ordinary clone --- and falls back
    to `origin/main` then `origin/master` only when that symref is unset,
    which a shallow or `--single-branch` fetch can leave absent even though
    the remote answers normally.
    """
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=10)
    except Exception:
        result = None
    if result is not None and result.returncode == 0:
        ref = result.stdout.strip()
        if ref:
            return ref
    for candidate in ("origin/main", "origin/master"):
        try:
            check = subprocess.run(
                ["git", "rev-parse", "--verify", "-q", candidate],
                cwd=cwd, capture_output=True, text=True, timeout=10)
        except Exception:
            continue
        if check.returncode == 0:
            return candidate
    return None


def _upstream_configured(cwd):
    """Whether HEAD's branch has an upstream CONFIGURED, gone ref or not.

    Distinct from whether `@{u}` RESOLVES: `git rev-list --count @{u}..HEAD`
    fails identically, and with the same exit code, whether no upstream was
    ever set or a real one was set and its remote-tracking ref later
    vanished (a squash-merged branch whose PR auto-deleted the remote
    branch) --- so that failure alone cannot tell the two apart, and the two
    want different answers. A genuinely unconfigured branch (or a detached
    HEAD) falls back to the remote's default below; a gone tracking ref
    stays undefined, because a fallback comparison against `origin/<default>`
    for a squash-merged branch counts the pre-squash commits as unshipped
    even though their content already shipped, which would newly block a
    session this hook used to leave alone.

    `branch.<name>.merge` is read purely from git config, so it still
    answers yes for a gone ref; a detached HEAD has no branch name at all
    and always answers no.
    """
    try:
        branch = subprocess.run(
            ["git", "symbolic-ref", "-q", "--short", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=10)
    except Exception:
        return False
    if branch.returncode != 0:
        return False
    name = branch.stdout.strip()
    if not name:
        return False
    try:
        cfg = subprocess.run(
            ["git", "config", "--get", f"branch.{name}.merge"],
            cwd=cwd, capture_output=True, text=True, timeout=10)
    except Exception:
        return False
    return cfg.returncode == 0 and bool(cfg.stdout.strip())


def unpushed_count(cwd):
    """Commits on HEAD that its upstream lacks, or None when git cannot say.

    `@{u}..HEAD` is ahead-only, so a branch behind its upstream counts 0 ---
    staleness is not unshippedness. A configured-but-gone upstream stays
    undefined (see `_upstream_configured`), and so does any other failure
    git cannot explain.

    NO upstream at all --- an untracked branch, or a detached HEAD --- is
    different: the branch was never told what to compare against, so
    falling back to `git rev-list --count origin/<default>..HEAD` is a real
    substitute rather than a guess, and a session sitting exactly on that
    tip has genuinely nothing to ship. A worktree left detached at
    `origin/main` with a clean tree used to read this exact case as
    undefined and block every Stop over it (ai-config#3739).
    """
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "@{u}..HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    if result.returncode == 0:
        try:
            return int(result.stdout.strip())
        except ValueError:
            return None
    if _upstream_configured(cwd):
        return None
    default_ref = _default_branch_ref(cwd)
    if not default_ref:
        return None
    try:
        fallback = subprocess.run(
            ["git", "rev-list", "--count", f"{default_ref}..HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    if fallback.returncode != 0:
        return None
    try:
        return int(fallback.stdout.strip())
    except ValueError:
        return None


def list_worktrees(cwd):
    """Return a list of worktree dicts for the git repo at cwd, or [] if unavailable.

    Each dict has:
      'path': absolute path to worktree root
      'head': commit SHA
      'branch': branch short name (or None if detached/bare)
      'detached': bool
      'bare': bool
    """
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=cwd, capture_output=True, text=True, timeout=10)
    except Exception:
        return []
    if result.returncode != 0:
        return []
    worktrees = []
    current = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            if current and "path" in current:
                worktrees.append(current)
                current = {}
            continue
        if line.startswith("worktree "):
            if current and "path" in current:
                worktrees.append(current)
                current = {}
            current["path"] = line[len("worktree "):].strip()
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD "):].strip()
        elif line.startswith("branch "):
            ref = line[len("branch "):].strip()
            if ref.startswith("refs/heads/"):
                ref = ref[len("refs/heads/"):]
            current["branch"] = ref
        elif line == "detached":
            current["detached"] = True
        elif line == "bare":
            current["bare"] = True
    if current and "path" in current:
        worktrees.append(current)
    return worktrees


def list_local_branches(cwd):
    """Return a list of (refname, upstream, track) for local branches."""
    try:
        result = subprocess.run(
            ["git", "for-each-ref", "--format=%(refname:short)|%(upstream:short)|%(upstream:track)", "refs/heads/"],
            cwd=cwd, capture_output=True, text=True, timeout=10)
    except Exception:
        return []
    if result.returncode != 0:
        return []
    branches = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        ref = parts[0]
        upstream = parts[1] if len(parts) > 1 else ""
        track = parts[2] if len(parts) > 2 else ""
        branches.append((ref, upstream, track))
    return branches


def unpushed_count_branch(cwd, branch, upstream):
    """Commits on branch that upstream lacks, or None."""
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{upstream}..refs/heads/{branch}"],
            cwd=cwd, capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def unpushed_commits_against_remotes(cwd, branch):
    """Commits on local branch that are not on any remote branch, or None."""
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"refs/heads/{branch}", "--not", "--remotes"],
            cwd=cwd, capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


PUSH_REMEDY = ("Push the branch, open or verify its PR, then report status. "
               "The standing rule is executable work, not a handoff item.")


_REVIEW_GUARD = None
_REVIEW_GUARD_LOADED = False


def _load_review_guard():
    global _REVIEW_GUARD, _REVIEW_GUARD_LOADED
    if _REVIEW_GUARD_LOADED:
        return _REVIEW_GUARD
    _REVIEW_GUARD_LOADED = True
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "no-push-without-self-review.py")
    if not os.path.isfile(path):
        return None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("no_push_without_self_review", path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _REVIEW_GUARD = module
        return module
    except Exception as exc:
        print(f"no-unshipped-commit: cannot load no-push-without-self-review.py ({exc})",
              file=sys.stderr)
        return None


def _rev_parse(cwd, rev="HEAD"):
    """40-hex commit SHA of rev in cwd, or None."""
    if not cwd or not os.path.exists(cwd):
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", rev],
            cwd=cwd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            sha = result.stdout.strip().lower()
            if re.fullmatch(r"[0-9a-f]{40}", sha):
                return sha
    except Exception:
        pass
    return None


def _current_branch(cwd):
    """The current branch name in cwd, or None if detached or unavailable."""
    if not cwd or not os.path.exists(cwd):
        return None
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            out = res.stdout.strip()
            if out and out != "HEAD":
                return out
    except Exception:
        pass
    return None


def _paths_overlap(p1, p2):
    """True if path p1 is equal to or a parent/child directory of p2."""
    if not p1 or not p2:
        return False
    try:
        p1_real = os.path.realpath(p1) if os.path.exists(p1) else p1
    except Exception:
        p1_real = p1
    try:
        p2_real = os.path.realpath(p2) if os.path.exists(p2) else p2
    except Exception:
        p2_real = p2
    p1_norm = os.path.normcase(os.path.normpath(p1_real))
    p2_norm = os.path.normcase(os.path.normpath(p2_real))
    if p1_norm == p2_norm:
        return True
    try:
        cp = os.path.normcase(os.path.commonpath([p1_norm, p2_norm]))
        return cp in (p1_norm, p2_norm)
    except Exception:
        return False


def _normalize_dir_key(d):
    """Normalize a directory path string for dictionary keying."""
    if not d:
        return ""
    try:
        d_real = os.path.realpath(d) if os.path.exists(d) else d
    except Exception:
        d_real = d
    return os.path.normcase(os.path.normpath(d_real))


def _canonical_dir(d, worktree_paths=None):
    """Map directory path d to its canonical worktree root or normalized path."""
    if not d:
        return ""
    norm = _normalize_dir_key(d)
    if not norm:
        return ""
    if worktree_paths:
        best_wt = None
        best_len = -1
        for wt_p in worktree_paths:
            if not wt_p:
                continue
            if norm == wt_p or norm.startswith(wt_p + os.sep) or norm.startswith(wt_p + "/"):
                if len(wt_p) > best_len:
                    best_len = len(wt_p)
                    best_wt = wt_p
        if best_wt is not None:
            return best_wt
    return norm


def _lookup_dir_branches(branches_by_dir, d, worktree_paths=None):
    """Lookup the set of recent branches for a directory."""
    canon = _canonical_dir(d, worktree_paths)
    if canon in branches_by_dir:
        return branches_by_dir[canon]
    if not worktree_paths:
        best_key = None
        best_len = -1
        for known_key in branches_by_dir:
            if not known_key:
                continue
            if canon.startswith(known_key + os.sep) or canon.startswith(known_key + "/"):
                if len(known_key) > best_len:
                    best_len = len(known_key)
                    best_key = known_key
        if best_key is not None:
            return branches_by_dir[best_key]
    if "" in branches_by_dir:
        return branches_by_dir[""]
    return set()


def _update_dir_branches(branches_by_dir, d, branches, worktree_paths=None):
    """Update the set of recent branches for a directory."""
    canon = _canonical_dir(d, worktree_paths)
    if not worktree_paths and canon not in branches_by_dir:
        best_key = None
        best_len = -1
        for known_key in branches_by_dir:
            if not known_key:
                continue
            if canon.startswith(known_key + os.sep) or canon.startswith(known_key + "/"):
                if len(known_key) > best_len:
                    best_len = len(known_key)
                    best_key = known_key
        if best_key is not None:
            branches_by_dir[best_key] = set(branches)
            return
    branches_by_dir[canon] = set(branches)


def _extract_dispatch_text(inp):
    """Flatten all string fields in a tool input dict/list for pattern matching."""
    texts = []
    if isinstance(inp, dict):
        for v in inp.values():
            if isinstance(v, str):
                texts.append(v)
            elif isinstance(v, (list, dict)):
                texts.append(_extract_dispatch_text(v))
    elif isinstance(inp, list):
        for item in inp:
            if isinstance(item, str):
                texts.append(item)
            elif isinstance(item, (list, dict)):
                texts.append(_extract_dispatch_text(item))
    elif isinstance(inp, str):
        texts.append(inp)
    return " ".join(texts)


def _git_common_dir(cwd):
    """Return the normalized common git dir for a repository/worktree, or ''."""
    if not cwd or not os.path.exists(cwd):
        return ""
    try:
        res = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            out = res.stdout.strip()
            if not os.path.isabs(out):
                out = os.path.normpath(os.path.join(cwd, out))
            return os.path.normcase(os.path.realpath(out))
    except Exception:
        pass
    return ""


def _is_commit_relevant(harness_dirs, commit_dir, named_paths, commit_branches, target_cwd_real, target_branch, effective_cwd=None):
    """True if a commit event is attributed to the target worktree or branch."""
    if target_cwd_real is None and target_branch is None:
        return True

    cwd_matches = False
    if target_cwd_real:
        all_paths = set(harness_dirs) | set(named_paths)
        if commit_dir:
            all_paths.add(commit_dir)
        elif effective_cwd:
            all_paths.add(effective_cwd)
        for p in all_paths:
            if _paths_overlap(p, target_cwd_real):
                cwd_matches = True
                break

    branch_matches = False
    if target_branch:
        if target_branch in commit_branches:
            branch_matches = True

    if target_cwd_real and target_branch:
        if commit_branches and target_branch not in commit_branches:
            return False
        return cwd_matches or branch_matches
    elif target_cwd_real:
        return cwd_matches
    elif target_branch:
        return branch_matches
    return False


def _is_dispatch_relevant(inp, tool_name, harness_dirs, cur_dir, target_cwd_real, target_branch,
                          head_sha, other_branches, effective_cwd=None, dispatch_branches=None,
                          current_repo_branch=None, last_commit_dir=None, dispatch_dir=None):
    """True if a reviewer dispatch targets this worktree, branch, or HEAD SHA."""
    if target_cwd_real is None and target_branch is None:
        return True

    text = _extract_dispatch_text(inp)
    text_lower = text.lower()

    if head_sha and head_sha[:7].lower() in text_lower:
        return True

    if target_branch and target_branch in text:
        return True

    if other_branches and any(ob in text for ob in other_branches):
        return False

    all_paths = set(harness_dirs)
    if cur_dir:
        all_paths.add(cur_dir)
    elif last_commit_dir:
        all_paths.add(last_commit_dir)
    elif effective_cwd:
        all_paths.add(effective_cwd)

    prompt_targets_worktree = False
    if isinstance(inp, dict):
        for k in ("Workspace", "workspace", "dir", "directory", "cwd", "Cwd"):
            v = inp.get(k)
            if isinstance(v, str) and v and v != "inherit":
                all_paths.add(v)
        prompt_text = str(
            inp.get("prompt") or inp.get("Prompt") or
            inp.get("command") or inp.get("cmd") or inp.get("CommandLine") or ""
        )
        prompt_text_lower = prompt_text.lower()
        norm_target = _normalize_dir_key(target_cwd_real)
        norm_target_slash = norm_target.replace("\\", "/").lower()
        prompt_slash = prompt_text.replace("\\", "/").lower()
        if norm_target_slash and norm_target_slash in prompt_slash:
            all_paths.add(norm_target)
            prompt_targets_worktree = True

    target_common = _git_common_dir(target_cwd_real) if target_cwd_real else ""
    cwd_matches = False
    if target_cwd_real:
        for p in all_paths:
            if _paths_overlap(p, target_cwd_real):
                cwd_matches = True
                break
            if target_common and _git_common_dir(p) == target_common:
                cwd_matches = True
                break
        if not cwd_matches:
            return False

    if target_branch and not prompt_targets_worktree:
        if dispatch_branches:
            if target_branch not in dispatch_branches:
                return False
        elif current_repo_branch and target_branch != current_repo_branch:
            return False

    return True


def _process_bash_tool_use(inp, cur_dir, branches_by_dir, target_cwd_real, target_branch,
                           head_sha, other_branches, effective_cwd, current_repo_branch,
                           guard, worktree_paths=None, last_commit_dir=None):
    """Process a bash/command invocation for commits, directory moves, and reviewer dispatches.

    Returns (new_cur_dir, commit_seen, dispatch_seen, commit_seen_dir).
    """
    harness_dirs, harness_cwd = set(), None
    if isinstance(inp, dict):
        for key in ("cwd", "workdir", "Cwd", "WorkingDirectory", "path"):
            val = inp.get(key)
            if isinstance(val, str) and val:
                harness_dirs.add(val)
                if harness_cwd is None:
                    harness_cwd = val

    cmd = str(inp.get("command") or inp.get("cmd") or inp.get("CommandLine") or inp.get("script") or "") if isinstance(inp, dict) else ""
    command = unwrap_command(cmd)
    scanned = strip_quoted(command)
    start_dir = harness_cwd or cur_dir or effective_cwd

    commit_seen = False
    commit_seen_dir = None
    for commit in COMMIT.finditer(scanned):
        before = scanned[:commit.start()]
        invocation = scanned[commit.start():commit.end()]
        commit_paths = harness_dirs | extract_named_paths(invocation)
        commit_dir = absolute_dir(shell_dir_after(before, start_dir))
        dir_before = commit_dir or start_dir
        dir_branches = _lookup_dir_branches(branches_by_dir, dir_before, worktree_paths)
        commit_branches = branches_after(before, dir_branches)
        if _is_commit_relevant(harness_dirs, commit_dir, commit_paths, commit_branches,
                               target_cwd_real, target_branch, effective_cwd=effective_cwd):
            commit_seen = True
            commit_seen_dir = dir_before

    end_dir = absolute_dir(shell_dir_after(scanned, start_dir, parent_only=True))
    target_update_dir = end_dir or start_dir
    dir_branches = _lookup_dir_branches(branches_by_dir, target_update_dir, worktree_paths)
    new_dir_branches = branches_after(scanned, dir_branches)
    _update_dir_branches(branches_by_dir, target_update_dir, new_dir_branches, worktree_paths)

    new_cur_dir = end_dir

    dispatch_seen = False
    if guard.external_reviewer_command(cmd) or "pre-push-review" in cmd:
        dispatch_dir = end_dir or start_dir
        dispatch_branches = _lookup_dir_branches(branches_by_dir, dispatch_dir, worktree_paths)
        if _is_dispatch_relevant(inp, "bash", harness_dirs, cur_dir, target_cwd_real,
                                target_branch, head_sha, other_branches,
                                effective_cwd=effective_cwd,
                                dispatch_branches=dispatch_branches,
                                current_repo_branch=current_repo_branch,
                                last_commit_dir=last_commit_dir,
                                dispatch_dir=dispatch_dir):
            dispatch_seen = True

    return new_cur_dir, commit_seen, dispatch_seen, commit_seen_dir


def _process_agent_tool_use(inp, tool_name, cur_dir, branches_by_dir, target_cwd_real,
                            target_branch, head_sha, other_branches, effective_cwd,
                            current_repo_branch, guard, worktree_paths=None, last_commit_dir=None):
    """Process an agent/subagent tool use for reviewer dispatch.

    Returns True if this invocation is a relevant reviewer dispatch.
    """
    if not (tool_name in guard.AGENT_TOOLS and tool_name not in guard.TASK_OUTPUT_TOOLS):
        return False
    if not (isinstance(inp, dict) and guard._is_reviewer_dispatch(inp)):
        return False

    agent_dirs = set()
    agent_cwd = None
    for key in ("cwd", "workdir", "Cwd", "WorkingDirectory", "path"):
        val = inp.get(key)
        if isinstance(val, str) and val:
            agent_dirs.add(val)
            if agent_cwd is None:
                agent_cwd = val

    dispatch_dir = agent_cwd or cur_dir or last_commit_dir or effective_cwd
    dispatch_branches = _lookup_dir_branches(branches_by_dir, dispatch_dir, worktree_paths)

    return _is_dispatch_relevant(inp, tool_name, agent_dirs, cur_dir, target_cwd_real,
                                target_branch, head_sha, other_branches,
                                effective_cwd=effective_cwd,
                                dispatch_branches=dispatch_branches,
                                current_repo_branch=current_repo_branch,
                                last_commit_dir=last_commit_dir,
                                dispatch_dir=dispatch_dir)


def _collect_worktrees_and_branches(cwd, session_cwd, target_branch):
    """Collect known other branches and worktree paths to disambiguate dispatches.

    Deduplicates list_worktrees invocations when cwd and session_cwd point
    to the same repository.
    """
    other_branches = set()
    worktree_paths = set()
    seen_common_dirs = set()
    seen_dirs = set()

    for is_cwd, d in ((True, cwd), (False, session_cwd)):
        if not d:
            continue
        norm_d = _normalize_dir_key(d)
        if not norm_d or norm_d in seen_dirs:
            continue
        seen_dirs.add(norm_d)

        # Deduplicate if this repository's common dir was already inspected
        common_dir = _git_common_dir(d)
        if common_dir:
            if common_dir in seen_common_dirs:
                continue
            seen_common_dirs.add(common_dir)
        elif norm_d in worktree_paths:
            continue

        try:
            for wt in list_worktrees(d):
                p = wt.get("path")
                if p:
                    worktree_paths.add(_normalize_dir_key(p))
                if is_cwd:
                    b = wt.get("branch")
                    if b and b != target_branch:
                        other_branches.add(b)
            if is_cwd:
                for b, _, _ in list_local_branches(d):
                    if b != target_branch:
                        other_branches.add(b)
        except Exception:
            pass

    return other_branches, worktree_paths


def _sha_matches(sha1, sha2):
    """True if sha1 and sha2 match on a 7-character prefix."""
    if not sha1 or not sha2:
        return False
    return sha1.startswith(sha2[:7]) or sha2.startswith(sha1[:7])


def _has_completed_head_review(guard, path, head_sha):
    """Check if guard already records a completed review covering head_sha."""
    if not head_sha:
        return False
    try:
        verdict, reviewed_commits, _ = guard.read_latest_review(path)
        if verdict in ("clean", "needs_work"):
            return any(_sha_matches(sha, head_sha) for sha in reviewed_commits)
    except Exception:
        pass
    return False


def is_push_held_by_blocking_review(cwd, path, branch=None):
    """True if the latest self-review is blocking and names this HEAD.

    `no-push-without-self-review.py` refuses every push while the latest
    verdict is blocking, so demanding a push of the very commit that verdict
    read leaves no way to end the turn while the fix round runs, typically in
    a subagent (ai-config#3270). The work owed is the fix, not the push. Once
    a fix commit moves HEAD past the reviewed commit, this is False again and
    the ordinary demand returns, since re-dispatching the reviewer is then a
    step the session can take.
    """
    if not path or not os.path.isfile(path) or not cwd:
        return False
    guard = _load_review_guard()
    if guard is None:
        return False
    head_sha = _rev_parse(cwd, branch or "HEAD")
    if not head_sha:
        return False
    try:
        verdict, reviewed_commits, _ = guard.read_latest_review(path)
    except Exception:
        return False
    return verdict == "needs_work" and any(
        _sha_matches(sha, head_sha) for sha in reviewed_commits)


def is_push_deferred(cwd, path, branch=None, session_cwd=None):
    """True when the push guard would rightly refuse the push this hook asks for."""
    return (is_pre_push_review_in_flight(cwd, path, branch=branch, session_cwd=session_cwd)
            or is_push_held_by_blocking_review(cwd, path, branch=branch))


def _is_verdict_covering_head(text, guard, head_sha, path=None, call_id=None):
    """True if text contains a review report covering head_sha."""
    found, shas = guard.parse_report_all(text or "")
    if not found and path and call_id:
        handback_text = guard._handback_report_text(path, call_id, text or "")
        if handback_text:
            found, shas = guard.parse_report_all(handback_text)
    if found:
        if not head_sha or not shas or any(_sha_matches(s, head_sha) for s in shas):
            return True
    return False


class _TranscriptScanner:
    """Scans transcript records to detect in-flight pre-push review dispatches."""

    def __init__(self, guard, path, head_sha, target_cwd_real, target_branch,
                 other_branches, effective_cwd, current_repo_branch, worktree_paths):
        self.guard = guard
        self.path = path
        self.head_sha = head_sha
        self.target_cwd_real = target_cwd_real
        self.target_branch = target_branch
        self.other_branches = other_branches
        self.effective_cwd = effective_cwd
        self.current_repo_branch = current_repo_branch
        self.worktree_paths = worktree_paths

        self.seq = 0
        self.omo_seq = 0
        self.last_commit_seq = None
        self.last_commit_dir = None
        self.last_dispatch_seq = None
        self.last_verdict_seq = None
        self.reviewer_call_ids = set()
        self.active_reviewer_task_ids = set()
        # Hand-backs whose sender is not yet a known reviewer id: the harness
        # writes the queue-operation enqueue before the dispatch result that
        # carries the agent id, so these are re-checked as ids register.
        self.pending_handbacks = []
        self.pending_omo_uses = {}
        self.ambiguous_omo_names = set()
        self.cur_dir = None
        self.branches_by_dir = {}

    def _matches_head_verdict(self, text, call_id=None):
        return _is_verdict_covering_head(text, self.guard, self.head_sha,
                                         path=self.path, call_id=call_id)

    def handle_omo_record(self, record, r_type, omo_name):
        """Process OpenCode/OMO style tool_use or tool_result record."""
        name = omo_name.lower()
        if r_type == "tool_use":
            self.seq += 1
            self.omo_seq += 1
            call_id = f"omo-{self.omo_seq}"
            self.pending_omo_uses.setdefault(name, []).append(call_id)
            inp = record.get("tool_input")
            if name in {"bash", "run_command", "terminal", "execute_command", "shell"}:
                self.cur_dir, commit_seen, dispatch_seen, commit_dir = _process_bash_tool_use(
                    inp, self.cur_dir, self.branches_by_dir, self.target_cwd_real,
                    self.target_branch, self.head_sha, self.other_branches,
                    self.effective_cwd, self.current_repo_branch, self.guard,
                    worktree_paths=self.worktree_paths, last_commit_dir=self.last_commit_dir)
                if commit_seen:
                    self.last_commit_seq = self.seq
                    self.last_commit_dir = commit_dir or self.cur_dir
                if dispatch_seen:
                    self.last_dispatch_seq = self.seq
                    self.reviewer_call_ids.add(call_id)
            elif _process_agent_tool_use(inp, name, self.cur_dir, self.branches_by_dir,
                                         self.target_cwd_real, self.target_branch,
                                         self.head_sha, self.other_branches,
                                         self.effective_cwd, self.current_repo_branch,
                                         self.guard, worktree_paths=self.worktree_paths,
                                         last_commit_dir=self.last_commit_dir):
                self.last_dispatch_seq = self.seq
                self.reviewer_call_ids.add(call_id)
        else:
            queue = self.pending_omo_uses.get(name) or []
            if len(queue) > 1 or name in self.ambiguous_omo_names:
                self.ambiguous_omo_names.add(name)
                self.pending_omo_uses[name] = []
                return
            call_id = queue.pop(0) if queue else None
            if call_id is not None and call_id in self.reviewer_call_ids:
                self.seq += 1
                if not record.get("is_error"):
                    out_text = self.guard._result_text({"content": record.get("tool_output")})
                    tid_match = re.search(r"\b(?:task[-_ ]?id|conversationId|agent[-_ ]?id)[:=]\s*[`\"']?([\w-]+)", out_text, re.I) or re.search(r"message from [`\"']?agent-?([\w-]+)[`\"']?", out_text, re.I)
                    if tid_match:
                        self.active_reviewer_task_ids.add(tid_match.group(1))
                        self.active_reviewer_task_ids.add(f"agent-{tid_match.group(1)}")
                    self._resolve_pending_handbacks()
                    if self._matches_head_verdict(out_text):
                        self.last_verdict_seq = self.seq

    def handle_reviewer_record(self, record):
        """Process reviewer records such as subagent handback messages."""
        if self.guard._is_reviewer_record(record):
            self.seq += 1
            msg_text = self.guard._result_text(
                record.get("message") if isinstance(record.get("message"), dict) else record
            )
            if self._matches_head_verdict(msg_text):
                self.last_verdict_seq = self.seq

    def handle_task_notification(self, record):
        """Process async task notification events from background tasks."""
        origin = record.get("origin")
        if isinstance(origin, dict) and origin.get("kind") in ("task-notification", "task_notification"):
            self.seq += 1
            origin_ids = self.guard._task_ids(origin, self.guard.TASK_ID_KEYS_ORIGIN)
            sender_id = str(record.get("sender") or "")
            if any(t in self.active_reviewer_task_ids for t in origin_ids) or (
                    sender_id and sender_id in self.active_reviewer_task_ids):
                content_text = str(record.get("content") or record.get("text") or "")
                if self._matches_head_verdict(content_text):
                    self.last_verdict_seq = self.seq

    def handle_subagent_handback(self, record):
        """Process a subagent hand-back carrying a review verdict.

        A hand-back counts only when a harness-written field names its sender
        and that sender is one of this session's reviewer dispatch ids -- the
        same rule the push guard applies (ai-config#3045). Text that merely
        quotes a hand-back marker, as a Read result or a pasted report can, is
        not a hand-back.
        """
        if not self.reviewer_call_ids and not self.active_reviewer_task_ids:
            return
        if self.guard._is_assistant_record(record):
            return
        for sender_ids, text in self.guard._handback_candidates(record):
            # A candidate naming no sender can never be tracked, so it is
            # refused here rather than queued for a recheck that cannot pass.
            if not text or not sender_ids:
                continue
            if self._sender_is_tracked(sender_ids):
                self._accept_handback(text)
            else:
                self.pending_handbacks.append((sender_ids, text))

    def _sender_is_tracked(self, sender_ids):
        return any(self.guard._id_is_tracked(s, self.active_reviewer_task_ids)
                   for s in sender_ids)

    def _accept_handback(self, text):
        if self._matches_head_verdict(text):
            self.seq += 1
            self.last_verdict_seq = self.seq

    def _resolve_pending_handbacks(self):
        """Accept queued hand-backs whose sender has since registered."""
        still_pending = []
        for sender_ids, text in self.pending_handbacks:
            if self._sender_is_tracked(sender_ids):
                self._accept_handback(text)
            else:
                still_pending.append((sender_ids, text))
        self.pending_handbacks = still_pending

    def handle_block(self, b, record):
        """Process an individual tool_use or tool_result block."""
        b_type = b.get("type")
        if b_type == "tool_use":
            self.seq += 1
            tool_name = (b.get("name") or "").lower()
            call_id = b.get("id")
            inp = b.get("input") or {}

            if tool_name in {"bash", "run_command", "terminal", "execute_command", "shell"}:
                self.cur_dir, commit_seen, dispatch_seen, commit_dir = _process_bash_tool_use(
                    inp, self.cur_dir, self.branches_by_dir, self.target_cwd_real,
                    self.target_branch, self.head_sha, self.other_branches,
                    self.effective_cwd, self.current_repo_branch, self.guard,
                    worktree_paths=self.worktree_paths, last_commit_dir=self.last_commit_dir)
                if commit_seen:
                    self.last_commit_seq = self.seq
                    self.last_commit_dir = commit_dir or self.cur_dir
                if dispatch_seen:
                    self.last_dispatch_seq = self.seq
                    if call_id:
                        self.reviewer_call_ids.add(call_id)
            elif _process_agent_tool_use(inp, tool_name, self.cur_dir, self.branches_by_dir,
                                         self.target_cwd_real, self.target_branch,
                                         self.head_sha, self.other_branches,
                                         self.effective_cwd, self.current_repo_branch,
                                         self.guard, worktree_paths=self.worktree_paths,
                                         last_commit_dir=self.last_commit_dir):
                self.last_dispatch_seq = self.seq
                if call_id:
                    self.reviewer_call_ids.add(call_id)
            elif tool_name == "send_message" and self.guard._is_reviewer_record(record):
                self.seq += 1
                msg_text = str(inp.get("Message") or inp.get("message") or "")
                if self._matches_head_verdict(msg_text):
                    self.last_verdict_seq = self.seq

        elif b_type == "tool_result":
            call_id = b.get("tool_use_id")
            if call_id and call_id in self.reviewer_call_ids:
                self.seq += 1
                if b.get("is_error"):
                    if self.last_dispatch_seq is not None:
                        self.last_dispatch_seq = None
                else:
                    res_text = self.guard._result_text(b)
                    try:
                        res_data = json.loads(res_text)
                        if isinstance(res_data, dict):
                            for tid in self.guard._registrable_task_ids(res_data):
                                self.active_reviewer_task_ids.add(tid)
                    except Exception:
                        pass
                    tid_match = re.search(r"\b(?:task[-_ ]?id|conversationId|agent[-_ ]?id)[:=]\s*[`\"']?([\w-]+)", res_text, re.I) or re.search(r"message from [`\"']?agent-?([\w-]+)[`\"']?", res_text, re.I)
                    if tid_match:
                        self.active_reviewer_task_ids.add(tid_match.group(1))
                        self.active_reviewer_task_ids.add(f"agent-{tid_match.group(1)}")
                    self._resolve_pending_handbacks()

                    if self._matches_head_verdict(res_text, call_id=call_id):
                        self.last_verdict_seq = self.seq

    def scan_record(self, record):
        """Scan a single parsed record line."""
        r_type = record.get("type")
        omo_name = record.get("tool_name")
        if r_type in ("tool_use", "tool_result") and isinstance(omo_name, str):
            self.handle_omo_record(record, r_type, omo_name)
            return

        self.handle_reviewer_record(record)
        self.handle_task_notification(record)

        self.handle_subagent_handback(record)

        for b in self.guard._iter_blocks(record):
            self.handle_block(b, record)

    def is_in_flight(self):
        """Determine whether review is in flight after scanning."""
        if self.last_dispatch_seq is None:
            return False
        if self.last_commit_seq is not None and self.last_commit_seq > self.last_dispatch_seq:
            return False
        if self.last_verdict_seq is not None and self.last_verdict_seq >= self.last_dispatch_seq:
            return False
        return True


def is_pre_push_review_in_flight(cwd, path, branch=None, session_cwd=None):
    """True if an adversarial pre-push review of HEAD is in flight.

    When Claude Code or Antigravity backgrounds an Agent or subagent review
    dispatch (e.g. Remote Control active or background agent isolation), the
    tool result is an async launch stub (e.g. `agentId: ...` or `status: running`),
    and task `output_file` remains at 0 bytes while running. Polling `output_file`
    for `Reviewed-Commit` never matches. The verdict arrives only via a subagent
    hand-back message after the turn ends.
    Meanwhile `no-unshipped-commit.py` as a Stop hook detects unpushed commits and
    blocks the turn from ending. The agent then attempts `git push`, which is refused
    by `no-push-without-self-review.py` ("no verdict came back as that call's own result").
    This creates an infinite deadlock loop (ai-config#4109).

    This predicate detects when a reviewer dispatch has occurred after the latest
    commit, and no review verdict (CLEAN or NEEDS WORK) covering the current HEAD has
    arrived yet. If so, `decide()` allows the turn to stop cleanly so the background
    reviewer can complete and deliver its verdict.

    Scoped per worktree and branch: commits and dispatches only affect the
    calculation for the specific worktree or branch they target, tracking
    working directories and checked-out branches to prevent cross-worktree or
    cross-branch suppression.
    """
    if not path or not os.path.isfile(path):
        return False
    guard = _load_review_guard()
    if guard is None:
        return False

    target_cwd_real = None
    if cwd:
        try:
            target_cwd_real = os.path.realpath(cwd) if os.path.exists(cwd) else cwd
        except Exception:
            target_cwd_real = cwd

    effective_cwd = None
    ref_cwd = session_cwd or cwd
    if ref_cwd:
        try:
            effective_cwd = os.path.realpath(ref_cwd) if os.path.exists(ref_cwd) else ref_cwd
        except Exception:
            effective_cwd = ref_cwd

    current_repo_branch = _current_branch(cwd) if cwd else None
    target_branch = branch or current_repo_branch
    head_sha = _rev_parse(cwd, target_branch or "HEAD") if cwd else None

    # Collect known other branches and worktree paths to disambiguate dispatches
    other_branches, worktree_paths = _collect_worktrees_and_branches(cwd, session_cwd, target_branch)

    # If read_latest_review already found a verdict covering current HEAD, review completed.
    if _has_completed_head_review(guard, path, head_sha):
        return False

    # Scan the transcript to check if a reviewer dispatch occurred after the latest commit
    scanner = _TranscriptScanner(
        guard=guard, path=path, head_sha=head_sha,
        target_cwd_real=target_cwd_real, target_branch=target_branch,
        other_branches=other_branches, effective_cwd=effective_cwd,
        current_repo_branch=current_repo_branch, worktree_paths=worktree_paths,
    )

    try:
        with open(path, encoding="utf-8", errors="ignore") as stream:
            for line in stream:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                if isinstance(record, dict):
                    scanner.scan_record(record)
    except Exception:
        return False

    return scanner.is_in_flight()


def decide(cwd, path):
    """The Stop verdict: the block reason, or "" to allow the stop.

    The transcript scan gates whether to look; `git rev-list --count
    @{u}..HEAD` across checkouts and branches answers (ai-config#2727,
    ai-config#2737). Inspects all linked worktrees of the repo
    via `git worktree list --porcelain` and unpushed local branches this
    session COMMITTED on, to detect unshipped session commits left across
    checkouts or on switched branches. Relevance is the payload `cwd` plus
    the commit-scoped sets `scan_transcript` derives, so another tool's
    dormant worktree the session merely visited is not this session's debt
    (ai-config#2422).
    Without a `cwd` in the hook payload, repository state is unknowable,
    so the verdict falls back to the transcript scan --- the old behaviour,
    fail-safe rather than blind.
    """
    saw_commit, pending, commit_branches, commit_paths = scan_transcript(path)
    if not saw_commit:
        return ""
    if not cwd:
        if not pending:
            return ""
        if is_push_deferred(cwd, path):
            return ""
        return ("A commit was made with no later push or PR creation, and "
                "repository state is unavailable to check. " + PUSH_REMEDY)

    worktrees = list_worktrees(cwd)
    if not worktrees:
        count = unpushed_count(cwd)
        if count == 0:
            return ""
        if count is None:
            if not pending:
                return ""
            if is_push_deferred(cwd, path):
                return ""
            return ("The unshipped count for this branch is undefined --- no "
                    "upstream is configured, or git failed to answer --- and the "
                    "transcript shows a commit with no later push or PR "
                    "creation. " + PUSH_REMEDY)
        if is_push_deferred(cwd, path):
            return ""
        return f"{count} commit(s) on HEAD are not on its upstream. {PUSH_REMEDY}"

    unpushed_wts = []
    undefined_wts = []
    checked_out_branches = set()
    cwd_real = os.path.realpath(cwd) if os.path.exists(cwd) else cwd
    commit_paths_real = set()
    for p in commit_paths:
        try:
            commit_paths_real.add(os.path.realpath(p))
        except Exception:
            commit_paths_real.add(p)

    for wt in worktrees:
        if wt.get("bare"):
            continue
        wt_path = wt.get("path") or ""
        wt_path_real = os.path.realpath(wt_path) if os.path.exists(wt_path) else wt_path
        wt_branch = wt.get("branch")

        # Only check checkouts this session committed in (cwd, commit paths,
        # or commit branches). cwd or a commit path may be a nested
        # subdirectory inside the worktree root.
        is_cwd_in_wt = False
        try:
            is_cwd_in_wt = (os.path.commonpath([cwd_real, wt_path_real]) == wt_path_real)
        except (ValueError, Exception):
            is_cwd_in_wt = (cwd_real == wt_path_real)

        is_commit_in_wt = False
        for p in commit_paths_real:
            try:
                if os.path.commonpath([p, wt_path_real]) == wt_path_real:
                    is_commit_in_wt = True
                    break
            except (ValueError, Exception):
                if p == wt_path_real:
                    is_commit_in_wt = True
                    break

        is_relevant = is_cwd_in_wt or is_commit_in_wt or (wt_branch and wt_branch in commit_branches)
        if not is_relevant:
            continue

        if wt_branch:
            checked_out_branches.add(wt_branch)
        count = unpushed_count(wt_path)
        if count is not None and count > 0:
            if not is_push_deferred(wt_path, path, branch=wt_branch, session_cwd=cwd):
                unpushed_wts.append((wt, count))
        elif count is None:
            if not is_push_deferred(wt_path, path, branch=wt_branch, session_cwd=cwd):
                undefined_wts.append(wt)

    # Check switched-away branches (local branches this session committed on,
    # not checked out in any worktree)
    unpushed_branches = []
    if commit_branches:
        for branch, upstream, _ in list_local_branches(cwd):
            if branch not in commit_branches:
                continue
            if branch in checked_out_branches:
                continue
            if upstream:
                b_count = unpushed_count_branch(cwd, branch, upstream)
                if b_count is not None and b_count > 0:
                    if not is_push_deferred(cwd, path, branch=branch, session_cwd=cwd):
                        unpushed_branches.append((branch, b_count))
            elif pending:
                b_count = unpushed_commits_against_remotes(cwd, branch)
                if b_count is not None and b_count > 0:
                    if not is_push_deferred(cwd, path, branch=branch, session_cwd=cwd):
                        unpushed_branches.append((branch, b_count))

    if unpushed_wts or unpushed_branches or (pending and undefined_wts):
        if len(unpushed_wts) == 1 and not unpushed_branches and not (pending and undefined_wts):
            wt, count = unpushed_wts[0]
            wt_real = os.path.realpath(wt["path"]) if os.path.exists(wt["path"]) else wt["path"]
            if wt_real == cwd_real:
                return f"{count} commit(s) on HEAD are not on its upstream. {PUSH_REMEDY}"
            else:
                branch_info = f" (branch '{wt['branch']}')" if wt.get("branch") else " (detached HEAD)"
                return f"{count} commit(s) on worktree '{wt['path']}'{branch_info} are not on its upstream. {PUSH_REMEDY}"
        elif not unpushed_wts and len(unpushed_branches) == 1 and not (pending and undefined_wts):
            branch, count = unpushed_branches[0]
            return f"{count} commit(s) on branch '{branch}' are not on its upstream. {PUSH_REMEDY}"
        elif not unpushed_wts and not unpushed_branches and len(undefined_wts) == 1:
            wt = undefined_wts[0]
            wt_real = os.path.realpath(wt["path"]) if os.path.exists(wt["path"]) else wt["path"]
            if wt_real == cwd_real or len(worktrees) == 1:
                return ("The unshipped count for this branch is undefined --- no "
                        "upstream is set and unpushed commits cannot be verified. "
                        "Set an upstream or push before ending the turn.")
            else:
                branch_info = f" (branch '{wt['branch']}')" if wt.get("branch") else ""
                return (f"The unshipped count for worktree '{wt['path']}'{branch_info} is undefined --- no "
                        "upstream is set and unpushed commits cannot be verified. "
                        "Set an upstream or push before ending the turn.")
        else:
            items = []
            for wt, count in unpushed_wts:
                wt_real = os.path.realpath(wt["path"]) if os.path.exists(wt["path"]) else wt["path"]
                if wt_real == cwd_real:
                    loc = f"HEAD (branch '{wt['branch']}')" if wt.get("branch") else "HEAD"
                else:
                    branch_info = f" (branch '{wt['branch']}')" if wt.get("branch") else " (detached HEAD)"
                    loc = f"worktree '{wt['path']}'{branch_info}"
                items.append(f"{count} commit(s) on {loc} are not on its upstream")
            for branch, count in unpushed_branches:
                items.append(f"{count} commit(s) on branch '{branch}' are not on its upstream")
            if pending:
                for wt in undefined_wts:
                    branch_info = f" (branch '{wt['branch']}')" if wt.get("branch") else ""
                    items.append(f"worktree '{wt['path']}'{branch_info} has undefined unshipped count (no upstream set)")
            return f"{'; '.join(items)}. {PUSH_REMEDY}"

    if not undefined_wts:
        return ""

    if not pending:
        return ""

    if len(undefined_wts) == 1:
        wt = undefined_wts[0]
        wt_real = os.path.realpath(wt["path"]) if os.path.exists(wt["path"]) else wt["path"]
        if wt_real == cwd_real or len(worktrees) == 1:
            return ("The unshipped count for this branch is undefined --- no "
                    "upstream is configured, or git failed to answer --- and the "
                    "transcript shows a commit with no later push or PR "
                    "creation. " + PUSH_REMEDY)
        else:
            branch_info = f" (branch '{wt['branch']}')" if wt.get("branch") else ""
            return (f"The unshipped count for worktree '{wt['path']}'{branch_info} is undefined --- no "
                    "upstream is configured, or git failed to answer --- and the "
                    "transcript shows a commit with no later push or PR "
                    "creation. " + PUSH_REMEDY)

    return ("The unshipped count for one or more worktrees is undefined --- no "
            "upstream is configured, or git failed to answer --- and the "
            "transcript shows a commit with no later push or PR "
            "creation. " + PUSH_REMEDY)


# In a project-thread session every user-visible sentence is the `text` input
# of an `mcp__hearthbot__reply` tool call, never an assistant text block.
# Measured on ai-config#3798: a reader that only walks `type == "text"` blocks
# is blind to the whole reply.
REPLY_TOOL_RX = re.compile(r"(^|__)(reply|post_message|update_message)$", re.I)


def _reply_payload(block):
    """The user-visible text of a reply-tool call, or '' for any other block."""
    if not isinstance(block, dict) or block.get("type") != "tool_use":
        return ""
    if not REPLY_TOOL_RX.search(block.get("name") or ""):
        return ""
    inp = block.get("input")
    if not isinstance(inp, dict):
        return ""
    txt = inp.get("text")
    return txt if isinstance(txt, str) else ""


def last_assistant_text(path):
    last_text = ""
    last_reply = ""
    saw_reply_tool = False
    try:
        with open(path, encoding="utf-8", errors="ignore") as stream:
            for line in stream:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if record.get("type") == "assistant" or record.get("role") == "assistant":
                    blocks = (record.get("message") or {}).get("content") or record.get("content") or []
                    if isinstance(blocks, list):
                        text = "".join(
                            b.get("text", "") for b in blocks
                            if isinstance(b, dict) and b.get("type") == "text"
                        )
                        if text.strip():
                            last_text = text
                        for b in blocks:
                            if isinstance(b, dict) and b.get(
                                "type"
                            ) == "tool_use" and REPLY_TOOL_RX.search(
                                b.get("name") or ""
                            ):
                                saw_reply_tool = True
                            payload = _reply_payload(b)
                            if payload.strip():
                                last_reply = payload
                    elif isinstance(blocks, str) and blocks.strip():
                        last_text = blocks
                if record.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or record.get("source") == "MODEL":
                    content = record.get("content")
                    if isinstance(content, str) and content.strip():
                        last_text = content
                    elif isinstance(content, list):
                        text = "".join(
                            (b.get("text", "") if isinstance(b, dict) else str(b))
                            for b in content
                        )
                        if text.strip():
                            last_text = text
    except Exception:
        return ""
    chosen = last_reply if saw_reply_tool else last_text
    return chosen if chosen.strip() else ""


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    path = payload.get("transcript_path") or ""
    if not path:
        return
    reason = decide(payload.get("cwd") or "", path)
    if not reason:
        return
    # ai-config#3739: the sentinel used to key on
    # sha256(path + reason + last_assistant_text(path)). Including the reply
    # text meant a differently-worded reply produced a fresh key every time,
    # so an unchanged unshipped state re-blocked on every single Stop --- the
    # measured incident was eight consecutive blocks in one session, none of
    # them suppressed, because no two replies were byte-identical. Dropping
    # the text keys the sentinel on (path, reason) alone: a genuinely
    # unchanged state (same transcript, same derived reason) is suppressed
    # after the first block. `reason` names only counts and paths, never a
    # commit, so the key also carries the tip SHA of every local branch and
    # worktree HEAD: a new unshipped commit at the same count (push A, then
    # commit B) changes the key and blocks once again (#4010 review).
    key = hashlib.sha256(
        (path + reason + _state_fingerprint(payload.get("cwd") or "")).encode()
    ).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-unshipped-commit-{key}")
    if os.path.exists(sentinel):
        return
    open(sentinel, "w", encoding="utf-8").close()
    print(json.dumps({"decision": "block", "reason": reason}))


def _state_fingerprint(cwd):
    """Tip SHAs of every local branch and worktree HEAD, or "" when git fails.

    Folded into the sentinel key so the once-per-state suppression is per
    commit, not per count. An empty result falls back to (path, reason).
    """
    if not cwd:
        return ""
    parts = []
    for args in (["for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/"],
                 ["worktree", "list", "--porcelain"]):
        try:
            out = subprocess.run(["git", "-C", cwd, *args], capture_output=True,
                                 text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return ""
        if out.returncode != 0:
            return ""
        parts.append(out.stdout)
    return "\n".join(parts)


if __name__ == "__main__":
    main()
