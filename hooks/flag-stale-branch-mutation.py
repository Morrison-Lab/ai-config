#!/usr/bin/env python3
"""PreToolUse guard: a mutating git command runs on a branch this SESSION did
not select, because something else silently switched the checkout in between.

## The incident

    1. git checkout main && git checkout -b fix/909-spellcheck-awk-newline
       -- verified: `git branch --show-current` printed the new branch.
    2. Several tool calls of ordinary work (edits, test runs).
    3. Concurrently, an `adversarial-reviewer` subagent ran WITHOUT worktree
       isolation, in the SAME checkout. Its own git commands left the
       checkout on a different branch, fix/892-slurm-env-and-srun-status.
    4. The session ran `git commit` -- it landed on fix/892, not fix/909.
       Then `git push -u origin fix/909-spellcheck-awk-newline` -- git
       pushes the NAMED ref, not HEAD, so it pushed the unchanged fix/909
       ref and reported success, printing the usual "Create a pull request
       for fix/909-spellcheck-awk-newline" hint.
    5. The mistake surfaced only when `gh pr create` failed with "No commits
       between main and fix/909-spellcheck-awk-newline".

Nothing warned at any of steps 2-4. The push even looked like success.

## Why a hook rather than a prose rule

`CLAUDE.md`'s "Check the remote immediately before every push" already tells
a session to verify state before pushing, and it did not help here: the
session HAD verified its checkout, at step 1 -- the rule was followed and the
mistake happened anyway, because the branch changed AFTER the verification,
in a tool call the session never issued itself. The one artifact that could
show the drift is the live `git` state at the moment of the LATER mutating
command, which nothing reads unless something is built to read it
--- `shared/principles/deterministic-tools.md`'s point that a rule is
consulted at read time and broken at composition time.

## Why this is a SEPARATE hook from flag-unchained-branch-switch.py

That sibling hook catches a switch and a mutation UNCHAINED within one Bash
call -- the `&&` on line 1 protects only line 1, so a later line in the SAME
command string runs on whatever branch is actually checked out. It has no
memory across tool calls: every invocation of it sees one `command` string in
isolation.

This incident is a different shape. The checkout succeeded, and the mutating
commands were each in their OWN, syntactically unremarkable Bash call --
`git commit -m "..."` on one line, `git push -u origin <branch>` on another.
Nothing about either command, read on its own, is wrong. The defect is only
visible by comparing what THIS session most recently, explicitly selected
against what is actually checked out right now -- which requires state that
survives between separate PreToolUse invocations, because each one is a
separate process with no memory of the last. This hook is the state.

## What is tracked, and how

Only an EXPLICIT selection counts: `git checkout <branch>` / `git checkout -b
<branch>` / `git switch <branch>` / `git switch -c <branch>`, all captured
only at a git command position (never inside a quoted string, a comment, or a
heredoc body -- see `_mask_noncommands`). Whenever this session's own Bash
call contains one, its target branch is written to a small per-session,
per-repository state file (`tempfile.gettempdir()`, keyed by a hash of the
session id and the repository's `--git-common-dir`, matching
`no-unauthorized-merge.py`'s `resolve_session_id` and per-repo registry
pattern). Nothing else -- not a `commit`, not a `push`, not the subagent's own
commands under a different session id -- ever writes to it.

A later Bash call carrying a MUTATING git command (`commit`, `merge`,
`cherry-pick`, `revert`, `rebase`) or a `git push` naming an explicit branch
is compared against that state, but ONLY by taking a fresh, live reading of
the actually-checked-out branch at the moment of the hook call (`git branch
--show-current` in the tool's own `cwd`) -- never by reasoning about what the
subagent, or anyone else, might have done. That is deliberate: the hook does
not need to know WHO changed the branch, only that the checkout the session
last explicitly selected and the checkout that is about to receive a mutation
are not the same one.

A Bash call that ITSELF contains an explicit switch is exempted entirely,
regardless of what mutating commands follow it in the same call -- that is
the ordinary "just checked out, now committing on it" case, and
`flag-unchained-branch-switch.py` already owns whether such a switch is
safely chained to what follows it in the SAME command string. This hook's
job starts where that one's ends: after the switch has already run, in a
call of its own.

## The push special case

A `git push -u origin <B>` / `git push origin <B>` whose `<B>` is the branch
the session most recently selected, while the checked-out branch is actually
something else, gets its own sharper message: `git push` pushes the NAMED
ref, not `HEAD`. It does not care what is checked out, it prints the usual
"Create a pull request for <B>" hint regardless, and it reports success --
which is exactly what happened in the incident, and it is "the one with no
other detector" this task exists to close, because nothing else in this
corpus reads the target of a push against session state.

DELIBERATELY NOT gated on the push naming SOME OTHER branch the checked-out
branch differs from: `git push origin main` while sitting on a feature
branch, or `git push origin some-other-branch:some-other-branch` from a
scripted sync, are ordinary and do not imply anything went wrong -- the
pushed ref does not have to be the checked-out one for a push to be correct.
The signal here is narrower and sharper: the NAMED branch is the one THIS
session itself explicitly selected earlier, and the checkout has since moved
away from it without the session doing so itself.

## WARNS, never blocks

Whether the drift matters is a judgment this hook cannot make -- the mutation
landing on the current branch may be exactly what is wanted, and a session
can always intend to work on whatever is actually checked out regardless of
what it selected earlier. Per README's "A hook that misfires is worse than a
missing one" this only ever adds context: no `permissionDecision` is ever
emitted, so the normal permission flow is untouched.

Fails OPEN and SILENT on: a non-git `cwd`, a detached `HEAD` (`git branch
--show-current` returns empty, which is not treated as a branch to compare
against), no session id resolvable, no prior explicit selection recorded this
session (nothing to compare against), and any git/subprocess trouble.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Never persist (or trust) a selection older than this. A leftover /tmp file
# from a stale or reused session id should not silently indict a checkout
# from hours ago.
TTL_SECONDS = 6 * 60 * 60

# Same construction as `no-unshipped-commit.py`'s `_ENV` / `_GIT_FLAGS` --
# linear, no self-ambiguous repetition under a shared quantifier, per
# `shared/coding/regex-backtracking-pitfalls.md` (the same clause was the
# fix in ai-config#3172). Reused rather than re-derived so this hook inherits
# an already-reviewed-safe pattern instead of a new one.
_ENV = r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
_GIT_FLAGS = r"(?:-(?:C\s*\S+|c\s*\S+|[a-zA-Z0-9_-]+(?:=\S*)?)\s+|--[a-zA-Z0-9_-]+(?:=\S*)?\s+)*"
_CMD_START = r"(?:^|[;&|\n])\s*"

SWITCH = re.compile(
    _CMD_START + _ENV + r"git\s+" + _GIT_FLAGS +
    r"(?P<sub>checkout|switch)(?![\w-])(?P<rest>[^\n;&|]*)",
    re.MULTILINE,
)
MUTATE = re.compile(
    _CMD_START + _ENV + r"git\s+" + _GIT_FLAGS +
    r"(?P<sub>commit|merge|cherry-pick|revert|rebase)(?![\w-])",
    re.MULTILINE,
)
PUSH = re.compile(
    _CMD_START + _ENV + r"git\s+" + _GIT_FLAGS +
    r"push(?![\w-])(?P<rest>[^\n;&|]*)",
    re.MULTILINE,
)

# `<<TAG` / `<<-TAG` / `<<'TAG'`, but never `<<<` (a herestring, no body).
# Verbatim from `flag-unchained-branch-switch.py`'s proven heredoc stripper.
HEREDOC = re.compile(r"(?<!<)<<(?P<dash>-?)\s*(?P<q>['\"]?)"
                     r"(?P<tag>[A-Za-z_][A-Za-z0-9_]*)(?P=q)(?!<)")

COMMENT = re.compile(r"(?:^|(?<=\s))#[^\n]*")


def _strip_heredocs(command):
    """Drop heredoc bodies, so a mentioned command inside one is not real."""
    lines = command.split("\n")
    kept = []
    i = 0
    while i < len(lines):
        line = lines[i]
        kept.append(line)
        i += 1
        match = HEREDOC.search(line)
        if not match:
            continue
        tag = match.group("tag")
        dash = match.group("dash")
        while i < len(lines):
            probe = lines[i].strip() if dash else lines[i].rstrip()
            i += 1
            if probe == tag:
                break
    return "\n".join(kept)


def _mask_quotes(command):
    """Blank quoted spans (length-preserving) so a git command mentioned
    inside a commit message or a quoted string is never read as a real
    command position. A masked quote can only make a match DISAPPEAR, never
    appear, which is the safe direction for a warn-only guard."""
    out = []
    i = 0
    n = len(command)
    while i < n:
        ch = command[i]
        if ch == "'":
            j = command.find("'", i + 1)
            end = n if j == -1 else j + 1
            out.append(" " * (end - i))
            i = end
            continue
        if ch == '"':
            j = i + 1
            while j < n:
                if command[j] == "\\":
                    j += 2
                    continue
                if command[j] == '"':
                    break
                j += 1
            end = n if j >= n else j + 1
            out.append(" " * (end - i))
            i = end
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _preprocess(command):
    """Heredoc bodies stripped, then quotes masked, then comments blanked --
    in that order, because a heredoc's own delimiter can be quoted (`<<'EOF'`)
    and must still be recognized before quote-masking would blank it away."""
    text = _strip_heredocs(command)
    text = _mask_quotes(text)
    text = COMMENT.sub(lambda m: " " * len(m.group(0)), text)
    return text


def _looks_like_pathspec(tok, cwd):
    """True when `git checkout <tok>` is restoring a file, not selecting a branch.

    `git checkout` is overloaded: with no `--` it takes either a branch or a
    pathspec, and `git checkout .` to discard local edits is routine. Reading
    that as a branch selection writes a bogus name into the session's tracked
    state, so every later mutating command is compared against it and warns.
    A false positive on an ordinary, undrifted command is exactly what this
    hook exists not to do.

    `git switch` never takes a pathspec, so this test applies to `checkout`
    alone.

    Two independent signals, either sufficient:

    - The token is shaped like a path. `.`, `..`, and anything starting
      `./`, `../` or `/` cannot be a branch name -- git rejects a ref
      component of `.` or `..` outright.
    - The token names something that exists on disk relative to `cwd`.
      A branch and a path of the same name is the ambiguous case git itself
      refuses without `--`, so declining to guess matches git's own
      behaviour.

    A glob is deliberately NOT treated as a pathspec here: `git check-ref-format`
    forbids `*` and `?` in a ref, so such a token never reaches this hook as a
    plausible branch name, and matching one against the filesystem would mean
    expanding it.
    """
    if tok in (".", ".."):
        return True
    if tok.startswith("./") or tok.startswith("../") or tok.startswith("/"):
        return True
    if cwd:
        try:
            return os.path.exists(os.path.join(cwd, tok))
        except (OSError, ValueError):
            return False
    return False


def _selected_branch(rest, sub="checkout", cwd=None):
    """The branch a `checkout`/`switch` command targets, or None.

    `-b`/`-B`/`-c`/`-C` create-and-switch, so the token right after one of
    them is the target. A bare `--` (file-restore form, `checkout -- path`)
    or a lone `-` (previous-branch shortcut, ambiguous without more context)
    resolve to nothing rather than a guess -- silence is the safe direction
    here, not a wrong branch name.

    The same safe direction governs a `checkout` whose operand looks like a
    pathspec: see `_looks_like_pathspec`. A token following an explicit
    `-b`/`-B`/`-c`/`-C` is exempt, because those flags name a branch to
    create and admit no pathspec at all.
    """
    tokens = rest.split()
    create_next = False
    for tok in tokens:
        if create_next:
            return tok
        if tok in ("-b", "-B", "-c", "-C"):
            create_next = True
            continue
        if tok in ("--", "-"):
            return None
        if tok.startswith("-"):
            continue
        if sub == "checkout" and _looks_like_pathspec(tok, cwd):
            return None
        return tok
    return None


def _push_target(rest):
    """The branch a `git push <remote> <branch>` command names, or None.

    Requires an EXPLICIT remote and branch (skips a bare `git push` / `git
    push origin`, which push whatever is checked out via the upstream
    tracking configuration and are not the failure this hook exists for).
    """
    tokens = [t for t in rest.split() if not t.startswith("-")]
    if len(tokens) < 2:
        return None
    branch = tokens[1]
    if branch.startswith("+"):
        branch = branch[1:]
    if ":" in branch:
        branch = branch.split(":", 1)[0]
    if branch.startswith("refs/heads/"):
        branch = branch[len("refs/heads/"):]
    return branch or None


def resolve_session_id(payload):
    """Same lookup order as `no-unauthorized-merge.py`'s `resolve_session_id`:
    the harness's own session id, then the transcript filename stem, then
    environment forms."""
    for key in ("session_id", "sessionId", "sessionID", "conversation_id", "conversationId"):
        sid = payload.get(key)
        if isinstance(sid, str) and sid.strip():
            return sid.strip()
    tpath = payload.get("transcript_path") or payload.get("transcriptPath")
    if isinstance(tpath, str) and tpath.strip():
        stem = Path(tpath.strip()).stem
        if stem:
            return stem
    return os.environ.get("AI_SESSION_ID") or os.environ.get("CLAUDE_SESSION_ID")


def _git(cwd, args, timeout=5):
    try:
        out = subprocess.run(["git", "-C", cwd] + args, capture_output=True,
                             text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def _repo_id(cwd):
    """A stable identity for the repository at `cwd`, or None outside one."""
    out = _git(cwd, ["rev-parse", "--git-common-dir"])
    if out is None:
        return None
    p = out.strip()
    if not p:
        return None
    if not os.path.isabs(p):
        p = os.path.normpath(os.path.join(cwd, p))
    return p


def _current_branch(cwd):
    """The actually-checked-out branch, or None (detached HEAD, or a git/
    subprocess failure -- both fail silent, never crash)."""
    out = _git(cwd, ["branch", "--show-current"])
    if out is None:
        return None
    branch = out.strip()
    return branch or None


def _state_path(session_id, repo_id):
    key = hashlib.sha256(f"{session_id}\n{repo_id}".encode()).hexdigest()[:16]
    return os.path.join(tempfile.gettempdir(), f".claude-branch-select-{key}.json")


def _load_state(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    branch = data.get("branch")
    ts = data.get("ts")
    if not isinstance(branch, str) or not branch:
        return None
    if isinstance(ts, (int, float)) and (time.time() - ts) > TTL_SECONDS:
        return None
    return branch


def _save_state(path, branch):
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"branch": branch, "ts": time.time()}, fh)
    except Exception:
        pass


MUTATE_NOTE = (
    "This session explicitly checked out `{selected}` earlier, but the "
    "branch actually checked out right now is `{actual}` -- a `git {sub}` "
    "about to run will land on `{actual}`, not `{selected}`.\n\n"
    "Nothing else would have reported this: the checked-out branch can "
    "change between Bash calls -- another agent running git commands "
    "unisolated in the same checkout, a peer session, a human -- with no "
    "error printed anywhere. The 2026-09-04 incident this guards against: a "
    "subagent ran without worktree isolation and left the checkout on its "
    "own branch; the session's next `git commit` landed there silently.\n\n"
    "If `{actual}` really is where this belongs, ignore this. Otherwise "
    "check out `{selected}` again before running it."
)

PUSH_NOTE = (
    "This session explicitly checked out `{selected}` earlier, and this "
    "`git push` names that SAME branch (`{branch}`), but the branch "
    "actually checked out right now is `{actual}`.\n\n"
    "`git push` pushes the NAMED ref, not `HEAD` -- it will push whatever "
    "local `{branch}` currently points at, print the usual \"Create a pull "
    "request for {branch}\" hint, and report success, regardless of what "
    "just happened on `{actual}`. That is exactly how a commit silently "
    "lands on the wrong branch's push: the only place it surfaces is a "
    "later `No commits between main and {branch}` from `gh pr create`.\n\n"
    "Check out `{branch}` again before pushing, or push `{actual}` if that "
    "is really what you meant."
)


def evaluate(command, cwd, session_id):
    """Return a warning message, or None."""
    text = _preprocess(command)

    switch_matches = list(SWITCH.finditer(text))
    mutate_matches = list(MUTATE.finditer(text))
    push_matches = list(PUSH.finditer(text))

    if not switch_matches and not mutate_matches and not push_matches:
        return None

    repo_id = _repo_id(cwd)
    if repo_id is None:
        return None
    state_path = _state_path(session_id, repo_id)

    if switch_matches:
        # An explicit switch anywhere in THIS call is recorded REGARDLESS of
        # whether this same call also carries a mutate/push -- a bare
        # `git checkout -b X` call is exactly how the session's selection
        # gets established for a LATER call to compare against, and it must
        # not be skipped just because nothing else is in this command.
        #
        # It is also the ordinary "just checked out, now committing on it"
        # case whenever a mutate/push DOES follow in the same call, and that
        # case must stay silent here. Whether it is safely CHAINED to what
        # follows it in this same command string is
        # flag-unchained-branch-switch.py's job, not this one's.
        target = None
        for m in switch_matches:
            branch = _selected_branch(m.group("rest"), m.group("sub"), cwd)
            if branch:
                target = branch
        if target:
            _save_state(state_path, target)
        return None

    if not mutate_matches and not push_matches:
        return None

    selected = _load_state(state_path)
    if selected is None:
        return None  # nothing explicitly selected yet this session

    actual = _current_branch(cwd)
    if actual is None:
        return None  # detached HEAD, or the read failed

    if actual == selected:
        return None  # no drift

    for m in push_matches:
        branch = _push_target(m.group("rest"))
        if branch and branch == selected:
            return PUSH_NOTE.format(selected=selected, actual=actual, branch=branch)

    if mutate_matches:
        subs = ", ".join(sorted({m.group("sub") for m in mutate_matches}))
        return MUTATE_NOTE.format(selected=selected, actual=actual, sub=subs)

    return None


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
        print(f"flag-stale-branch-mutation: unreadable hook input ({exc})",
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

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    command = tool_input.get("command") or tool_input.get("CommandLine") or tool_input.get("cmd") or tool_input.get("script")
    if not isinstance(command, str) or not command.strip():
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    cwd = payload.get("cwd") or os.getcwd()

    session_id = resolve_session_id(payload)
    if not session_id:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    try:
        note = evaluate(command, cwd, session_id)
    except Exception as exc:  # fail open on any parse or subprocess trouble
        print(f"flag-stale-branch-mutation: could not evaluate command ({exc})",
              file=sys.stderr)
        return 0

    if note is None:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    # No `permissionDecision` key at all: an absent decision defers to the
    # normal permission flow. Naming "allow" here would BYPASS a prompt the
    # user would otherwise have seen, which is more permissive than no hook.
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": note,
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            "Branch may have drifted since this session last checked one out "
            "explicitly -- see additionalContext for the selected vs. actual "
            "branch."
        )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
