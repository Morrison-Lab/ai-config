#!/usr/bin/env python3
"""PreToolUse deny: no routine merge of main into a PR branch (ai-config#5988).

Ezra, 2026-11-20, chose "Make it permanent" on stopping main merges: each one
re-runs a PR's whole CI and voids its review, and routine merges helped queue
499 lds runs on 2026-11-19 (Morrison-Lab/lds#2992). Denies, on Bash,
`git merge` and `git pull` of main, master or origin/HEAD's branch (any ref
form, or a `FETCH_HEAD` holding one), through `cd`, `git -C` and `bash -c`,
unless the current branch is that branch, the merge changes nothing, or:
(a) the branch conflicts with main (`git merge-tree --write-tree`);
(b) a `MERGE_MAIN_FOR=<sha>` or `MERGE_MAIN_FOR='#<N>'` prefix on the git
    command names a commit on main the branch lacks, or a PR whose `(#N)` or
    `Merge pull request #N` subject is on main and not on the branch;
(c) main changed `.github/workflows/` since the merge base, a superset of
    `check-pr-fully-clean.py`'s stale-head refusal (ai-config#2982).
Also denies `update_pull_request_branch`, `gh pr update-branch` and
`gh api .../update-branch`, which cannot say why; merge locally instead.
No bare override: `MERGE_MAIN_FOR` passes only when it names a real fix, and
a session-wide value is ignored. A `FETCH_HEAD` fetched on the same line is
read as the remote-tracking ref, so fetch main in its own command first.
Fails open on helper, parse or git trouble (git before 2.38 lacks
`merge-tree --write-tree`). Rule: shared/workflow/sync-with-main.md.
"""

import json
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.realpath(__file__))
try:
    sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "scripts", "lib"))
    from shellcmd import (simple_commands_with_scope, walk_dirs, git_subcommand,
                          env_value, nested_shell_commands, strip_env)
    from sibling import load_sibling
    _STASH = load_sibling(__file__, "no-bare-stash-pop.py", "_nbsp")
except Exception as _exc:  # broken install: degrade, never block
    print(f"no-routine-main-merge: helpers did not load ({_exc})", file=sys.stderr)
    _STASH = None

SHELL_TOOLS = {"Bash", "bash", "run_command", "execute_command", "terminal", "shell"}
REASON_VAR = "MERGE_MAIN_FOR"
MAIN_NAMES = {"main", "master"}
PR_TOKEN = re.compile(r"(?:[\w.-]+/[\w.-]+)?#?(\d{1,7})")
SHA_TOKEN = re.compile(r"[0-9a-fA-F]{7,40}")
NO_OP_FLAGS = {"--abort", "--continue", "--quit", "--skip", "-h", "--help"}
MERGE_VALUE_OPTS = {"-m", "-F", "--file", "-s", "--strategy", "-X",
                    "--strategy-option", "--cleanup", "--into-name"}
PULL_VALUE_OPTS = {"-s", "--strategy", "-X", "--strategy-option", "--depth",
                   "--deepen", "--shallow-since", "--shallow-exclude", "-j",
                   "--jobs", "--upload-pack", "--negotiation-tip",
                   "--recurse-submodules-default", "-o", "--server-option"}
RULE = ("A PR branch takes main only when (a) it conflicts with main, (b) it "
        "needs a fix on main, named with a MERGE_MAIN_FOR=<sha> or "
        "MERGE_MAIN_FOR='#<PR>' prefix on this git command, or (c) main "
        "changed .github/workflows since the merge base (the runner checker's "
        "stale rule). Every main merge re-runs the PR's CI and voids its "
        "review; routine merges helped queue 499 lds runs on 2026-11-19 "
        "(Ezra, 2026-11-20: \"Make it permanent\"). Fetch main in its own "
        "command first, so the check reads the current main. "
        "Rule: shared/workflow/sync-with-main.md.")
DENY = "Refused: `{segment}` merges {target} into `{branch}`, and {why}. " + RULE
SERVER_DENY = ("Refused: updating a PR branch from its base on the server "
               "cannot show that the branch needs main. " + RULE +
               " If it does, merge locally (`git merge origin/main`, with "
               "MERGE_MAIN_FOR when the reason is (b)) and push.")


def git(cwd, *args):
    """`(returncode, stdout)` of `git -C cwd args`, or `(None, "")` on error."""
    try:
        p = subprocess.run(["git", "-C", cwd, *args], capture_output=True,
                           text=True, timeout=15, encoding="utf-8")
    except (OSError, subprocess.SubprocessError):
        return None, ""
    return p.returncode, p.stdout.strip()


