#!/usr/bin/env python3
"""PreToolUse DENY: a PR merge with no `check-pr-fully-clean.py` pass for its head.

## The failure this exists for

On 2026-10-26 two thread sessions merged psw#354 (at 6ebf005) and gha#1239 (at
f450d6f) under a standing `mwc` without a `check-pr-fully-clean.py` run that
exited 0 on the head being merged. psw#354's only run had been made while
`build / build` was still pending. The rule was in project memory and
AGENTS.md, and both sessions knew it. It had happened before (ai-config#4399,
2026-10-08; ai-config#4538, 2026-10-15), and each time a hook "warned".

## Why the existing hooks did not stop it

* `no-unauthorized-merge.py` gates PERMISSION (the `mwc` grant), not
  cleanliness. A standing grant satisfied it.
* `enforce-mwc-review-gate.py` gates the live review state read from GitHub,
  not the instrument, and not the cloud case where it cannot run.
* `warn-merge-without-fully-clean.py` is the right idea and only WARNS (its
  docstring says it was "intended to be promoted to a deny once its
  false-positive rate is measured"). A warning arrives as context the session
  can read past. It also ties a run to the PR NUMBER, never to the HEAD SHA,
  so a run from before the last push, or one made while a check was pending,
  can pass; it credits only a Bash run in this transcript, which a cloud
  session cannot produce (the checker needs GraphQL, so it runs through a
  Remote Control session and the result comes back as a relayed message); and
  it lets a merge naming no PR number through.

## The condition (all must hold, or the merge is DENIED)

1. The merge names its PR (repo, number) and EXPECTED HEAD SHA (40 hex):
   `expectedHeadSha` on the MCP tool, `--match-head-commit` on `gh pr merge`,
   `-f sha=` on `gh api .../merge`, `"sha"` in a `curl` body. Pinning the sha
   is what lets GitHub itself refuse a merge if the head moved after the run.
2. The transcript holds the instrument's own line
   `<owner>/<repo>#<N> is FULLY CLEAN on HEAD <sha8>` for that repo, that
   number, and a sha that is a prefix of the merge's sha. That line is printed
   only on exit 0, so it IS the exit status; it is tied to the head by
   construction, which makes "after the last push" a non-question: a push
   changes the head, and the old line no longer matches.
3. The line is in a RESULT, not in the model's own words. Accepted sources:
   * a Bash result whose command RAN the instrument (command word or an
     interpreter's first operand), with no `echo`/`printf`/`cat`/`tee` in the
     same command able to print it, and not a subagent's;
   * a RELAYED result: a user-role message (the coordinator or Ezra relays
     the Remote Control run's output), or the result of a message-reading
     tool (`ReadNotifications`, `mcp__hearthbot__read_*`,
     `mcp__claude-code-remote__get_event|list_events`). This is the cloud
     path: the session cannot run the checker, a Remote Control session does,
     and its output line comes back with the SHA in it.
   The assistant's own prose, and tool INPUTS, never count.
4. A "NOT fully clean" line in the same Bash result vetoes it.

No escape variable: a gate with a reflex escape stops being a gate
(`feedback-fix-wrong-gate-never-override`). A checker that looks wrong is
fixed or its input corrected, then re-run.

## Recognised merge routes

`mcp__github__merge_pull_request`; `gh pr merge`; `gh api -X PUT
repos/o/r/pulls/N/merge`; `curl -X PUT .../repos/o/r/pulls/N/merge`; and a
`gh api graphql` call naming `mergePullRequest`, which cannot be tied to a
PR and is denied outright (use `gh pr merge`). Command position comes from
`scripts/lib/shellcmd.py`, so an echoed, grepped or heredoc-quoted merge is
inert.

LIMITS
------
* A relayed line is trusted as relayed: a session that forges a message-reading
  result is outside what a transcript can show. The sha tie still means the
  line must name the exact head being merged.
* `mcp__github__enable_pr_auto_merge` merges later with no sha and is not
  covered here; `no-unauthorized-merge.py` still gates it.
* GitHub web UI merges and merges by another session or the `@claude` agent
  are not seen.
* Fails OPEN when the payload or transcript is unreadable (some harnesses
  supply no transcript); a broken `shellcmd` import writes one STDERR line.
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.realpath(__file__))
try:
    _LIB = os.path.join(os.path.dirname(_HERE), "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import simple_commands, strip_env, shell_c_expansions
except Exception as _exc:  # broken install: degrade, never block
    print(f"block-merge-without-clean-checker: cannot load "
          f"scripts/lib/shellcmd.py ({_exc}); no gate will run", file=sys.stderr)
    simple_commands = strip_env = shell_c_expansions = None

SHELL_TOOLS = frozenset({"Bash", "bash", "PowerShell", "run_command",
                         "execute_command", "terminal", "shell"})
MCP_MERGE_TOOL = "mcp__github__merge_pull_request"
RELAY_TOOLS = frozenset({
    "ReadNotifications", "mcp__claude-code-remote__get_event",
    "mcp__claude-code-remote__list_events",
})
RELAY_PREFIXES = ("mcp__hearthbot__read_",)
INSTRUMENT = "check-pr-fully-clean.py"
RUNNERS = frozenset({"python", "python3", "py", "python3.11", "python3.12",
                     "python3.13", "uv", "uvx", "poetry", "pdm", "hatch",
                     "pipenv", "rye", "pixi"})
NOT_A_FILE = frozenset({"-c", "--command", "-m", "--module", "-h", "--help",
                        "-V", "--version"})
PRINTERS = frozenset({"echo", "printf", "cat", "tee"})
RX_EVIDENCE = re.compile(
    r"([\w.-]+/[\w.-]+)#(\d+) is FULLY CLEAN on HEAD ([0-9a-f]{7,40})\b")
RX_NOT_CLEAN = re.compile(r"NOT fully clean", re.IGNORECASE)
RX_SHA40 = re.compile(r"^[0-9a-fA-F]{40}$")
RX_API_MERGE = re.compile(
    r"repos/([^/\s]+/[^/\s]+)/pulls/(\d+)/merge/?(?:\?.*)?$")
RX_BODY_SHA = re.compile(r"""["']?sha["']?\s*[:=]\s*["']?([0-9a-fA-F]{7,40})""")

DENY_TEXT = (
    "BLOCKED: merging {target} needs {need}.\n\n"
    "{why}\n\n"
    "What to do:\n"
    "1. Get the head SHA: the PR's `head.sha` (40 hex).\n"
    "2. Run `python3 scripts/{inst} {num} -R {repo}` (local or Bash), and see "
    "exit 0 with the line `{repo}#{num} is FULLY CLEAN on HEAD <sha8>`.\n"
    "   In a cloud session the checker cannot run (it needs GraphQL): build "
    "the payload with `scripts/build-pr-payload.py`, or run the checker "
    "through a Remote Control session on the XPS, and get its output line "
    "relayed back into this session.\n"
    "3. Retry the merge with the full head SHA pinned "
    "(`expectedHeadSha` / `--match-head-commit`). A run made while a check "
    "was pending, or before the last push, names the wrong state and does "
    "not match.\n"
    "Do not infer a pass from an earlier or near-final run, and do not merge "
    "over a checker that looks wrong: fix the checker or its input, then "
    "re-run (psw#354 and gha#1239, 2026-10-26)."
)


def _basename(tok):
    return os.path.basename(tok.strip("'\"").replace("\\", "/"))


def _flag_value(args, names):
    for i, tok in enumerate(args):
        for name in names:
            if tok == name and i + 1 < len(args):
                return args[i + 1]
            if tok.startswith(name + "="):
                return tok[len(name) + 1:]
    return None


def _known_repo(value):
    return None if not value or "{" in value else value


def _is_put(args):
    for i, tok in enumerate(args):
        if tok in ("-X", "--request", "--method") and i + 1 < len(args):
            if args[i + 1].upper() == "PUT":
                return True
        elif tok.startswith(("--method=", "--request=")):
            if tok.split("=", 1)[1].upper() == "PUT":
                return True
        elif tok.startswith("-X") and tok[2:].upper() == "PUT":
            return True
    return False


def _api_target(args):
    """(num, repo) of the `.../pulls/N/merge` URL in *args*, else None."""
    for tok in args:
        m = RX_API_MERGE.search(tok.strip("'\""))
        if m:
            return int(m.group(2)), _known_repo(m.group(1))
    return None


def _field_sha(args):
    """sha from `-f sha=X`, `-F sha=X`, `--field sha=X`, or a JSON body."""
    for i, tok in enumerate(args):
        cand = None
        if tok in ("-f", "-F", "--field", "--raw-field") and i + 1 < len(args):
            cand = args[i + 1]
        elif tok in ("-d", "--data", "--data-raw", "--json") and i + 1 < len(args):
            cand = args[i + 1]
        elif tok.startswith("sha="):
            cand = tok
        if cand:
            m = RX_BODY_SHA.search(cand)
            if m:
                return m.group(1)
    return None


def _gh_pr_number(args):
    skip = False
    for tok in args:
        if skip:
            skip = False
            continue
        if tok in ("-R", "--repo", "-t", "--subject", "-b", "--body", "-F",
                   "--body-file", "--match-head-commit", "-A", "--author-email"):
            skip = True
            continue
        if tok.startswith("-"):
            continue
        if tok.isdigit():
            return int(tok)
        m = re.search(r"/pull/(\d+)(?:[/?#].*)?$", tok)
        if m:
            return int(m.group(1))
    return None


def _argv_merge(rest):
    """(num|None, repo|None, sha|None) when argv *rest* merges a PR, else None.

    num None means the merge cannot be tied to a PR; "graphql" in the third
    slot of the returned tuple's num marks a GraphQL merge.
    """
    if not rest:
        return None
    head = _basename(rest[0])
    if head == "gh":
        i = 1
        while i < len(rest) and rest[i].startswith("-"):
            i += 2 if rest[i] in ("-R", "--repo") else 1
        sub = rest[i:i + 2]
        if sub == ["pr", "merge"]:
            args = rest[i + 2:]
            repo = (_flag_value(args, ("-R", "--repo"))
                    or _flag_value(rest[1:i], ("-R", "--repo")))
            return (_gh_pr_number(args), _known_repo(repo),
                    _flag_value(args, ("--match-head-commit",)))
        if rest[i:i + 1] == ["api"]:
            args = rest[i + 1:]
            if "graphql" in args and any("mergePullRequest" in t for t in args):
                return (None, None, None)
            if _is_put(args):
                hit = _api_target(args)
                if hit:
                    return hit[0], hit[1], _field_sha(args)
    elif head == "curl":
        args = rest[1:]
        hit = _api_target(args)
        if hit and _is_put(args):
            return hit[0], hit[1], _field_sha(args)
    return None


def _shell_command(tool_input):
    if not isinstance(tool_input, dict):
        return None
    cmd = (tool_input.get("command") or tool_input.get("CommandLine")
           or tool_input.get("cmd") or tool_input.get("script"))
    return cmd if isinstance(cmd, str) and cmd.strip() else None


def merge_targets(tool, tool_input):
    """[(num|None, repo|None, sha|None)] for every merge this call performs."""
    if tool == MCP_MERGE_TOOL:
        num = tool_input.get("pullNumber") or tool_input.get("pull_number")
        owner, name = tool_input.get("owner"), tool_input.get("repo")
        repo = f"{owner}/{name}" if owner and name else None
        sha = (tool_input.get("expectedHeadSha")
               or tool_input.get("expected_head_sha"))
        try:
            num = int(num)
        except (TypeError, ValueError):
            num = None
        return [(num, repo, sha)]
    command = _shell_command(tool_input)
    if command is None:
        return []
    out = []
    for line in shell_c_expansions(command):
        for argv in simple_commands(line) or []:
            hit = _argv_merge(strip_env(argv)[1])
            if hit:
                out.append(hit)
    return out


def _runs_instrument(command):
    """True when *command* runs the instrument and cannot print its own line."""
    ran = False
    for line in shell_c_expansions(command):
        for argv in simple_commands(line) or []:
            rest = strip_env(argv)[1]
            if not rest:
                continue
            head = _basename(rest[0])
            if head in PRINTERS:
                return False
            if head == INSTRUMENT:
                ran = True
            elif head in RUNNERS:
                for tok in rest[1:]:
                    if tok in NOT_A_FILE or tok[:2] in ("-c", "-m"):
                        break
                    if tok.startswith("-") or tok in ("run", "exec"):
                        continue
                    if _basename(tok) == INSTRUMENT:
                        ran = True
                    break
    return ran


def _blocks(rec):
    content = (rec.get("message") or {}).get("content") or rec.get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _result_text(block):
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    return ""


def _is_relay_tool(name):
    return name in RELAY_TOOLS or (name or "").startswith(RELAY_PREFIXES)


def evidence(path):
    """{(repo_lower, num, sha)} of FULLY CLEAN lines from accepted sources."""
    found = set()
    bash_ids, relay_ids = set(), set()

    def take(text, veto):
        if veto and RX_NOT_CLEAN.search(text):
            return
        for repo, num, sha in RX_EVIDENCE.findall(text):
            found.add((repo.lower(), int(num), sha.lower()))

    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("isSidechain"):
                continue
            role = rec.get("type") or (rec.get("message") or {}).get("role")
            for b in _blocks(rec):
                kind = b.get("type")
                if kind == "tool_use":
                    name = b.get("name")
                    if name in SHELL_TOOLS:
                        cmd = _shell_command(b.get("input") or {})
                        try:
                            if cmd and _runs_instrument(cmd):
                                bash_ids.add(b.get("id"))
                        except Exception:
                            pass
                    elif _is_relay_tool(name):
                        relay_ids.add(b.get("id"))
                elif kind == "tool_result":
                    tid = b.get("tool_use_id")
                    if tid in bash_ids:
                        take(_result_text(b), veto=True)
                    elif tid in relay_ids:
                        take(_result_text(b), veto=False)
                elif kind == "text" and role == "user":
                    take(b.get("text") or "", veto=False)
    return found


def deny(reason):
    return {
        "decision": "deny",
        "reason": reason,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    }


def _refuse(target, need, why, num, repo):
    return deny(DENY_TEXT.format(
        target=target, need=need, why=why, inst=INSTRUMENT,
        num=num if num is not None else "<N>", repo=repo or "<owner>/<repo>"))


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
    if tool not in SHELL_TOOLS and tool != MCP_MERGE_TOOL:
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = payload.get("toolInput")
    if not isinstance(tool_input, dict):
        return 0
    try:
        targets = merge_targets(tool, tool_input)
    except Exception:
        return 0
    if not targets:
        return 0

    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        print("block-merge-without-clean-checker: no transcript; not gating",
              file=sys.stderr)
        return 0
    try:
        found = evidence(path)
    except Exception:
        return 0

    for num, repo, sha in targets:
        target = (f"{repo}#{num}" if repo and num is not None
                  else f"PR #{num}" if num is not None
                  else "a PR that cannot be identified")
        if num is None or not repo:
            print(json.dumps(_refuse(
                target, "an explicit PR number and repository",
                "A merge that names no PR or no repository cannot be tied to "
                "a checker run. A GraphQL `mergePullRequest` call cannot be "
                "tied at all: use `gh pr merge N -R o/r --match-head-commit "
                "<sha>` or the MCP merge tool.", num, repo)))
            return 0
        if not sha or not RX_SHA40.match(sha):
            print(json.dumps(_refuse(
                target, "the full 40-character head SHA pinned",
                "Without `expectedHeadSha` (MCP) or `--match-head-commit` "
                "(`gh pr merge`) the merge cannot be tied to the head the "
                "checker measured, and GitHub cannot refuse it if the head "
                "moved after the run.", num, repo)))
            return 0
        sha = sha.lower()
        ok = any(r == repo.lower() and n == num and sha.startswith(s)
                 for r, n, s in found)
        if not ok:
            print(json.dumps(_refuse(
                target, f"a `{INSTRUMENT}` pass on head {sha[:8]}",
                f"No `{repo}#{num} is FULLY CLEAN on HEAD {sha[:8]}` line is "
                "in this session's checker results or relayed messages.",
                num, repo)))
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
