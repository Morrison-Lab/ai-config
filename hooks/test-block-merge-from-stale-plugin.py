#!/usr/bin/env python3
"""Tests for hooks/block-merge-from-stale-plugin.py (ai-config#5603).

Builds a fake `~/.claude/plugins` with an installed snapshot whose
hooks/hooks.json registers small stand-in PreToolUse hooks, points the hook
at it with AI_CONFIG_PLUGINS_DIR, and sets AI_CONFIG_SELF_ROOT to choose
whether the running copy is the installed snapshot or a stale one:

  1. Stale, MCP merge, an installed hook denies: deny, naming that hook.
  2. Stale, MCP merge, installed hooks all pass: allow with context.
  3. Stale, MCP merge, an installed hook exits 1: deny (fail closed).
  4. Stale, `gh pr merge` via Bash, an installed Bash hook denies: deny.
  5. Current (running copy is the installed snapshot): silent.
  6. Stale, but the call is not a merge (`gh pr view`): silent.
  7. No installed_plugins.json: silent.
  8. Stale, installed snapshot has no hooks.json: deny (fail closed).
  9. A project-scope entry for another project only: silent.
 10. An installed hook whose matcher does not match the tool is not run.
 11. A legacy {"decision": "block"} output counts as a deny.
 12. The sibling cannot be imported: a merge is still gated (fail closed).
 13. The budget runs out: a later gate is reported as not reached, and denied.
 14. The repo hooks.json registers the hook for Bash and mcp__github__.*.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(sys.argv[1] if len(sys.argv) > 1 else
            os.path.join(os.path.dirname(__file__), "block-merge-from-stale-plugin.py"))

failures = []


def check(name, cond, detail=""):
    if not cond:
        failures.append(f"{name}: {detail}")
    print(("PASS " if cond else "FAIL ") + name)


DENY = ('import json;print(json.dumps({"hookSpecificOutput":{"hookEventName":'
        '"PreToolUse","permissionDecision":"deny","permissionDecisionReason":'
        '"needs a cross-harness read"}}))')
PASS = 'import sys;sys.stdin.read()'
FAIL = 'import sys;sys.exit(1)'
BLOCK = 'import json;print(json.dumps({"decision":"block","reason":"legacy no"}))'
SLOW = 'import time;time.sleep(5)'


def snapshot(base, groups):
    """An installed snapshot whose hooks.json holds *groups*: [(matcher, [(script, code)])]."""
    root = base / "cache" / "Morrison-Lab" / "ai-config" / "newsha"
    hooks = root / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    spec = []
    for matcher, scripts in groups:
        entries = []
        for script, code in scripts:
            (hooks / script).write_text(code + "\n", encoding="utf-8")
            entries.append({"type": "command", "script": script, "timeout": 10,
                            "command": f'python3 "${{CLAUDE_PLUGIN_ROOT}}/hooks/{script}"'})
        spec.append({"matcher": matcher, "hooks": entries})
    (hooks / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": spec}}), encoding="utf-8")
    return root


def record(base, root, scope="user", project=None):
    entry = {"scope": scope, "installPath": str(root)}
    if project:
        entry["projectPath"] = project
    (base / "installed_plugins.json").write_text(
        json.dumps({"plugins": {"ai-config@Morrison-Lab": [entry]}}), encoding="utf-8")


def run(base, self_root, payload):
    env = dict(os.environ, AI_CONFIG_PLUGINS_DIR=str(base),
               AI_CONFIG_SELF_ROOT=str(self_root))
    proc = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, timeout=120)
    out = json.loads(proc.stdout) if proc.stdout.strip() else None
    return proc.returncode, out


def decision(out):
    spec = (out or {}).get("hookSpecificOutput") or {}
    return spec.get("permissionDecision"), spec.get("permissionDecisionReason", ""), spec.get("additionalContext", "")


MCP_MERGE = {"tool_name": "mcp__github__merge_pull_request",
             "tool_input": {"owner": "Morrison-Lab", "repo": "mds", "pullNumber": 748}}
GH_MERGE = {"tool_name": "Bash",
            "tool_input": {"command": "gh pr merge 748 -R Morrison-Lab/mds --squash"}}
GH_VIEW = {"tool_name": "Bash", "tool_input": {"command": "gh pr view 748"}}

tmp = Path(tempfile.mkdtemp())
try:
    stale = tmp / "cache" / "Morrison-Lab" / "ai-config" / "oldsha"
    stale.mkdir(parents=True)

    def case(name, groups, payload, scope="user", project=None):
        base = tmp / name
        if base.exists():
            shutil.rmtree(base)
        base.mkdir()
        root = snapshot(base, groups)
        record(base, root, scope, project)
        return base, root

    base, root = case("c1", [("mcp__github__.*", [("gate-a.py", PASS), ("gate-b.py", DENY)])], MCP_MERGE)
    rc, out = run(base, stale, dict(MCP_MERGE, cwd=str(tmp)))
    d, reason, _ = decision(out)
    check("1 stale MCP merge, installed gate denies", rc == 0 and d == "deny" and "gate-b.py" in reason
          and "needs a cross-harness read" in reason, f"{rc} {out}")

    base, root = case("c2", [("mcp__github__.*", [("gate-a.py", PASS)])], MCP_MERGE)
    rc, out = run(base, stale, dict(MCP_MERGE, cwd=str(tmp)))
    d, reason, ctx = decision(out)
    check("2 stale MCP merge, installed gates pass", d is None and "none refused" in ctx, f"{out}")

    base, root = case("c3", [("mcp__github__.*", [("gate-a.py", FAIL)])], MCP_MERGE)
    rc, out = run(base, stale, dict(MCP_MERGE, cwd=str(tmp)))
    d, reason, _ = decision(out)
    check("3 installed gate errors: fail closed", d == "deny" and "did not run" in reason, f"{out}")

    base, root = case("c4", [("Bash", [("gate-b.py", DENY)])], GH_MERGE)
    rc, out = run(base, stale, dict(GH_MERGE, cwd=str(tmp)))
    d, reason, _ = decision(out)
    check("4 stale gh pr merge, installed Bash gate denies", d == "deny" and "gate-b.py" in reason, f"{out}")

    base, root = case("c5", [("mcp__github__.*", [("gate-b.py", DENY)])], MCP_MERGE)
    rc, out = run(base, root, dict(MCP_MERGE, cwd=str(tmp)))
    check("5 current snapshot: silent", rc == 0 and out is None, f"{out}")

    base, root = case("c6", [("Bash", [("gate-b.py", DENY)])], GH_VIEW)
    rc, out = run(base, stale, dict(GH_VIEW, cwd=str(tmp)))
    check("6 not a merge: silent", rc == 0 and out is None, f"{out}")

    base = tmp / "c7"
    base.mkdir()
    rc, out = run(base, stale, dict(MCP_MERGE, cwd=str(tmp)))
    check("7 no installed_plugins.json: silent", rc == 0 and out is None, f"{out}")

    base, root = case("c8", [("mcp__github__.*", [("gate-a.py", PASS)])], MCP_MERGE)
    (root / "hooks" / "hooks.json").unlink()
    rc, out = run(base, stale, dict(MCP_MERGE, cwd=str(tmp)))
    d, reason, _ = decision(out)
    check("8 installed hooks.json missing: fail closed", d == "deny" and "could not be run" in reason, f"{out}")

    other = tmp / "other-project"
    other.mkdir()
    base, root = case("c9", [("mcp__github__.*", [("gate-b.py", DENY)])], MCP_MERGE,
                      scope="project", project=str(other))
    rc, out = run(base, stale, dict(MCP_MERGE, cwd=str(tmp)))
    check("9 project entry for another project: silent", rc == 0 and out is None, f"{out}")

    base, root = case("c10", [("Bash", [("gate-b.py", DENY)]),
                              ("mcp__github__.*", [("gate-a.py", PASS)])], MCP_MERGE)
    rc, out = run(base, stale, dict(MCP_MERGE, cwd=str(tmp)))
    d, reason, ctx = decision(out)
    check("10 non-matching matcher not run", d is None and "none refused" in ctx, f"{out}")

    base, root = case("c11", [("mcp__github__.*", [("gate-c.py", BLOCK)])], MCP_MERGE)
    rc, out = run(base, stale, dict(MCP_MERGE, cwd=str(tmp)))
    d, reason, _ = decision(out)
    check("11 legacy decision:block is a deny", d == "deny" and "legacy no" in reason, f"{out}")

    # 12. The hook copied alone, so its sibling cannot be imported: the
    # coarse merge test still runs the installed gates (fail closed).
    lone = tmp / "lone"
    lone.mkdir()
    shutil.copy(HOOK, lone / HOOK.name)
    base, root = case("c12", [("mcp__github__.*", [("gate-b.py", DENY)])], MCP_MERGE)
    env = dict(os.environ, AI_CONFIG_PLUGINS_DIR=str(base), AI_CONFIG_SELF_ROOT=str(stale))
    proc = subprocess.run([sys.executable, str(lone / HOOK.name)],
                          input=json.dumps(dict(MCP_MERGE, cwd=str(tmp))),
                          capture_output=True, text=True, env=env, timeout=120)
    out = json.loads(proc.stdout) if proc.stdout.strip() else None
    d, reason, _ = decision(out)
    check("12 sibling unavailable: merge still gated", d == "deny" and "gate-b.py" in reason,
          f"{proc.returncode} {out} {proc.stderr[-300:]}")

    # 13. A slow first gate uses the whole budget: the second is reported as
    # not reached, and the merge is refused.
    base, root = case("c13", [("mcp__github__.*", [("gate-s.py", SLOW), ("gate-a.py", PASS)])],
                      MCP_MERGE)
    env = dict(os.environ, AI_CONFIG_PLUGINS_DIR=str(base), AI_CONFIG_SELF_ROOT=str(stale),
               AI_CONFIG_STALE_GATE_BUDGET="1")
    proc = subprocess.run([sys.executable, str(HOOK)],
                          input=json.dumps(dict(MCP_MERGE, cwd=str(tmp))),
                          capture_output=True, text=True, env=env, timeout=120)
    out = json.loads(proc.stdout) if proc.stdout.strip() else None
    d, reason, _ = decision(out)
    check("13 budget exhausted: later gate not reached, deny",
          d == "deny" and "gate-s.py: timed out" in reason
          and "gate-a.py: not reached" in reason, f"{out}")

    # 14. The repo's own hooks.json registers this hook for both merge
    # surfaces, with the script field matching_hooks uses to skip itself.
    spec = json.loads((HOOK.parent / "hooks.json").read_text(encoding="utf-8"))
    groups = [g.get("matcher") for g in spec["hooks"]["PreToolUse"]
              if any(h.get("script") == HOOK.name for h in g.get("hooks", []))]
    check("14 registered for Bash and mcp__github__.*",
          "Bash" in groups and "mcp__github__.*" in groups, f"{groups}")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if failures:
    print(f"\n{len(failures)} failure(s):")
    for f in failures:
        print("  " + f)
    sys.exit(1)
print("\nall passed")
