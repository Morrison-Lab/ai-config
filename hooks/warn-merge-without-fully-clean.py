#!/usr/bin/env python3
"""PreToolUse warning: `gh pr merge N` with no passing fully-clean run for N.

## The failure this exists for

On 2026-10-08 a session merged ai-config#4383 and ai-config#4396 under the
standing ai-config `mwc` grant. The decision rested on `gh pr checks`,
`mergeStateStatus`, and a hand-parse of the latest review-data JSON.
`scripts/check-pr-fully-clean.py` ran only afterwards, when a Stop hook
objected to the "fully clean" wording. Both PRs happened to be clean, but the
merge ran ahead of the instrument that authorizes it (ai-config#4399).

`no-unauthorized-merge.py` gates PERMISSION to merge. Nothing at PreToolUse
tied the merge to CLEANLINESS, and the Stop-time siblings
(`no-stale-pr-status.py`, `no-incomplete-check-enumeration.py`) only see the
prose claim after the fact, not the merge command itself.

## The condition

Decidable from the transcript, so a hook rather than a rule to remember:

    the command merges PR N   (`gh pr merge N`, or the MCP merge tool)
    AND NOT  some earlier Bash call ran `scripts/check-pr-fully-clean.py N`
             whose result shows the "is FULLY CLEAN" line
             AND that call came AFTER the last `git push` in the transcript
    AND NOT  the same command runs the instrument for N before the merge,
             joined to it by `&&` only (a `;` or `||` join, a `git push`
             between them, or a pipe on the instrument does not discharge)

The evidence is POSITIVE only. An empty result, a backgrounded run ("Command
running in background with ID: ...") and a result that merely lacks an error
say nothing about the verdict, so silence is never read as success.

Also recognised as a merge: `gh api -X PUT|--method PUT .../pulls/N/merge`.

A push moves the head, and a clean verdict measures one head, so a run before
the last push proves nothing about the head being merged.

## Why WARN and not deny

The sibling guards split the same way: `no-unauthorized-merge.py` denies
because merging without permission is irreversible AND decidable from the
command alone. This one's evidence is a transcript inference, and the
transcript is a lossy witness: the clean run may have happened in another
session or terminal (a peer's PR, a resumed session), a record may omit the
exit status, and a push by another session cannot be seen at all. Denying on
an inference that can be wrong in both directions teaches the operator to set
an escape variable by reflex, which disarms the guard for the cases where it
is right. A warning costs one line and names the command to run. It is
intended to be promoted to a deny once its false-positive rate is measured.

## Command position, not substring

The merge is recognised only as the command word of a simple command (via
`scripts/lib/shellcmd.py`), so `echo "gh pr merge 5"`, a commit message, or a
heredoc body that merely names the command is inert. Likewise a run counts
only when `check-pr-fully-clean.py` is invoked as a script (directly or as an
interpreter's first operand), never when `grep` or `cat` names it.

LIMITS
------
* A result carries no cwd, so a clean run in one worktree is credited for a
  merge from another. The PR number (and `-R`, when both name one) is the
  only key.
* A merge naming no PR number (`gh pr merge` on the current branch, or a
  branch name) cannot be tied to a number, so any post-push clean run
  discharges it.
* A "NOT fully clean" line vetoes a result even beside a FULLY CLEAN line.
* Other merge routes (GraphQL `mergePullRequest`, `glab`, `gh pr merge` via a
  shell function or alias) are not recognised; `no-unauthorized-merge.py`
  covers those for permission, and this hook covers only the routes above.

Fails OPEN on any trouble reading the payload or transcript, printing
nothing; a broken `shellcmd` import writes one line to STDERR. Nothing but the
warning is ever written to stdout.
"""
import json
import os
import re
import shlex
import sys

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import (simple_commands, git_subcommand, strip_env,
                          shell_c_expansions, _heredoc_free, _comment_free)
