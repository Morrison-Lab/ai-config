#!/usr/bin/env python3
"""Test the guard-slide-major-tag PreToolUse hook.

Verifies:
  - Adding a job permission to a reusable workflow (on: workflow_call) denies slide-major-tag.
  - Removing a permission allows.
  - Adding a permission to a non-workflow_call workflow allows.
  - Adding a `# checks: read` comment line allows.
  - ALLOW_BREAKING_SLIDE=1 allows.
  - Non-slide commands allow.
  - Unrelated step input (e.g. access: write inside with:) allows even when file has permissions block.
  - Adding a permission at workflow root (2-space indent) denies slide-major-tag.
  - Adding a quoted permission value (checks: "read") denies slide-major-tag.
  - Adding a permission under a quoted key ('permissions':) denies slide-major-tag.
  - Missing PyYAML fails closed (denies) with PyYAML explanation.
  - Malformed workflow YAML fails closed (denies) with YAML parse error explanation.
  - Malformed workflow YAML at tag ref fails closed (denies).
  - Unparseable non-workflow_call workflow allows.
  - Unparseable workflow containing workflow_call denies.
  - Unicode-escaped workflow_call key with added permission denies.
  - Parseable workflow genuinely lacking workflow_call allows.
  - Missing tag allows with stderr note.
  - Missing remote branch allows with stderr note.
  - Mutation check: flipping the regex to ignore 'read' fails the deny test.
  - Mutation check: consulting raw scan for parseable file fails unicode-escaped test.
  - Escalating permission from none to read denies slide-major-tag (both job and workflow root).
  - All rank upward pairs (none->read, none->write, read->write, absent->read, absent->write, absent->none) deny.
  - All rank downward pairs (write->read, write->none, read->none, key removed) allow.
  - Permission value outside rank (e.g. admin) filtered upstream by RX_PERM_VAL and does not deny.
  - Mutation check: making none and read compare equal fails the deny test.


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

        # 8b. False positive regression: unrelated step input (access: write inside with:)
        # in a file that already has permissions allows.
        repo8b = _make_repo(
            permissions_block="    permissions:\n      contents: read\n"
        )
        new_content8b = (
            "name: Workflow\n"
            "on:\n  workflow_call:\n"
            "jobs:\n"
            "  review:\n"
            "    runs-on: ubuntu-latest\n"
            "    permissions:\n"
            "      contents: read\n"
            "    steps:\n"
            "      - run: echo ok\n"
            "      - uses: actions/checkout@v4\n"
            "        with:\n"
            "          access: write\n"
        )
        _advance_commit(repo8b, "reusable.yml", new_content8b)
        v8b, _, _ = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo8b)
        check(
            v8b == "allow",
            "allow unrelated step input (access: write) in with: block",
            f"got verdict={v8b}",
        )

        # 8c. False negative regression: adding permission at workflow root denies.
        repo8c = _make_repo(
            permissions_block=""
        )
        new_content8c = (
            "name: Workflow\n"
            "on:\n  workflow_call:\n"
            "permissions:\n"
            "  checks: read\n"
            "jobs:\n"
            "  review:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: echo ok\n"
        )
        _advance_commit(repo8c, "reusable.yml", new_content8c)
        v8c, r8c, _ = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo8c)
        check(
            v8c == "deny" and "checks: read" in r8c and "reusable.yml" in r8c and "ALLOW_BREAKING_SLIDE=1" in r8c,
            "deny added workflow-root permission to reusable workflow",
            f"got verdict={v8c}, reason={r8c}",
        )

        # 8d. Quoted permission value: checks: "read" denies.
        repo8d = _make_repo()
        new_content8d = (
            "name: Workflow\n"
            "on:\n  workflow_call:\n"
            "jobs:\n"
            "  review:\n"
            "    runs-on: ubuntu-latest\n"
            "    permissions:\n"
            "      contents: read\n"
            '      checks: "read"\n'
            "    steps:\n"
            "      - run: echo ok\n"
        )
        _advance_commit(repo8d, "reusable.yml", new_content8d)
        v8d, r8d, _ = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo8d)
        check(
            v8d == "deny" and "checks: read" in r8d and "reusable.yml" in r8d and "ALLOW_BREAKING_SLIDE=1" in r8d,
            'deny quoted permission value (checks: "read") in reusable workflow',
            f"got verdict={v8d}, reason={r8d}",
        )

        # 8e. Quoted permissions key: 'permissions': denies added permission.
        repo8e = _make_repo()
        new_content8e = (
            "name: Workflow\n"
            "on:\n  workflow_call:\n"
            "jobs:\n"
            "  review:\n"
            "    runs-on: ubuntu-latest\n"
            "    'permissions':\n"
            "      contents: read\n"
            "      checks: read\n"
            "    steps:\n"
            "      - run: echo ok\n"
        )
        _advance_commit(repo8e, "reusable.yml", new_content8e)
        v8e, r8e, _ = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo8e)
        check(
            v8e == "deny" and "checks: read" in r8e and "reusable.yml" in r8e and "ALLOW_BREAKING_SLIDE=1" in r8e,
            "deny added permission under quoted key ('permissions':) in reusable workflow",
            f"got verdict={v8e}, reason={r8e}",
        )

        # 8f. Fail closed when PyYAML is unavailable: denies with explanation and PyYAML note.
        with open(HOOK, encoding="utf-8") as f:
            hook_src_no_yaml = f.read().replace("import yaml", "yaml = None # import yaml")
        no_yaml_fd, no_yaml_path = tempfile.mkstemp(suffix=".py")
        os.close(no_yaml_fd)
        _write_file(no_yaml_path, hook_src_no_yaml)
        try:
            v8f, r8f, _ = run_hook(no_yaml_path, "gh workflow run slide-major-tag.yml", repo1)
            check(
                v8f == "deny" and "PyYAML is not installed" in r8f and "ALLOW_BREAKING_SLIDE=1" in r8f,
                "fail closed: deny slide-major-tag when PyYAML is unavailable",
                f"got verdict={v8f}, reason={r8f}",
            )
            v8f_override, _, _ = run_hook(
                no_yaml_path, "ALLOW_BREAKING_SLIDE=1 gh workflow run slide-major-tag.yml", repo1
            )
            check(
                v8f_override == "allow",
                "allow when ALLOW_BREAKING_SLIDE=1 even if PyYAML is unavailable",
                f"got verdict={v8f_override}",
            )
        finally:
            if os.path.exists(no_yaml_path):
                os.unlink(no_yaml_path)

        # 8g. Fail closed when workflow YAML is malformed: denies with parse error note.
        repo8g = _make_repo()
        new_content8g = (
            "name: Workflow\n"
            "on:\n  workflow_call:\n"
            "jobs: [invalid syntax:\n"
        )
        _advance_commit(repo8g, "reusable.yml", new_content8g)
        v8g, r8g, _ = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo8g)
        check(
            v8g == "deny" and "could not be parsed as valid YAML" in r8g and "ALLOW_BREAKING_SLIDE=1" in r8g,
            "fail closed: deny slide-major-tag when workflow YAML is malformed",
            f"got verdict={v8g}, reason={r8g}",
        )
        v8g_override, _, _ = run_hook(
            HOOK, "ALLOW_BREAKING_SLIDE=1 gh workflow run slide-major-tag.yml", repo8g
        )
        check(
            v8g_override == "allow",
            "allow when ALLOW_BREAKING_SLIDE=1 even if workflow YAML is malformed",
            f"got verdict={v8g_override}",
        )

        # 8h. Fail closed when workflow YAML at tag ref is malformed.
        repo8h = _make_repo()
        bad_tag_content = (
            "name: Workflow\n"
            "on:\n  workflow_call:\n"
            "jobs: [broken syntax:\n"
        )
        _advance_commit(repo8h, "reusable.yml", bad_tag_content)
        _run(repo8h, "tag", "-f", "v2")
        _advance_commit(repo8h, "reusable.yml", new_content1)
        v8h, r8h, _ = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo8h)
        check(
            v8h == "deny" and "could not be parsed as valid YAML" in r8h and "at v2" in r8h,
            "fail closed: deny slide-major-tag when workflow YAML at tag is malformed",
            f"got verdict={v8h}, reason={r8h}",
        )

        # 8i. Regression: unparseable NON-workflow_call file allows
        # (e.g. reusable.yml unchanged, lint.yml has syntax error without workflow_call)
        repo8i = _make_repo()
        lint_file8i = os.path.join(repo8i, ".github", "workflows", "lint.yml")
        lint_content8i = (
            "name: Lint\n"
            "on: [push\n"
            "jobs:\n"
            "  lint:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: echo ok\n"
        )
        _write_file(lint_file8i, lint_content8i)
        _run(repo8i, "add", ".")
        _run(repo8i, "commit", "-qm", "add unparseable lint.yml without workflow_call")
        _run(repo8i, "update-ref", "refs/remotes/origin/main", "HEAD")
        v8i, r8i, _ = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo8i)
        check(
            v8i == "allow",
            "allow slide-major-tag when unparseable workflow does not contain workflow_call",
            f"got verdict={v8i}, reason={r8i}",
        )

        # 8j. Mirror regression: unparseable file that DOES contain workflow_call still denies
        repo8j = _make_repo()
        lint_file8j = os.path.join(repo8j, ".github", "workflows", "lint.yml")
        lint_content8j = (
            "name: Lint\n"
            "# workflow_call is mentioned here\n"
            "on: [push\n"
            "jobs:\n"
            "  lint:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: echo ok\n"
        )
        _write_file(lint_file8j, lint_content8j)
        _run(repo8j, "add", ".")
        _run(repo8j, "commit", "-qm", "add unparseable lint.yml containing workflow_call")
        _run(repo8j, "update-ref", "refs/remotes/origin/main", "HEAD")
        v8j, r8j, _ = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo8j)
        check(
            v8j == "deny" and "could not be parsed as valid YAML" in r8j and "ALLOW_BREAKING_SLIDE=1" in r8j,
            "fail closed: deny slide-major-tag when unparseable workflow contains workflow_call token",
            f"got verdict={v8j}, reason={r8j}",
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

        # 8k. Unicode-escaped workflow_call key with added permission denies.
        # Valid YAML resolves "\u0077orkflow_call" to "workflow_call", but raw text
        # does not contain the substring "workflow_call". Parsing before filtering
        # ensures the permission addition is caught.
        repo8k = _make_repo(
            on_block='  "\\u0077orkflow_call":\n',
            permissions_block="    permissions:\n      contents: read\n",
        )
        new_content8k = (
            "name: Workflow\n"
            'on:\n  "\\u0077orkflow_call":\n'
            "jobs:\n"
            "  review:\n"
            "    runs-on: ubuntu-latest\n"
            "    permissions:\n"
            "      contents: read\n"
            "      checks: read\n"
            "    steps:\n"
            "      - run: echo ok\n"
        )
        _advance_commit(repo8k, "reusable.yml", new_content8k)
        v8k, r8k, _ = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo8k)
        check(
            v8k == "deny" and "checks: read" in r8k and "reusable.yml" in r8k and "ALLOW_BREAKING_SLIDE=1" in r8k,
            "deny added permission when workflow_call key is unicode-escaped",
            f"got verdict={v8k}, reason={r8k}",
        )

        # 8l. Parseable file genuinely lacking workflow_call allows (step 2 does not over-deny).
        repo8l = _make_repo(
            on_block="  push:\n    branches: [main]\n",
            permissions_block="    permissions:\n      contents: read\n",
        )
        new_content8l = (
            "name: Workflow\n"
            "on:\n  push:\n    branches: [main]\n"
            "jobs:\n"
            "  review:\n"
            "    runs-on: ubuntu-latest\n"
            "    permissions:\n"
            "      contents: read\n"
            "      checks: read\n"
            "    steps:\n"
            "      - run: echo ok\n"
        )
        _advance_commit(repo8l, "reusable.yml", new_content8l)
        v8l, r8l, _ = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo8l)
        check(
            v8l == "allow",
            "allow permission addition to parseable workflow without workflow_call (no over-deny)",
            f"got verdict={v8l}, reason={r8l}",
        )

        # 10. Mutation check for reorder: break step 2 so it consults raw scan for parseable file.
        # Under this mutant, the unicode-escaped key is falsely skipped and allowed instead of denied.
        with open(HOOK, encoding="utf-8") as f:
            src10 = f.read()

        break_step2_target = "if not _has_workflow_call(new_data):"
        break_step2_replacement = 'if "workflow_call" not in new_content or not _has_workflow_call(new_data):'
        if break_step2_target not in src10:
            sys.exit(f"FATAL: {break_step2_target} not found in {HOOK}")

        mutant10_src = src10.replace(break_step2_target, break_step2_replacement, 1)
        mutant10_fd, mutant10_path = tempfile.mkstemp(suffix=".py")
        os.close(mutant10_fd)
        _write_file(mutant10_path, mutant10_src)

        try:
            v10_mutant, _, _ = run_hook(mutant10_path, "gh workflow run slide-major-tag.yml", repo8k)
            # Under the broken step 2 mutant, the unicode-escaped workflow is skipped (returns 'allow')
            check(
                v10_mutant == "allow",
                "mutation check: consulting raw scan for parseable file flips unicode-escaped deny to allow",
                f"expected allow under mutant, got {v10_mutant}",
            )
        finally:
            if os.path.exists(mutant10_path):
                os.unlink(mutant10_path)

        # 11. Direct test of permission rank comparison covering all pairs
        import importlib.util
        spec11 = importlib.util.spec_from_file_location("guard_hook_mod", HOOK)
        guard_mod = importlib.util.module_from_spec(spec11)
        spec11.loader.exec_module(guard_mod)

        # 11a. Upward pairs (escalation -> must be flagged):
        # none->read, none->write, read->write, absent->read, absent->write, absent->none
        upward_pairs = [
            ("none->read", {"checks": "none"}, {"checks": "read"}, "checks: read"),
            ("none->write", {"checks": "none"}, {"checks": "write"}, "checks: write"),
            ("read->write", {"checks": "read"}, {"checks": "write"}, "checks: write"),
            ("absent->read", {}, {"checks": "read"}, "checks: read"),
            ("absent->write", {}, {"checks": "write"}, "checks: write"),
            ("absent->none", {}, {"checks": "none"}, "checks: none"),
        ]
        for name, old_d, new_d, expected_line in upward_pairs:
            res_up = guard_mod._find_added_permissions(
                {"job:review": old_d}, {"job:review": new_d}
            )
            check(
                res_up == [("job:review", expected_line)],
                f"rank upward pair: {name} detected as escalation",
                f"expected [('job:review', '{expected_line}')], got {res_up}",
            )

        # 11b. Workflow root upward pair (none->read)
        res_wf_up = guard_mod._find_added_permissions(
            {"workflow": {"checks": "none"}}, {"workflow": {"checks": "read"}}
        )
        check(
            res_wf_up == [("workflow", "checks: read")],
            "rank upward pair: workflow-root none->read detected as escalation",
            f"expected [('workflow', 'checks: read')], got {res_wf_up}",
        )

        # 11c. Downward pairs (de-escalation / reduction -> must NOT be flagged / allowed):
        # write->read, write->none, read->none, key removed
        downward_pairs = [
            ("write->read", {"checks": "write"}, {"checks": "read"}),
            ("write->none", {"checks": "write"}, {"checks": "none"}),
            ("read->none", {"checks": "read"}, {"checks": "none"}),
            ("key removed", {"checks": "read"}, {}),
        ]
        for name, old_d, new_d in downward_pairs:
            res_down = guard_mod._find_added_permissions(
                {"job:review": old_d}, {"job:review": new_d}
            )
            check(
                res_down == [],
                f"rank downward pair: {name} allowed",
                f"expected [], got {res_down}",
            )

        # 11d. End-to-end: permission value outside rank (e.g. admin) filtered upstream
        # by RX_PERM_VAL before comparison; does not produce a spurious deny
        repo11d = _make_repo(
            permissions_block="    permissions:\n      contents: none\n"
        )
        new_content11d = (
            "name: Workflow\n"
            "on:\n  workflow_call:\n"
            "jobs:\n"
            "  review:\n"
            "    runs-on: ubuntu-latest\n"
            "    permissions:\n"
            "      contents: none\n"
            "      checks: admin\n"
            "    steps:\n"
            "      - run: echo ok\n"
        )
        _advance_commit(repo11d, "reusable.yml", new_content11d)
        v11d, r11d, e11d = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo11d)
        check(
            v11d == "allow",
            "permission value outside rank (admin) filtered by RX_PERM_VAL and does not produce spurious deny",
            f"got verdict={v11d}, reason={r11d}",
        )
        # The verdict alone cannot tell the two ways of reaching "allow" apart.
        # If RX_PERM_VAL ever stops filtering, the out-of-rank value reaches
        # PERM_RANK[...], raises KeyError, and main()'s blanket handler turns
        # that into exit 0 with empty stdout -- ALLOW again, from a crash.
        # stderr is what separates them, so assert on it: a clean run says
        # nothing there, and the fail-open path prints "could not evaluate".
        check(
            "could not evaluate command" not in (e11d or ""),
            "admin is filtered upstream rather than crashing into a fail-open allow",
            f"got stderr={(e11d or '')!r}",
        )

        # 11e. Shorthand forms (read-all / write-all) rank on the same scale.
        # A strict downgrade must not be reported as an addition, in either
        # direction across the shorthand/dict boundary.
        shorthand_allowed = [
            ("write-all->read-all", "write-all", "read-all"),
            ("write-all->write-all", "write-all", "write-all"),
            ("read-all->read-all", "read-all", "read-all"),
            ("write-all->{contents: read}", "write-all", {"contents": "read"}),
            ("write-all->{contents: write}", "write-all", {"contents": "write"}),
            ("read-all->{contents: read}", "read-all", {"contents": "read"}),
        ]
        for name, old_v, new_v in shorthand_allowed:
            res_sa = guard_mod._find_added_permissions(
                {"job:review": old_v}, {"job:review": new_v}
            )
            check(
                res_sa == [],
                f"shorthand rank: {name} allowed",
                f"expected [], got {res_sa}",
            )

        shorthand_denied = [
            ("read-all->write-all", "read-all", "write-all"),
            ("read-all->{contents: write}", "read-all", {"contents": "write"}),
            ("{contents: write}->read-all", {"contents": "write"}, "read-all"),
            # id-token is NOT covered by either shorthand: it accepts only
            # `write` or `none`, never `read`, so read-all provably cannot
            # grant it and write-all's coverage is documented nowhere. An
            # explicit grant must stay reportable, or a slide that adds
            # id-token: write to a write-all job passes the guard silently
            # and startup-fails every consumer that has not granted it.
            ("write-all->{id-token: write}", "write-all", {"id-token": "write"}),
            ("read-all->{id-token: write}", "read-all", {"id-token": "write"}),
        ]
        for name, old_v, new_v in shorthand_denied:
            res_sd = guard_mod._find_added_permissions(
                {"job:review": old_v}, {"job:review": new_v}
            )
            check(
                res_sd != [],
                f"shorthand rank: {name} detected as escalation",
                f"expected a finding, got {res_sd}",
            )

        # 11e-bis. The uncovered-key carve-out is scoped to that key alone:
        # a COVERED key at the shorthand's own rank stays allowed, so the
        # exemption cannot be widened into "ignore the floor entirely".
        res_cov = guard_mod._find_added_permissions(
            {"job:review": "write-all"}, {"job:review": {"contents": "write"}}
        )
        check(
            res_cov == [],
            "shorthand rank: covered key at the shorthand's own rank allowed",
            f"expected [], got {res_cov}",
        )

        # 11f. A scope absent from the baseline gains a shorthand grant.
        res_sf = guard_mod._find_added_permissions({}, {"job:review": "read-all"})
        check(
            res_sf == [("job:review", "read-all")],
            "shorthand rank: absent->read-all detected as escalation",
            f"expected [('job:review', 'read-all')], got {res_sf}",
        )

        # 11g. An unrecognized shorthand is reported rather than ranked, so the
        # guard fails toward denying a grant it cannot interpret.
        res_sg = guard_mod._find_added_permissions(
            {"job:review": "read-all"}, {"job:review": "admin-all"}
        )
        check(
            res_sg == [("job:review", "admin-all")],
            "shorthand rank: unrecognized shorthand reported",
            f"expected [('job:review', 'admin-all')], got {res_sg}",
        )

        # 12a. End-to-end: job-level checks: none -> checks: read denies slide-major-tag
        repo12a = _make_repo(
            permissions_block="    permissions:\n      contents: none\n      checks: none\n"
        )
        new_content12a = (
            "name: Workflow\n"
            "on:\n  workflow_call:\n"
            "jobs:\n"
            "  review:\n"
            "    runs-on: ubuntu-latest\n"
            "    permissions:\n"
            "      contents: none\n"
            "      checks: read\n"
            "    steps:\n"
            "      - run: echo ok\n"
        )
        _advance_commit(repo12a, "reusable.yml", new_content12a)
        v12a, r12a, _ = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo12a)
        check(
            v12a == "deny" and "checks: read" in r12a and "reusable.yml" in r12a and "ALLOW_BREAKING_SLIDE=1" in r12a,
            "deny job-level permission escalation from none to read in reusable workflow",
            f"got verdict={v12a}, reason={r12a}",
        )

        # 12b. End-to-end: workflow-root checks: none -> checks: read denies slide-major-tag
        repo12b = _make_repo(
            permissions_block=""
        )
        root_v2_content = (
            "name: Workflow\n"
            "on:\n  workflow_call:\n"
            "permissions:\n"
            "  checks: none\n"
            "jobs:\n"
            "  review:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: echo ok\n"
        )
        _advance_commit(repo12b, "reusable.yml", root_v2_content)
        _run(repo12b, "tag", "-f", "v2")
        root_main_content = (
            "name: Workflow\n"
            "on:\n  workflow_call:\n"
            "permissions:\n"
            "  checks: read\n"
            "jobs:\n"
            "  review:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: echo ok\n"
        )
        _advance_commit(repo12b, "reusable.yml", root_main_content)
        v12b, r12b, _ = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo12b)
        check(
            v12b == "deny" and "checks: read" in r12b and "reusable.yml" in r12b and "ALLOW_BREAKING_SLIDE=1" in r12b,
            "deny workflow-root permission escalation from none to read in reusable workflow",
            f"got verdict={v12b}, reason={r12b}",
        )

        # 12c. End-to-end: downward permission transition (checks: write -> checks: read) allows
        repo12c = _make_repo(
            permissions_block="    permissions:\n      contents: read\n      checks: write\n"
        )
        new_content12c = (
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
        _advance_commit(repo12c, "reusable.yml", new_content12c)
        v12c, r12c, _ = run_hook(HOOK, "gh workflow run slide-major-tag.yml", repo12c)
        check(
            v12c == "allow",
            "allow downward permission transition (checks: write -> checks: read)",
            f"got verdict={v12c}, reason={r12c}",
        )

        # 13. Mutation check: make two distinct rank levels compare equal (none == read)
        # and confirm that none->read fails to deny (returns allow under mutant).
        with open(HOOK, encoding="utf-8") as f:
            src13 = f.read()

        rank_orig = '"none": 1,\n    "read": 2,'
        rank_mutant = '"none": 2,\n    "read": 2,'
        if rank_orig not in src13:
            sys.exit(f"FATAL: rank pattern not found in {HOOK}")

        mutant13_src = src13.replace(rank_orig, rank_mutant, 1)
        mutant13_fd, mutant13_path = tempfile.mkstemp(suffix=".py")
        os.close(mutant13_fd)
        _write_file(mutant13_path, mutant13_src)

        try:
            v13_mutant, _, _ = run_hook(mutant13_path, "gh workflow run slide-major-tag.yml", repo12a)
            check(
                v13_mutant == "allow",
                "mutation check: making none and read compare equal flips deny to allow",
                f"expected allow under mutant, got {v13_mutant}",
            )
        finally:
            if os.path.exists(mutant13_path):
                os.unlink(mutant13_path)

    finally:
        for d in _TMPDIRS:
            shutil.rmtree(d, ignore_errors=True)

    total = passes + failures
    print(f"\n{passes}/{total} tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
