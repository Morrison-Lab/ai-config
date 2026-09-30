#!/usr/bin/env python3
"""Test the warn-unparseable-staged-config hook and verify mutations.

Run: python3 hooks/test-warn-unparseable-staged-config.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = os.path.realpath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "warn-unparseable-staged-config.py"
)

with open(HOOK, "r", encoding="utf-8") as fh:
    SOURCE = fh.read()

# ---------------------------------------------------------------------------
# Test Cases definition
# ---------------------------------------------------------------------------

CASES = {
    # TOML cases
    "W_toml_escape": (
        "lychee.toml",
        b'regex = "a\\.b"\n',
        "git commit -m 'test'",
        "TOML file containing invalid escape 'a\\.b' (Issue #4086 incident)",
    ),
    "W_toml_syntax": (
        "config.toml",
        b"key = \n",
        "git commit -m 'test'",
        "TOML file with syntax error (missing value)",
    ),
    "S_toml_valid": (
        "config.toml",
        b'key = "valid value"\nnum = 42\n',
        "git commit -m 'test'",
        "valid TOML file",
    ),
    # JSON cases
    "W_json_syntax": (
        "data.json",
        b'{"key": "value",}\n',
        "git commit -m 'test'",
        "JSON file with trailing comma syntax error",
    ),
    "W_json_unclosed": (
        "config.json",
        b'{"key": "value"',
        "git commit -m 'test'",
        "JSON file with unclosed brace",
    ),
    "S_json_valid": (
        "data.json",
        b'{"key": "value", "items": [1, 2, 3]}\n',
        "git commit -m 'test'",
        "valid JSON file",
    ),
    # YAML cases
    "W_yaml_syntax": (
        "config.yaml",
        b"foo:\n  bar: 1\n baz: 2\n",
        "git commit -m 'test'",
        "YAML file with indentation error",
    ),
    "W_yml_syntax": (
        "config.yml",
        b"foo:\n  bar: 1\n baz: 2\n",
        "git commit -m 'test'",
        ".yml extension with indentation error",
    ),
    "S_yaml_valid": (
        "config.yaml",
        b"foo: bar\nitems:\n  - 1\n  - 2\n",
        "git commit -m 'test'",
        "valid YAML file",
    ),
    "S_yaml_multidoc": (
        "manifest.yaml",
        b"a: 1\n---\nb: 2\n",
        "git commit -m 'test'",
        "valid multi-document YAML file",
    ),
    # Non-config files with syntax errors should NOT warn
    "S_txt_ignored": (
        "notes.txt",
        b'regex = "a\\.b"\n',
        "git commit -m 'test'",
        "text file with invalid TOML escape is ignored",
    ),
    # Non-commit command
    "S_non_commit_cmd": (
        "bad.toml",
        b'regex = "a\\.b"\n',
        "git status",
        "git status does not trigger hook even with staged invalid file",
    ),
    # Override
    "S_override_env": (
        "bad.toml",
        b'regex = "a\\.b"\n',
        "ALLOW_UNPARSEABLE_CONFIG=1 git commit -m 'test'",
        "ALLOW_UNPARSEABLE_CONFIG=1 inline assignment suppresses warning",
    ),
    # Stages tracked (commit -a)
    "W_commit_dash_a": (
        "tracked.toml",
        b'regex = "a\\.b"\n',
        "git commit -a -m 'test'",
        "git commit -a picks up unstaged modification in tracked TOML",
    ),
    # Subcommand -C option must not collide with global git -C
    "W_commit_reuse_msg": (
        "bad.toml",
        b'regex = "a\\.b"\n',
        "git commit -C HEAD -m 'test'",
        "git commit -C HEAD does not treat -C as change-directory option",
    ),
}

EXPECTED = {
    "W_toml_escape": True,
    "W_toml_syntax": True,
    "S_toml_valid": False,
    "W_json_syntax": True,
    "W_json_unclosed": True,
    "S_json_valid": False,
    "W_yaml_syntax": True,
    "W_yml_syntax": True,
    "S_yaml_valid": False,
    "S_yaml_multidoc": False,
    "S_txt_ignored": False,
    "S_non_commit_cmd": False,
    "S_override_env": False,
    "W_commit_dash_a": True,
    "W_commit_reuse_msg": True,
}


def run_case_in_repo(hook_path: str, case_id: str, extra_env: dict[str, str] | None = None) -> tuple[bool, dict]:
    rel_path, content, command, _desc = CASES[case_id]
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["git", "init", "-b", "main"], cwd=td, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=td, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=td, check=True)

        full_path = os.path.join(td, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        if case_id == "W_commit_dash_a":
            # Initial valid commit to track the file
            with open(full_path, "wb") as f:
                f.write(b"key = 1\n")
            subprocess.run(["git", "add", rel_path], cwd=td, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=td, check=True, capture_output=True)
            # Modify on disk without git add
            with open(full_path, "wb") as f:
                f.write(content)
        elif case_id == "W_commit_reuse_msg":
            seed_file = os.path.join(td, "seed.txt")
            with open(seed_file, "w", encoding="utf-8") as f:
                f.write("initial\n")
            subprocess.run(["git", "add", "seed.txt"], cwd=td, check=True)
            subprocess.run(["git", "commit", "-m", "seed commit"], cwd=td, check=True, capture_output=True)
            with open(full_path, "wb") as f:
                f.write(content)
            subprocess.run(["git", "add", rel_path], cwd=td, check=True)
        else:
            with open(full_path, "wb") as f:
                f.write(content)
            subprocess.run(["git", "add", rel_path], cwd=td, check=True)

        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "cwd": td,
        }
        lib_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(hook_path))), "scripts", "lib")
        env = {**os.environ, **(extra_env or {})}
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{lib_dir}{os.pathsep}{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = lib_dir

        proc = subprocess.run(
            [sys.executable, hook_path],
            input=json.dumps(payload),
            cwd=td,
            capture_output=True,
            text=True,
            env=env,
        )
        if proc.returncode != 0:
            return False, {}
        out_text = proc.stdout.strip()
        if not out_text:
            return False, {}
        try:
            data = json.loads(out_text)
            # Check shape: warn-only PreToolUse hook emits additionalContext or systemMessage
            has_context = bool(data.get("hookSpecificOutput", {}).get("additionalContext"))
            has_sys = bool(data.get("systemMessage"))
            fired = has_context or has_sys
            return fired, data
        except Exception:
            return False, {}


def main() -> int:
    print(f"Testing {HOOK} against test cases...")
    wrong = 0
    for case_id, expected_warn in EXPECTED.items():
        _path, _content, _cmd, desc = CASES[case_id]
        fired, data = run_case_in_repo(HOOK, case_id)
        ok = (fired == expected_warn)
        if not ok:
            wrong += 1
            print(f"FAIL: {case_id} (expected {expected_warn}, got {fired}): {desc}")
        else:
            print(f"PASS: {case_id}: {desc}")

        # Check payload shape details for warning cases
        if expected_warn:
            ctx = data.get("hookSpecificOutput", {}).get("additionalContext", "")
            sys_msg = data.get("systemMessage", "")
            if not ctx:
                wrong += 1
                print(f"FAIL: {case_id} missing additionalContext in payload")
            if not sys_msg and not os.environ.get("ANTIGRAVITY_AGENT"):
                wrong += 1
                print(f"FAIL: {case_id} missing systemMessage in non-ANTIGRAVITY payload")

    # Special case: ANTIGRAVITY_AGENT suppression of systemMessage
    fired_ag, data_ag = run_case_in_repo(HOOK, "W_toml_escape", extra_env={"ANTIGRAVITY_AGENT": "1"})
    if not fired_ag:
        wrong += 1
        print("FAIL: W_toml_escape under ANTIGRAVITY_AGENT did not fire")
    else:
        has_context = bool(data_ag.get("hookSpecificOutput", {}).get("additionalContext"))
        has_sys = bool(data_ag.get("systemMessage"))
        if not has_context:
            wrong += 1
            print("FAIL: ANTIGRAVITY_AGENT output missing additionalContext")
        if has_sys:
            wrong += 1
            print("FAIL: ANTIGRAVITY_AGENT output must not carry systemMessage")
        if has_context and not has_sys:
            print("PASS: ANTIGRAVITY_AGENT emits additionalContext and suppresses systemMessage")

    # Special case: Dry run
    dry_payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "git commit -m 'test'"},
        "dryRun": True,
    }
    proc_dry = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(dry_payload),
        capture_output=True,
        text=True,
    )
    try:
        dry_data = json.loads(proc_dry.stdout.strip())
        if dry_data.get("hookSpecificOutput", {}).get("hookEventName") == "PreToolUse":
            print("PASS: dryRun returns empty PreToolUse payload")
        else:
            wrong += 1
            print("FAIL: dryRun did not return hookEventName: PreToolUse")
    except Exception as exc:
        wrong += 1
        print(f"FAIL: dryRun output not valid JSON ({exc})")

    # Special case: CLI mode
    with tempfile.TemporaryDirectory() as td:
        bad_f = os.path.join(td, "bad.toml")
        with open(bad_f, "wb") as f:
            f.write(b'regex = "a\\.b"\n')
        good_f = os.path.join(td, "good.toml")
        with open(good_f, "wb") as f:
            f.write(b'key = "value"\n')

        res_bad = subprocess.run([sys.executable, HOOK, bad_f], capture_output=True)
        if res_bad.returncode == 1:
            print("PASS: CLI mode exits 1 on invalid file")
        else:
            wrong += 1
            print(f"FAIL: CLI mode expected rc 1, got {res_bad.returncode}")

        res_good = subprocess.run([sys.executable, HOOK, good_f], capture_output=True)
        if res_good.returncode == 0:
            print("PASS: CLI mode exits 0 on valid file")
        else:
            wrong += 1
            print(f"FAIL: CLI mode expected rc 0, got {res_good.returncode}")

    # -----------------------------------------------------------------------
    # Mutation tests
    # -----------------------------------------------------------------------
    MUTATIONS = {
        "M1_toml_parser": (
            "removing TOML validation silences TOML errors",
            [("    if ext == \".toml\":\n        return check_toml(content_bytes)",
              "    if ext == \".toml\":\n        return None")],
            {"W_toml_escape", "W_toml_syntax", "W_commit_dash_a", "W_commit_reuse_msg"},
        ),
        "M2_json_parser": (
            "removing JSON validation silences JSON errors",
            [("    if ext == \".json\":\n        return check_json(content_bytes)",
              "    if ext == \".json\":\n        return None")],
            {"W_json_syntax", "W_json_unclosed"},
        ),
        "M3_yaml_parser": (
            "removing YAML validation silences YAML errors",
            [("    if ext in (\".yaml\", \".yml\"):\n        return check_yaml(content_bytes)",
              "    if ext in (\".yaml\", \".yml\"):\n        return None")],
            {"W_yaml_syntax", "W_yml_syntax"},
        ),
        "M4_commit_filter": (
            "requiring command to be something other than commit silences all warnings",
            [("        if subcmd != \"commit\":\n            continue",
              "        if subcmd != \"not-a-commit\":\n            continue")],
            {"W_toml_escape", "W_toml_syntax", "W_json_syntax", "W_json_unclosed",
             "W_yaml_syntax", "W_yml_syntax", "W_commit_dash_a", "W_commit_reuse_msg"},
        ),
        "M5_override_ignored": (
            "ignoring override causes override case to warn",
            [("        if os.environ.get(OVERRIDE) == \"1\" or any(tok == f\"{OVERRIDE}=1\" for tok in env_tokens):\n            continue",
              "        if False:\n            continue")],
            {"S_override_env"},
        ),
        "M6_stages_tracked_disabled": (
            "disabling stages_tracked suppresses unstaged modifications in git commit -a",
            [("        stages_tracked = any(",
              "        stages_tracked = False and any(")],
            {"W_commit_dash_a"},
        ),
        "M7_cdir_unbounded": (
            "scanning whole argv for -C treats git commit -C HEAD as cd HEAD and suppresses warning",
            [("        global_opts = argv[:subcmd_idx]",
              "        global_opts = argv")],
            {"W_commit_reuse_msg"},
        ),
    }

    print("\nRunning mutation checks (revert clauses and verify flipping):")
    mutation_wrong = 0
    for clause, (stmt, edits, expected_flips) in MUTATIONS.items():
        mutated = SOURCE
        for find, replace in edits:
            count = mutated.count(find)
            if count != 1:
                sys.exit(f"FATAL: clause {clause} anchor count is {count} (!= 1) in {HOOK}")
            mutated = mutated.replace(find, replace)

        if mutated == SOURCE:
            sys.exit(f"FATAL: clause {clause} produced identical source")

        fd, path = tempfile.mkstemp(dir=os.path.dirname(HOOK), prefix="tmp_mut_", suffix=".py")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(mutated)

        try:
            flipped = set()
            for case_id in CASES:
                fired, _ = run_case_in_repo(path, case_id)
                if fired != EXPECTED[case_id]:
                    flipped.add(case_id)
        finally:
            os.unlink(path)

        ok = (flipped == expected_flips)
        if not ok:
            mutation_wrong += 1
            print(f"FAIL: {clause}: {stmt}\n      expected flips: {sorted(expected_flips)}\n      actual flips:   {sorted(flipped)}")
        else:
            print(f"PASS: {clause}: flipped {sorted(flipped)} as expected")

    print(f"\nSummary: {len(EXPECTED) - wrong}/{len(EXPECTED)} test cases passed.")
    print(f"Mutations: {len(MUTATIONS) - mutation_wrong}/{len(MUTATIONS)} clauses flipped as declared.")

    if wrong or mutation_wrong:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
