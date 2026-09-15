#!/usr/bin/env python3
"""Tests for hooks/warn-python3-cannot-read-hooks.sh (ai-config#3624).

The hook exists because a `python3` that cannot read the plugin root takes
every Python hook down at once, and each resulting denial names a hook rather
than the interpreter. Its whole job is to say which half is broken.

Five cases, every one against a `python3` stub rather than the ambient host,
so the suite passes and fails for the same reasons on Windows, on macOS, and
on Ubuntu CI -- none of which reproduces the Store-alias condition:

  1. Healthy: the stub answers "the file exists" -- the hook prints NOTHING.
     This is the negative control, and it is the one that matters most: a
     hook that warned unconditionally would be indistinguishable from a
     correct one in every other case here, while costing context on every
     prompt forever.
  2. Blind: the stub answers "the file does not exist" -- the hook names the
     resolved interpreter, the path it could not read, and the remedy.
  3. Absent: no `python3` on PATH at all -- a different failure with a
     different remedy, so it gets its own message.
  4. Broken: the stub exits 2 -- neither "fine" nor "blind", so the hook
     reports the status rather than asserting a cause it did not observe.
  5. Path fidelity: the hook must hand `python3` the path the harness gave
     it, byte for byte. The risk a rewritten path carries is MASKING, not a
     false alarm -- resolving a symlink can land the probe in a directory the
     interpreter can read while the registered path stays invisible, which
     reports an all-clear over a total outage. The case invokes the hook
     through a path carrying a `..` segment and requires that segment to
     survive.

Every case also requires exit 0. This is a `UserPromptSubmit` hook whose
diagnosis reaches the session through plain stdout; exiting non-zero would
make the one hook that reports the outage part of it.
"""
import os
import re
import stat
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "warn-python3-cannot-read-hooks.sh")

wrong = 0
ran = 0


def check(desc, cond):
    global wrong, ran
    ran += 1
    wrong += not cond
    print(f"  {'ok' if cond else 'WRONG':<6} {desc}")


def stub_dir(exit_code):
    """A temp dir holding a `python3` stub for PATH.

    The stub answers only for the hook's actual invocation shape -- `-c`, a
    program mentioning `os.path.exists`, then a path -- and exits `exit_code`.
    Keying on the shape is what makes the cases pin the hook's behaviour: a
    stub that answered regardless would pass case 1 identically if the hook
    dropped the path argument entirely.

    It records the path argument at `$PY_ARG_FILE`, so case 5 can compare it
    whole against the path the hook was invoked with. The destination comes
    from the environment rather than from the stub's own `$0`, because under
    Git Bash that `$0` is an MSYS path (`/tmp/...`) whose Windows mapping the
    test cannot read back.
    """
    d = tempfile.mkdtemp()
    p = os.path.join(d, "python3")
    with open(p, "w") as fh:
        fh.write(
            "#!/bin/sh\n"
            '[ "$1" = -c ] || exit 90\n'
            'case "$2" in *os.path.exists*) ;; *) exit 91 ;; esac\n'
            '[ -n "${3:-}" ] || exit 92\n'
            'printf \'%s\' "$3" > "$PY_ARG_FILE"\n'
            f"exit {exit_code}\n")
    os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR)
    return d


def run(path_dirs, hook=HOOK, py_arg_file=None):
    # Forward slashes: the stub is run by the shell, which under Git Bash does
    # not read a backslash-separated Windows path as a redirect target.
    dest = py_arg_file or os.path.join(tempfile.mkdtemp(), "py-arg")
    env = dict(os.environ, PATH=os.pathsep.join(path_dirs),
               PY_ARG_FILE=dest.replace(os.sep, "/"))
    p = subprocess.run(["sh", hook], capture_output=True, text=True, env=env)
    return p.returncode, p.stdout


# A PATH with no `python3` on it, for case 3. Built from a temp dir rather
# than the empty string: an empty PATH makes some shells fall back to a
# built-in default path, which could put a real python3 back in scope.
EMPTY = tempfile.mkdtemp()

print("case 1 -- healthy interpreter (negative control):")
d = stub_dir(0)
rc, out = run([d])
check("exit 0", rc == 0)
check("prints nothing at all", out == "")

print("\ncase 2 -- interpreter cannot read the hook directory:")
d = stub_dir(1)
rc, out = run([d])
check("exit 0 (warn-only; never blocks the prompt)", rc == 0)
check("says the Python hooks are inert", "inert this session" in out)
# `command -v` answers in the shell's own path dialect -- under Git Bash an
# MSYS path, not the Windows one the test built -- so this pins the shape the
# hook controls (a non-empty path naming python3) rather than the spelling the
# shell chose. An empty or missing value still fails.
check("names the resolved interpreter",
      bool(re.search(r"python3 resolves to: +\S*python3\b", out)))
check("names the path it could not read", HOOK in out)
check("says the file exists and the interpreter is the blind half",
      "the interpreter is the half that cannot see it" in out)
check("names the Store App Execution Alias as the cause",
      "App Execution Alias" in out)
check("gives the alias remedy", "App execution aliases" in out)
check("gives the PATH remedy", "ahead of WindowsApps on PATH" in out)
check("tells the reader not to blame the plugin cache",
      "not\nas a corrupt plugin cache" in out)
check("does not claim the probe merely failed to run",
      "could not run a one-line probe" not in out)
# Pinned because the backslash reaches the reader through a printf FORMAT
# string, where an undefined escape is implementation-defined: `\C` happens to
# pass through on dash and bash, and is not guaranteed to anywhere else.
check("renders the Windows path literally, backslash intact",
      r"%APPDATA%\Claude" in out)

print("\ncase 3 -- no python3 on PATH:")
rc, out = run([EMPTY])
check("exit 0", rc == 0)
check("says the Python hooks are inert", "inert this session" in out)
check("names the actual condition", "`python3` is not on PATH" in out)
check("gives the install remedy, not the alias remedy",
      "expose it under the name `python3`" in out
      and "App Execution Alias" not in out)

print("\ncase 4 -- probe neither succeeds nor cleanly reports absence:")
d = stub_dir(2)
rc, out = run([d])
check("exit 0", rc == 0)
check("reports the probe failure rather than asserting a cause",
      "could not run a one-line probe" in out)
check("prints the observed exit status", "probe exit status:   2" in out)
check("does not assert the Store-alias cause it did not observe",
      "App Execution Alias" not in out)

print("\ncase 5 -- the probed path is the harness's own spelling, unnormalised:")
d = stub_dir(1)
arg_file = os.path.join(tempfile.mkdtemp(), "py-arg")
hook_dir = os.path.dirname(os.path.realpath(HOOK))
# A `..` round trip: same file, different spelling. A hook that resolved the
# path before probing would hand the stub the collapsed form instead.
indirect = os.path.join(hook_dir, os.pardir, os.path.basename(hook_dir),
                        os.path.basename(HOOK))
rc, out = run([d], hook=indirect, py_arg_file=arg_file)
check("exit 0", rc == 0)
with open(arg_file) as fh:
    probed = fh.read()
check("hands python3 the path it was invoked with, byte for byte",
      probed == indirect)
check("does not collapse the `..` segment before probing",
      os.pardir in probed)

# Derived, not hard-coded: a later assertion added below would otherwise
# still print 23/23 while 24 ran, which is a passing-looking undercount.
total = ran
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
