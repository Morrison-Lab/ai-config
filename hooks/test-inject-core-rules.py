#!/usr/bin/env python3
"""Tests for hooks/inject-core-rules.py (ai-config#4206).

Copies the hook into a fake plugin root (`<root>/hooks/`, where it lives) and
runs it as a subprocess, so each case exercises the real stdin/stdout
contract:

  1. A consumer project: SessionStart additionalContext that names both files
     by absolute path, orders AGENTS.md read in full, lists its section
     headings, and does not inline section bodies.
  2. The project is an ai-config checkout whose AGENTS.md differs from the
     plugin's cached copy (a branch editing it): the checkout's copy is named
     and indexed, not the cache's.
  3. A subdirectory of an ai-config checkout: the same.
  4. Negative control: a project with its own AGENTS.md and a
     marketplace.json under another name -- the plugin's copy.
  5. No AGENTS.md in the plugin root: exit 0, stdout empty, stderr names it.
  6. A stray copy outside any plugin or checkout (the old ~/.claude/hooks
     install, beside a leftover AGENTS.md): exit 0, stdout empty, stderr
     says so.
  7. Garbage stdin, project from CLAUDE_PROJECT_DIR; no env and no payload
     cwd, project from the process cwd (the Cursor adapter's case).
  8. A CLAUDE_PLUGIN_ROOT pointing at a directory with no AGENTS.md is
     ignored, as under the generated hooks-only plugin.
  9. Under Cursor (CURSOR_PROJECT_DIR set) in an ai-config workspace: silent,
     since Cursor reads that AGENTS.md itself; elsewhere it still injects.
 10. This repository's real AGENTS.md under a long plugin-cache path stays
     within Claude Code's 10,000-character cap, so all of it reaches the
     model rather than a 2,000-character preview.
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
REAL_AGENTS = Path(__file__).resolve().parent.parent / "AGENTS.md"
RULES = "# AGENTS.md\n\n## Rule one: verify\n\nBody text that is never inlined.\n"


def make_root(base, with_agents=True, plugin=True, agents=RULES):
    (base / "hooks").mkdir(parents=True)
    shutil.copy(HOOK, base / "hooks" / "inject-core-rules.py")
    if plugin:
        (base / ".claude-plugin").mkdir()
        (base / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
    if with_agents:
        (base / "AGENTS.md").write_text(agents, encoding="utf-8")
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
           if k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT", "CURSOR_PROJECT_DIR")}
    if project is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project)
    env.update(env_extra or {})
    if stdin is None:
        stdin = json.dumps({"hook_event_name": "SessionStart", "source": "startup"})
    return subprocess.run([sys.executable, str(root / "hooks" / "inject-core-rules.py")],
                          input=stdin, env=env, cwd=cwd, capture_output=True,
                          text=True, timeout=30)


def context(proc):
    assert proc.returncode == 0, proc.stderr
    hso = json.loads(proc.stdout)["hookSpecificOutput"]
    assert hso["hookEventName"] == "SessionStart", hso
    return hso["additionalContext"]


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    root = make_root(tmp / "plugin")
    consumer = tmp / "consumer"
    consumer.mkdir()

    # 1. Consumer project.
    ctx = context(run(root, consumer))
    assert str(root.resolve() / "AGENTS.md") in ctx, ctx
    assert str(root.resolve() / "CLAUDE.md") in ctx, ctx
    assert "read AGENTS.md in full" in ctx, ctx
    assert "do not load it whole" in ctx, ctx
    assert "- Rule one: verify" in ctx, ctx
    assert "Body text" not in ctx, ctx

    # 2. An ai-config checkout whose AGENTS.md differs from the plugin copy.
    selfrepo = make_ai_config(tmp / "ai-config", agents=RULES + "\n## New rule\n")
    ctx = context(run(root, selfrepo))
    assert "- New rule" in ctx and str(selfrepo.resolve() / "AGENTS.md") in ctx, ctx
    assert str(root.resolve()) not in ctx, ctx

    # 3. A subdirectory of it.
    sub = selfrepo / "skills" / "x"
    sub.mkdir(parents=True)
    assert "- New rule" in context(run(root, sub))

    # 4. Negative control: other repo, other marketplace name.
    other = make_ai_config(tmp / "other", name="someone-else")
    assert str(root.resolve()) in context(run(root, other))

    # 5. Broken install.
    empty = make_root(tmp / "empty-plugin", with_agents=False)
    proc = run(empty, consumer)
    assert proc.returncode == 0 and proc.stdout == "", proc.stdout
    assert "no AGENTS.md" in proc.stderr, proc.stderr

    # 6. Stray copy beside a leftover AGENTS.md.
    stray = make_root(tmp / "dot-claude", plugin=False)
    proc = run(stray, consumer)
    assert proc.returncode == 0 and proc.stdout == "", proc.stdout
    assert "stray" in proc.stderr, proc.stderr

    # 7. Garbage stdin; then project from the payload, then the process cwd.
    assert "- New rule" in context(run(root, selfrepo, stdin="not json"))
    ctx = context(run(root, consumer, stdin="not json"))
    assert "- Rule one" in ctx and "New rule" not in ctx, ctx
    assert "- New rule" in context(run(root, None, stdin="{}", cwd=selfrepo))
    assert "- New rule" in context(
        run(root, None, stdin=json.dumps({"cwd": str(selfrepo)}), cwd=consumer))

    # 8. CLAUDE_PLUGIN_ROOT elsewhere is ignored.
    assert "- Rule one" in context(
        run(root, consumer, env_extra={"CLAUDE_PLUGIN_ROOT": str(empty)}))

    # 9. Cursor in an ai-config workspace reads AGENTS.md itself: silent.
    proc = run(root, selfrepo, env_extra={"CURSOR_PROJECT_DIR": str(selfrepo)})
    assert proc.returncode == 0 and proc.stdout == "", proc.stdout
    assert "- Rule one" in context(
        run(root, consumer, env_extra={"CURSOR_PROJECT_DIR": str(consumer)}))

    # 10. The real AGENTS.md under a long cache path fits the cap.
    deep = make_root(tmp / ".claude" / "plugins" / "synced"
                     / "b5b13525-7253-4506-8dbd-37004bb96493_488ecef7-2d6b-47fc-b492-24a0c8e4c81a"
                     / "ai-config" / "cache" / "0123456789abcdef0123456789abcdef01234567",
                     agents=REAL_AGENTS.read_text(encoding="utf-8"))
    ctx = context(run(deep, consumer))
    assert len(ctx) < 10_000, len(ctx)
    assert "section index omitted" not in ctx, "index no longer fits the cap"

print("ok: inject-core-rules.py, 10 cases")