def git_out(cwd, *args):
    code, out = git(cwd, *args)
    return out if code == 0 else None


def default_names(cwd):
    """`main`, `master`, and the branch origin/HEAD points at."""
    names = set(MAIN_NAMES)
    head = git_out(cwd, "symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD")
    if head and "/" in head:
        names.add(head.split("/", 1)[1])
    return names


def is_main_name(name, names):
    """True for `main`, `origin/main`, `refs/remotes/<r>/main`,
    `refs/heads/main`, and the same forms of the origin/HEAD branch."""
    tail = re.sub(r"^(?:refs/heads/|refs/remotes/[^/]+/|[^/]+/)", "", name)
    return tail in names


def fetch_head_branches(cwd):
    """Branch names `FETCH_HEAD` marks for merge, from the file."""
    path = git_out(cwd, "rev-parse", "--git-path", "FETCH_HEAD")
    if not path:
        return []
    path = path if os.path.isabs(path) else os.path.join(cwd, path)
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        if "\tnot-for-merge\t" in line:
            continue
        m = re.search(r"\tbranch '([^']+)' of ", line)
        if m:
            out.append(m.group(1))
    return out


def positionals(rest, value_opts):
    """Non-option arguments of `rest`, skipping option values; None when a
    no-op flag (`--abort`, `--continue`, help) makes the command change
    nothing."""
    rest = _strip_redirections(rest)
    out, i = [], 0
    while i < len(rest):
        a = rest[i]
        if a == "--":
            out.extend(rest[i + 1:])
            break
        if a in NO_OP_FLAGS:
            return None
        if a.startswith("-"):
            i += 2 if a in value_opts else 1
            continue
        out.append(a)
        i += 1
    return out


def _strip_redirections(rest):
    out, i = [], 0
    while i < len(rest):
        redir = _STASH.REDIR.match(rest[i])
        nxt = rest[i + 1] if i + 1 < len(rest) else ""
        if rest[i].isdigit() and _STASH.REDIR.match(nxt):
            i += 1
        elif redir:
            i += 1 if redir.group(1) else 2
        else:
            out.append(rest[i])
            i += 1
    return out


def main_targets(sub, rest, cwd, fetched):
    """`(label, ref)` pairs: each main-like thing the command merges in, with
    the local ref that stands for it."""
    names = default_names(cwd)
    if sub == "merge":
        args = positionals(rest, MERGE_VALUE_OPTS)
        if not args:
            return []
        out = []
        for a in args:
            if a == "FETCH_HEAD":
                if fetched is not None:
                    remote, branches = fetched
                    out += [(f"FETCH_HEAD ({b})", f"refs/remotes/{remote}/{b}")
                            for b in branches if b in names]
                else:
                    out += [(f"FETCH_HEAD ({b})", "FETCH_HEAD")
                            for b in fetch_head_branches(cwd) if b in names][:1]
            elif is_main_name(a, names):
                out.append((a, a))
        return out
    if sub == "pull":
        args = positionals(rest, PULL_VALUE_OPTS)
        if not args or len(args) < 2:
            return []
        remote = args[0]
        out = []
        for spec in args[1:]:
            src = spec.lstrip("+").split(":", 1)[0]
            src = re.sub(r"^refs/heads/", "", src)
            if src in names:
                out.append((f"{remote} {src}", f"refs/remotes/{remote}/{src}"))
        return out
    return []


def fetched_branches(sub, rest):
    """`(remote, [branch...])` for a `git fetch <remote> <refspec>...`."""
    if sub != "fetch":
        return None
    args = positionals(rest, PULL_VALUE_OPTS) or []
    if len(args) < 2:
        return None
    return args[0], [re.sub(r"^refs/heads/", "", s.lstrip("+").split(":", 1)[0])
                     for s in args[1:]]


