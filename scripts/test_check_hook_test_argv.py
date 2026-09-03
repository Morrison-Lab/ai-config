#!/usr/bin/env python3
"""Regression tests for check-hook-test-argv.py.

Every case runs the real script as a subprocess against a synthetic hooks
directory, verifying that:
  1. A stub that reads sys.argv is not flagged.
  2. A stub that ignores argv is flagged, advisory by default.
  3. --strict turns that finding into a non-zero exit.
  4. A shell stub is judged on its own forms ("$@"), not on Python ones.
  5. A stub split across an f-string is read whole, not per literal,
     and an enclosing block mentioning sys.argv does not mask a blind stub.
  6. A shebang in fixture content, with no stub installed, is not a finding.
  7. A shell-hook subject is examined rather than dropped for its extension.
  8. A path named argv_log does not, by itself, count as reading argv.
  9. Unparseable test source fails loudly; a missing directory exits 2.
 10. The live repository is clean, and the report names how many stubs it saw.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "check-hook-test-argv.py"
ROOT = Path(__file__).resolve().parent.parent

passes = 0
failures = 0


def check(name: str, condition: bool, extra: str = "") -> None:
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name} {extra}")
        failures += 1


def make_hooks_dir(tmpdir: str, files: dict[str, str]) -> Path:
    hooks_dir = Path(tmpdir) / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (hooks_dir / name).write_text(content, encoding="utf-8")
    return hooks_dir


def run(hooks_dir: Path, strict: bool = False) -> tuple[int, str]:
    cmd = [sys.executable, str(SCRIPT), "--hooks-dir", str(hooks_dir)]
    if strict:
        cmd.append("--strict")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def case(
    name: str,
    files: dict[str, str],
    want_exit: int = 0,
    needle: str | None = None,
    absent: str | None = None,
    strict: bool = False,
) -> None:
    with tempfile.TemporaryDirectory() as td:
        hooks_dir = make_hooks_dir(td, files)
        rc, out = run(hooks_dir, strict=strict)
    ok = rc == want_exit
    if ok and needle:
        ok = needle in out
    if ok and absent:
        ok = absent not in out
    check(name, ok, f"(rc={rc} want={want_exit} needle={needle!r} out={out!r})")


HOOK_SRC = 'import json\nprint(json.dumps({"systemMessage": "warn"}))\n'

ARGV_AWARE_TEST = '''import os, stat, tempfile
SHIM = """#!/usr/bin/env python3
import sys
args = sys.argv[1:]
if "view" in args:
    print("parent-branch")
"""
with tempfile.TemporaryDirectory() as tmp:
    shim = os.path.join(tmp, "gh")
    open(shim, "w").write(SHIM)
    os.chmod(shim, os.stat(shim).st_mode | stat.S_IEXEC)
'''

ARGV_BLIND_TEST = '''import os, stat, tempfile
SHIM = """#!/usr/bin/env python3
print("parent-branch")
"""
with tempfile.TemporaryDirectory() as tmp:
    shim = os.path.join(tmp, "gh")
    open(shim, "w").write(SHIM)
    os.chmod(shim, os.stat(shim).st_mode | stat.S_IEXEC)
'''

# --- 1. A stub that reads argv is not flagged ---
case(
    "argv-aware stub is not flagged",
    {"warn.py": HOOK_SRC, "test-warn.py": ARGV_AWARE_TEST},
    want_exit=0,
    absent="FINDING:",
)

# --- 2. A stub that ignores argv is flagged, advisory by default ---
case(
    "argv-blind stub is flagged and stays advisory",
    {"warn.py": HOOK_SRC, "test-warn.py": ARGV_BLIND_TEST},
    want_exit=0,
    needle="never reads its own argv",
)

# --- 3. --strict turns the same finding into a non-zero exit ---
case(
    "argv-blind stub exits 1 under --strict",
    {"warn.py": HOOK_SRC, "test-warn.py": ARGV_BLIND_TEST},
    want_exit=1,
    needle="never reads its own argv",
    strict=True,
)

case(
    "an argv-aware stub still exits 0 under --strict",
    {"warn.py": HOOK_SRC, "test-warn.py": ARGV_AWARE_TEST},
    want_exit=0,
    absent="FINDING:",
    strict=True,
)

# --- 4. A shell stub is judged on shell forms ---
SHELL_AWARE_TEST = '''import os, stat, tempfile
SHIM = """#!/bin/sh
exec /usr/bin/real "$@"
"""
with tempfile.TemporaryDirectory() as tmp:
    shim = os.path.join(tmp, "gh")
    open(shim, "w").write(SHIM)
    os.chmod(shim, 0o755)
'''

case(
    "shell stub reading \"$@\" is not flagged",
    {"warn.py": HOOK_SRC, "test-warn.py": SHELL_AWARE_TEST},
    want_exit=0,
    absent="FINDING:",
)

SHELL_BLIND_TEST = '''import os, stat, tempfile
SHIM = """#!/bin/sh
echo parent-branch
"""
with tempfile.TemporaryDirectory() as tmp:
    shim = os.path.join(tmp, "gh")
    open(shim, "w").write(SHIM)
    os.chmod(shim, 0o755)
'''

case(
    "shell stub echoing a fixture is flagged",
    {"warn.py": HOOK_SRC, "test-warn.py": SHELL_BLIND_TEST},
    want_exit=0,
    needle="never reads its own argv",
)

# --- 5. A stub split across an f-string is read whole ---
# The shebang lands in one literal and "$@" in the next, so a per-constant scan
# reads the second half as a separate program and reports a false finding.
FSTRING_TEST = '''import os, stat, tempfile
real = "/usr/bin/gh"
with tempfile.TemporaryDirectory() as tmp:
    shim = os.path.join(tmp, "gh")
    with open(shim, "w") as fh:
        fh.write(f'#!/bin/sh\\nexec {real} "$@"\\n')
    os.chmod(shim, 0o755)
'''

case(
    "stub built from an f-string is read as one program",
    {"warn.py": HOOK_SRC, "test-warn.py": FSTRING_TEST},
    want_exit=0,
    absent="FINDING:",
)

# --- 5b. An enclosing block that mentions sys.argv must not mask a blind stub ---
MASKING_TEST = '''import os, stat, subprocess, sys, tempfile
with tempfile.TemporaryDirectory() as tmp:
    shim = os.path.join(tmp, "gh")
    with open(shim, "w") as fh:
        fh.write("#!/bin/sh\\necho parent-branch\\n")
    os.chmod(shim, 0o755)
    subprocess.run([sys.executable, sys.argv[1]])
'''

case(
    "an enclosing block mentioning sys.argv does not mask a blind stub",
    {"warn.py": HOOK_SRC, "test-warn.py": MASKING_TEST},
    want_exit=0,
    needle="never reads its own argv",
)

# --- 6. A shebang in fixture content, with no stub installed, is not a finding ---
FIXTURE_ONLY_TEST = '''HUNK = """@@ -1,3 +1,3 @@
 #!/bin/bash
