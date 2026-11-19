#!/usr/bin/env python3
"""Tests for hooks/sync-auto-mode-approvals.py (ai-config#5853)."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOOK = HERE / "sync-auto-mode-approvals.py"
spec = importlib.util.spec_from_file_location("wire", HERE.parent / "scripts" / "wire-user-config.py")
wire = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wire)
FAILED = []
RAN = []


def check(label, cond):
    RAN.append(label)
    print(("PASS: " if cond else "FAIL: ") + label)
    if not cond:
        FAILED.append(label)


def run(home, **env):
    full = {k: v for k, v in os.environ.items()
            if k not in ("CLAUDE_CODE_REMOTE", "AI_CONFIG_NO_APPROVAL_SYNC",
                         "CLAUDE_HOME")}
    full.update({"HOME": str(home)}, **env)
    proc = subprocess.run([sys.executable, str(HOOK)], input="{}", text=True,
                          capture_output=True, env=full)
    return proc


def allow(home):
    data = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    return data.get("autoMode", {}).get("allow", [])


def main():
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        (home / ".claude").mkdir()
        (home / ".claude" / "settings.json").write_text(
            json.dumps({"autoMode": {"allow": ["$defaults", "mine"]}}),
            encoding="utf-8")
        proc = run(home)
        check("exits 0", proc.returncode == 0)
        rules = allow(home)
        check("adds the verdict-post rule (the measured gap)",
              wire.VERDICT_POST_AUTO_MODE_RULE in rules)
        check("adds every approval-scope rule, branch push and run cancel",
              all(r in rules for r in (*wire.APPROVAL_SCOPE_AUTO_MODE_RULES,
                                       wire.BRANCH_PUSH_AUTO_MODE_RULE,
                                       wire.CANCEL_AUTO_MODE_RULE)))
        check("keeps the existing entries first", rules[:2] == ["$defaults", "mine"])
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        check("reports the write as SessionStart context",
              out["hookEventName"] == "SessionStart"
              and "next session" in out["additionalContext"])
        again = run(home)
        check("a second run is silent and changes nothing",
              again.stdout.strip() == "" and allow(home) == rules)

    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        (home / ".claude").mkdir()
        (home / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
        proc = run(home, CLAUDE_CODE_REMOTE="true")
        check("a remote container writes nothing",
              proc.stdout.strip() == "" and allow(home) == [])
        proc = run(home, AI_CONFIG_NO_APPROVAL_SYNC="1")
        check("the opt-out writes nothing",
              proc.stdout.strip() == "" and allow(home) == [])

    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        (home / ".claude").mkdir()
        (home / ".claude" / "settings.json").write_text("[1]", encoding="utf-8")
        proc = run(home)
        check("a non-object settings file fails open and is left alone",
              proc.returncode == 0 and proc.stdout.strip() == ""
              and (home / ".claude" / "settings.json").read_text(encoding="utf-8") == "[1]")
        check("a skipped step reports its reason on stderr",
              "is not a JSON object" in proc.stderr)

    print(f"\n{len(RAN) - len(FAILED)} passed, {len(FAILED)} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
