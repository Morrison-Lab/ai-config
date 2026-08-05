#!/usr/bin/env python3
"""PreToolUse guard: mechanistically prohibit PR/MR merge commands.

Prohibits commands attempting to merge PRs/MRs (e.g. `gh pr merge`, `glab mr merge`,
or `gh api .../merge`) unless explicit authorization is present via ALLOW_MERGE=1
or --allow-merge.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

LEAD = r"""^\s*(?:[A-Za-z_][A-Za-z0-9_]*=(?:"[^"]*"|'[^']*'|\S*)\s+)*"""

MERGE_PATTERNS = [
    (LEAD + r"gh(?:\s+[^\n]+)?\s+pr\s+merge\b", "gh pr merge"),
    (LEAD + r"glab(?:\s+[^\n]+)?\s+mr\s+merge\b", "glab mr merge"),
    (LEAD + r"gh(?:\s+[^\n]+)?\s+api\b[^\n]*/pulls/\d+/merge\b", "gh api PR merge"),
]

ALLOW_FLAG = re.compile(r"\bALLOW_MERGE=1\b|\b--allow-merge\b")
SPLIT = re.compile(r"&&|\|\||;|\||\n")


def mask_strings(text: str) -> str:
    """Mask string literals so trigger patterns inside comments/bodies are not matched."""
    def repl(m):
        raw = m.group(0)
        return raw[0] + (" " * (len(raw) - 2)) + raw[-1] if len(raw) >= 2 else raw

    text = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', repl, text)
    text = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", repl, text)
    return text


def is_session_alive(sess_file: Path) -> bool:
    try:
        content = sess_file.read_text(encoding="utf-8")
        sess_data = dict(line.split("=", 1) for line in content.splitlines() if "=" in line)
        pid = sess_data.get("pid")
        if pid:
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


def check_mwc_active() -> bool:
    try:
        common_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        reg_dir = Path(common_dir) / "ai-sessions"
        if not reg_dir.exists():
            return False

        current_session = os.environ.get("AI_SESSION_ID") or os.environ.get("CLAUDE_SESSION_ID")

        for mwc_file in reg_dir.glob("*.mwc"):
            s_id = mwc_file.stem
            if current_session and s_id != current_session:
                continue
            sess_file = reg_dir / f"{s_id}.session"
            if sess_file.exists() and is_session_alive(sess_file):
                return True
    except Exception:
        pass
    return False


def offending(command: str):
    mwc_active = check_mwc_active()
    for segment in SPLIT.split(command):
        if ALLOW_FLAG.search(segment) or mwc_active:
            continue
        masked_segment = mask_strings(segment)
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
