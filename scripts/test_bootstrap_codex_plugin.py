#!/usr/bin/env python3
"""Exercise bootstrap's mutually-exclusive Codex skill installation paths."""
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


def run_bootstrap(tmp: Path, config: str) -> tuple[Path, str]:
    codex = tmp / "codex"
    codex.mkdir(parents=True)
    (codex / "config.toml").write_text(config, encoding="utf-8")
    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    scontrol = bin_dir / "scontrol"
    scontrol.write_text("#!/usr/bin/env sh\nexit 1\n", encoding="utf-8")
    scontrol.chmod(0o755)
    env = os.environ | {
        "HOME": str(tmp / "home"),
        "CLAUDE_HOME": str(tmp / "claude"),
        "CODEX_HOME": str(codex),
        "GEMINI_HOME": str(tmp / "gemini"),
        "GEMINI_CONFIG_HOME": str(tmp / "gemini-config"),
        "CURSOR_HOME": str(tmp / "cursor"),
        "COPILOT_MEMORY_DIR": str(tmp / "copilot-memory"),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
    }
    result = subprocess.run(
        ["bash", str(BOOTSTRAP)], cwd=ROOT, env=env, text=True,
        capture_output=True, check=True,
    )
    return codex, result.stdout


with tempfile.TemporaryDirectory() as raw:
    tmp = Path(raw)
    codex, output = run_bootstrap(
        tmp / "plugin-enabled", '[plugins."ai-config@the repository owner"]\nenabled = true\n'
    )
    check("enabled plugin skips bare Codex wrappers", not (codex / "skills" / "ardi").exists())
    check("enabled plugin reports the skipped wrapper route", "ai-config plugin is enabled" in output)

with tempfile.TemporaryDirectory() as raw:
    tmp = Path(raw)
    codex, _ = run_bootstrap(
        tmp / "plugin-disabled", '[plugins."ai-config@the repository owner"]\nenabled = false\n'
    )
    ardi = codex / "skills" / "ardi"
    check("disabled plugin installs bare Codex wrappers", ardi.is_symlink())
    check("installed wrapper targets this checkout", ardi.readlink() == ROOT / "codex-skills" / "ardi")

with tempfile.TemporaryDirectory() as raw:
    tmp = Path(raw)
    root = tmp / "stale-link"
    codex = root / "codex"
    (codex / "skills").mkdir(parents=True)
    (codex / "config.toml").write_text(
        '[plugins."ai-config@the repository owner"]\nenabled = true\n', encoding="utf-8"
    )
    stale = codex / "skills" / "ardi"
    stale.symlink_to(ROOT / "codex-skills" / "ardi")
    bin_dir = root / "bin"
    bin_dir.mkdir()
    scontrol = bin_dir / "scontrol"
    scontrol.write_text("#!/usr/bin/env sh\nexit 1\n", encoding="utf-8")
    scontrol.chmod(0o755)
    env = os.environ | {
        "HOME": str(root / "home"), "CLAUDE_HOME": str(root / "claude"),
        "CODEX_HOME": str(codex), "GEMINI_HOME": str(root / "gemini"),
        "GEMINI_CONFIG_HOME": str(root / "gemini-config"),
        "CURSOR_HOME": str(root / "cursor"), "COPILOT_MEMORY_DIR": str(root / "copilot-memory"),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
    }
    subprocess.run(["bash", str(BOOTSTRAP)], cwd=ROOT, env=env, check=True,
                   capture_output=True, text=True)
    check("enabled plugin removes a same-checkout stale wrapper", not stale.exists())

print(f"\n{passes} passed, {failures} failed")
raise SystemExit(1 if failures else 0)
