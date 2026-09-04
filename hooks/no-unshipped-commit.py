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
    from shellcmd import resolve_cd_target, simple_commands, strip_env
except Exception as _exc:  # broken install; fail open and say so
    print(f"no-unshipped-commit: cannot load scripts/lib/shellcmd.py "
          f"({_exc}); not tracking the shell's directory", file=sys.stderr)
    resolve_cd_target = simple_commands = strip_env = None

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
_GIT_FLAGS = r"(?:-(?:C\s*\S+|c\s*\S+|[a-zA-Z0-9_-]+(?:=\S*)?)\s+|--[a-zA-Z0-9_-]+(?:=\S*)?\s+)*"
COMMIT = re.compile(r"(?:^|[;&|\n])\s*" + _ENV + r"git\s+" + _GIT_FLAGS + r"commit(?![\w-])", re.MULTILINE)
PUSH = re.compile(r"(?:^|[;&|\n])\s*" + _ENV + r"git\s+" + _GIT_FLAGS + r"push(?![\w-])", re.MULTILINE)
CREATE = re.compile(r"(?:^|[;&|\n])\s*" + _ENV + r"gh\s+pr\s+create\b", re.MULTILINE)

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
WORKTREE_ADD_CMD = re.compile(
    r"(?:^|[;&|\n])\s*" + _ENV + r"git\s+worktree\s+add\s+([^;&|\n]+)",
    re.MULTILINE
)
BRANCH_CMD = re.compile(
    r"(?:^|[;&|\n])\s*" + _ENV + r"git\s+(?:checkout|switch|branch)\s+([^;&|\n]+)",
    re.MULTILINE
)
# Calls that MOVE HEAD, as opposed to merely naming a branch. Matched for
# their own sake rather than for the names they carry: `git checkout -`
# switches back and names nothing, and a switch that names nothing still has
# to supersede the branch a commit would otherwise inherit (ai-config#2422).
#
# Three near-misses are excluded, because supersession CLEARS the carried
# branch and clearing on a call that moved nothing loses the switched-branch
# attribution ai-config#2737 added. `git branch feature` creates without
# switching. `git worktree add <path> <branch>` creates a second checkout and
# leaves this one exactly where it stood, so it belongs beside `git branch`
# rather than here --- and its `-b` form still supersedes, through the branch
# name it names rather than through this pattern. `git checkout -p` stages
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
# A cheap pre-filter for `shell_dir_after`. Parsing every call's argv would
# run `shlex` twice per Bash call across a whole transcript, and a Stop hook
# has to answer promptly; a command carrying none of these three words moves
# the shell nowhere, so the parse has nothing to find. `(?![\w-])` again, so
# `cdate` and `cd-into` do not arm it.
DIR_MOVE = re.compile(r"(?:^|[;&|\n(]|\s)(?:cd|pushd|popd)(?![\w-])", re.MULTILINE)


def switches_branch(command):
    """Whether this command moves HEAD, whether or not it names a branch."""
    for m in SWITCH_CMD.finditer(command):
        args = m.group(1).split()
        if any(a in PATCH_FLAGS for a in args):
            continue
        return True
    return False


def shell_dir_after(text, cur_dir):
    """The directory the shell stands in after `text`, given `cur_dir` before.

    `None` means INDETERMINATE, never "unchanged": `cd -`, `popd`, a `$VAR`
    target, and an unparseable command each move the shell somewhere this
    scan cannot name, so nothing after them may inherit the directory they
    left. That is the whole of ai-config#2422's directory half --- a session
    that visits a dormant foreign worktree and then returns must not attribute
    its own later commit to the worktree it visited.
    """
    if simple_commands is None or not DIR_MOVE.search(text):
        return cur_dir
    argvs = simple_commands(text)
    if argvs is None:
        return None
    for argv in argvs:
        _, rest = strip_env(argv)
        if rest and rest[0] in ("cd", "pushd", "popd"):
            cur_dir = resolve_cd_target(rest, cur_dir)
    return cur_dir


def absolute_dir(path):
    """`path` when it names a directory absolutely, else None.

    A relative target resolved against an unknown starting directory comes
    back as the literal the user typed (`hooks`), which no worktree path can
    be compared against. Dropping it is the honest answer.
    """
    return path if path and os.path.isabs(path) else None


