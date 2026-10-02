#!/usr/bin/env python3
"""Tests for hooks/inject-core-rules.py (ai-config#4206).

Copies the hook into a fake plugin root (`<root>/hooks/`, where it always
lives) and runs it as a subprocess, so each case exercises the real
stdin/stdout contract:

  1. A consumer project: SessionStart additionalContext whose header names
     both files by absolute path, inside the 2,000-character preview Claude
     Code keeps when output exceeds its 10,000-character cap.
  2. The project is an ai-config checkout whose AGENTS.md differs from the
     plugin's cached copy (a branch editing it): the checkout's copy is
     injected and named, not the cache's.
  3. A subdirectory of an ai-config checkout: the same.
  4. Negative control: a project with its own unrelated AGENTS.md and a
     marketplace.json under another name -- the plugin's copy.
  5. No AGENTS.md in the plugin root: exit 0, stdout empty, stderr names it.
  6. Garbage stdin, project from CLAUDE_PROJECT_DIR; no env and no payload
     cwd, project from the process cwd (the Cursor adapter's case).
  8. A plugin root under a long cache path still keeps the header inside the
     2,000-character preview.
  9. Under Cursor (CURSOR_PROJECT_DIR set) in an ai-config workspace: silent,
     since Cursor reads that AGENTS.md itself; elsewhere it still injects.
  7. A CLAUDE_PLUGIN_ROOT pointing at a directory with no AGENTS.md is
     ignored, as under the generated hooks-only plugin.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(sys.argv[1] if len(sys.argv) > 1 else
            os.path.join(os.path.dirname(__file__), "inject-core-rules.py"))
RULES = "# AGENTS.md\n\nRule one: never assume; always verify.\n"


def make_root(base, with_agents=True):
    (base / "hooks").mkdir(parents=True)
    shutil.copy(HOOK, base / "hooks" / "inject-core-rules.py")
    if with_agents:
        (base / "AGENTS.md").write_text(RULES, encoding="utf-8")
    (base / "CLAUDE.md").write_text("# CLAUDE.md\n", encoding="utf-8")
    return base


def make_ai_config(base, agents=RULES, name="Morrison-Lab"):
    (base / ".claude-plugin").mkdir(parents=True)
    (base / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"name": name}), encoding="utf-8")
    (base / "AGENTS.md").write_text(agents, encoding="utf-8")
    return base


def run(root, project, stdin=None, cwd=None, env_extra=None):
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT")}
    if project is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project)
    env.update(env_extra or {})
    if stdin is None:
        stdin = json.dumps({"hook_event_name": "SessionStart", "source": "startup"})
    return subprocess.run([sys.executable, str(root / "hooks" / "inject-core-rules.py")],
                          input=stdin, env=env, cwd=cwd, capture_output=True,
                          text=True, timeout=30)


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    root = make_root(tmp / "plugin")
    consumer = tmp / "consumer"
    consumer.mkdir()

    # 1. Consumer project.
    proc = run(root, consumer)
    assert proc.returncode == 0, proc.stderr
    hso = json.loads(proc.stdout)["hookSpecificOutput"]
    assert hso["hookEventName"] == "SessionStart", hso
    ctx = hso["additionalContext"]
    agents_at = ctx.index(str(root.resolve() / "AGENTS.md"))
    claude_at = ctx.index(str(root.resolve() / "CLAUDE.md"))
    rules_at = ctx.index("Rule one: never assume")
    assert agents_at < rules_at and claude_at < rules_at, ctx
    assert "read AGENTS.md in full" in ctx, ctx
    assert "do not load it whole" in ctx, ctx
    assert ctx.index("---") < 2000, ctx.index("---")

    # 2. An ai-config checkout whose AGENTS.md differs from the plugin copy.
    selfrepo = make_ai_config(tmp / "ai-config", agents=RULES + "new rule\n")
    proc = run(root, selfrepo)
    assert proc.returncode == 0, proc.stderr
    ctx = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "new rule" in ctx and str(selfrepo.resolve() / "AGENTS.md") in ctx, ctx
    assert str(root.resolve()) not in ctx, ctx

    # 3. A subdirectory of it.
    sub = selfrepo / "skills" / "x"
    sub.mkdir(parents=True)
    proc = run(root, sub)
    assert proc.returncode == 0 and "new rule" in proc.stdout, proc.stdout

    # 4. Negative control: other repo, other marketplace name, same AGENTS.md.
    other = make_ai_config(tmp / "other", agents=RULES, name="someone-else")
    proc = run(root, other)
    assert proc.returncode == 0 and str(root.resolve()) in proc.stdout, proc.stdout

    # 5. Broken install.
    empty = make_root(tmp / "empty-plugin", with_agents=False)
    proc = run(empty, consumer)
    assert proc.returncode == 0 and proc.stdout == "", proc.stdout
    assert "no AGENTS.md" in proc.stderr, proc.stderr

    # 6. Garbage stdin; then project from the process cwd.
    proc = run(root, selfrepo, stdin="not json")
    assert proc.returncode == 0 and "new rule" in proc.stdout, proc.stdout
    proc = run(root, consumer, stdin="not json")
    assert proc.returncode == 0 and "Rule one" in proc.stdout, proc.stderr
    assert "new rule" not in proc.stdout, proc.stdout
    proc = run(root, None, stdin="{}", cwd=selfrepo)
    assert proc.returncode == 0 and "new rule" in proc.stdout, proc.stdout
    proc = run(root, None, stdin=json.dumps({"cwd": str(selfrepo)}), cwd=consumer)
    assert proc.returncode == 0 and "new rule" in proc.stdout, proc.stdout

    # 7. CLAUDE_PLUGIN_ROOT elsewhere is ignored.
    proc = run(root, consumer, env_extra={"CLAUDE_PLUGIN_ROOT": str(empty)})
    assert proc.returncode == 0 and "Rule one" in proc.stdout, proc.stderr

    # 9. Cursor in an ai-config workspace reads AGENTS.md itself: silent.
    proc = run(root, selfrepo, env_extra={"CURSOR_PROJECT_DIR": str(selfrepo)})
    assert proc.returncode == 0 and proc.stdout == "", proc.stdout
    proc = run(root, consumer, env_extra={"CURSOR_PROJECT_DIR": str(consumer)})
    assert proc.returncode == 0 and "Rule one" in proc.stdout, proc.stdout

    # 8. A long plugin-cache path.
    deep = make_root(tmp / ".claude" / "plugins" / "synced"
                     / "b5b13525-7253-4506-8dbd-37004bb96493_488ecef7-2d6b-47fc-b492-24a0c8e4c81a"
                     / "ai-config" / "cache" / "0123456789abcdef0123456789abcdef01234567")
    proc = run(deep, consumer)
    ctx = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
    assert ctx.index("---") < 2000, ctx.index("---")

print("ok: inject-core-rules.py, 9 cases")
