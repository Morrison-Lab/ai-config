#!/usr/bin/env python3
"""Regression tests for check-hook-output-shape.py.

Every case runs the real script as a subprocess against a synthetic scratch repo,
verifying that:
  1. A clean suite passes (both synthetic and live repo).
  2. A warn-only hook emitting `reason` without `decision` fails (the defect from #1566).
  3. A warn-only Stop hook that fails to emit `systemMessage` fails.
  4. A test for a warn-only hook that does not assert payload shape fails (test-side blindness).
  5. A warn-only PreToolUse hook emitting neither additionalContext nor
     systemMessage fails, while one that blocks -- by a `deny` decision or by
     exiting 2 -- does not; an error-path `return 1` does not exempt, an
     exit 2 inside an `except` handler does not exempt, and an `if`-guarded
     error-path `return 2` DOES exempt, which is the narrowing's edge and is
     pinned so widening it stays a deliberate change (#3068).
  6. Missing or unparseable hooks.json fails loudly with usage exit code 2.
  7. Unparseable Python source in a hook fails loudly with a diagnostic.
  8. The success line encodes on a cp1252 stdout (ai-config#2038).
  9. parse_string_constants does not emit ast.Str DeprecationWarning.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "check-hook-output-shape.py"
ROOT = Path(__file__).resolve().parent.parent

passes = 0
failures = 0


def check(name: str, condition: bool, extra: str = "") -> None:
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name} {extra}")
        failures += 1


def make_repo(
    tmpdir: str,
    hooks_json_data: dict | None,
    files: dict[str, str],
) -> Path:
    root = Path(tmpdir)
    scripts_dir = root / "scripts"
    hooks_dir = root / "hooks"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    hooks_dir.mkdir(parents=True, exist_ok=True)

    # Copy the real check script into the scratch repo
    (scripts_dir / "check-hook-output-shape.py").write_text(
        SCRIPT.read_text(encoding="utf-8"), encoding="utf-8"
    )

    # Write hooks.json if provided
    if hooks_json_data is not None:
        (hooks_dir / "hooks.json").write_text(
            json.dumps(hooks_json_data, indent=2), encoding="utf-8"
        )

    # Write individual hook and test files
    for relpath, content in files.items():
        p = root / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    return root


def run(root: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "check-hook-output-shape.py")],
        capture_output=True,
        text=True,
        cwd=str(root),
    )
    return proc.returncode, proc.stdout + proc.stderr


def case(
    name: str,
    hooks_json_data: dict | None,
    files: dict[str, str],
    want_exit: int = 0,
    needle: str | None = None,
) -> None:
    with tempfile.TemporaryDirectory() as td:
        root = make_repo(td, hooks_json_data, files)
        rc, out = run(root)
    ok = (rc == want_exit)
    if ok and needle:
        ok = needle in out
    check(name, ok, f"(rc={rc} want={want_exit}, needle={needle!r}, out={out!r})")


# --- 1. Clean synthetic baseline ---
CLEAN_HOOKS_JSON = {
    "hooks": {
        "Stop": [
            {
                "hooks": [
                    {"type": "command", "script": "blocking-stop.py"},
                    {"type": "command", "script": "warn-stop.py"},
                ]
            }
        ],
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {"type": "command", "script": "warn-pretool.py"},
                ]
            }
        ]
    }
}

CLEAN_FILES = {
    "hooks/blocking-stop.py": (
        'import json\nprint(json.dumps({"decision": "block", "reason": "blocked"}))\n'
    ),
    "hooks/test-blocking-stop.py": (
        'import json\nout = \'{"decision": "block"}\'\nassert "decision" in out\n'
    ),
    "hooks/warn-stop.py": (
        'import json\nprint(json.dumps({"systemMessage": "warning"}))\n'
    ),
    "hooks/test-warn-stop.py": (
        'import json\nout = \'{"systemMessage": "warning"}\'\n'
        'payload = json.loads(out)\nassert payload.get("systemMessage")\n'
    ),
    "hooks/warn-pretool.py": (
        'import json\nprint(json.dumps({"systemMessage": "warn", "hookSpecificOutput": {"additionalContext": "ctx"}}))\n'
    ),
    "hooks/test-warn-pretool.py": (
        'import json\nout = \'{"hookSpecificOutput": {"additionalContext": "ctx"}}\'\n'
        'payload = json.loads(out)\nassert payload["hookSpecificOutput"]["additionalContext"]\n'
    ),
}

case("clean synthetic repo passes", CLEAN_HOOKS_JSON, CLEAN_FILES, want_exit=0)

# --- 2. Warn-only hook emitting reason without decision (defect from #1566) ---
BAD_REASON_FILES = dict(CLEAN_FILES)
BAD_REASON_FILES["hooks/warn-stop.py"] = (
    'import json\nprint(json.dumps({"reason": "silent warning that is dropped"}))\n'
)

case(
    "warn-only hook emitting reason without decision fails",
    CLEAN_HOOKS_JSON,
    BAD_REASON_FILES,
    want_exit=1,
    needle="emits 'reason' without 'decision'",
)

# --- 3. Warn-only Stop hook emitting neither decision nor systemMessage ---
NO_SYSMSG_FILES = dict(CLEAN_FILES)
NO_SYSMSG_FILES["hooks/warn-stop.py"] = (
    'import json\nprint(json.dumps({"unrecognized": "value"}))\n'
)

case(
    "warn-only Stop hook without systemMessage fails",
    CLEAN_HOOKS_JSON,
    NO_SYSMSG_FILES,
    want_exit=1,
    needle="does not emit 'systemMessage'",
)

# --- 4. Test-side blindness: warn-only Stop test checking only bool(out) ---
BLIND_TEST_FILES = dict(CLEAN_FILES)
BLIND_TEST_FILES["hooks/test-warn-stop.py"] = (
    'import subprocess\nout = "something"\nassert bool(out)\n'
)

case(
    "test-side blindness on warn-only Stop hook fails",
    CLEAN_HOOKS_JSON,
    BLIND_TEST_FILES,
    want_exit=1,
    needle="never inspects 'systemMessage'",
)

# --- 5. Test-side blindness: warn-only PreToolUse test checking only bool(out) ---
BLIND_PRETOOL_TEST_FILES = dict(CLEAN_FILES)
BLIND_PRETOOL_TEST_FILES["hooks/test-warn-pretool.py"] = (
    'import subprocess\nout = "something"\nassert bool(out)\n'
)

case(
    "test-side blindness on warn-only PreToolUse hook fails",
    CLEAN_HOOKS_JSON,
    BLIND_PRETOOL_TEST_FILES,
    want_exit=1,
    needle="never inspects 'additionalContext' or 'systemMessage'",
)

# --- 5b. Warn-only PreToolUse hook with no delivery channel at all (#3068) ---
# The defect: the hook printed its warning to stderr and exited 0, which
# reaches the debug log and nobody else. Before this rule the hook fell
# through every check, because the test-side rule only looks at hooks that
# already emit one of the two channels.
NO_CHANNEL_FILES = dict(CLEAN_FILES)
NO_CHANNEL_FILES["hooks/warn-pretool.py"] = (
    'import sys\nprint("warning", file=sys.stderr)\n'
)

case(
    "warn-only PreToolUse hook with neither channel fails (#3068)",
    CLEAN_HOOKS_JSON,
    NO_CHANNEL_FILES,
    want_exit=1,
    needle="neither blocks (no blocking 'decision' emit and no exit 2)",
)

# A PreToolUse hook that BLOCKS is out of scope for the rule: its `deny`
# carries a reason the harness does show, so it needs no advisory channel.
BLOCKING_PRETOOL_FILES = dict(CLEAN_FILES)
BLOCKING_PRETOOL_FILES["hooks/warn-pretool.py"] = (
    'import json\nprint(json.dumps({"hookSpecificOutput": '
    '{"permissionDecision": "deny", "permissionDecisionReason": "no"}}))\n'
)
BLOCKING_PRETOOL_FILES["hooks/test-warn-pretool.py"] = (
    'import json\nout = \'{"hookSpecificOutput": {"permissionDecision": "deny"}}\'\n'
    'assert "permissionDecision" in out\n'
)

case(
    "blocking PreToolUse hook needs no advisory channel (#3068)",
    CLEAN_HOOKS_JSON,
    BLOCKING_PRETOOL_FILES,
    want_exit=0,
)

# A PreToolUse hook that blocks by EXIT CODE is equally out of scope: exit 2
# denies the tool call and its stderr is fed back to Claude, so the advisory
# channel Rule 3 demands would be redundant. #3068's own derivation excluded
# this shape (`exit(2)`, `return 2`); the rule has to as well.
EXIT2_PRETOOL_FILES = dict(CLEAN_FILES)
EXIT2_PRETOOL_FILES["hooks/warn-pretool.py"] = (
    "import sys\n"
    "if True:\n"
    "    print('nope', file=sys.stderr)\n"
    "    sys.exit(2)\n"
)
EXIT2_PRETOOL_FILES["hooks/test-warn-pretool.py"] = (
    "assert 2 == 2\n"
)

case(
    "PreToolUse hook blocking by exit 2 needs no advisory channel (#3068)",
    CLEAN_HOOKS_JSON,
    EXIT2_PRETOOL_FILES,
    want_exit=0,
)

# A non-zero status that is NOT 2 is a non-blocking error, so it must not
# exempt. Here the `return 1` sits on a plain CLI path, outside any handler --
# the shape hooks/flag-stale-adjacent-comment.py carries at its `run_cli()`
# verdict return. A rule reading any non-zero literal as blocking would exempt
# this hook while its warning path still reaches nobody.
CLI_STATUS_PRETOOL_FILES = dict(CLEAN_FILES)
CLI_STATUS_PRETOOL_FILES["hooks/warn-pretool.py"] = (
    "import sys\n"
    "def main():\n"
    "    if sys.argv[1:] == ['--help']:\n"
    "        print('usage', file=sys.stderr)\n"
    "        return 1\n"
    "    print('warning', file=sys.stderr)\n"
    "    return 0\n"
    "sys.exit(main())\n"
)

case(
    "a CLI-path 'return 1' does not exempt a warn-only PreToolUse hook (#3068)",
    CLEAN_HOOKS_JSON,
    CLI_STATUS_PRETOOL_FILES,
    want_exit=1,
    needle="neither blocks (no blocking 'decision' emit and no exit 2)",
)

# The same for the near-universal "bail out on an unreadable payload" branch,
# which is the shape most likely to be mistaken for a block.
ERROR_PATH_PRETOOL_FILES = dict(CLEAN_FILES)
ERROR_PATH_PRETOOL_FILES["hooks/warn-pretool.py"] = (
    "import json\n"
    "import sys\n"
    "def main():\n"
    "    try:\n"
    "        json.load(sys.stdin)\n"
    "    except json.JSONDecodeError:\n"
    "        print('bad payload', file=sys.stderr)\n"
    "        return 1\n"
    "    print('warning', file=sys.stderr)\n"
    "    return 0\n"
    "sys.exit(main())\n"
)

case(
    "an unreadable-payload 'return 1' does not exempt either (#3068)",
    CLEAN_HOOKS_JSON,
    ERROR_PATH_PRETOOL_FILES,
    want_exit=1,
    needle="neither blocks (no blocking 'decision' emit and no exit 2)",
)

# An exit 2 raised INSIDE an `except` handler reports that the hook itself
# broke, not that it denied a tool call, so it must not exempt either. This is
# the shape hooks/flag-stale-adjacent-comment.py carries in its `run_cli()`.
EXCEPT_EXIT2_PRETOOL_FILES = dict(CLEAN_FILES)
EXCEPT_EXIT2_PRETOOL_FILES["hooks/warn-pretool.py"] = (
    "import sys\n"
    "def main():\n"
    "    try:\n"
    "        open('nope')\n"
    "    except OSError:\n"
    "        return 2\n"
    "    print('warning', file=sys.stderr)\n"
    "    return 0\n"
    "sys.exit(main())\n"
)

case(
    "exit 2 inside an except handler does not exempt (#3068)",
    CLEAN_HOOKS_JSON,
    EXCEPT_EXIT2_PRETOOL_FILES,
    want_exit=1,
    needle="neither blocks (no blocking 'decision' emit and no exit 2)",
)

# The converse, pinned because it is the narrowing's edge rather than an
# oversight: the exemption keys on the `except` handler and nothing wider, so
# an `if`-guarded `return 2` on an error path DOES exempt. Whoever widens
# blocks_by_exit_2 past ast.ExceptHandler has to change this case on purpose.
IF_EXIT2_PRETOOL_FILES = dict(CLEAN_FILES)
IF_EXIT2_PRETOOL_FILES["hooks/warn-pretool.py"] = (
    "import pathlib\n"
    "import sys\n"
    "def main():\n"
    "    if not pathlib.Path('nope').exists():\n"
    "        print('cannot read', file=sys.stderr)\n"
    "        return 2\n"
    "    print('warning', file=sys.stderr)\n"
    "    return 0\n"
    "sys.exit(main())\n"
)

case(
    "an if-guarded error-path exit 2 DOES exempt, by design (#3068)",
    CLEAN_HOOKS_JSON,
    IF_EXIT2_PRETOOL_FILES,
    want_exit=0,
)

# The decision arm's edge: it reads the emitted decision VALUE, so a
# `permissionDecision` of "allow" blocks nothing and does not exempt.
ALLOW_DECISION_PRETOOL_FILES = dict(CLEAN_FILES)
ALLOW_DECISION_PRETOOL_FILES["hooks/warn-pretool.py"] = (
    "import json\n"
    "import sys\n"
    "print('warning', file=sys.stderr)\n"
    'print(json.dumps({"hookSpecificOutput": {"permissionDecision": "allow"}}))\n'
)

case(
    "a non-blocking 'allow' decision does not exempt (#3068)",
    CLEAN_HOOKS_JSON,
    ALLOW_DECISION_PRETOOL_FILES,
    want_exit=1,
    needle="neither blocks (no blocking 'decision' emit and no exit 2)",
)

# --- 6. Missing hooks.json fails loudly with usage exit 2 ---
case(
    "missing hooks.json fails with exit code 2",
    None,
    CLEAN_FILES,
    want_exit=2,
    needle="no hooks parsed",
)

# --- 7. Unparseable Python source in a hook fails loudly ---
SYNTAX_ERR_FILES = dict(CLEAN_FILES)
SYNTAX_ERR_FILES["hooks/warn-stop.py"] = (
    'def invalid_syntax(\n'
)

case(
    "unparseable hook source fails with parse error",
    CLEAN_HOOKS_JSON,
    SYNTAX_ERR_FILES,
    want_exit=1,
    needle="could not be parsed as Python",
)

# --- 8. Live repository holding-constant check ---
proc = subprocess.run(
    [sys.executable, str(SCRIPT)],
    capture_output=True,
    text=True,
    cwd=str(ROOT),
)
check("real repository output shape is clean", proc.returncode == 0, f"\n{proc.stdout}{proc.stderr}")

# --- 9. Success line encodes on cp1252 stdout (ai-config#2038) ---
# The defect: every check passed, then print("\u2713 ...") raised
# UnicodeEncodeError on a Windows cp1252 stream and the process exited 1.
cp1252_env = os.environ.copy()
cp1252_env["PYTHONIOENCODING"] = "cp1252"
cp_proc = subprocess.run(
    [sys.executable, str(SCRIPT)],
    capture_output=True,
    env=cp1252_env,
    cwd=str(ROOT),
)
check(
    "success path exits 0 on a cp1252 stdout (#2038)",
    cp_proc.returncode == 0,
    f"rc={cp_proc.returncode} stderr={cp_proc.stderr!r}",
)
try:
    cp_text = cp_proc.stdout.decode("ascii")
    cp_ascii = True
except UnicodeDecodeError:
    cp_text = ""
    cp_ascii = False
check(
    "success stdout is ASCII (#2038)",
    cp_ascii and "OK: Checked" in cp_text,
    f"ascii={cp_ascii} out={cp_proc.stdout!r}",
)

# --- 10. parse_string_constants must not visit deprecated ast.Str (#2038) ---
spec = importlib.util.spec_from_file_location("check_hook_output_shape", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always", DeprecationWarning)
    strings, err = mod.parse_string_constants('x = "hello"\ny = "world"')
check(
    "parse_string_constants extracts string literals",
    strings == {"hello", "world"} and err is None,
    f"strings={strings!r} err={err!r}",
)
str_warnings = [
    w for w in caught
    if issubclass(w.category, DeprecationWarning) and "ast.Str" in str(w.message)
]
check(
    "parse_string_constants emits no ast.Str DeprecationWarning (#2038)",
    not str_warnings,
    extra=repr([str(w.message) for w in str_warnings]),
)

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