except Exception as _exc:  # broken install: degrade silently, never block
    print(f"warn-merge-without-fully-clean: cannot load "
          f"scripts/lib/shellcmd.py ({_exc}); no warning will be emitted",
          file=sys.stderr)
    simple_commands = git_subcommand = strip_env = shell_c_expansions = None
    _heredoc_free = _comment_free = None

SHELL_TOOLS = frozenset({
    "Bash", "bash", "PowerShell", "run_command", "execute_command",
    "terminal", "shell",
})
MCP_MERGE_TOOL = "mcp__github__merge_pull_request"
INSTRUMENT = "check-pr-fully-clean.py"

RUNNERS = frozenset({
    "python", "python3", "py", "python3.11", "python3.12", "python3.13",
    "uv", "uvx", "poetry", "pdm", "hatch", "pipenv", "rye", "pixi",
})
NOT_A_FILE = frozenset({"-c", "--command", "-m", "--module",
                        "-h", "--help", "-V", "--version"})
RUNNER_SUBCOMMANDS = frozenset({"run", "exec"})

# gh global/subcommand options that take a separate value.
GH_VALUE_FLAGS = frozenset({"-R", "--repo", "-t", "--subject", "-b", "--body",
                            "-F", "--body-file", "--match-head-commit",
                            "-A", "--author-email"})
RX_PR_NUM = re.compile(r"^\d+$")
RX_PR_URL = re.compile(r"/pull/(\d+)(?:[/?#].*)?$")
RX_CLEAN_LINE = re.compile(r"\bis FULLY CLEAN\b")
RX_NOT_CLEAN = re.compile(r"NOT fully clean", re.IGNORECASE)
RX_API_MERGE = re.compile(r"(?:^|/)repos/([^/]+/[^/]+)/pulls/(\d+)/merge$")
SHELL_OPS = frozenset("();|&")

NOTE = (
    "About to merge {target}, but this session has no passing "
    "`scripts/{instrument}` run for it after the last push.\n"
    "`gh pr checks`, `mergeStateStatus` and a hand-read review verdict are "
    "not the instrument: on 2026-10-08 two ai-config PRs were merged on those "
    "alone and the instrument ran only afterwards (ai-config#4399). A clean "
    "verdict also measures one head, so a run from before your last push does "
    "not count.\n"
    "Run it, see exit 0 on the current head, then merge:\n\n"
    "    python3 scripts/{instrument} {num}{repo}\n"
)


def _basename(token):
    return os.path.basename(token.strip("'\"").replace("\\", "/"))


def _flag_value(args, names):
    """Value of the first `-R x` / `--repo=x` style flag in *args*, or None."""
    for i, tok in enumerate(args):
        for name in names:
            if tok == name and i + 1 < len(args):
                return args[i + 1]
            if tok.startswith(name + "="):
                return tok[len(name) + 1:]
            if len(name) == 2 and tok.startswith(name) and len(tok) > 2 \
                    and not tok.startswith("--"):
                return tok[2:]
    return None


def _pr_number(args):
    """The PR number named by positional operands in *args*, or None."""
    skip = False
    for tok in args:
        if skip:
            skip = False
            continue
        if tok in GH_VALUE_FLAGS:
            skip = True
            continue
        if tok.startswith("-"):
            continue
        if RX_PR_NUM.match(tok):
            return int(tok)
        m = RX_PR_URL.search(tok)
        if m:
            return int(m.group(1))
    return None


def _gh_merge(rest):
    """(number|None, repo|None) when argv `rest` is `gh pr merge ...`."""
    if not rest or _basename(rest[0]) != "gh":
        return None
    i = 1
    while i < len(rest) and rest[i].startswith("-"):  # global flags
        i += 2 if rest[i] in GH_VALUE_FLAGS else 1
    if rest[i:i + 1] == ["api"]:
        return _gh_api_merge(rest[i + 1:])
    if rest[i:i + 2] != ["pr", "merge"]:
        return None
    args = rest[i + 2:]
    return _pr_number(args), _flag_value(args, ("-R", "--repo"))


