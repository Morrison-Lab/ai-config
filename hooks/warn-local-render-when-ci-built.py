#!/usr/bin/env python3
"""PreToolUse (Bash): warn before a local `quarto render` in a repo whose CI publishes to gh-pages.

ai-config#4724; shared/workflow/lab-operating-rules.md. Ezra, 2026-10-25:
"isn't it already rendered in mlg ... remember that going forward". A repo with a
gh-pages ref already has CI-built HTML and PDFs for main's head, so a local render
(for a Canvas upload, a preview, a check) repeats work and can differ from what
students see. Adds a warning, never blocks: a local render is right when the source
changed and CI has not built it yet. Fails open on any parse or git trouble.
"""
import json
import os
import re
import subprocess
import sys

RENDER = re.compile(r"(?:^|[;&|(\s])quarto\s+render\b")

WARNING = (
    "[hook: warn-local-render-when-ci-built] This repo has a gh-pages ref, so CI has "
    "probably already built the output. Download the PDF or HTML from the gh-pages "
    "branch or the published site instead of rendering locally "
    "(Canvas uploads always use the CI-built PDF). Render locally only when the "
    "source changed and CI has not built it yet. "
    "shared/workflow/lab-operating-rules.md; ai-config#4724."
)


def has_gh_pages(cwd: str) -> bool:
    for ref in ("refs/remotes/origin/gh-pages", "refs/heads/gh-pages"):
        try:
            done = subprocess.run(
                ["git", "-C", cwd, "rev-parse", "--verify", "--quiet", ref],
                capture_output=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return False
        if done.returncode == 0:
            return True
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not RENDER.search(command):
        return 0
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not os.path.isdir(cwd):
        return 0
    if has_gh_pages(cwd):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": WARNING,
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
