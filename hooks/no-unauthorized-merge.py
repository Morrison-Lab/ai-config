#!/usr/bin/env python3
"""PreToolUse guard: mechanistically prohibit PR/MR merge commands.

Prohibits commands attempting to merge PRs/MRs (e.g. `gh pr merge`, `glab mr merge`,
`gh api .../merge`, `glab api .../merge`, or GraphQL `mergePullRequest` / `enablePullRequestAutoMerge`)
unless explicit authorization is present via ALLOW_MERGE=1 or --allow-merge.
"""
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

LEAD = r"""(?:^|[\s;&|`()\"']|(?:\$\())"""
ENV_WRAP = r"""(?:[A-Za-z_][A-Za-z0-9_]*=(?:"[^"]*"|'[^']*'|\S*)\s+)*"""
EXEC_WRAP = r"""(?:[/\w.-]+/)?(?:env|exec|command|bash|sh|zsh|eval)\s+"""
OPT_VAL = r"""(?:="[^"]*"|='[^']*'|=[^\s;&|`()]+|\s+"[^"]*"|\s+'[^']*'|\s+[^\s;&|`()]+)"""
OPT_FLAGS = rf"(?:\s+-[A-Za-z0-9_-]+(?:{OPT_VAL})?)*"
HTTP_METHOD = r"(?:[pP][uU][tT]|[pP][oO][sS][tT]|[pP][aA][tT][cC][hH])"
API_WRITE_FLAG = rf"(?:-X\s*=?\s*{HTTP_METHOD}|--method\s*=?\s*{HTTP_METHOD}|-f\b|-F\b|--field\b|--raw-field\b|--input\b)"

