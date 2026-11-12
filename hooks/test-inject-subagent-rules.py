#!/usr/bin/env python3
"""Tests for hooks/inject-subagent-rules.py (ai-config#4698)."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).with_name("inject-subagent-rules.py"))
RULES = HOOK.resolve().parent.parent / "shared" / "workflow" / "subagent-core-rules.md"
_spec = importlib.util.spec_from_file_location("inject_subagent_rules", HOOK)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)


def run(stdin):
    p = subprocess.run([sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True)
    return p.returncode, p.stdout


def main():
    fails = []
    rc, out = run(json.dumps({"hook_event_name": "SubagentStart", "agent_type": "general-purpose"}))
    data = json.loads(out)["hookSpecificOutput"]
    if rc != 0 or data["hookEventName"] != "SubagentStart":
        fails.append("no SubagentStart output")
    if "one div per subfile" not in data["additionalContext"]:
        fails.append("rules text missing")
    if len(data["additionalContext"]) > 10_000:
        fails.append("over the 10,000-character cap")
    rc, out = run("not json")
    if rc != 0 or not out:
        fails.append("garbage stdin must still inject")
    if len(RULES.read_text(encoding="utf-8")) > _hook.RULES_BUDGET:
        fails.append(f"rules file over its {_hook.RULES_BUDGET:,}-character budget")
    for f in fails:
        print("FAIL:", f)
    print("ok" if not fails else f"{len(fails)} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
