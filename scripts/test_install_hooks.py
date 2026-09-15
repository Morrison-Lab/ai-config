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
check("an undefined variable in the path is missing, not skipped",
      hp.classify_command("python3 $NO_SUCH_VAR_2392/hooks/guard.py")[0] == "missing")
check("a POSIX path with an escaped space keeps its escape",
      hp.script_token("python3 /path/with\\ space/x.py") == "/path/with space/x.py")
check("an unquoted Windows path keeps its backslashes",
      hp.script_token(r"python3 C:\Users\me\.claude\hooks\x.py")
      == r"C:\Users\me\.claude\hooks\x.py")
check("a drive path elsewhere in the command leaves an escaped space alone",
      hp.script_token("python3 /path/with\\ space/x.py --root C:\\Users\\me")
      == "/path/with space/x.py")
check("a drive path glued to a flag by = keeps its backslashes",
      hp.script_token(r"python3 --file=C:\x\y.py") == r"--file=C:\x\y.py")
check("a mixed-separator drive path keeps its backslashes",
      hp.script_token(r"python3 C:/Users\me\x.py") == r"C:/Users\me\x.py")
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


with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp) / "claude"
    present = home / "guard.py"
    home.mkdir(parents=True)
    present.write_text("import sys" + NL + "sys.exit(0)" + NL)

    # The resolution of a Windows-shaped path is OS-native (Path.is_file),
    # so these three run only on Windows; the token-level Windows cases
    # above run everywhere.
    if os.name == "nt":
        # Backslash Windows path
        windows_path = str(present).replace('/', '\\')
        write_settings(home, settings_with(f'python3 "{windows_path}"'))
        result = run_check(home)
        check("a backslash Windows path that exists is reported ok",
              result.returncode == 0 and "Every registered hook path resolves" in result.stdout)
        write_settings(home, settings_with(f'python3 {windows_path}'))
        result = run_check(home)
        check("an UNQUOTED backslash Windows path that exists is reported ok",
              result.returncode == 0 and "Every registered hook path resolves" in result.stdout)

        # Forward-slash Windows path (str(Path) might use backslashes on Windows, so force forward slash)
        forward_path = str(present).replace('\\', '/')
        write_settings(home, settings_with(f'python3 "{forward_path}"'))
        result = run_check(home)
        check("a forward-slash Windows path that exists is reported ok",
              result.returncode == 0 and "Every registered hook path resolves" in result.stdout)
    else:
        print("SKIP: Windows-path resolution checks (not on Windows)")

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp) / "claude"
    write_settings(home, settings_with('echo hello'))
    result = run_check(home)
    check("--check prints a skipped row with its reason",
          "SKIPPED" in result.stdout and "no script token found" in result.stdout)
    check("--check exits 0 for skipped alone",
          result.returncode == 0)

# --- interpreter probe (ai-config#3624) -------------------------------------
#
# Every check above asks THIS process whether a path exists. That is the wrong
# process: the harness spawns the hook command, and the interpreter it resolves
# may not see the same filesystem. On Windows bare `python3` commonly resolves
# to the Store App Execution Alias, which cannot read %APPDATA%\Claude -- so
# every path above reports ok while every hook denies every tool call.
#
# Known-positive first, per this file's own negative-control rule: a probe that
# never returns "blind" is indistinguishable from one that never runs.

check("interpreter_token reads the interpreter out of a hook command",
      hp.interpreter_token('python3 "/x/y.py"') == "python3")
check("interpreter_token returns None for a script that runs itself",
      hp.interpreter_token('"/x/y.sh"') is None)
check("interpreter_token returns None for an empty command",
      hp.interpreter_token("") is None)