MERGE_PATTERNS = [
    (LEAD + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?(?:[/\w.-]+/)?gh\b" + OPT_FLAGS + r"\s+pr\b" + OPT_FLAGS + r"\s+merge\b", "gh pr merge"),
    (LEAD + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?(?:[/\w.-]+/)?glab\b" + OPT_FLAGS + r"\s+mr\b" + OPT_FLAGS + r"\s+merge\b", "glab mr merge"),
    (LEAD + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?(?:[/\w.-]+/)?gh\b[^\n]*\s+api\b[^\n]*" + API_WRITE_FLAG + r"[^\n]*/pulls/[^\n]+/merge\b", "gh api PR merge"),
    (LEAD + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?(?:[/\w.-]+/)?gh\b[^\n]*\s+api\b[^\n]*/pulls/[^\n]+/merge\b[^\n]*" + API_WRITE_FLAG, "gh api PR merge"),
    (LEAD + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?(?:[/\w.-]+/)?gh\b[^\n]*\s+api\b[^\n]*" + API_WRITE_FLAG + r"[^\n]*/repos/[^\n]+/merges\b", "gh api repository merge"),
    (LEAD + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?(?:[/\w.-]+/)?gh\b[^\n]*\s+api\b[^\n]*/repos/[^\n]+/merges\b[^\n]*" + API_WRITE_FLAG, "gh api repository merge"),
    (LEAD + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?(?:[/\w.-]+/)?gh\b(?:\s+[^\n]+)?\s+api\b[^\n]*graphql\b[^\n]*(?:mergePullRequest|enablePullRequestAutoMerge|disablePullRequestAutoMerge)", "gh api GraphQL PR merge"),
    (LEAD + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?(?:[/\w.-]+/)?glab\b[^\n]*\s+api\b[^\n]*" + API_WRITE_FLAG + r"[^\n]*/merge_requests/[^\n]+/merge\b", "glab api MR merge"),
    (LEAD + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?(?:[/\w.-]+/)?glab\b[^\n]*\s+api\b[^\n]*/merge_requests/[^\n]+/merge\b[^\n]*" + API_WRITE_FLAG, "glab api MR merge"),
]

ALLOW_FLAG = re.compile(r"(?:^|[\s;&|`\n])\s*(?:export\s+)?ALLOW_MERGE=(?:\"1\"|'1'|1\b)|(?:^|[\s;&|`\n])--allow-merge\b")
SPLIT = re.compile(r"&&|\|\||;|\||\n")


def mask_payloads(text: str) -> str:
    """Mask text payloads (comment bodies, commit messages, trailing shell comments, body files, API payload fields)
    so trigger patterns inside prose or file paths do not cause false positives or allow-flag bypasses.
    Handles escaped quotes inside multiline string literals without consuming command separators.
    Preserves newlines inside multiline string literals so segment alignment remains 1-to-1.
    """
    flag_pattern = r"(?:--body-file\b|--body\b|--title\b|--comment\b|--message\b|--reason\b|--notes\b|--description\b|-m\b|-b\b|-d\b|(?:-f|-F|--field|--raw-field|--input)\s+(?:body|title|comment|message|reason|notes|description)\b)"
    hspace = r"[ \t]*"

    def repl_flag(m):
        flag = m.group(1)
        val = m.group(2)
        masked_val = "".join("\n" if c == "\n" else " " for c in val)
        return flag + masked_val

    # 1. Mask quoted string payloads first (so # inside string literals is preserved for flag parsing)
    text = re.sub(rf"({flag_pattern}{hspace}=?{hspace})(\"(?:\\.|[^\"])*\")", repl_flag, text, flags=re.DOTALL)
    text = re.sub(rf"({flag_pattern}{hspace}=?{hspace})(\'(?:\\.|[^\'])*\')", repl_flag, text, flags=re.DOTALL)

    # 2. Mask trailing shell comments (# ...) only when preceded by whitespace/separator
    text = re.sub(r"(?:^|[\s;&|`()])#.*$", lambda m: " " * len(m.group(0)), text, flags=re.MULTILINE)

    # 3. Mask unquoted single-token flag values (e.g. --body-file /tmp/file.txt), allowing hyphens inside paths
    text = re.sub(rf"({flag_pattern}{hspace}=?{hspace})([^-;\s&|\n][^;\s&|\n]*)", repl_flag, text)

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
        local_host = platform.node()
        if pid and (not host or host == local_host):
            try:
                os.kill(int(pid), 0)
                return True
            except OSError:
                return False  # PID is dead on local host
        hb = int(sess_data.get("heartbeat") or sess_data.get("started") or 0)
        return (time.time() - hb) < 1800
    except Exception:
        pass
    return False


def get_git_common_dirs() -> list[Path]:
    dirs = []
    try:
        common_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"],
            text=True,
            stderr=subprocess.DEVNULL,
            cwd=os.getcwd(),
        ).strip()
        common_path = Path(common_dir)
        if not common_path.is_absolute():
            common_path = (Path.cwd() / common_path).resolve()
        dirs.append(common_path)
    except Exception:
        pass

    repo_dir = os.environ.get("CLAUDE_PROJECT_DIR") or str(Path(__file__).resolve().parents[1])
    try:
        common_dir = subprocess.check_output(
            ["git", "-C", repo_dir, "rev-parse", "--git-common-dir"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        common_path = Path(common_dir)
        if not common_path.is_absolute():
            common_path = (Path(repo_dir) / common_path).resolve()
        if common_path not in dirs:
            dirs.append(common_path)
    except Exception:
        pass

    pwd_git = Path.cwd() / ".git"
    if pwd_git.is_dir() and pwd_git.resolve() not in dirs:
        dirs.append(pwd_git.resolve())

    home_git = Path.home() / ".git"
    if home_git not in dirs:
        dirs.append(home_git)

    return dirs


def check_mwc_active() -> bool:
    try:
        current_session = os.environ.get("AI_SESSION_ID") or os.environ.get("CLAUDE_SESSION_ID")
        if not current_session:
            return False

        sanitized_session = sanitize(current_session)
        for common_dir in get_git_common_dirs():
            reg_dir = common_dir / "ai-sessions"
            if not reg_dir.exists():
                continue
            mwc_file = reg_dir / f"{sanitized_session}.mwc"
            if mwc_file.exists():
                sess_file = reg_dir / f"{sanitized_session}.session"
                if sess_file.exists() and is_session_alive(sess_file):
                    return True
    except Exception:
        pass
    return False


def offending(command: str):
    # 1. Normalize bash backslash-newline line continuations (matching bash semantics: remove backslash and newline without inserting a space)
    norm_command = re.sub(r"\\\n", "", command)
    # 2. Mask prose payloads across the entire command BEFORE splitting on separators/newlines
    masked_command = mask_payloads(norm_command)

    mwc_active = check_mwc_active()

    # 3. Use finditer on masked_command to derive exact character slice offsets for norm_command
    matches = list(SPLIT.finditer(masked_command))
    starts = [0] + [m.end() for m in matches]
    ends = [m.start() for m in matches] + [len(masked_command)]

    for start, end in zip(starts, ends):
        masked_seg = masked_command[start:end]
        orig_seg = norm_command[start:end]
        if ALLOW_FLAG.search(masked_seg) or mwc_active:
            continue
        for pattern, label in MERGE_PATTERNS:
            if re.search(pattern, masked_seg):
                return label, orig_seg.strip()
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
