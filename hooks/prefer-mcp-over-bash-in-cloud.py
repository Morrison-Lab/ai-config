#!/usr/bin/env python3
"""PreToolUse (Bash): in a cloud session, use the GitHub MCP tool, not `gh`.

ai-config#5613 (Ezra, 2026-11-13): a cloud Bash call can prompt for approval,
and an MCP call does not. Only when CLAUDE_CODE_REMOTE=true, DENIES at a
command position (also inside `bash -c`): a `gh pr|issue|run|workflow|release`
subcommand in `MCP_SUBCOMMANDS`; `gh api` on any path but `search/`, `graphql`
or check-run `annotations`, which have no MCP tool; and `curl`/`wget` to
api.github.com under the same exceptions. git, `gh auth|search|secret|label`
and quoted mentions pass. A deny, not a warning, since a warning gets read
past (ai-config#4741). With no MCP tool for the job, prefix the command with
the assignment `ALLOW_BASH_OVER_MCP=1` and say why. Fails open; silent locally.
"""
import json
import os
import re
import sys

_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                    "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
try:
    from shellcmd import simple_commands, strip_env
except ImportError as exc:
    print(f"prefer-mcp-over-bash-in-cloud: cannot load scripts/lib/shellcmd.py ({exc}); "
          "not gating", file=sys.stderr)
    simple_commands = strip_env = None

OVERRIDE = "ALLOW_BASH_OVER_MCP=1"

# gh subcommand -> the MCP tools that do its job.
GH_MCP = {
    "pr": "mcp__github__pull_request_read / create_pull_request / update_pull_request / "
          "merge_pull_request / add_issue_comment",
    "issue": "mcp__github__issue_read / issue_write / list_issues / add_issue_comment",
    "run": "mcp__github__actions_list / actions_get / get_job_logs / actions_run_trigger",
    "workflow": "mcp__github__actions_list / actions_run_trigger",
    "release": "mcp__github__list_releases / get_latest_release / get_release_by_tag",
    "api": "the matching mcp__github__* tool (get_file_contents, pull_request_read, "
           "issue_read, actions_get, get_commit, ...)",
}
# The subcommands those tools cover; any other (`pr checkout`, `run watch`,
# `release create`) passes.
MCP_SUBCOMMANDS = {
    "pr": {"view", "list", "create", "edit", "merge", "comment", "review", "diff", "checks",
           "close", "reopen", "ready", "status", "update-branch"},
    "issue": {"view", "list", "create", "edit", "comment", "close", "reopen", "status"},
    "run": {"view", "list", "rerun", "cancel"},
    "workflow": {"run", "list", "view"},
    "release": {"view", "list"},
}
GH_API_HOST = re.compile(r"^(?:https?://)?api\.github\.com(?:/|$)", re.I)
# Endpoints the MCP server has no tool for. `..` is refused so
# `search/../repos/...` cannot pass as a search.
NO_MCP_PATH = re.compile(
    r"^(?:https?://api\.github\.com)?/?(?:search/|graphql(?:$|[/?])"
    r"|repos/[^/?]+/[^/?]+/check-runs/\d+/annotations(?:$|[/?]))",
    re.I,
)
# gh's global flags that take a value and may precede the subcommand.
GH_VALUE_FLAGS = {"-R", "--repo", "--hostname"}
SHELLS = {"bash", "sh", "zsh", "dash"}
# `gh api` flags that take a separate value, which must not be read as the endpoint.
GH_API_VALUE_FLAGS = {"-X", "--method", "-H", "--header", "-f", "--raw-field", "-F", "--field",
                      "-q", "--jq", "-t", "--template", "--input", "--hostname", "--cache",
                      "-p", "--preview"}


def _gh_hit(rest):
    """The MCP replacement for a `gh` argv (program first), or None."""
    args = rest[1:]
    while args and args[0].startswith("-"):
        flag = args[0]
        if flag in GH_VALUE_FLAGS:
            args = args[2:]
        elif flag.startswith(("--repo=", "--hostname=")) or (flag.startswith("-R") and len(flag) > 2):
            args = args[1:]
        else:
            break
    if not args or args[0] not in GH_MCP:
        return None
    sub = args[0]
    if sub != "api":
        verb = args[1] if len(args) > 1 else ""
        if verb not in MCP_SUBCOMMANDS[sub]:
            return None
    else:
        path, it = "", iter(args[1:])
        for arg in it:
            if arg in GH_API_VALUE_FLAGS:
                next(it, None)  # `-X GET`: GET is the flag's value, not the endpoint
            elif not arg.startswith("-"):
                path = arg
                break
        if _no_mcp_path(path):
            return None
    return f"gh {sub}", GH_MCP[sub]


def _no_mcp_path(path):
    """Whether `path` is an endpoint the MCP server lacks (search, graphql, annotations)."""
    return ".." not in path and bool(NO_MCP_PATH.match(path))


def _http_hit(rest):
    """The MCP replacement for a curl/wget to api.github.com, or None."""
    for arg in rest[1:]:
        if GH_API_HOST.match(arg):
            path = re.sub(r"^(?:https?://)?api\.github\.com", "", arg, flags=re.I)
            if _no_mcp_path(path):
                return None
            return f"{rest[0]} api.github.com", GH_MCP["api"]
    return None


def offending(command):
    """`(what, mcp_tools)` for the first Bash use an MCP tool covers, or None."""
    for argv in simple_commands(command) or []:
        env, rest = strip_env(argv)
        if not rest or OVERRIDE in env:
            continue
        prog = os.path.basename(rest[0])
        hit = None
        if prog in SHELLS and "-c" in rest[1:-1]:
            hit = offending(rest[rest.index("-c", 1) + 1])
        elif prog == "gh":
            hit = _gh_hit(rest)
        elif prog in ("curl", "wget"):
            hit = _http_hit(rest)
        if hit:
            return hit
    return None


def main() -> int:
    if os.environ.get("CLAUDE_CODE_REMOTE", "").lower() != "true" or simple_commands is None:
        return 0
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    inp = payload.get("tool_input")
    command = inp.get("command") if isinstance(inp, dict) else None
    if not isinstance(command, str):
        return 0
    try:
        hit = offending(command)
    except Exception as exc:
        print(f"prefer-mcp-over-bash-in-cloud: {type(exc).__name__}: {exc}; not gating",
              file=sys.stderr)
        return 0
    if not hit:
        return 0
    what, tools = hit
    reason = (
        f"[hook: prefer-mcp-over-bash-in-cloud] This is a cloud session, and `{what}` has an MCP "
        f"equivalent: {tools}. Use the MCP tool instead; it needs no approval prompt "
        "(Ezra, 2026-11-13: cloud sessions use MCP tools rather than Bash wherever possible). "
        "tool-mappings.md maps each gh command. GitHub search is the exception (`gh api "
        f"search/...` passes). Only if no MCP tool can do this, prefix `{OVERRIDE}` and say why."
    )
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
