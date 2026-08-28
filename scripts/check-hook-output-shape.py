#!/usr/bin/env python3
"""Assert warn-only hooks emit systemMessage rather than reason, and tests assert shape.

A `Stop` hook's `reason` is read ONLY alongside `"decision": "block"`.
A warn-only `Stop` hook that emits `reason` by itself prints valid JSON that the
Claude Code harness silently discards (ai-config#1566, ai-config#1582). A detector
that fires silently is indistinguishable from one that never fires.

This checks two things:

  1. Hook source output shape:
     - For every hook in `hooks/hooks.json` (and `hooks/*.py`): if its source
       never emits `"decision"` (or `permissionDecision: deny`), it must not
       emit `"reason"` alone, and warn-only Stop hooks must emit `"systemMessage"`.
  2. Test-side payload inspection:
     - For every test suite `hooks/test-*.py` of a warn-only hook: the test must
       inspect the emitted payload shape (e.g. asserting `systemMessage` or
       `additionalContext`) rather than merely testing `bool(out)` or non-empty output.

Hard-gating rather than advisory.

Run: python3 scripts/check-hook-output-shape.py
"""
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = ROOT / "hooks"
HOOKS_JSON = HOOKS_DIR / "hooks.json"

SUCCESS_EXIT = 0
CHECK_FAIL_EXIT = 1
USAGE_EXIT = 2


def parse_string_constants(source_code: str) -> tuple[set[str], str | None]:
    """Extract all string literal constants from Python source code via AST.

    Returns (set of strings, error_message if syntax error else None).
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError as err:
        return set(), f"could not be parsed as Python ({err})"

    strings = set()
    for node in ast.walk(tree):
        # ast.Constant covers string literals on Python 3.8+.
        # ast.Str was deprecated in 3.8 and removed in 3.14; visiting it
        # emits DeprecationWarning on 3.12/3.13 (ai-config#2038).
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            strings.add(node.value)
    return strings, None


def load_registered_hooks(hooks_json_path: Path) -> dict[str, list[tuple[str, str]]]:
    """Map script_name -> [(event, matcher)]."""
    if not hooks_json_path.is_file():
        return {}
    try:
        with open(hooks_json_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}
    out: dict[str, list[tuple[str, str]]] = {}
    for event, groups in data.get("hooks", {}).items():
        for group in groups:
            matcher = group.get("matcher") or ""
            for entry in group.get("hooks", []):
                script = entry.get("script")
                if script:
                    out.setdefault(script, []).append((event, matcher))
    return out


def check_hook_sources(
    hooks_dir: Path,
    registered: dict[str, list[tuple[str, str]]]
) -> list[str]:
    """Check all hook sources in hooks_dir for correct output shape."""
    errors = []
    scripts = sorted(set(registered.keys()) | {p.name for p in hooks_dir.glob("*.py") if not p.name.startswith("test-")})

    for script in scripts:
        if not script.endswith(".py"):
            continue
        script_path = hooks_dir / script
        if not script_path.is_file():
            continue

        source = script_path.read_text(encoding="utf-8")
        constants, parse_err = parse_string_constants(source)
        if parse_err:
            errors.append(f"FAIL: {script} {parse_err}")
            continue

        has_decision = "decision" in constants or "permissionDecision" in constants
        has_reason = "reason" in constants
        has_system_message = "systemMessage" in constants

        events = [ev for ev, _ in registered.get(script, [])]

        # Rule 1: A hook that never emits decision must not emit reason
        if has_reason and not has_decision:
            errors.append(
                f"FAIL: {script} emits 'reason' without 'decision'. "
                "A warn-only hook's 'reason' is discarded by the harness unless "
                "paired with 'decision: block'. Emit 'systemMessage' instead."
            )

        # Rule 2: A Stop hook with no block decision is warn-only, so it must emit systemMessage
        if "Stop" in events and not has_decision:
            if not has_system_message:
                errors.append(
                    f"FAIL: {script} is registered as a Stop hook without a 'decision' "
                    "block emit, but does not emit 'systemMessage'. "
                    "Warn-only Stop hooks must emit 'systemMessage'."
                )

    return errors


def check_hook_tests(
    hooks_dir: Path,
    registered: dict[str, list[tuple[str, str]]]
) -> list[str]:
    """Check all warn-only hook test suites for payload shape inspection."""
    errors = []

    for test_path in sorted(hooks_dir.glob("test-*.py")):
        subject_name = test_path.name[len("test-"):]
        subject_path = hooks_dir / subject_name
        if not subject_path.is_file() or not subject_name.endswith(".py"):
            continue

        subject_source = subject_path.read_text(encoding="utf-8")
        subject_constants, subj_err = parse_string_constants(subject_source)
        if subj_err:
            errors.append(f"FAIL: {subject_name} {subj_err}")
            continue

        has_decision = "decision" in subject_constants or "permissionDecision" in subject_constants
        has_system_message = "systemMessage" in subject_constants
        has_additional_context = "additionalContext" in subject_constants

        events = [ev for ev, _ in registered.get(subject_name, [])]

        is_warn_only_stop = "Stop" in events and not has_decision
        is_warn_only_pretool = "PreToolUse" in events and not has_decision and (has_system_message or has_additional_context)

        test_source = test_path.read_text(encoding="utf-8")
        test_constants, test_err = parse_string_constants(test_source)
        if test_err:
            errors.append(f"FAIL: {test_path.name} {test_err}")
            continue

        if is_warn_only_stop:
            if "systemMessage" not in test_constants:
                errors.append(
                    f"FAIL: {test_path.name} tests warn-only Stop hook {subject_name}, "
                    "but never inspects 'systemMessage' in its payload. "
                    "A test asserting bool(out) cannot tell a surfaced warning from discarded output."
                )
        elif is_warn_only_pretool:
            if "additionalContext" not in test_constants and "systemMessage" not in test_constants:
                errors.append(
                    f"FAIL: {test_path.name} tests warn-only PreToolUse hook {subject_name}, "
                    "but never inspects 'additionalContext' or 'systemMessage'. "
                    "A test asserting bool(out) cannot tell a surfaced warning from discarded output."
                )

    return errors


def main() -> int:
    registered = load_registered_hooks(HOOKS_JSON)
    if not registered:
        print(f"FAIL: no hooks parsed from {HOOKS_JSON}")
        return USAGE_EXIT

    source_errors = check_hook_sources(HOOKS_DIR, registered)
    test_errors = check_hook_tests(HOOKS_DIR, registered)

    all_errors = source_errors + test_errors

    if all_errors:
        for err in all_errors:
            print(err)
        print(f"\n{len(all_errors)} output-shape check error(s) found.")
        return CHECK_FAIL_EXIT

    print(
        f"OK: Checked {len(registered)} registered hook(s) and their test suites: "
        "all warn-only hooks emit systemMessage and tests inspect payload shape."
    )
    return SUCCESS_EXIT


if __name__ == "__main__":
    sys.exit(main())
