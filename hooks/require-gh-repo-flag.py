#!/usr/bin/env python3
"""PreToolUse guard: refuse mutating, repo-scoped `gh` commands that omit -R.

Without an explicit -R/--repo, `gh` takes its target from the current working
directory. That is fine for reads and dangerous for writes: on 2026-07-29 a
`gh secret set CLAUDE_CODE_OAUTH_TOKEN` meant for Morrison-Lab/wai ran while cwd
was the ucdavis/bcs checkout and overwrote bcs's token instead. Nothing in the
command named the wrong repo, so nothing looked wrong.

Scope is deliberately narrow -- destructive or expensive operations only. Reads
(`gh pr view`, `gh run list`) and high-frequency low-harm writes (`gh pr
comment`, `gh issue comment`) are NOT gated: a comment on the wrong repo is
visible and trivially deleted, and gating them would train the guard into
noise, which is worse than not having it.

Fails OPEN. A guard that breaks every Bash call when python or jq misbehaves
costs more than the failure it prevents; it reports the problem on stderr
instead of blocking.
"""
import json
import re
import sys

# Anchored at the start of a shell segment, after optional leading whitespace
# and VAR=value assignments -- so `gh secret set` only matches where `gh` is
# actually the command being run. Without the anchor the guard fires on any
# command whose *text* merely contains the pattern: a heredoc documenting the
# command, an `echo`, or a JSON payload piped to a script. That is a false
# positive with real cost, since a blocked turn is more disruptive than a
# missed one here (the miss is caught by the -R habit; the false positive
# teaches you to distrust the guard).
# The value slot accepts a quoted string as well as a bare token: `\S*` alone
# stops at the first space, so `VAR="two words" gh secret set` would fail to
# match the prefix and the whole segment would be treated as not-a-gh-command.
# That direction is a false NEGATIVE -- the guard would wave the command
# through -- which is worse here than the false positive the anchor was added
# to fix.
LEAD = r"""^\s*(?:[A-Za-z_][A-Za-z0-9_]*=(?:"[^"]*"|'[^']*'|\S*)\s+)*gh\s+"""

GATED = [
    (LEAD + r"secret\s+(set|delete|remove)\b", "gh secret set/delete"),
    (LEAD + r"variable\s+(set|delete|remove)\b", "gh variable set/delete"),
    (LEAD + r"pr\s+(merge|close|reopen)\b", "gh pr merge/close/reopen"),
    (LEAD + r"issue\s+(close|reopen|delete|transfer)\b", "gh issue close/reopen/delete"),
    (LEAD + r"release\s+(create|delete|edit|upload)\b", "gh release create/delete/edit"),
    (LEAD + r"workflow\s+(run|enable|disable)\b", "gh workflow run/enable/disable"),
    (LEAD + r"run\s+(rerun|cancel|delete)\b", "gh run rerun/cancel/delete"),
    (LEAD + r"repo\s+(delete|archive|rename)\b", "gh repo delete/archive/rename"),
    (LEAD + r"label\s+(create|delete|edit)\b", "gh label create/delete/edit"),
    (LEAD + r"ruleset\s+\w+", "gh ruleset (write)"),
]

# `gh api` with {owner}/{repo} placeholders resolves them from cwd, so it has
# the same implicit-target hazard even though the path looks explicit.
API_PLACEHOLDER = re.compile(LEAD + r"api\b[^\n]*\{(owner|repo)\}")

HAS_REPO_FLAG = re.compile(r"(^|\s)(-R\b|--repo(=|\s))")

# Split on shell operators so `cd x && gh secret set Y` is judged per segment.
SPLIT = re.compile(r"&&|\|\||;|\||\n")


def offending(command: str):
    for segment in SPLIT.split(command):
        if "gh" not in segment:
            continue
        if HAS_REPO_FLAG.search(segment):
            continue
        for pattern, label in GATED:
            if re.search(pattern, segment):
                return label, segment.strip()
        if API_PLACEHOLDER.search(segment):
            return "gh api with {owner}/{repo} placeholders", segment.strip()
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:  # fail open, but say so
        print(f"require-gh-repo-flag: unreadable hook input ({exc})", file=sys.stderr)
        return 0

    if payload.get("tool_name") != "Bash":
        return 0

    command = (payload.get("tool_input") or {}).get("command") or ""
    hit = offending(command)
    if not hit:
        return 0

    label, segment = hit
    reason = (
        f"Blocked: `{label}` without an explicit -R/--repo.\n\n"
        f"    {segment}\n\n"
        "`gh` would take the target repo from the current working directory, "
        "which is how a secret meant for one repo got written to another on "
        "2026-07-29. Re-issue the command with the repo named explicitly:\n\n"
        f"    -R <owner>/<repo>\n\n"
        "If you genuinely mean 'whatever repo the cwd points at', run `git "
        "remote -v` first and then pass that repo by name anyway."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