def _is_put(args):
    """True when *args* carry an explicit PUT method (`-X PUT`, `-XPUT`, ...)."""
    for i, tok in enumerate(args):
        if tok in ("-X", "--method") and i + 1 < len(args):
            if args[i + 1].upper() == "PUT":
                return True
        elif tok.startswith("--method="):
            if tok[9:].upper() == "PUT":
                return True
        elif tok.startswith("-X") and tok[2:].upper() == "PUT":
            return True
    return False


def _gh_api_merge(args):
    """(number, repo) for `gh api -X PUT repos/<o>/<r>/pulls/<N>/merge`."""
    if not _is_put(args):
        return None
    for tok in args:
        m = RX_API_MERGE.search(tok)
        if m:
            return int(m.group(2)), m.group(1)
    return None


def _instrument_run(rest):
    """(number|None, repo|None) when argv `rest` RUNS the instrument."""
    if not rest:
        return None
    head = _basename(rest[0])
    if head == INSTRUMENT:
        args = rest[1:]
    elif head in RUNNERS:
        args = None
        for j, tok in enumerate(rest[1:], 1):
            if tok in NOT_A_FILE or tok[:2] in ("-c", "-m"):
                return None
            if tok.startswith("-") or tok in RUNNER_SUBCOMMANDS:
                continue
            if _basename(tok) == INSTRUMENT:
                args = rest[j + 1:]
            break
        if args is None:
            return None
    else:
        return None
    return _pr_number(args), _flag_value(args, ("-R", "--repo"))


def _walk(command, fn):
    """Yield fn(argv-without-env) hits over every simple command in *command*."""
    for line in shell_c_expansions(command):
        for argv in simple_commands(line) or []:
            _env, rest = strip_env(argv)
            hit = fn(rest)
            if hit is not None:
                yield hit


def _is_push(command):
    for line in shell_c_expansions(command):
        for argv in simple_commands(line) or []:
            parsed = git_subcommand(argv)
            if parsed and parsed[0] == "push":
                return True
    return False


def records(path):
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


def _blocks(record):
    content = (record.get("message") or {}).get("content") or record.get("content")
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _result_text(block):
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    return ""


def _passed(block):
    """True only on POSITIVE evidence: the "is FULLY CLEAN" line.

    Silence is never success. An empty result, a backgrounded run ("Command
    running in background with ID: ...") and a result that merely lacks an
    error all say nothing about the verdict, so none of them passes.
    """
    text = _result_text(block)
    return bool(RX_CLEAN_LINE.search(text)) and not RX_NOT_CLEAN.search(text)


def scan(path):
    """Return (last_push_seq, [(seq, number, repo)] of passing instrument runs)."""
    last_push = -1
    pending = {}  # tool_use_id -> (seq, number, repo)
    passing = []
    for seq, rec in enumerate(records(path)):
        for b in _blocks(rec):
            kind = b.get("type")
            if kind == "tool_use" and b.get("name") in SHELL_TOOLS:
                cmd = (b.get("input") or {}).get("command")
                if not isinstance(cmd, str):
                    continue
                try:
                    if _is_push(cmd):
                        last_push = seq
                    if rec.get("isSidechain"):
                        continue  # a subagent's reading is not this session's
                    for num, repo in _walk(cmd, _instrument_run):
                        pending[b.get("id")] = (seq, num, repo)
                except Exception:
                    continue
            elif kind == "tool_result" and b.get("tool_use_id") in pending:
                seq0, num, repo = pending.pop(b["tool_use_id"])
                if _passed(b):
                    passing.append((seq0, num, repo))
    return last_push, passing


def _covers(run, num, repo):
    _seq, rnum, rrepo = run
    if num is not None and rnum is not None and rnum != num:
        return False
    if repo and rrepo and repo.lower() != rrepo.lower():
        return False
    return True