def named_fix_present(cwd, ref, value):
    """`(ok, detail)` for a MERGE_MAIN_FOR value: ok when every named commit
    or PR is on `ref` and not yet on HEAD."""
    tokens = [t for t in re.split(r"[,\s]+", value or "") if t]
    if not tokens:
        return False, f"{REASON_VAR} is empty"
    log = git_out(cwd, "log", "--format=%s", f"HEAD..{ref}")
    if log is None:
        return False, "the commits main has and the branch lacks could not be read"
    subjects = log.splitlines()
    for tok in tokens:
        if "#" not in tok and SHA_TOKEN.fullmatch(tok) and git_out(
                cwd, "rev-parse", "--verify", "-q", tok + "^{commit}"):
            on_main = git(cwd, "merge-base", "--is-ancestor", tok, ref)[0] == 0
            on_head = git(cwd, "merge-base", "--is-ancestor", tok, "HEAD")[0] == 0
            if not on_main or on_head:
                return False, (f"commit {tok} is "
                               + ("already on the branch" if on_head else "not on main"))
            continue
        m = PR_TOKEN.fullmatch(tok)
        if m:
            n = m.group(1)
            pat = re.compile(rf"\(#{n}\)|Merge pull request #{n}\b")
            if not any(pat.search(s) for s in subjects):
                return False, (f"no commit on main that the branch lacks "
                               f"names PR #{n}")
            continue
        return False, f"{REASON_VAR} value {tok!r} names no commit or PR"
    return True, ""


def why_not_needed(cwd, ref, env):
    """None when the merge is allowed, else why it is routine."""
    if git(cwd, "merge-base", "--is-ancestor", ref, "HEAD")[0] == 0:
        return None  # already merged: nothing changes
    code, _out = git(cwd, "merge-tree", "--write-tree", "--no-messages", "HEAD", ref)
    if code is None or code not in (0, 1):
        return None  # old git or error: fail open
    if code == 1:
        return None  # (a) conflict
    base = git_out(cwd, "merge-base", "HEAD", ref)
    if base is None:
        return None
    changed = git_out(cwd, "diff", "--name-only", base, ref, "--", ".github/workflows")
    if changed is None or changed:
        return None  # (c) stale by the checker's rule (or unreadable)
    value = env_value(env, REASON_VAR)
    if value is not None:
        ok, detail = named_fix_present(cwd, ref, value)
        return None if ok else f"{detail}, so (b) does not hold"
    return ("it does not conflict, main changed no workflow since the merge "
            "base, and the command names no fix it needs")


def is_server_update(argv):
    _env, rest = strip_env(argv)
    if not rest or os.path.basename(rest[0]) != "gh":
        return False
    if rest[1:3] == ["pr", "update-branch"]:
        return True
    return len(rest) > 1 and rest[1] == "api" and any(
        re.search(r"/pulls/[^/\s]+/update-branch/?$", a) for a in rest[2:])


def evaluate(command, cwd, depth=0):
    """The deny reason, or None."""
    if _STASH is None:
        return None
    fetched = None
    for argv, env, _rest, cur in walk_dirs(
            simple_commands_with_scope(command) or [], cwd):
        if is_server_update(argv):
            return SERVER_DENY
        if cur is None or any(env_value(env, v) is not None
                              for v in ("GIT_DIR", "GIT_WORK_TREE")):
            continue
        for inner in nested_shell_commands(argv) if depth < 3 else []:
            reason = evaluate(inner, cur, depth + 1)
            if reason:
                return reason
        sub, rest, genv = git_subcommand(argv) or (None, [], [])
        dirs, ok = _STASH._git_dir_opt(argv)
        for d in dirs:
            cur = os.path.normpath(os.path.join(cur, os.path.expanduser(d)))
        if not ok or sub is None:
            continue
        got = fetched_branches(sub, rest)
        if got:
            fetched = got
            continue
        if sub not in ("merge", "pull"):
            continue
        branch = git_out(cur, "symbolic-ref", "-q", "--short", "HEAD") or "HEAD"
        if branch in default_names(cur):
            continue
        for label, ref in main_targets(sub, rest, cur, fetched):
            if not git_out(cur, "rev-parse", "--verify", "-q", ref + "^{commit}"):
                continue  # git itself will refuse an unknown ref
            why = why_not_needed(cur, ref, genv or env)
            if why:
                return DENY.format(segment=" ".join(argv), target=label,
                                   branch=branch, why=why)
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    tool = payload.get("tool_name") or ""
    reason = None
    if isinstance(tool, str) and tool.endswith("update_pull_request_branch"):
        reason = SERVER_DENY
    elif tool in SHELL_TOOLS:
        inp = payload.get("tool_input")
        command = inp.get("command") if isinstance(inp, dict) else None
        cwd = payload.get("cwd")
        if not isinstance(cwd, str) or not os.path.isabs(cwd):
            cwd = os.getcwd()
        try:
            reason = evaluate(command, cwd) if isinstance(command, str) else None
        except Exception as exc:  # fail open
            print(f"no-routine-main-merge: could not evaluate ({exc})", file=sys.stderr)
            return 0
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
