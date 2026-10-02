#!/usr/bin/env python3
"""Tests for hooks/inject-core-rules.py (ai-config#4206).

Runs the hook as a subprocess against a fake plugin root, so each case
exercises the real stdin/stdout contract:

  1. A consumer project: the hook emits SessionStart additionalContext whose
     header names both files by absolute path BEFORE the inlined AGENTS.md,
     so a truncated preview still carries the read instruction.
  2. The project is ai-config itself (byte-identical AGENTS.md): silent.
  3. A project whose AGENTS.md differs from the plugin's: not silent. This is
     the negative control for case 2 -- a hook that went silent whenever any
     AGENTS.md existed would pass case 2 and fail here.
  4. No AGENTS.md in the plugin root: exit 0, stdout empty, stderr names it.
  5. Unparseable stdin falls back to CLAUDE_PROJECT_DIR and still works.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "inject-core-rules.py")
RULES = "# AGENTS.md\n\nRule one: never assume; always verify.\n"


def run(root, project, stdin=None):
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    env["CLAUDE_PLUGIN_ROOT"] = str(root)
    if project is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project)
    if stdin is None:
        stdin = json.dumps({"hook_event_name": "SessionStart", "source": "startup"})
    return subprocess.run([sys.executable, HOOK], input=stdin, env=env,
                          capture_output=True, text=True, timeout=30)


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    root = tmp / "plugin"
    root.mkdir()
    (root / "AGENTS.md").write_text(RULES, encoding="utf-8")
    (root / "CLAUDE.md").write_text("# CLAUDE.md\n", encoding="utf-8")

    # 1. Consumer project with no AGENTS.md of its own.
    consumer = tmp / "consumer"
    consumer.mkdir()
    proc = run(root, consumer)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "SessionStart", hso
    ctx = hso["additionalContext"]
    agents_at = ctx.index(str(root / "AGENTS.md"))
    claude_at = ctx.index(str(root / "CLAUDE.md"))
    rules_at = ctx.index("Rule one: never assume")
    assert agents_at < rules_at and claude_at < rules_at, ctx
    assert "read both files in full" in ctx, ctx

    # 2. The project is ai-config itself.
    selfrepo = tmp / "ai-config"
    selfrepo.mkdir()
    (selfrepo / "AGENTS.md").write_text(RULES, encoding="utf-8")
    proc = run(root, selfrepo)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == "", proc.stdout

    # 3. Negative control: a project with its own, different AGENTS.md.
    other = tmp / "other"
    other.mkdir()
    (other / "AGENTS.md").write_text("# other repo rules\n", encoding="utf-8")
    proc = run(root, other)
    assert proc.returncode == 0, proc.stderr
    assert "Rule one: never assume" in proc.stdout, proc.stdout

    # 4. Broken install: no AGENTS.md under the plugin root.
    empty = tmp / "empty-plugin"
    empty.mkdir()
    proc = run(empty, consumer)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == "", proc.stdout
    assert "no AGENTS.md" in proc.stderr, proc.stderr

    # 5. Garbage stdin still injects, and still honours CLAUDE_PROJECT_DIR.
    proc = run(root, selfrepo, stdin="not json")
    assert proc.returncode == 0 and proc.stdout == "", (proc.stdout, proc.stderr)
    proc = run(root, consumer, stdin="not json")
    assert proc.returncode == 0 and "Rule one" in proc.stdout, proc.stderr

print("ok: inject-core-rules.py, 5 cases")
