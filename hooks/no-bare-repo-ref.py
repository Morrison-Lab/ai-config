#!/usr/bin/env python3
"""PreToolUse: a PR or issue mention such as psw#542 must be a markdown link.

ai-config#5164. Ezra, 2026-11-09: "why didn't you hyperlink those PR
mentions?" Every `repo#N` or `owner/repo#N` mention in a user-visible message
must be a link to its GitHub URL, e.g. `[psw#542](https://github.com/Morrison-Lab/psw/pull/542)`.

Scope: the user-visible hearthbot tools (post_message, request_decision, reply,
update_message, edit_message), in every session. A deny is possible because the
failing shape is lexical: a `repo#N` token left outside a markdown link, a code
span, a fenced block or a URL. A reminder would be read past (ai-config#4741),
and CLAUDE.md's "Link PRs in tables" prose was already missed.
`ALLOW_BARE_REPO_REF=1` overrides. Fails open on any parse trouble.
"""
import json
import os
import re
import sys

OVERRIDE = "ALLOW_BARE_REPO_REF"
TOOL = re.compile(
    r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message|request_decision)$")

SHIELDED = re.compile(
    r"```.*?```|~~~.*?~~~|`[^`\n]*`|\[[^\]\n]*\]\([^)\n]*\)|<https?://[^>\n]*>|https?://\S+",
    re.S)
BARE = re.compile(r"(?<![\w/.#-])(?:[A-Za-z0-9_.-]+/)?[A-Za-z][A-Za-z0-9_.-]*#\d+\b")

REASON = (
    "[hook: no-bare-repo-ref] {refs} is a PR or issue mention that is not a hyperlink "
    "(ai-config#5164, Ezra 2026-11-09). Write each as a markdown link to its GitHub URL, "
    "such as [psw#542](https://github.com/Morrison-Lab/psw/pull/542) (use /issues/ for "
    "an issue). Look up whether it is a PR or an issue rather than guessing. "
    "Set ALLOW_BARE_REPO_REF=1 only when the user asked for the bare form."
)


def user_text(tool_input: dict) -> str:
    parts = [tool_input.get("text"), tool_input.get("question")]
    for opt in tool_input.get("options") or []:
        if isinstance(opt, dict):
            parts += [opt.get("label"), opt.get("consequence")]
    return "\n".join(p for p in parts if isinstance(p, str))


def bare_refs(text: str) -> list:
    """Every repo#N token outside a link, code span, fence or URL, in order."""
    return BARE.findall(SHIELDED.sub(" ", text))


def denial(payload: dict):
    if os.environ.get(OVERRIDE) or not isinstance(payload, dict):
        return None
    if not TOOL.search(str(payload.get("tool_name") or "")):
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    refs = bare_refs(user_text(tool_input))
    if not refs:
        return None
    shown = ", ".join(dict.fromkeys(refs[:5]))
    return REASON.format(refs=shown)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        reason = denial(payload)
    except Exception:
        return 0
    if reason:
        json.dump({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason}}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
