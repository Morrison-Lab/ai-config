#!/usr/bin/env python3
"""Tests for gen-hooks-plugin.py (ai-config#2004)."""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "gen", Path(__file__).parent / "gen-hooks-plugin.py"
)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

passes = 0
failures = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


CATALOG = {
    "_comment": ["canonical"],
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {"type": "command",
                     "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/a.py"',
                     "timeout": 10, "script": "a.py"},
                    {"type": "command",
                     "command": 'X=1 python3 "${CLAUDE_PLUGIN_ROOT}/hooks/b.py"'},
                ],
            }
        ],
        "Stop": [
            {"hooks": [{"type": "command",
                        "command": '"${CLAUDE_PLUGIN_ROOT}/hooks/c.sh"'}]}
        ],
    },
}

out = gen.generate(CATALOG)
cmds = [h["command"] for g in out["hooks"].values() for grp in g
        for h in grp["hooks"]]

check("every event is carried over", set(out["hooks"]) == {"PreToolUse", "Stop"})
check("matcher survives", out["hooks"]["PreToolUse"][0]["matcher"] == "Bash")
check("metadata keys survive",
      out["hooks"]["PreToolUse"][0]["hooks"][0]["script"] == "a.py")
check("every command runs through run-hook.sh",
      all(c.startswith("${CLAUDE_PLUGIN_ROOT}/run-hook.sh '") for c in cmds))
check("every command points two levels up at the checkout's hooks/",
      all("${CLAUDE_PLUGIN_ROOT}/../../hooks/" in c for c in cmds)
      and not any("${CLAUDE_PLUGIN_ROOT}/hooks/" in c for c in cmds))
check("env-assignment form is preserved inside the quoted command",
      cmds[1] == "${CLAUDE_PLUGIN_ROOT}/run-hook.sh "
                 "'X=1 python3 \"${CLAUDE_PLUGIN_ROOT}/../../hooks/b.py\"'")
check("the generated comment says it is generated",
      any("GENERATED" in line for line in out["_comment"]))

try:
    gen.rewrite_command("python3 /abs/hooks/x.py")
    check("a command without ${CLAUDE_PLUGIN_ROOT}/hooks/ is rejected", False)
except ValueError:
    check("a command without ${CLAUDE_PLUGIN_ROOT}/hooks/ is rejected", True)

try:
    gen.rewrite_command("python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/x.py\" 'q'")
    check("a command containing a single quote is rejected", False)
except ValueError:
    check("a command containing a single quote is rejected", True)

# --check against a temp target: fresh output passes, any edit fails.
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    src = tmp / "hooks.json"
    src.write_text(json.dumps(CATALOG), encoding="utf-8")
    target = tmp / "out" / "hooks.json"
    orig_source, orig_target, orig_root = gen.SOURCE, gen.TARGET, gen.ROOT
    gen.SOURCE, gen.TARGET, gen.ROOT = src, target, tmp
    try:
        check("--check fails when the target is missing", gen.main(["--check"]) == 1)
        check("generate writes the target", gen.main([]) == 0 and target.is_file())
        check("--check passes on fresh output", gen.main(["--check"]) == 0)
        target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        check("--check fails after an edit", gen.main(["--check"]) == 1)
    finally:
        gen.SOURCE, gen.TARGET, gen.ROOT = orig_source, orig_target, orig_root

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