def extract_named_paths(command):
    """Directories a command NAMES without moving the shell into them.

    `git -C <dir>` and `git worktree add <path>` both point at a repository
    while leaving the shell where it stood, so they attribute a commit on
    their own and need no carrying forward. Where the shell IS standing is
    tracked separately by `shell_dir_after`, because a `cd` persists across
    tool calls while this function sees one call.
    """
    paths = set()
    for m in GIT_C_CMD.finditer(command):
        p = m.group(1).strip("\"'").strip()
        if p:
            paths.add(p)
    for m in WORKTREE_ADD_CMD.finditer(command):
        args = m.group(1).split()
        for arg in args:
            if arg.startswith("-") or arg == "add":
                continue
            p = arg.strip("\"'").strip()
            if p and ("/" in p or os.path.exists(p)):
                paths.add(p)
    return paths


def extract_touched_branches(command):
    """Extract branch names touched by checkout/switch/branch/worktree add commands."""
    branches = set()
    for m in BRANCH_CMD.finditer(command):
        args = m.group(1).split()
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
    for m in WORKTREE_ADD_CMD.finditer(command):
        args = m.group(1).split()
        for i, arg in enumerate(args):
            if arg in ("-b", "-B") and i + 1 < len(args):
                branches.add(args[i + 1])
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
    is what makes both halves narrow. The directory is the one `cd` calls
    EARLIER IN THE SAME CALL leave the shell in, over the harness-recorded
    working directory of that call, over the directory carried from the
    previous call --- so `git commit -m x && cd /elsewhere` attributes where
    the shell stood, not where it ends up. The branch is the one named
    earlier in the same call, and otherwise the branch carried forward.
    A `git -C <dir>` or `git worktree add <path>` anywhere in a committing
    call names a repository directly and attributes on its own.

    Both carried values are SUPERSEDED by a later call that moves the shell
    even when that call names nothing: `git checkout -` and `cd -` move away
    while yielding no name, and `popd` and a bare `cd` do too, so inspecting
    a dormant worktree or branch and then returning leaves the dormant one
    unattributed (ai-config#2422). Attribution is per commit rather than per
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
            call_branches = extract_touched_branches(scanned)
            commit = COMMIT.search(scanned)
            if commit:
                saw = True
                pending = command
                before = scanned[:commit.start()]
                commit_paths |= harness_dirs | extract_named_paths(scanned)
                commit_dir = absolute_dir(shell_dir_after(before, start_dir))
                if commit_dir:
                    commit_paths.add(commit_dir)
                commit_branches |= extract_touched_branches(before) or recent_branches
            # The carried state is updated AFTER the commit is attributed, so
            # `git commit -m x && git checkout -` reports the branch the
            # commit landed on rather than the one the call ended on.
            if switches_branch(scanned) or call_branches:
                recent_branches = call_branches
            cur_dir = absolute_dir(shell_dir_after(scanned, start_dir))
            if pending and (PUSH.search(scanned) or CREATE.search(scanned)):
                pending = None
    except Exception:
        return saw, pending, commit_branches, commit_paths
    return saw, pending, commit_branches, commit_paths


def pending_commit(path):
    return scan_transcript(path)[1]


def unpushed_count(cwd):
    """Commits on HEAD that its upstream lacks, or None when git cannot say.

    `@{u}..HEAD` is ahead-only, so a branch behind its upstream counts 0 ---
    staleness is not unshippedness. No upstream, a detached HEAD, and a gone
    upstream branch all exit non-zero and return None: the count is
    undefined there, and the caller falls back to the transcript verdict.
    """
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "@{u}..HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip())
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
            return ("The unshipped count for this branch is undefined --- no "
                    "upstream is configured, or git failed to answer --- and the "
                    "transcript shows a commit with no later push or PR "
                    "creation. " + PUSH_REMEDY)
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
            unpushed_wts.append((wt, count))
        elif count is None:
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
                    unpushed_branches.append((branch, b_count))
            elif pending:
                b_count = unpushed_commits_against_remotes(cwd, branch)
                if b_count is not None and b_count > 0:
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


def last_assistant_text(path):
    last = ""
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
                            last = text
                    elif isinstance(blocks, str) and blocks.strip():
                        last = blocks
                if record.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or record.get("source") == "MODEL":
                    content = record.get("content")
                    if isinstance(content, str) and content.strip():
                        last = content
                    elif isinstance(content, list):
                        text = "".join(
                            (b.get("text", "") if isinstance(b, dict) else str(b))
                            for b in content
                        )
                        if text.strip():
                            last = text
    except Exception:
        return ""
    return last


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
    text = last_assistant_text(path)
    key = hashlib.sha256((path + reason + text).encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-unshipped-commit-{key}")
    if os.path.exists(sentinel):
        return
    open(sentinel, "w").close()
    print(json.dumps({"decision": "block", "reason": reason}))


if __name__ == "__main__":
    main()
