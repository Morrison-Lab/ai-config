#!/usr/bin/env python3
"""Exercise bootstrap's Cursor skill and rule skip when a plugin is live.

A full bootstrap always installs ``~/.claude/skills`` first, and Cursor
discovers that directory, so the Cursor section must not also link
``~/.cursor/skills`` on top. A marketplace/local Cursor plugin is the other
skill skip. The remaining skill-install path is covered by unit tests on
``skip_reason()`` with empty Claude and Cursor dirs.

The plugin also ships ``cursor-rules/``. Bootstrap must not also link
``~/.cursor/rules`` on top of that (ai-config#2291). A live Claude skill
catalog is not a skip for rules.
"""
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


def run_bootstrap(
    tmp: Path,
    with_plugin: bool,
    stale_link: bool | str = False,
) -> tuple[Path, str]:
    cursor = tmp / "cursor"
    cursor.mkdir(parents=True, exist_ok=True)
    if with_plugin:
        (cursor / "plugins" / "local" / "ai-config").mkdir(parents=True, exist_ok=True)
    if stale_link:
        dest = cursor / "skills" / "ardi"
        dest.parent.mkdir(parents=True)
        target = ROOT / "README.md" if stale_link == "repo-file" else ROOT / "skills" / "ardi"
        dest.symlink_to(target)
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
    check("plugin present skips ~/.cursor/rules",
          not (cursor / "rules" / "000-global-workflow.mdc").exists())
    check("plugin skip reports Cursor rules", "skip  Cursor rules" in output)

try:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        dest = tmp / "probe"
        dest.symlink_to(ROOT / "skills" / "ardi")
        can_link = dest.is_symlink()
except OSError:
    can_link = False
if can_link:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        cursor, output = run_bootstrap(tmp / "stale-link", with_plugin=True, stale_link=True)
        check("plugin skip removes this checkout's stale skill link",
              not (cursor / "skills" / "ardi").exists())
        check("skip reports stale-link removal", "stale skill link" in output)
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        cursor, output = run_bootstrap(
            tmp / "repo-file-link", with_plugin=True, stale_link="repo-file"
        )
        check(
            "plugin skip removes a repo link that is not skills/<name>",
            not (cursor / "skills" / "ardi").exists(),
        )
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        home = tmp / "stale-rule"
        cursor = home / "cursor"
        dest = cursor / "rules" / "000-global-workflow.mdc"
        dest.parent.mkdir(parents=True)
        dest.symlink_to(ROOT / "cursor-rules" / "000-global-workflow.mdc")
        real = cursor / "rules" / "001-code-quality.mdc"
        real.write_text("do not clobber\n", encoding="utf-8")
        foreign_target = tmp / "foreign.mdc"
        foreign_target.write_text("foreign\n", encoding="utf-8")
        foreign = cursor / "rules" / "foreign.mdc"
        foreign.symlink_to(foreign_target)
        cursor, output = run_bootstrap(home, with_plugin=True)
        check(
            "plugin skip removes this checkout's stale rule link",
            not dest.exists(),
        )
        check("skip reports stale-rule removal", "stale rule link" in output)
        check("plugin skip does not clobber a real rule file",
              real.is_file() and not real.is_symlink())
        check("plugin skip does not remove a foreign rule symlink",
              foreign.is_symlink() and foreign.exists())
else:
    print("SKIP: stale-link removal (platform cannot create symlink)")

with tempfile.TemporaryDirectory() as raw:
    tmp = Path(raw)
    cursor, output = run_bootstrap(tmp / "no-plugin", with_plugin=False)
    check("Claude skill install also skips ~/.cursor/skills",
          not (cursor / "skills" / "ardi").exists())
    check("skip names the Claude catalog Cursor already loads",
          "claude/skills" in output.replace("~/", ""))
    check("no-plugin path does not claim a plugin skip",
          "Cursor plugin is already installed" not in output)
    check(
        "Claude catalog skip still installs user-global rules",
        (cursor / "rules" / "000-global-workflow.mdc").is_symlink(),
    )

print(f"\n{passes} passed, {failures} failed")
raise SystemExit(1 if failures else 0)
