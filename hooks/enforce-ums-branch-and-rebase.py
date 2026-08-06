#!/usr/bin/env python3
"""PreToolUse guard enforcing dedicated UMS branch naming and origin/main rebase freshness.

CLAUDE.md / memories/preferences.md standing directives:
1. "Always create a dedicated ums-<topic> or ums/<topic> branch off origin/main for UMS memory passes."
2. "Always fetch and merge origin/main into the UMS branch before opening a UMS PR."

This hook intercepts PreToolUse Bash calls to `git commit`, `git push`, and `gh pr create` that stage or modify memory/skill files (memories/*.md, MEMORY.md, CLAUDE.md, GEMINI.md, skills/*):
  1. BLOCKS commits/pushes of memory/skill files on non-UMS branches (e.g. main or feature branches like rule/*, feat/*).
  2. BLOCKS commits/pushes/PR creation on `ums/*` or `ums-*` branches if the branch is behind `origin/main`.
"""

import json
import os
import re
import subprocess
import sys


def get_current_branch(cwd: str) -> str:
    """Return the active git branch name for cwd."""
    try:
        res = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return ""


def get_changed_files_against_main(cwd: str) -> list[str]:
    """Return all file paths changed between origin/main and HEAD."""
    try:
        res = subprocess.run(
            ["git", "diff", "origin/main...HEAD", "--name-only"],
            cwd=cwd,
            text=True,
            capture_output=True,
        )
        if res.returncode == 0:
            return [f.strip() for f in res.stdout.splitlines() if f.strip()]
    except Exception:
        pass
    return []


def get_staged_or_modified_files(cwd: str) -> list[str]:
    """Return list of staged, modified, or branch-changed file paths."""
    files = set()
    try:
        # Check staged files
        res = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=cwd,
            text=True,
            capture_output=True,
        )
        if res.returncode == 0:
            files.update(res.stdout.splitlines())

        # Union with full diff against origin/main
        files.update(get_changed_files_against_main(cwd))
    except Exception:
        pass
    return [f.strip() for f in files if f.strip()]


def touches_memory_or_skill(files: list[str]) -> bool:
    """Return True if any file path is a memory or skill documentation file."""
    pattern = re.compile(r"^(?:memories/|MEMORY\.md|CLAUDE\.md|GEMINI\.md|skills/)", re.I)
    return any(pattern.search(f) for f in files)


def is_behind_origin_main(cwd: str) -> bool:
    """Return True if current branch is behind origin/main."""
    try:
        res = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..origin/main"],
            cwd=cwd,
            text=True,
            capture_output=True,
        )
        if res.returncode == 0 and res.stdout.strip().isdigit():
            return int(res.stdout.strip()) > 0
    except Exception:
        pass
    return False


def inspect_command(command: str, cwd: str = ".") -> str | None:
    """Inspect bash command and return blocking message if UMS branch or rebase rule is violated."""
    is_commit = re.search(r"\bgit\s+commit\b", command)
    is_push = re.search(r"\bgit\s+push\b", command)
    is_pr_create = re.search(r"\bgh\s+pr\s+create\b", command)

    if not (is_commit or is_push or is_pr_create):
        return None

    branch = get_current_branch(cwd)
    if not branch:
        return None

    # Support both slash (ums/topic) and hyphen (ums-topic) branch naming conventions
    is_ums_branch = bool(re.match(r"^(?:ums|docs|chore)[/-]", branch))

    # For PR creation on UMS branches
    if is_pr_create and is_ums_branch:
        if is_behind_origin_main(cwd):
            return (
                f"MECHANISTIC PROHIBITION: UMS branch '{branch}' is behind origin/main. "
                f"Please run 'git fetch origin main && git merge origin/main' before creating the PR to prevent merge conflicts."
            )
        return None

    # For git commit / git push: check if memory or skill files are touched
    files = get_staged_or_modified_files(cwd)
    if touches_memory_or_skill(files):
        if not is_ums_branch:
            return (
                f"MECHANISTIC PROHIBITION: UMS memory/skill updates (modifying {', '.join(f for f in files if touches_memory_or_skill([f]))}) "
                f"must be committed to a dedicated 'ums/<topic>' or 'ums-<topic>' branch off origin/main, not directly to feature branch '{branch}'. "
                f"Please create a dedicated worktree via 'git worktree add -b ums/<topic> origin/main' first."
            )
        if is_behind_origin_main(cwd):
            return (
                f"MECHANISTIC PROHIBITION: UMS branch '{branch}' is behind origin/main. "
                f"Please run 'git fetch origin main && git merge origin/main' to bring it up to date before committing or pushing."
            )

    return None


def main() -> int:
    try:
        data = json.load(sys.stdin)
        command = data.get("tool_input", {}).get("command", "")
        cwd = data.get("cwd", os.getcwd())
    except Exception:
        return 0

    reason = inspect_command(command, cwd)
    if reason:
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
        print(json.dumps(out))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
