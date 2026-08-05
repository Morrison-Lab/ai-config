#!/usr/bin/env python3
"""PreToolUse guard: mechanistically prohibit PR/MR merge commands.

Prohibits commands attempting to merge PRs/MRs (e.g. `gh pr merge`, `glab mr merge`,
`gh api .../merge`, `glab api .../merge`, or GraphQL `mergePullRequest`) unless
explicit authorization is present via ALLOW_MERGE=1 or --allow-merge.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

LEAD = r"""(?:^|[\s;&|`()]|(?:\$\())"""
ENV_WRAP = r"""(?:[A-Za-z_][A-Za-z0-9_]*=(?:"[^"]*"|'[^']*'|\S*)\s+)*"""
EXEC_WRAP = r"""(?:[/\w.-]+/)?(?:env|exec|command)\s+"""
OPT_FLAGS = r"(?:\s+-[A-Za-z0-9_-]+(?:[=\s][^\s;&|`()]+)?)*"

MERGE_PATTERNS = [
    (LEAD + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?(?:[/\w.-]+/)?gh\b" + OPT_FLAGS + r"\s+pr\b" + OPT_FLAGS + r"\s+merge\b", "gh pr merge"),
    (LEAD + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?(?:[/\w.-]+/)?glab\b" + OPT_FLAGS + r"\s+mr\b" + OPT_FLAGS + r"\s+merge\b", "glab mr merge"),
    (LEAD + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?(?:[/\w.-]+/)?gh\b(?:\s+[^\n]+)?\s+api\b[^\n]*/pulls/[^\n]+/merge\b", "gh api PR merge"),
    (LEAD + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?(?:[/\w.-]+/)?gh\b(?:\s+[^\n]+)?\s+api\b[^\n]*graphql\b[^\n]*mergePullRequest", "gh api GraphQL PR merge"),
    (LEAD + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?(?:[/\w.-]+/)?glab\b(?:\s+[^\n]+)?\s+api\b[^\n]*/merge_requests/[^\n]+/merge\b", "glab api MR merge"),
]

ALLOW_FLAG = re.compile(r"\bALLOW_MERGE=1\b|\b--allow-merge\b")
SPLIT = re.compile(r"&&|\|\||;|\||\n")


def mask_payloads(text: str) -> str:
    """Mask text payloads (comment bodies, commit messages, trailing shell comments, body files)
    so trigger patterns inside prose or file paths do not cause false positives or allow-flag bypasses.
    Handles escaped quotes inside string literals and unquoted file/field values.
    """
    # 1. Mask trailing shell comments (# ...)
    text = re.sub(r"#.*$", lambda m: " " * len(m.group(0)), text, flags=re.MULTILINE)

    # 2. Mask values of prose/file-carrying flags (--body, --body-file, --title, --comment, --message, -m, -b, -F, -f, --raw-field, --field, etc.)
    flag_pattern = r"(?:--body-file|--body|--title|--comment|--message|--reason|--notes|--description|-m|-b|-F|-f|--raw-field|--field|--template|--search)"

    def repl_flag(m):
        flag = m.group(1)
        val = m.group(2)
        return flag + (" " * len(val))

    text = re.sub(rf"({flag_pattern}\s+=?\s*)(\"(?:\\.|[^\"])*\")", repl_flag, text)
    text = re.sub(rf"({flag_pattern}\s+=?\s*)(\'(?:\\.|[^\'])*\')", repl_flag, text)
    text = re.sub(rf"({flag_pattern}\s+=?\s*)(\S+)", repl_flag, text)

    return text


def sanitize(name: str) -> str:
    """Sanitize session ID matching ai-session.sh: tr -c 'A-Za-z0-9._-' '_'"""
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def is_session_alive(sess_file: Path) -> bool:
    try:
        content = sess_file.read_text(encoding="utf-8")
        sess_data = dict(line.split("=", 1) for line in content.splitlines() if "=" in line)
        pid = sess_data.get("pid")
        host = sess_data.get("host")
        local_host = os.uname().nodename
        if pid and (not host or host == local_host):
            try:
                os.kill(int(pid), 0)
                return True
            except OSError:
                return False
        hb = int(sess_data.get("heartbeat", 0))
        return (time.time() - hb) < 1800
    except Exception:
        pass
    return False


def get_git_common_dir() -> Path:
    try:
        common_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return Path(common_dir).resolve()
    except Exception:
        pass

    pwd_git = Path.cwd() / ".git"
    if pwd_git.exists():
        return pwd_git.resolve()
    return Path.home() / ".git"


def check_mwc_active() -> bool:
    try:
        current_session = os.environ.get("AI_SESSION_ID") or os.environ.get("CLAUDE_SESSION_ID")
        if not current_session:
            return False

        common_dir = get_git_common_dir()
        reg_dir = common_dir / "ai-sessions"
        if not reg_dir.exists():
            return False

        sanitized_session = sanitize(current_session)
        mwc_file = reg_dir / f"{sanitized_session}.mwc"
        if mwc_file.exists():
            sess_file = reg_dir / f"{sanitized_session}.session"
            if sess_file.exists() and is_session_alive(sess_file):
                return True
    except Exception:
        pass
    return False


def offending(command: str):
    mwc_active = check_mwc_active()
    for segment in SPLIT.split(command):
        masked_segment = mask_payloads(segment)
        if ALLOW_FLAG.search(masked_segment) or mwc_active:
            continue
        for pattern, label in MERGE_PATTERNS:
            if re.search(pattern, masked_segment):
                return label, segment.strip()
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"no-unauthorized-merge: unreadable hook input ({exc})", file=sys.stderr)
        return 0

    if payload.get("tool_name") != "Bash":
        return 0

    command = (payload.get("tool_input") or {}).get("command") or ""
    hit = offending(command)
    if not hit:
        return 0

    label, segment = hit
    reason = (
        f"MECHANISTIC PROHIBITION: `{label}` is strictly blocked without explicit permission.\n\n"
        f"    Offending command segment: {segment}\n\n"
        "AI agents are mechanistically forbidden from merging PRs/MRs unless explicitly instructed "
        "by the user or executing under an explicit override (e.g. ALLOW_MERGE=1 or active /mwc)."
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