with tempfile.TemporaryDirectory() as tmp:
    present = Path(tmp) / "hook.py"
    present.write_text("")
    absent = Path(tmp) / "no-such-hook.py"

    check("probe_interpreter reports ok when the interpreter can read the file",
          hp.probe_interpreter(sys.executable, str(present)) == "ok")
    # The known-positive. A real interpreter pointed at a file that is really
    # absent produces the same observation the Store alias produces for a file
    # that is present -- which is what makes the verdict meaningful.
    check("probe_interpreter reports blind when the interpreter cannot see it",
          hp.probe_interpreter(sys.executable, str(absent)) == "blind")
    check("probe_interpreter reports unlaunchable for a name that will not run",
          hp.probe_interpreter("python3-no-such-interpreter-xyz",
                               str(present)) == "unlaunchable")
    # `-c` is a Python flag. Handing it to sh or node would test the prober.
    check("probe_interpreter skips a non-Python interpreter",
          hp.probe_interpreter("node", str(present)) == "skipped")

    # End to end: --check runs the probe and says how many it probed, so a
    # silent pass cannot be mistaken for a clean one.
    home = Path(tmp) / "claude"
    write_settings(home, settings_with(f'"{sys.executable}" "{present}"'))
    result = run_check(home)
    check("--check reports how many interpreters it probed",
          "probed 1 interpreter(s)" in result.stdout)
    check("--check stays green when the interpreter can read its hook",
          result.returncode == 0)

    # An interpreter that did not resolve HERE is not a finding: the harness
    # spawns hooks through its own shell, and reading our PATH backwards would
    # be the same mistake #3624 is about, pointed the other way.
    write_settings(home, settings_with(
        f'python3-no-such-interpreter-xyz "{present}"'))
    result = run_check(home)
    check("--check names an interpreter it could not launch",
          "NO EXEC" in result.stdout)
    check("--check does not fail the install over an unlaunchable name",
          result.returncode == 0 and "Not findings" in result.stdout)
    # The count is the whole reason that line exists, so it must not credit a
    # probe that reached no answer.
    check("--check does not count an unlaunchable name as probed",
          "probed 0 interpreter(s)" in result.stdout)

    # The END-TO-END known positive. Without it, deleting the escalation
    # entirely leaves the suite green: every other case here is either a unit
    # call or a clean run.
    stub_dir = Path(tmp) / "stub"
    stub_dir.mkdir()
    if os.name == "nt":
        stub = stub_dir / "python3blind.bat"
        stub.write_text("@exit /b 1" + NL)
    else:
        stub = stub_dir / "python3blind"
        stub.write_text("#!/bin/sh" + NL + "exit 1" + NL)
        stub.chmod(0o755)
    write_settings(home, settings_with(f'"{stub}" "{present}"'))
    result = run_check(home)
    check("--check names an interpreter that reported a present file absent",
          "BLIND" in result.stdout)
    check("--check counts the blind interpreter as probed",
          "probed 1 interpreter(s)" in result.stdout)
    check("--check fails the install on a blind interpreter",
          result.returncode == 1)
    check("--check gives the blind interpreter's remedy",
          "App execution aliases" in result.stdout)
    check("--check does not also print the all-clear sentence",
          "Every registered hook path resolves." not in result.stdout)

    # A plugin-root command is `skipped` by the path check -- and it is the
    # exact registration shape #3624 was observed in, so dropping it silently
    # would end this check on an all-clear for the one case it is written for.
    write_settings(home, settings_with(
        'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/a.py"'))
    result = run_check(home)
    check("--check reports a plugin-root command as unprobed, not as clean",
          "UNPROBED" in result.stdout)
    check("--check says why the plugin-root command could not be probed",
          "expands only in the plugin loader" in result.stdout)
    check("--check does not claim to have probed it",
          "probed 0 interpreter(s)" in result.stdout)

with tempfile.TemporaryDirectory() as tmp:
    present = Path(tmp) / "hook.py"
    present.write_text("")
    # A leading assignment is part of the command, not the name of it.
    check("interpreter_token skips a leading environment assignment",
          hp.interpreter_token('PYTHONPATH=/x python3 "/y/a.py"') == "python3")
    check("interpreter_token skips several leading assignments",
          hp.interpreter_token('A=1 B=2 python3 "/y/a.py"') == "python3")
    check("interpreter_token does not mistake a path containing = for one",
          hp.interpreter_token('/opt/a=b/python3 "/y/a.py"') == "/opt/a=b/python3")
    # TimeoutExpired IS a SubprocessError, so folding them would report an
    # interpreter that launched and hung as one that never launched.
    check("probe_interpreter separates a hang from a failure to launch",
          hp.probe_interpreter(sys.executable,
                               str(present), timeout=0.0) == "timeout")

print(NL + f"{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
