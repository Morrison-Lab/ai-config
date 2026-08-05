#!/usr/bin/env python3
"""PreToolUse guard: mechanistically prohibit PR/MR merge commands.

Prohibits commands attempting to merge PRs/MRs (e.g. `gh pr merge`, `glab mr merge`,
or `gh api .../merge`) unless explicit authorization is present via ALLOW_MERGE=1
or --allow-merge.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

LEAD = r"""^\s*(?:[A-Za-z_][A-Za-z0-9_]*=(?:"[^"]*"|'[^']*'|\S*)\s+)*"""

MERGE_PATTERNS = [
    (LEAD + r"gh\s+pr\s+merge\b", "gh pr merge"),
    (LEAD + r"glab\s+mr\s+merge\b", "glab mr merge"),
    (LEAD + r"gh\s+api\b[^\n]*/pulls/\d+/merge\b", "gh api PR merge"),
]

ALLOW_FLAG = re.compile(r"\bALLOW_MERGE=1\b|\b--allow-merge\b")
SPLIT = re.compile(r"&&|\|\||;|\||\n")


def check_mwc_active() -> bool:
    try:
        common_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        reg_dir = Path(common_dir) / "ai-sessions"
        if reg_dir.exists():
            for mwc_file in reg_dir.glob("*.mwc"):
                session_id = mwc_file.stem
                sess_file = reg_dir / f"{session_id}.session"
                if sess_file.exists():
                    return True
    except Exception:
        pass
    return False


def offending(command: str):
    if ALLOW_FLAG.search(command) or check_mwc_active():
        return None
    for segment in SPLIT.split(command):
        for pattern, label in MERGE_PATTERNS:
            if re.search(pattern, segment):
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
        "by the user or executing under an explicit override (e.g. ALLOW_MERGE=1)."
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
