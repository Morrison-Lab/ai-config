#!/usr/bin/env python3
"""Tests for skills/ai-config-hooks/run-hook.sh (ai-config#2004).

The runner must pass the hook payload through on stdin, and must stand down
only when the marketplace plugin is enabled under Claude Code's scope
precedence (local > project > user), so a `false` in a higher scope wins.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "skills" / "ai-config-hooks" / "run-hook.sh"

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


def write(path: Path, enabled: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"enabledPlugins": enabled}), encoding="utf-8")


def run(home: Path, project: Path, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(home), "CLAUDE_PROJECT_DIR": str(project)}
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    return subprocess.run(
        ["bash", str(RUNNER), *args], input=stdin, capture_output=True,
        text=True, env=env, cwd=str(project),
    )


ECHO = 'cat; echo "root=${CLAUDE_PLUGIN_ROOT}"'

with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    home = tmp / "home"
    project = tmp / "project"
    home.mkdir()
    project.mkdir()

    r = run(home, project, ECHO, stdin='{"prompt":"x"}')
    check("no settings anywhere: the hook runs", r.returncode == 0 and "root=" in r.stdout)
    check("stdin payload reaches the hook", '{"prompt":"x"}' in r.stdout)
    check("CLAUDE_PLUGIN_ROOT is exported when the harness did not set it",
          f"root={RUNNER.parent.resolve()}" in r.stdout)

    r = run(home, project)
    check("no argument: exit 2", r.returncode == 2)
    r = run(home, project, "a", "b")
    check("two arguments: exit 2", r.returncode == 2)

    r = run(home, project, "exit 7")
    check("the hook's exit code is the runner's exit code", r.returncode == 7)

    write(home / ".claude" / "settings.json", {"ai-config@Morrison-Lab": True})
    r = run(home, project, ECHO, stdin="payload")
    check("user scope enables the plugin: stand down, exit 0",
          r.returncode == 0 and r.stdout == "")

    write(project / ".claude" / "settings.local.json", {"ai-config@Morrison-Lab": False})
    r = run(home, project, ECHO, stdin="payload")
    check("local false overrides user true: the hook runs", "payload" in r.stdout)

    write(project / ".claude" / "settings.json", {"ai-config@Morrison-Lab": True})
    r = run(home, project, ECHO, stdin="payload")
    check("local false still overrides project true", "payload" in r.stdout)

    (project / ".claude" / "settings.local.json").unlink()
    (home / ".claude" / "settings.json").unlink()
    r = run(home, project, ECHO, stdin="payload")
    check("project scope alone enables the plugin: stand down",
          r.returncode == 0 and r.stdout == "")

    write(project / ".claude" / "settings.json", {"other@Morrison-Lab": True})
    r = run(home, project, ECHO, stdin="payload")
    check("an unrelated plugin entry does not stand down", "payload" in r.stdout)

    write(home / ".claude" / "settings.json", {"ai-config@Morrison-Lab": False})
    r = run(home, project, ECHO, stdin="payload")
    check("an explicit false in the only file that names it: the hook runs",
          "payload" in r.stdout)

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
