#!/usr/bin/env python3
"""Regression tests for `install-hooks.py --check` and `scripts/lib/hook_paths.py`.

The behaviour under test is the one whose absence caused ai-config#2392: a
settings.json that registers a hook at a path with no file behind it denies
every tool call its matcher names, because `python3` exits 2 on a file it
cannot open and exit 2 is the `PreToolUse` deny signal.

The known-positive case runs first, per `fail-fast.md`'s negative-control
rule: a checker whose every input is clean proves only that it stays quiet,
and quiet is also what a checker that examines nothing produces.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
INSTALLER = SCRIPTS / "install-hooks.py"
LIB = SCRIPTS / "lib" / "hook_paths.py"

# chr(10) rather than a literal escape: this file is written through a tool
# transport that collapses a doubled backslash (see CLAUDE.md).
NL = chr(10)

spec = importlib.util.spec_from_file_location("hook_paths", LIB)
hp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hp)

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


def run_check(home):
    """Run `install-hooks.py --check` with CLAUDE_HOME pointed at `home`."""
    env = dict(os.environ, CLAUDE_HOME=str(home), PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(INSTALLER), "--check"],
                          capture_output=True, text=True, env=env)


def settings_with(command, matcher="Bash", event="PreToolUse"):
    return {"hooks": {event: [{"matcher": matcher,
                               "hooks": [{"type": "command",
                                          "command": command}]}]}}


def write_settings(home, settings):
    home.mkdir(parents=True, exist_ok=True)
    (home / "settings.json").write_text(json.dumps(settings, indent=2))


# --- the library, known positive first ---------------------------------------

check("a python3 command naming an absent file classifies as missing",
      hp.classify_command('python3 "/nonexistent-dir/guard.py"')[0] == "missing")
check("a bare .sh command naming an absent file classifies as missing",
      hp.classify_command('"/nonexistent-dir/guard.sh"')[0] == "missing")
check("this very test file classifies as ok",
      hp.classify_command(f'python3 "{__file__}"')[0] == "ok")
check("an unexpandable plugin-root path is skipped, not missing",
      hp.classify_command(
          'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/guard.py"')[0] == "skipped")
check("a command naming no script at all is skipped",
      hp.classify_command("echo hello")[0] == "skipped")
check("script_token reads the script past its interpreter",
      hp.script_token('python3 "/a/b/guard.py"') == "/a/b/guard.py")
check("registered_hooks yields one row per bound command",
      list(hp.registered_hooks(settings_with("python3 /a/guard.py")))
      == [("PreToolUse", "Bash", "python3 /a/guard.py")])
check("registered_hooks tolerates a settings file with no hooks key",
      list(hp.registered_hooks({})) == [])


# --- the CLI ------------------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp) / "claude"
    absent = Path(tmp) / "no-such-hook.py"
    write_settings(home, settings_with(f'python3 "{absent}"'))
    result = run_check(home)
    check("--check exits non-zero over a registered path that does not resolve",
          result.returncode == 1)
    check("--check names the unresolvable path",
          str(absent) in result.stdout)
    check("--check names the event the broken hook is bound to",
          "PreToolUse" in result.stdout and "Bash" in result.stdout)
    check("--check reports how many commands it examined",
          "examined 1 registered hook command(s)" in result.stdout)

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp) / "claude"
    present = Path(tmp) / "guard.py"
    present.write_text("import sys" + NL + "sys.exit(0)" + NL)
    write_settings(home, settings_with(f'python3 "{present}"'))
    result = run_check(home)
    check("--check exits 0 when every registered path resolves",
          result.returncode == 0)
    check("--check says so explicitly rather than printing nothing",
          "Every registered hook path resolves." in result.stdout)

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp) / "claude"
    home.mkdir(parents=True)
    result = run_check(home)
    check("--check exits non-zero when no settings file exists at all",
          result.returncode == 1)
    check("--check says the zero case is not a clean one",
          "zero case" in result.stdout)

print(NL + f"{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
