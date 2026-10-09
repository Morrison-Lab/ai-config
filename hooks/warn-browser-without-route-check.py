#!/usr/bin/env python3
"""PreToolUse reminder: a browser call with no search for a CLI/MCP/API route.

The rule (use the browser only when nothing else can) lives in
`shared/workflow/browser-last-resort.md`, but a written rule did not fire at
the moment of the browser call: on 2026-10-09 an agent opened Claude in Chrome
to change Google Analytics settings without first checking the Admin API or an
MCP (ai-config#4461).

THE CHECK
---------
Fires only when ALL of these hold:

  1. The tool call is a browser call:
       - `mcp__claude-in-chrome__navigate`
       - `mcp__Claude_Browser__navigate`
       - `mcp__Claude_Browser__preview_start` whose input has a `url`
       - `mcp__computer-use__request_access` whose `apps` name a browser
         (Chrome, Safari, Firefox, Arc, Edge)
  2. The target is not a render check: localhost, 127.0.0.1, `*.localhost`,
     `file://`, and `_site/` paths are exempt.
  3. No earlier tool call since the last real user message is a route search:
       - WebFetch or WebSearch
       - ToolSearch
       - a Bash command containing `mcp list`, `command -v`, `which `,
         `--help`, or `gh api`
  4. No earlier browser call since the last user message already drew this
     warning (it warns on the FIRST such call only).

WARN, NEVER BLOCK
-----------------
Whether a route exists is not lexically decidable, and a blocked navigation
costs more than an ignorable reminder. The message asks the agent to say, in
its next reply, which CLI, MCP, or API route it checked, or why none fits.

FAILS OPEN
----------
An unreadable transcript, a malformed payload, or any parse trouble returns 0
silently: a reminder that cannot establish its own precondition must not fire.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
_LIB = os.path.join(os.path.dirname(HERE), "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
try:
    from transcript_meta import is_hook_feedback, is_skill_load_meta
except Exception as _exc:  # broken install: degrade loudly, not silently
    print(f"warn-browser-without-route-check: cannot load "
          f"scripts/lib/transcript_meta.py ({_exc}); harness-injected user "
          f"records may reset the turn", file=sys.stderr)

    def is_skill_load_meta(entry):  # noqa: D103
        return False

    def is_hook_feedback(entry):  # noqa: D103
        return False

NAV_TOOLS = (
    "mcp__claude-in-chrome__navigate",
    "mcp__Claude_Browser__navigate",
)
PREVIEW_TOOL = "mcp__Claude_Browser__preview_start"
ACCESS_TOOL = "mcp__computer-use__request_access"

BROWSER_APPS = re.compile(
    r"\b(chrome|safari|firefox|arc|edge)\b", re.I)

# Render-check targets: local development hosts, file URLs, and built-site paths.
RX_LOCAL = re.compile(
    r"^\s*(?:(?:https?://)?(?:localhost|127\.0\.0\.1|\[::1\]|[^/\s:]+\.localhost)"
    r"(?::\d+)?(?:[/?#]|$)|file://)",
    re.I,
)
# A filesystem path: absolute, home-relative, dot-relative, a drive letter, or
# dotless leading segments (a host has a dot before its first slash).
RX_FS_PATH = re.compile(r"^\s*(?:[/~]|\.{1,2}[/\\]|[A-Za-z]:[\\/]|[\w-]+[/\\])")
# User records the harness injects that are not a person's turn.
RX_INJECTED_USER = re.compile(
    r"^\s*(?:<(?:system-reminder|task-notification|command-name|"
    r"local-command-stdout)\b|\[Request interrupted)", re.I)
RX_SITE_PATH = re.compile(r"(?:^|[/\\])_site[/\\]")

SEARCH_TOOLS = ("WebFetch", "WebSearch", "ToolSearch")
RX_ROUTE_BASH = re.compile(r"mcp\s+list|command\s+-v|\bwhich\s|--help|\bgh\s+api\b")
BASH_TOOL_NAMES = ("Bash", "bash", "PowerShell")

MESSAGE = (
    "This opens a browser, and no search for a CLI, MCP, or API route appears "
    "since the last user message.\n\n"
    "The rule is in shared/workflow/browser-last-resort.md: use the browser "
    "only when nothing else can do the job. On 2026-10-09 an agent opened "
    "Claude in Chrome to change Google Analytics settings without checking the "
    "Admin API or an MCP first (ai-config#4461).\n\n"
    "Before continuing, check for a route (a WebSearch or WebFetch of the "
    "service's API docs, ToolSearch for an MCP, `claude mcp list`, "
    "`command -v <cli>`, a CLI `--help`, `gh api`). In your next reply, say "
    "which CLI, MCP, or API route you checked, or why none fits.\n\n"
    "This is a reminder, not a refusal."
)


def browser_target(tool_name, tool_input):
    """(is_browser_call, exempt) for this tool call."""
    if not isinstance(tool_input, dict):
        tool_input = {}
    if tool_name in NAV_TOOLS:
        url = tool_input.get("url")
        if _is_history_or_empty(url):
            return False, False
        return True, _is_render_target(url)
    if tool_name == PREVIEW_TOOL:
        url = tool_input.get("url")
        if not url:
            return False, False  # dev-server start by name: not a browser visit
        return True, _is_render_target(url)
    if tool_name == ACCESS_TOOL:
        apps = tool_input.get("apps")
        if isinstance(apps, str):
            apps = [apps]
        if not isinstance(apps, list):
            return False, False
        names = " ".join(
            (a.get("displayName") or a.get("name") or "") if isinstance(a, dict) else str(a)
            for a in apps)
        return bool(BROWSER_APPS.search(names)), False
    return False, False


def _is_render_target(url):
    if not isinstance(url, str) or not url.strip():
        return False
    if RX_LOCAL.match(url):
        return True
    if not RX_FS_PATH.match(url):
        return False  # host-first string such as admin.example.com/_site/x
    return bool(RX_SITE_PATH.search(url))


def _is_history_or_empty(url):
    """navigate's documented back/forward, or no url at all: not a visit."""
    return not isinstance(url, str) or url.strip().lower() in ("", "back", "forward")


