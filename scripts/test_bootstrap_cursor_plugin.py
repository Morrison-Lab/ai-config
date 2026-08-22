#!/usr/bin/env python3
"""Exercise bootstrap's Cursor skill-install skip when a plugin is present."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BOOTSTRAP = ROOT / "bootstrap.sh"

passes = 0
failures = 0


def check(name: str, condition: bool) -> None:
    global passes, failures
    print(f"{'PASS' if condition else 'FAIL'}: {name}")
    passes += condition
    failures += not condition


def run_bootstrap(tmp: Path, with_plugin: bool) -> tuple[Path, str]:
    cursor = tmp / "cursor"
    cursor.mkdir(parents=True)
    if with_plugin:
        (cursor / "plugins" / "local" / "ai-config").mkdir(parents=True)
    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    scontrol = bin_dir / "scontrol"
    scontrol.write_text("#!/usr/bin/env sh\nexit 1\n", encoding="utf-8")
    scontrol.chmod(0o755)
    env = os.environ | {
        "HOME": str(tmp / "home"),
        "CLAUDE_HOME": str(tmp / "claude"),
        "CODEX_HOME": str(tmp / "codex"),
        "GEMINI_HOME": str(tmp / "gemini"),
        "GEMINI_CONFIG_HOME": str(tmp / "gemini-config"),
        "CURSOR_HOME": str(cursor),
        "COPILOT_MEMORY_DIR": str(tmp / "copilot-memory"),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
    }
    result = subprocess.run(
        ["bash", str(BOOTSTRAP)], cwd=ROOT, env=env, text=True,
        capture_output=True, check=True,
    )
    return cursor, result.stdout


with tempfile.TemporaryDirectory() as raw:
    tmp = Path(raw)
    cursor, output = run_bootstrap(tmp / "with-plugin", with_plugin=True)
    check("plugin present skips ~/.cursor/skills/ardi",
          not (cursor / "skills" / "ardi").exists())
    check("plugin skip is reported", "Cursor plugin is already installed" in output)
    check("user-global rules still install",
          (cursor / "rules" / "000-global-workflow.mdc").exists())

with tempfile.TemporaryDirectory() as raw:
    tmp = Path(raw)
    cursor, output = run_bootstrap(tmp / "no-plugin", with_plugin=False)
    ardi = cursor / "skills" / "ardi"
    check("no plugin installs ~/.cursor/skills/ardi", ardi.exists())
    check("installed Cursor skill targets this checkout",
          ardi.is_symlink() and ardi.readlink() == ROOT / "skills" / "ardi")
    check("no-plugin path does not claim a plugin skip",
          "Cursor plugin is already installed" not in output)

print(f"\n{passes} passed, {failures} failed")
raise SystemExit(1 if failures else 0)