-old
+new
"""
assert "#!/bin/bash" in HUNK
'''

case(
    "a shebang in diff-hunk fixture content is not a stub",
    {"warn.py": HOOK_SRC, "test-warn.py": FIXTURE_ONLY_TEST},
    want_exit=0,
    needle="0 of which install an executable stub",
)

# --- 7. A shell-hook subject is examined rather than dropped ---
case(
    "a shell hook's suite is examined",
    {"warn.sh": "#!/bin/sh\nexit 0\n", "test-warn.py": ARGV_BLIND_TEST},
    want_exit=0,
    needle="Examined 1 hook test suite(s)",
)

# --- 8. A path named argv_log does not, by itself, count as reading argv ---
ARGV_LOG_NAME_ONLY_TEST = '''import os, stat, tempfile
with tempfile.TemporaryDirectory() as tmp:
    argv_log = os.path.join(tmp, "argv.log")
    shim = os.path.join(tmp, "gh")
    with open(shim, "w") as fh:
        fh.write("#!/usr/bin/env python3\\n" + f"open({argv_log!r}, 'a').write('called')\\n")
    os.chmod(shim, 0o755)
'''

case(
    "a variable named argv_log does not count as reading argv",
    {"warn.py": HOOK_SRC, "test-warn.py": ARGV_LOG_NAME_ONLY_TEST},
    want_exit=0,
    needle="never reads its own argv",
)

# --- 9. Unparseable test source, and a missing directory ---
case(
    "unparseable test source fails loudly",
    {"warn.py": HOOK_SRC, "test-warn.py": "import os\nos.chmod(\ndef broken(\n"},
    want_exit=1,
    needle="could not be parsed as Python",
)

with tempfile.TemporaryDirectory() as td:
    rc, out = run(Path(td) / "no-such-dir")
check(
    "a missing hooks directory exits 2",
    rc == 2 and "no hooks directory" in out,
    f"rc={rc} out={out!r}",
)

with tempfile.TemporaryDirectory() as td:
    empty = make_hooks_dir(td, {})
    rc, out = run(empty)
check(
    "an empty hooks directory exits 2",
    rc == 2 and "no hook test suites" in out,
    f"rc={rc} out={out!r}",
)

# --- 10. Live repository, and the negative control the report carries ---
proc = subprocess.run(
    [sys.executable, str(SCRIPT), "--strict"],
    capture_output=True,
    text=True,
    cwd=str(ROOT),
)
check(
    "the real repository has no argv-blind stub",
    proc.returncode == 0,
    f"\n{proc.stdout}{proc.stderr}",
)
check(
    "the report names how many suites install a stub",
    "of which install an executable stub" in proc.stdout,
    f"out={proc.stdout!r}",
)
# A zero finding count over zero stubs is indistinguishable from a detector
# that never ran, so the live sweep must actually have inspected some stubs.
stub_line = [ln for ln in proc.stdout.splitlines() if "install an executable stub" in ln]
saw_stubs = bool(stub_line) and " 0 of which install" not in stub_line[0]
check(
    "the live sweep inspected at least one stub",
    saw_stubs,
    f"line={stub_line!r}",
)

cp1252_env = os.environ.copy()
cp1252_env["PYTHONIOENCODING"] = "cp1252"
cp_proc = subprocess.run(
    [sys.executable, str(SCRIPT)],
    capture_output=True,
    env=cp1252_env,
    cwd=str(ROOT),
)
check(
    "the report encodes on a cp1252 stdout",
    cp_proc.returncode == 0 and b"Examined" in cp_proc.stdout,
    f"rc={cp_proc.returncode} out={cp_proc.stdout!r}",
)

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