def _is_real_user_message(rec):
    """True for the user's own turn, False for a tool_result record."""
    if (rec.get("type") or rec.get("role")) != "user":
        return False
    if rec.get("isSidechain") or is_skill_load_meta(rec) or is_hook_feedback(rec):
        return False
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, str):
        return not RX_INJECTED_USER.match(content)
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result"
               for b in content):
            return False
        texts = [b.get("text") or "" for b in content
                 if isinstance(b, dict) and b.get("type") == "text"]
        return not (texts and all(RX_INJECTED_USER.match(t) for t in texts))
    return False


def _tool_uses(rec):
    content = (rec.get("message") or {}).get("content")
    if not isinstance(content, list):
        return
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            yield (block.get("id") or "", block.get("name") or "",
                   block.get("input") or {})


def _collect_result_ids(rec, out):
    content = (rec.get("message") or {}).get("content")
    if not isinstance(content, list):
        return
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_result":
            out.add(block.get("tool_use_id") or "")


def is_route_search(name, tool_input):
    if name in SEARCH_TOOLS:
        return True
    if name in BASH_TOOL_NAMES and isinstance(tool_input, dict):
        command = tool_input.get("command") or ""
        return isinstance(command, str) and bool(RX_ROUTE_BASH.search(command))
    return False


def turn_state(transcript_path):
    """(searched, already_warned) over the records since the last user message.

    Returns None when the transcript cannot be read.
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return None
    searched = False
    browser_ids = set()
    result_ids = set()
    with open(transcript_path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if not isinstance(rec, dict):
                continue
            if _is_real_user_message(rec):
                searched = False
                browser_ids = set()
                result_ids = set()
                continue
            _collect_result_ids(rec, result_ids)
            for tool_id, name, tool_input in _tool_uses(rec):
                if is_route_search(name, tool_input):
                    searched = True
                is_browser, exempt = browser_target(name, tool_input)
                if is_browser and not exempt and tool_id:
                    browser_ids.add(tool_id)
    # The call under evaluation is already in the transcript when PreToolUse
    # runs but has no result yet, so only answered browser calls are "prior".
    return searched, bool(browser_ids & result_ids)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    try:
        is_browser, exempt = browser_target(
            payload.get("tool_name") or "", payload.get("tool_input"))
        if not is_browser or exempt:
            return 0
        state = turn_state(payload.get("transcript_path") or "")
        if state is None:
            return 0
        searched, prior_browser_call = state
        if searched or prior_browser_call:
            return 0
        print(json.dumps({"systemMessage": MESSAGE}))
        return 0
    except Exception as exc:  # fail open on any parse trouble
        print(f"warn-browser-without-route-check: could not evaluate ({exc})",
              file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
