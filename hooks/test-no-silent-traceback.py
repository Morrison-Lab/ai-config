"""Test the no-silent-traceback PostToolUse guard.

Case 1 is the incident verbatim: a heredoc assert raised, Rscript ran anyway,
and the combined output carried a traceback while the harness exit was 0.

Run: python3 hooks/test-no-silent-traceback.py hooks/no-silent-traceback.py
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HOOK = sys.argv[1]

_spec = importlib.util.spec_from_file_location("hook", HOOK)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

INCIDENT_OUTPUT = """\
Traceback (most recent call last):
  File "<stdin>", line 2, in <module>
AssertionError
[1] "ok"
"""

INCIDENT = """cd some/dir && python3 - <<'PY'
s = open(p).read()
assert s.count(old) == 1
open(p, "w").write(...)
PY
R_PROFILE_USER=/dev/null Rscript -e '...'
"""


def payload(command, stdout="", stderr="", tool_name="Bash"):
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": {"command": command},
        "tool_response": {
            "stdout": stdout,
            "stderr": stderr,
            "interrupted": False,
            "isImage": False,
        },
    }


def run(payload_dict):
    out = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload_dict),
        capture_output=True,
        text=True,
    ).stdout
    return "additionalContext" in out or "systemMessage" in out


CASES = [
    (payload(INCIDENT, stderr=INCIDENT_OUTPUT), True,
     "incident verbatim: traceback in output on a successful Bash call"),
    (payload("python3 -c 'print(1)'", stdout="1\n"), False,
     "clean stdout, no traceback"),
    (payload("grep -n Traceback CLAUDE.md",
               stdout="42: prose quoting `Traceback (most recent call last):`"),
     False,
     "prose quoting the phrase mid-line does not warn"),
    (payload("echo hi", stdout="hi\n"), False,
     "unrelated successful command stays silent"),
    ({**payload("true"), "tool_name": "Read"}, False,
     "non-Bash tool stays silent"),
]


def main():
    passes = failures = 0

    for pl, expected, label in CASES:
        got = mod.should_warn(pl)
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected warn={expected}, got {got})")
            failures += 1

    # Integration: subprocess path emits JSON on warn
    if run(payload(INCIDENT, stderr=INCIDENT_OUTPUT)):
        print("PASS: hook subprocess emits context on incident output")
        passes += 1
    else:
        print("FAIL: hook subprocess silent on incident output")
        failures += 1

    if not run(payload("true", stdout="ok\n")):
        print("PASS: hook subprocess stays silent on clean output")
        passes += 1
    else:
        print("FAIL: hook subprocess warned on clean output")
        failures += 1

    # Mutation: a substring matcher would false-positive on mid-line prose
    saved = mod.TRACEBACK
    mid = payload("grep Traceback x", stdout="x: Traceback (most recent call last):")
    mod.TRACEBACK = __import__("re").compile(r"Traceback \(most recent call last\):")
    if mod.should_warn(mid):
        print("PASS: mutation --- without line anchor, mid-line quote warns")
        passes += 1
    else:
        print("FAIL: substring matcher did not false-positive on mid-line quote")
        failures += 1
    mod.TRACEBACK = saved
    if not mod.should_warn(mid):
        print("PASS: line anchor suppresses mid-line prose quote")
        passes += 1
    else:
        print("FAIL: restored anchor still warns on mid-line quote")
        failures += 1

    # PostToolUseFailure is not hooked --- non-zero exits are already visible
    manifest_path = Path(__file__).resolve().parent / "hooks.json"
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    bound = [e.get("script") for groups in manifest.get("hooks", {}).values()
             for g in (groups if isinstance(groups, list) else [])
             for e in (g.get("hooks", []) if isinstance(g, dict) else [])]
    if "no-silent-traceback.py" in bound and "PostToolUseFailure" not in manifest.get("hooks", {}):
        print("PASS: hook binds only to PostToolUse, not PostToolUseFailure")
        passes += 1
    else:
        print("FAIL: hook should bind PostToolUse only")
        failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
