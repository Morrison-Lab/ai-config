#!/usr/bin/env python3
"""Test suite for hooks/warn-recursive-search-cloud-mount.py."""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = ROOT / "hooks" / "warn-recursive-search-cloud-mount.py"

# Import hook as module
sys.path.insert(0, str(ROOT / "hooks"))
mod = importlib.import_module("warn-recursive-search-cloud-mount")


def run_hook(payload: dict, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Execute the hook with JSON payload on stdin."""
    run_env = os.environ.copy()
    run_env.pop("ANTIGRAVITY_AGENT", None)
    if env:
        run_env.update(env)
    res = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=run_env,
    )
    return res.returncode, res.stdout, res.stderr


def test_path_matcher() -> None:
    """Test is_cloud_mount_path on various path formats."""
    # Positive cloud mounts
    assert mod.is_cloud_mount_path(r"G:\My Drive\Texts 2")
    assert mod.is_cloud_mount_path("G:/My Drive/Texts 2")
    assert mod.is_cloud_mount_path("G:")
    assert mod.is_cloud_mount_path("G:\\")
    assert mod.is_cloud_mount_path("/g/My Drive/Texts 2")
    assert mod.is_cloud_mount_path("//g/My Drive")
    assert mod.is_cloud_mount_path("/cygdrive/g/Texts")
    assert mod.is_cloud_mount_path("/mnt/g/Texts")
    assert mod.is_cloud_mount_path(r"C:\Users\dougm\OneDrive\Documents")
    assert mod.is_cloud_mount_path("/c/Users/dougm/OneDrive - Personal/Docs")
    assert mod.is_cloud_mount_path("~/OneDrive/Work")
    assert mod.is_cloud_mount_path(r"C:\Users\user\Dropbox\Projects")
    assert mod.is_cloud_mount_path("~/Dropbox/files")
    assert mod.is_cloud_mount_path("/Users/user/Library/CloudStorage/GoogleDrive-me@org.com/My Drive")
    assert mod.is_cloud_mount_path(r"\\fileserver\share\datasets")
    assert mod.is_cloud_mount_path("//fileserver/share/datasets")
    assert mod.is_cloud_mount_path(r"C:\Users\user\Box Sync\Folder")
    assert mod.is_cloud_mount_path("~/iCloud Drive/Documents")

    # Negative: local paths
    assert not mod.is_cloud_mount_path(r"C:\Users\dougm\ai-config")
    assert not mod.is_cloud_mount_path("/home/user/ai-config")
    assert not mod.is_cloud_mount_path("/c/Users/dougm/projects")
    assert not mod.is_cloud_mount_path("src/lib")
    assert not mod.is_cloud_mount_path(".")
    assert not mod.is_cloud_mount_path("")


def test_evaluate_find_positives() -> None:
    """Positive find cases that must trigger warning."""
    positives = [
        ('find "G:\\My Drive\\Texts 2" -name "*.pdf"', None, "find"),
        ('find /g/My\\ Drive/Texts\\ 2 -type f', None, "find"),
        ('find "C:\\Users\\user\\OneDrive\\Docs"', None, "find"),
        ('find "//server/share/data" -iname "*report*"', None, "find"),
        (r"find '\\server\share\data' -name '*.csv'", None, "find"),
        ('cd "G:\\My Drive\\Texts 2" && find . -name "*.pdf"', None, "find"),
        ('cd /g/My\\ Drive && find Texts -type f', None, "find"),
        ('timeout 300 find /g/My\\ Drive/Texts\\ 2 -iname "*hastie*"', None, "find"),
        ('timeout 400s find "G:\\My Drive\\Texts 2" -print', None, "find"),
        ('time find "G:\\My Drive" -type d', None, "find"),
        ('find . -name "*.pdf"', r"G:\My Drive\Texts 2", "find"),
    ]
    for cmd, cwd, expected_cmd in positives:
        hit = mod.evaluate_command(cmd, cwd)
        assert hit is not None, f"Expected warning for command: {cmd!r}"
        matched_cmd, path = hit
        assert matched_cmd == expected_cmd, f"Expected {expected_cmd}, got {matched_cmd}"
        assert mod.is_cloud_mount_path(path), f"Path not recognized as cloud mount: {path}"


def test_evaluate_grep_positives() -> None:
    """Positive grep cases that must trigger warning."""
    positives = [
        ('grep -r "needle" "G:\\My Drive\\Texts 2"', None, "grep"),
        ('grep -R "needle" /g/My\\ Drive/', None, "grep"),
        ('grep -rn "needle" ~/Dropbox', None, "grep"),
        ('rgrep "needle" /g/Texts', None, "rgrep"),
        ('cd "G:\\My Drive\\Texts 2" && grep -r "needle" .', None, "grep"),
        ('timeout 200 grep -r "needle" "G:\\My Drive"', None, "grep"),
    ]
    for cmd, cwd, expected_cmd in positives:
        hit = mod.evaluate_command(cmd, cwd)
        assert hit is not None, f"Expected warning for command: {cmd!r}"
        matched_cmd, path = hit
        assert matched_cmd == expected_cmd
        assert mod.is_cloud_mount_path(path)


def test_evaluate_rg_and_fd_positives() -> None:
    """Positive rg and fd cases that must trigger warning."""
    positives = [
        ('rg "needle" "G:\\My Drive\\Texts 2"', None, "rg"),
        ('rg "needle" /g/My\\ Drive', None, "rg"),
        ('cd "G:\\My Drive" && rg "needle"', None, "rg"),
        ('fd "pattern" "G:\\My Drive"', None, "fd"),
        ('fdfind "pattern" /g/My\\ Drive', None, "fdfind"),
    ]
    for cmd, cwd, expected_cmd in positives:
        hit = mod.evaluate_command(cmd, cwd)
        assert hit is not None, f"Expected warning for command: {cmd!r}"
        matched_cmd, path = hit
        assert matched_cmd == expected_cmd
        assert mod.is_cloud_mount_path(path)


def test_evaluate_other_positives() -> None:
    """Positive ls -R, dir /s, glob **, and PowerShell cases."""
    positives = [
        ('ls -R "G:\\My Drive"', None, "ls -R"),
        ('ls --recursive /g/My\\ Drive', None, "ls -R"),
        ('dir /s "G:\\My Drive"', None, "dir /s"),
        ('Get-ChildItem -Recurse "G:\\My Drive"', None, "get-childitem -Recurse"),
        ('gci -r "G:\\My Drive"', None, "gci -Recurse"),
        ('for f in "G:\\My Drive\\**\\*.pdf"; do echo $f; done', None, "glob **"),
        ('ls "G:/My Drive/**/*.pdf"', None, "glob **"),
    ]
    for cmd, cwd, expected_cmd in positives:
        hit = mod.evaluate_command(cmd, cwd)
        assert hit is not None, f"Expected warning for command: {cmd!r}"
        matched_cmd, path = hit
        assert matched_cmd == expected_cmd


def test_evaluate_negatives() -> None:
    """Negative cases that must NOT trigger warning."""
    negatives = [
        # Bounded find
        ('find "G:\\My Drive\\Texts 2" -maxdepth 1', None),
        ('find /g/My\\ Drive -maxdepth 0', None),
        ('find "G:\\My Drive" -maxdepth=1 -type d', None),
        ('find "G:\\My Drive" -maxdepth 1 -name "*.pdf"', None),
        # Bounded rg and fd
        ('rg --max-depth 1 "needle" "G:\\My Drive"', None),
        ('rg -d 1 "needle" /g/My\\ Drive', None),
        ('rg --max-depth=1 "needle" "G:\\My Drive"', None),
        ('fd -d 1 "pattern" "G:\\My Drive"', None),
        ('fd --max-depth 1 "pattern" /g/My\\ Drive', None),
        # Plain listing and non-recursive inspection
        ('ls "G:\\My Drive\\Texts 2"', None),
        ('ls -la "G:\\My Drive\\Texts 2\\Texts_by_Title"', None),
        ('dir "G:\\My Drive"', None),
        # Non-recursive grep on a single file
        ('grep "needle" "G:\\My Drive\\Texts 2\\book.txt"', None),
        ('grep -n "needle" /g/My\\ Drive/index.md', None),
        # Searches in local repositories
        ('find . -name "*.py"', r"C:\Users\dougm\ai-config"),
        ('find src/ -type f', "/home/user/code"),
        ('grep -r "needle" src/', r"C:\Users\dougm\ai-config"),
        ('rg "needle" .', r"C:\Users\dougm\ai-config"),
        ('fd "test" hooks/', r"C:\Users\dougm\ai-config"),
        ('ls -R hooks/', r"C:\Users\dougm\ai-config"),
        # Explicit bypass
        ('ALLOW_RECURSIVE_CLOUD_SEARCH=1 find "G:\\My Drive"', None),
        ('ALLOW_RECURSIVE_CLOUD_SEARCH=1 grep -r "needle" "G:\\My Drive"', None),
        ('export ALLOW_RECURSIVE_CLOUD_SEARCH=1 && find "G:\\My Drive"', None),
    ]
    for cmd, cwd in negatives:
        hit = mod.evaluate_command(cmd, cwd)
        assert hit is None, f"Expected NO warning for command: {cmd!r}, got: {hit}"


def test_hook_output_shape_and_payload() -> None:
    """Assert hook emits correct output shape with additionalContext and systemMessage."""
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": 'timeout 300 find "G:\\My Drive\\Texts 2" -name "*.pdf"'
        },
        "cwd": r"C:\Users\dougm\ai-config",
    }
    rc, stdout, stderr = run_hook(payload)
    assert rc == 0, f"Hook exited with non-zero code {rc}: {stderr}"
    data = json.loads(stdout)

    # Must contain hookSpecificOutput with additionalContext
    hook_out = data.get("hookSpecificOutput", {})
    assert hook_out.get("hookEventName") == "PreToolUse"
    assert "additionalContext" in hook_out
    assert "memories/course-repos.md" in hook_out["additionalContext"]
    assert "Texts_by_Title" in hook_out["additionalContext"]

    # Must contain systemMessage when ANTIGRAVITY_AGENT is not set
    assert "systemMessage" in data
    assert "memories/course-repos.md" in data["systemMessage"]


def test_hook_dry_run_and_clean_run() -> None:
    """Test hook handles dry-run mode and clean local commands."""
    # Clean local command
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "git status"},
        "cwd": r"C:\Users\dougm\ai-config",
    }
    rc, stdout, stderr = run_hook(payload)
    assert rc == 0
    assert stdout.strip() == ""

    # Dry-run on clean command
    payload["is_dry_run"] = True
    payload["tool_input"]["command"] = "git status"
    rc, stdout, stderr = run_hook(payload)
    assert rc == 0
    data = json.loads(stdout)
    assert data.get("hookSpecificOutput", {}).get("hookEventName") == "PreToolUse"
    assert "additionalContext" not in data.get("hookSpecificOutput", {})

    # Dry-run on warning command: still emits additionalContext
    payload["tool_input"]["command"] = 'find "G:\\My Drive"'
    rc, stdout, stderr = run_hook(payload)
    assert rc == 0
    data = json.loads(stdout)
    assert "additionalContext" in data.get("hookSpecificOutput", {})


def test_env_override() -> None:
    """Test environment variable bypass."""
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": 'find "G:\\My Drive"'},
        "cwd": r"C:\Users\dougm\ai-config",
    }
    rc, stdout, stderr = run_hook(payload, env={"ALLOW_RECURSIVE_CLOUD_SEARCH": "1"})
    assert rc == 0
    assert stdout.strip() == ""


def main() -> int:
    test_path_matcher()
    test_evaluate_find_positives()
    test_evaluate_grep_positives()
    test_evaluate_rg_and_fd_positives()
    test_evaluate_other_positives()
    test_evaluate_negatives()
    test_hook_output_shape_and_payload()
    test_hook_dry_run_and_clean_run()
    test_env_override()
    print("All tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
