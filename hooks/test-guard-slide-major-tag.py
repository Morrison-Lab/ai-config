#!/usr/bin/env python3
"""Test the guard-slide-major-tag PreToolUse hook.

Verifies:
  - Adding a job permission to a reusable workflow (on: workflow_call) denies slide-major-tag.
  - Removing a permission allows.
  - Adding a permission to a non-workflow_call workflow allows.
  - Adding a `# checks: read` comment line allows.
  - ALLOW_BREAKING_SLIDE=1 allows.
  - Non-slide commands allow.
  - Missing tag allows with stderr note.
  - Missing remote branch allows with stderr note.
  - Mutation check: flipping the regex to ignore 'read' fails the deny test.

Run:
    python3 hooks/test-guard-slide-major-tag.py [hooks/guard-slide-major-tag.py]
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
    HOOK = os.path.abspath(sys.argv[1])
else:
    HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard-slide-major-tag.py")

_TMPDIRS: list[str] = []


def _run(cwd: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def _write_file(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _make_repo(
    workflow_name: str = "reusable.yml",
    on_block: str = "  workflow_call:\n",
    permissions_block: str = "    permissions:\n      contents: read\n",
    create_tag: bool = True,
    create_remote: bool = True,
) -> str:
    path = tempfile.mkdtemp()
    _TMPDIRS.append(path)
    _run(path, "init", "-q", "-b", "main")
    _run(path, "config", "user.email", "test@example.com")
    _run(path, "config", "user.name", "Test User")

    wf_file = os.path.join(path, ".github", "workflows", workflow_name)
    initial_content = (
        f"name: Workflow\n"
        f"on:\n{on_block}"
        f"jobs:\n"
        f"  review:\n"
        f"    runs-on: ubuntu-latest\n"
        f"{permissions_block}"
        f"    steps:\n"
        f"      - run: echo ok\n"
    )
    _write_file(wf_file, initial_content)
    _run(path, "add", ".")
    _run(path, "commit", "-qm", "initial commit")

    if create_tag:
        _run(path, "tag", "v2")

    if create_remote:
        _run(path, "update-ref", "refs/remotes/origin/main", "HEAD")

    return path


def _advance_commit(
    path: str,
    workflow_name: str,
    new_content: str,
    update_remote: bool = True,
) -> None:
    wf_file = os.path.join(path, ".github", "workflows", workflow_name)
    _write_file(wf_file, new_content)
    _run(path, "add", ".")
    _run(path, "commit", "-qm", "update workflow")
    if update_remote:
        _run(path, "update-ref", "refs/remotes/origin/main", "HEAD")


def run_hook(hook_path: str, command: str, cwd: str) -> tuple[str, str, str]:
    """Run hook subprocess; return (verdict, reason, stderr).
    verdict is 'deny' or 'allow'.
    """
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": cwd,
    }
    proc = subprocess.run(
        [sys.executable, hook_path],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    if proc.stdout.strip():
        try:
            data = json.loads(proc.stdout)
            hso = data.get("hookSpecificOutput", {})
            if hso.get("permissionDecision") == "deny":
                return "deny", hso.get("permissionDecisionReason", ""), proc.stderr
        except json.JSONDecodeError:
            pass
    return "allow", "", proc.stderr


def main() -> int:
    passes = 0
    failures = 0

    def check(condition: bool, label: str, detail: str = "") -> None:
        nonlocal passes, failures
        if condition:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label}{' - ' + detail if detail else ''}")
            failures += 1

    try:
        # 1. Deny added job permission in reusable workflow
        repo1 = _make_repo()
        new_content1 = (
            "name: Workflow\n"
            "on:\n  workflow_call:\n"
            "jobs:\n"
            "  review:\n"
            "    runs-on: ubuntu-latest\n"
            "    permissions:\n"
            "      contents: read\n"
            "      checks: read\n"
            "    steps:\n"
            "      - run: echo ok\n"
        )
        _advance_commit(repo1, "reusable.yml", new_content1)
        v, r, _ = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo1)
        check(
            v == "deny" and "checks: read" in r and "reusable.yml" in r and "ALLOW_BREAKING_SLIDE=1" in r,
            "deny added job permission to reusable workflow",
            f"got verdict={v}, reason={r}",
        )

        # 1b. Deny with arguments in other orders (e.g. -R flag)
        v_order, _, _ = run_hook(HOOK, "gh workflow run -R Morrison-Lab/gha slide-major-tag.yml", repo1)
        check(v_order == "deny", "deny slide-major-tag with -R flag before workflow name")

        v_order2, _, _ = run_hook(HOOK, "gh -R Morrison-Lab/gha workflow run slide-major-tag.yml", repo1)
        check(v_order2 == "deny", "deny slide-major-tag with -R flag before workflow subcommand")

        # 2. Allow removed permission
        repo2 = _make_repo(
            permissions_block="    permissions:\n      contents: read\n      checks: read\n"
        )
        new_content2 = (
            "name: Workflow\n"
            "on:\n  workflow_call:\n"
            "jobs:\n"
            "  review:\n"
            "    runs-on: ubuntu-latest\n"
            "    permissions:\n"
            "      contents: read\n"
            "    steps:\n"
            "      - run: echo ok\n"
        )
        _advance_commit(repo2, "reusable.yml", new_content2)
        v2, _, _ = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo2)
        check(v2 == "allow", "allow permission removal", f"got verdict={v2}")

        # 3. Allow permission addition to workflow without workflow_call
        repo3 = _make_repo(on_block="  push:\n")
        new_content3 = (
            "name: Workflow\n"
            "on:\n  push:\n"
            "jobs:\n"
            "  review:\n"
            "    runs-on: ubuntu-latest\n"
            "    permissions:\n"
            "      contents: read\n"
            "      checks: read\n"
            "    steps:\n"
            "      - run: echo ok\n"
        )
        _advance_commit(repo3, "reusable.yml", new_content3)
        v3, _, _ = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo3)
        check(v3 == "allow", "allow permission addition to non-workflow_call workflow", f"got verdict={v3}")

        # 4. Allow '# checks: read' comment line addition
        repo4 = _make_repo()
        new_content4 = (
            "name: Workflow\n"
            "on:\n  workflow_call:\n"
            "jobs:\n"
            "  review:\n"
            "    runs-on: ubuntu-latest\n"
            "    permissions:\n"
            "      contents: read\n"
            "      # checks: read\n"
            "    steps:\n"
            "      - run: echo ok\n"
        )
        _advance_commit(repo4, "reusable.yml", new_content4)
        v4, _, _ = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo4)
        check(v4 == "allow", "allow # checks: read comment line addition", f"got verdict={v4}")

        # 5. Allow when ALLOW_BREAKING_SLIDE=1 override prefix is present
        v5, _, _ = run_hook(HOOK, "ALLOW_BREAKING_SLIDE=1 gh workflow run slide-major-tag.yml", repo1)
        check(v5 == "allow", "allow when ALLOW_BREAKING_SLIDE=1 prefix present", f"got verdict={v5}")

        # 6. Allow non-slide command
        v6, _, _ = run_hook(HOOK, "git status", repo1)
        check(v6 == "allow", "allow non-slide command (git status)", f"got verdict={v6}")

        v6b, _, _ = run_hook(HOOK, "gh workflow run other.yml", repo1)
        check(v6b == "allow", "allow other workflow run", f"got verdict={v6b}")

        # 7. Missing tag: allow with note
        repo7 = _make_repo(create_tag=False)
        _advance_commit(repo7, "reusable.yml", new_content1)
        v7, _, err7 = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo7)
        check(
            v7 == "allow" and "tag v2 does not resolve" in err7,
            "allow with stderr note when tag does not resolve",
            f"got verdict={v7}, stderr={err7}",
        )

        # 8. Missing remote branch: allow with note
        repo8 = _make_repo(create_remote=False)
        _advance_commit(repo8, "reusable.yml", new_content1, update_remote=False)
        v8, _, err8 = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo8)
        check(
            v8 == "allow" and "remote branch origin/main does not resolve" in err8,
            "allow with stderr note when remote branch does not resolve",
            f"got verdict={v8}, stderr={err8}",
        )

        # 9. Mutation check: flip regex to ignore 'read' and assert deny test fails
        with open(HOOK, encoding="utf-8") as f:
            src = f.read()

        orig_pattern = r"(read|write|none)"
        mutated_pattern = r"(write|none)"
        if orig_pattern not in src:
            sys.exit(f"FATAL: {orig_pattern} not found in {HOOK}")

        mutant_src = src.replace(orig_pattern, mutated_pattern)
        mutant_fd, mutant_path = tempfile.mkstemp(suffix=".py")
        os.close(mutant_fd)
        _write_file(mutant_path, mutant_src)

        try:
            v_mutant, _, _ = run_hook(mutant_path, "gh workflow run slide-major-tag.yml", repo1)
            # Under the mutant ignoring 'read', 'checks: read' must NOT be blocked (i.e. returns 'allow')
            check(
                v_mutant == "allow",
                "mutation check: flipping regex to ignore 'read' flips deny to allow",
                f"expected allow under mutant, got {v_mutant}",
            )
        finally:
            if os.path.exists(mutant_path):
                os.unlink(mutant_path)

    finally:
        for d in _TMPDIRS:
            shutil.rmtree(d, ignore_errors=True)

    total = passes + failures
    print(f"\n{passes}/{total} tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
