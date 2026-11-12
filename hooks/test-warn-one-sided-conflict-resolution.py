#!/usr/bin/env python3
"""Tests for hooks/warn-one-sided-conflict-resolution.py (ai-config#5407).

Each case feeds a PreToolUse payload to the hook as a subprocess and checks
whether the warning fires.

Run:
    python3 hooks/test-warn-one-sided-conflict-resolution.py [hook path]
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
    HOOK = os.path.realpath(sys.argv[1])
else:
    HOOK = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                        "warn-one-sided-conflict-resolution.py")

WARN = (
    "git checkout --ours -- a.txt",
    "git checkout --theirs a.txt b.txt",
    "git restore --theirs -- a.txt",
    "git -C repo checkout --ours a.txt",
    "GIT_TRACE=0 git checkout --theirs a.txt",
    "git status && git checkout --ours a.txt",
    "git merge -X ours main",
    "git merge -X theirs origin/main",
    "git merge -Xtheirs main",
    "git merge --strategy-option=ours main",
    "git merge --strategy-option theirs main",
    "git rebase -X theirs origin/main",
    "git cherry-pick -X ours abc123",
    "git revert -X theirs abc123",
    "git pull -X theirs origin main",
    "git merge -s ours old-branch",
    "git merge -sours old-branch",
    "git merge --strategy=ours old-branch",
    "git cherry-pick --strategy ours abc123",
    "sudo git merge -s recursive -X ours main",
    "git restore --ours a.txt",
    "git merge-file --ours a base b",
    "git merge-file --theirs a base b",
    "git checkout --our a.txt",
    "git checkout --thei a.txt",
    "git restore --th a.txt",
    "git restore --t a.txt",
    "git merge-file --t a base b",
    "git checkout -3 a.txt",
    "git restore -2 a.txt",
    "git checkout -f3 a.txt",
    "git restore -W3 a.txt",
    "git merge -qs ours x",
    "git merge -ns ours x",
    "git merge -qXours x",
    "git rebase -fXours main",
    "git rebase -sours main",
    "git pull -sours origin main",
    "git pull -v -s ours origin main",
    "git rebase --strategy-o=theirs main",
    "git checkout --ou a.txt",
    "git checkout --th a.txt",
    "git restore --ou a.txt",
    "git merge-file --ou a base b",
    "git checkout --ours -- a --abort",
    "git checkout --theirs -- --quit",
    "git merge -s ours --no-edit x",
    "git merge -S -s ours x",
    "git merge -s ours -- --abort",
    "git rebase -s ours main",
    "git rebase --strategy=ours main",
    "git pull -s ours origin main",
    "git revert --strategy ours abc123",
    "git rebase --strategy-option=theirs main",
    "git cherry-pick --strategy-option ours abc123",
    "git merge --strategy-opt=ours main",
    "git rebase --strategy- theirs main",
    "bash -c 'git merge -X ours main'",
    "sh -c \"git checkout --theirs a.txt\"",
    "bash -lc 'cd repo && git checkout --ours a.txt'",
    # Three nested shells is within MAX_DEPTH.
    "bash -c \"bash -c 'bash -c git\\ merge\\ -X\\ ours'\"",
)

SILENT = (
    "git checkout main",
    "git checkout -- a.txt",
    "git checkout -b ours",
    "git checkout feature -- theirs.txt",
    "git checkout -- --ours",
    "git restore --staged a.txt",
    "git merge main",
    "git merge -X patience main",
    "git merge -s recursive main",
    "git merge -s theirs main",
    "git cherry-pick -s abc123",
    "git revert -s ours",
    "git rebase origin/main",
    "echo 'git checkout --ours a.txt'",
    "grep -n 'merge -X ours' notes.md",
    "git log --grep=ours",
    "git diff --ours",
    "git rebase -s recursive main",
    "git pull -s recursive origin main",
    "git merge -X ours --abort",
    "git rebase -X theirs --quit",
    "git checkout --o a.txt",
    "git checkout --t origin/x",
    "git restore --o a.txt",
    "git merge-file --o a base b",
    "git merge-file -2 a base b",
    "git checkout -b3",
    "git restore -s3 a.txt",
    "git checkout -B3",
    "git merge -m -X ours main",
    "git merge -m '-s ours' main",
    "git merge --message -X ours main",
    "git merge -F -s ours main",
    "git rebase -x -sours main",
    "git rebase -Sours main",
    "git rebase -Ssours main",
    "git merge -mXours x",
    "git merge -s ours --abort",
    "git rebase --strat=ours main",
    "git pull --strat=ours origin main",
    "git restore -Ws3 a.txt",
    "git checkout --ourselves a.txt",
    "git restore --theirsx a.txt",
    "git merge-file --theirsx a base b",
    "git checkout --orphan new",
    "git merge-file --union a base b",
    "bash -c 'git status'",
    "git merge main -X",
    "git merge --strat=ours main",
    "git merge --strategy-opt=patience main",
    "git merge --strategy-options=ours main",
    "git merge main -- -X ours",
    # Four nested shells is past MAX_DEPTH (3), so it is not unwrapped.
    "bash -c \"bash -c 'bash -c \\\"bash -c git\\\\ merge\\\\ -X\\\\ ours\\\"'\"",
    "",
)


def run(command: str) -> str:
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    proc = subprocess.run(
        [sys.executable, HOOK], input=json.dumps(payload),
        capture_output=True, text=True, encoding="utf-8",
    )
    if not proc.stdout.strip():
        return ""
    data = json.loads(proc.stdout)
    return data["hookSpecificOutput"].get("additionalContext", "")


def main() -> int:
    failures = 0
    total = 0
    for command in WARN:
        total += 1
        text = run(command)
        if "warn-one-sided-conflict-resolution" not in text:
            failures += 1
            print(f"FAIL (no warning): {command}")
    for command in SILENT:
        total += 1
        text = run(command)
        if text:
            failures += 1
            print(f"FAIL (warned): {command}")
    # The warning names the command form it found, and what it drops.
    for command, label, effect in (
            ("git merge -s ours x", "`git merge -s ours`", "other side's changes entirely"),
            ("git revert --strategy=ours a", "`git revert --strategy ours`", "entirely"),
            ("git checkout --our a", "`git checkout --ours`", "whole file"),
            ("git restore --theirs a", "`git restore --theirs`", "whole file"),
            ("git merge-file --ours a b c", "`git merge-file --ours`", "per-hunk decision"),
            ("git merge -Xtheirs x", "`git merge -X theirs`", "per-hunk decision"),
    ):
        total += 1
        text = run(command)
        if label not in text or effect not in text:
            failures += 1
            print(f"FAIL: warning for {command!r} lacks {label} or {effect!r}")
    # Non-Bash tools and unreadable input stay silent.
    for raw in ('{"tool_name": "Edit", "tool_input": {"command": "git checkout --ours a"}}',
                "not json"):
        total += 1
        proc = subprocess.run([sys.executable, HOOK], input=raw,
                              capture_output=True, text=True, encoding="utf-8")
        if proc.stdout.strip() or proc.returncode != 0:
            failures += 1
            print(f"FAIL (non-Bash or bad input produced output): {raw}")
    # Both fail-open paths exit 0 with no output and say why on stderr: a
    # missing scripts/lib (broken install), and an exception while parsing.
    stub_raises = "def simple_commands(c):\n    raise RuntimeError('boom')\n" \
        "git_subcommand = nested_shell_commands = simple_commands\n"
    for lib, note in ((None, "cannot load"), (stub_raises, "boom")):
        total += 1
        tmp = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(tmp, "hooks"))
            hook = os.path.join(tmp, "hooks", os.path.basename(HOOK))
            shutil.copy(HOOK, hook)
            if lib is not None:
                os.makedirs(os.path.join(tmp, "scripts", "lib"))
                with open(os.path.join(tmp, "scripts", "lib", "shellcmd.py"),
                          "w", encoding="utf-8") as fh:
                    fh.write(lib)
            payload = {"tool_name": "Bash",
                       "tool_input": {"command": "git checkout --ours a"}}
            proc = subprocess.run([sys.executable, hook], input=json.dumps(payload),
                                  capture_output=True, text=True, encoding="utf-8")
        finally:
            shutil.rmtree(tmp)
        if proc.returncode != 0 or proc.stdout.strip() or note not in proc.stderr:
            failures += 1
            print(f"FAIL (fail-open {note!r}): rc={proc.returncode} "
                  f"stdout={proc.stdout!r} stderr={proc.stderr!r}")
    print(f"\n{total - failures}/{total} tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