def _segments(line):
    """[(operator_before, argv)] for each simple command in *line*, or None.

    Unlike `simple_commands`, keeps the operator token that joined each
    command to its predecessor (`&&`, `;`, `||`, `|`, `)&&(`, ...), because
    only an exact `&&` makes the earlier command a precondition of the later.
    """
    if _heredoc_free is None:
        return None
    text = _heredoc_free(line)
    text = re.sub(r"\\\r?\n", " ", text)
    text = _comment_free(text).replace("\n", ";")
    try:
        lex = shlex.shlex(text, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return None
    segs, cur, op = [], [], None
    for tok in toks:
        if tok and set(tok) <= SHELL_OPS:
            if cur:
                segs.append((op, strip_env(cur)[1]))
                cur = []
            op = tok
        else:
            cur.append(tok)
    if cur:
        segs.append((op, strip_env(cur)[1]))
    return segs


def _chain_discharged(segs, j, num, repo):
    """True when an `&&` chain of commands before segment *j* ran the
    instrument for the same PR, with no `git push` between it and the merge."""
    k = j
    while k > 0 and segs[k][0] == "&&":
        k -= 1
        rest = segs[k][1]
        parsed = git_subcommand(rest) if rest else None
        if parsed and parsed[0] == "push":
            return False
        run = _instrument_run(rest)
        if run is not None and _covers((0, run[0], run[1]), num, repo):
            return True
    return False


def _bash_merge_targets(command):
    """Undischarged [(number|None, repo|None)] merges in a shell command."""
    targets = []
    for line in shell_c_expansions(command):
        segs = _segments(line)
        if segs is None:  # unparseable: fall back to the flat split
            targets.extend(h for argv in simple_commands(line) or []
                           for h in [_gh_merge(strip_env(argv)[1])] if h)
            continue
        for j, (_op, rest) in enumerate(segs):
            hit = _gh_merge(rest)
            if hit and not _chain_discharged(segs, j, *hit):
                targets.append(hit)
    return targets


def _merge_targets(tool, tool_input):
    """[(number|None, repo|None)] for every merge this call performs."""
    if tool == MCP_MERGE_TOOL:
        num = tool_input.get("pullNumber") or tool_input.get("pull_number")
        owner, name = tool_input.get("owner"), tool_input.get("repo")
        repo = f"{owner}/{name}" if owner and name else None
        try:
            return [(int(num), repo)]
        except (TypeError, ValueError):
            return [(None, repo)]
    command = (tool_input.get("command") or tool_input.get("CommandLine")
               or tool_input.get("cmd") or tool_input.get("script"))
    if not isinstance(command, str) or not command.strip():
        return []
    return _bash_merge_targets(command)


def main() -> int:
    if simple_commands is None:
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    tool = payload.get("tool_name") or payload.get("toolName") or ""
    if tool and tool not in SHELL_TOOLS and tool != MCP_MERGE_TOOL:
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = payload.get("toolInput")
    if not isinstance(tool_input, dict):
        return 0

    try:
        targets = _merge_targets(tool, tool_input)
    except Exception:
        return 0
    if not targets:
        return 0

    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return 0
    try:
        last_push, passing = scan(path)
    except Exception:
        return 0
    fresh = [r for r in passing if r[0] > last_push]

    missing = [(n, r) for n, r in targets
               if not any(_covers(run, n, r) for run in fresh)]
    if not missing:
        return 0

    num, repo = missing[0]
    target = f"PR #{num}" if num is not None else "a PR (number not named)"
    note = NOTE.format(target=target, instrument=INSTRUMENT,
                       num=num if num is not None else "<N>",
                       repo=f" -R {repo}" if repo else " -R <owner>/<repo>")
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                  "additionalContext": note}}
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            f"Merging {target} with no passing {INSTRUMENT} run after the "
            f"last push in this session.")
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
