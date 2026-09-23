#!/usr/bin/env python3
"""Tests for no-binary-file-read.py.

The QUIET cases carry most of the design weight, same reasoning as
`test-flag-cd-into-main-checkout.py`: this guard's whole risk is noise from a
whole-file reader that is legitimately reading a small text file, and a
version that flagged those gets switched off within a day, taking the one
real case with it. `strings` staying silent, `head -c N` staying silent, and
a missing/directory/unmatched-glob path staying silent are the cases that
matter most.

The end-to-end `check_delivery()` cases run the hook as a real subprocess and
read the payload it prints, the same distinction
`test-flag-cd-into-main-checkout.py` draws: `evaluate()` returning the right
text proves nothing about whether the warning actually reaches the session
(`hookSpecificOutput.additionalContext` on exit 0 is the only channel that
does).

`mutate()` is a self-contained mutation harness, the same shape as
`test-flag-indirect-gnu-grep-flag.py`'s: it string-replaces one anchor in the
subject's own source, loads the mutant from a uniquely-named temp file, and
asserts that a NAMED case flips. `sys.dont_write_bytecode` is forced True for
every mutant load and the ORIGINAL load alike, so a stale `.pyc` under
`hooks/__pycache__` can never be read back in place of a just-restored
original -- CLAUDE.md's own note ("Python bytecode is cached... a stale .pyc
has already produced a false 'restored code still fails' reading in this
project today") is what this guards against.

Run: python3 hooks/test-no-binary-file-read.py hooks/no-binary-file-read.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

HOOK = os.path.realpath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-binary-file-read.py")


def _load(path, modname):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


guard = _load(HOOK, "guard_no_binary_file_read")


# ---------------------------------------------------------------------------
# Fixtures: real files on disk, since this guard's whole job is inspecting
# actual file content and existence -- a fixture-free suite could not
# exercise the NUL sniff, the directory case, or the missing-path case.

def setup_fixtures():
    d = tempfile.mkdtemp(prefix="no-binary-file-read-test-")
    with open(os.path.join(d, "binary.bin"), "wb") as fh:
        fh.write(b"\x00\x01\x02BINARY-PAYLOAD" * 20)
    with open(os.path.join(d, "text.txt"), "w", encoding="utf-8") as fh:
        fh.write("hello world\n" * 50)
    # No NUL byte at all -- caught only via the extension-shortcut path.
    with open(os.path.join(d, "fake.exe"), "w", encoding="utf-8") as fh:
        fh.write("not actually binary, but named like it\n")
    # The NUL sits past SNIFF_BYTES (8192), so the sniff must NOT see it.
    # `.dat`, deliberately NOT in BINARY_EXTENSIONS -- this fixture exists to
    # test the NUL-sniff boundary in isolation, and a `.bin` name would let
    # the extension shortcut pass it regardless of content.
    with open(os.path.join(d, "nul-beyond-sniff.dat"), "wb") as fh:
        fh.write(b"A" * 9000 + b"\x00" + b"B" * 100)
    # Same reasoning: `.dat`, not `.bin`.
    with open(os.path.join(d, "empty.dat"), "wb"):
        pass
    os.mkdir(os.path.join(d, "adir"))
    # A pre-existing BINARY file used only as a REDIRECTION TARGET -- the
    # `cat note.txt > redirect-target.bin` case must not fire on it, since
    # it is being written, not read.
    with open(os.path.join(d, "redirect-target.bin"), "wb") as fh:
        fh.write(b"\x00old binary content that must not be reported as read")
    # A binary file reachable only via a glob pattern, to prove a MATCHED
    # glob is expanded rather than silently missed like an unmatched one.
    os.mkdir(os.path.join(d, "globdir"))
    with open(os.path.join(d, "globdir", "only.weirdext"), "wb") as fh:
        fh.write(b"\x00glob-matched binary payload")
    return d


CWD = setup_fixtures()
# Posix-style, matching how an absolute path actually appears inside a
# BASH command on this platform (Git Bash / MSYS): a native
# `C:\Users\...\binary.bin` form is not what a real command line contains,
# and feeding it through `shlex` in posix mode (which treats `\` as an
# escape character) would mangle it -- that is a property of testing with an
# unrealistic input, not a bug in the guard.
BIN_ABS = os.path.join(CWD, "binary.bin").replace("\\", "/")

# MSYS (`/c/Users/...`) and WSL-mount (`/mnt/c/Users/...`) spellings of the
# same fixture, built from CWD's own drive letter rather than a fixed "C" so
# the suite works whatever drive the temp directory actually lands on.
# Windows-only: on any other OS a leading slash is already the native form,
# so `/c/...` is simply not this fixture's own binary.bin there, and
# exercising the translation would test nothing.
if os.name == "nt":
    _drive = CWD[0].lower()
    _rest = CWD[2:].replace("\\", "/")
    MSYS_BIN_ABS = f"/{_drive}{_rest}/binary.bin"
    WSL_BIN_ABS = f"/mnt/{_drive}{_rest}/binary.bin"
else:
    MSYS_BIN_ABS = WSL_BIN_ABS = None

# (id, command) -- must warn.
FIRES = [
    ("F1-cat-binary", "cat binary.bin"),
    ("F2-head-binary", "head binary.bin"),
    ("F3-tail-n-does-not-exempt", "tail -n 5 binary.bin"),
    ("F4-less-binary", "less binary.bin"),
    ("F5-more-binary", "more binary.bin"),
    ("F6-compound-command", "echo hi && cat binary.bin"),
    ("F7-absolute-path", f"cat {BIN_ABS}"),
    ("F8-quoted-path", 'cat "binary.bin"'),
    ("F9-extension-shortcut-no-nul", "cat fake.exe"),
    ("F10-mixed-text-and-binary-args", "cat text.txt binary.bin"),
    # `cat` has no byte-limit option at all -- `-c` is just an ordinary
    # (unsupported) flag to it, so the head/tail-only exemption must not
    # apply here.
    ("F11-cat-dash-c-is-not-an-exemption", "cat -c binary.bin"),
    # Output redirection must not blind the guard to the actual INPUT.
    ("F12-binary-input-with-redirected-output", "cat binary.bin > /dev/null"),
    # A binary file reachable only by expanding the glob -- see the
    # `globdir` fixture. Proves a MATCHED glob is expanded, not silently
    # missed like an unmatched one.
    ("F13-matched-glob", "cat globdir/*.weirdext"),
]

if os.name == "nt":
    FIRES.append(("F14-msys-style-absolute-path", f"cat {MSYS_BIN_ABS}"))
    FIRES.append(("F15-wsl-mount-style-absolute-path", f"cat {WSL_BIN_ABS}"))

# (id, command) -- must stay silent. This list is where the guard earns its
# keep: every one of these is an ordinary, legitimate command.
QUIET = [
    ("Q1-cat-text-file", "cat text.txt"),
    ("Q2-strings-is-not-flagged", "strings binary.bin"),
    ("Q3-head-c-space-form", "head -c 100 binary.bin"),
    ("Q4-head-c-attached-form", "head -c100 binary.bin"),
    ("Q5-head-bytes-equals-form", "head --bytes=100 binary.bin"),
    ("Q6-head-bytes-space-form", "head --bytes 100 binary.bin"),
    ("Q7-tail-c-space-form", "tail -c 50 binary.bin"),
    ("Q8-missing-file", "cat missing-nonexistent.bin"),
    ("Q9-directory", "cat adir"),
    ("Q10-unmatched-glob", "cat *.nomatchxyz"),
    ("Q11-empty-file", "cat empty.dat"),
    ("Q12-nul-past-sniff-window", "cat nul-beyond-sniff.dat"),
    ("Q13-head-n-on-a-text-file", "head -n 5 text.txt"),
    ("Q14-no-path-argument", "cat"),
    ("Q15-unrelated-command", "git status --short"),
    ("Q16-unparseable-command", "cat 'unterminated"),
    # The redirection TARGET is a pre-existing binary file; the command
    # reads a text file and only WRITES the binary one, so this must stay
    # silent -- the exact false positive the adversarial review found.
    ("Q17-redirect-target-not-read", "cat text.txt > redirect-target.bin"),
    ("Q18-redirect-target-append-not-read", "cat text.txt >> redirect-target.bin"),
    # `2>` (no space) is indistinguishable, after tokenizing, from the
    # argument "2" followed by a `>` redirect -- seeing "2" as a path
    # candidate would misreport a stderr redirect as an offending read.
    ("Q19-stderr-redirect-fd-not-a-path", "cat text.txt 2> redirect-target.bin"),
    # `>|` (the noclobber-override redirect) tokenizes as its own punctuation
    # token, distinct from `>` -- a second adversarial-review round found it
    # missing from REDIR_OPS, reopening the exact false positive Q17 exists
    # to close.
    ("Q21-noclobber-override-redirect-not-a-path", "cat text.txt >| redirect-target.bin"),
    # Full end-to-end exercise of the device-path guard THROUGH evaluate(),
    # not just a direct is_binary_file() call -- proves the resolution
    # pipeline (absolute-path detection, then the device check) actually
    # reaches it, rather than merely proving the device check is correct in
    # isolation.
    ("Q20-dev-null-via-evaluate", "cat /dev/null"),
]


def run_hook(command, cwd, tool_name="Bash", antigravity=False):
    """Run the hook as the harness does; return (rc, stdout, stderr)."""
    payload = {"tool_name": tool_name, "tool_input": {"command": command},
               "cwd": cwd}
    env = {k: v for k, v in os.environ.items() if k != "ANTIGRAVITY_AGENT"}
    if antigravity:
        env["ANTIGRAVITY_AGENT"] = "1"
    proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_raw_payload(payload):
    """Run the hook against an arbitrary JSON-able payload; return
    (rc, stdout, stderr). For payload shapes `run_hook` cannot construct,
    such as a non-dict `tool_input`."""
    proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


DELIVERY_CASES = 11


def check_delivery():
    """The warning must reach the session, and its remedies must be real.

    Same rationale as `test-flag-cd-into-main-checkout.py`'s
    `check_delivery`: `evaluate()` returning text proves nothing about
    delivery, since a `PreToolUse` hook exiting 0 surfaces ONLY
    `hookSpecificOutput.additionalContext` (and, outside Antigravity, a
    paired `systemMessage`) -- plain stdout and stderr on exit 0 reach
    neither the model nor the user.

    Returns `(failures, ran)`, counted the same defensive way: `ran`
    increments BEFORE each check so `main()` can refuse a run whose count
    does not match `DELIVERY_CASES`.
    """
    failures = 0
    ran = 0

    rc, out, err = run_hook("cat binary.bin", CWD)
    ran += 1
    if rc != 0:
        print(f"::error::hook must never block; exited {rc}\n{err}", file=sys.stderr)
        return failures + 1, ran

    ran += 1
    try:
        payload = json.loads(out)
    except json.JSONDecodeError as exc:
        print(f"::error::hook emitted non-JSON on stdout ({exc}): {out!r}", file=sys.stderr)
        return failures + 1, ran

    hso = payload.get("hookSpecificOutput") or {}
    context = hso.get("additionalContext") or ""

    ran += 1
    if "binary.bin" not in context:
        print(f"::error::additionalContext omits the offending path: {context!r}", file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: additionalContext names the offending path")

    ran += 1
    missing = [needed for needed in ("file ", "xxd", "strings ")
               if needed not in context]
    if missing:
        print(f"::error::additionalContext omits remedy text {missing}: {context!r}", file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: additionalContext names real remedies (file/xxd/strings)")

    ran += 1
    if hso.get("hookEventName") != "PreToolUse":
        print(f"::error::hookEventName must be PreToolUse, got {hso.get('hookEventName')!r}", file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: hookEventName names PreToolUse")

    ran += 1
    if "permissionDecision" in hso:
        print(f"::error::guard emitted permissionDecision={hso['permissionDecision']!r}; "
              "it must only ever warn, never block", file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: no permissionDecision (warn-only)")

    ran += 1
    if not payload.get("systemMessage"):
        print("::error::warning carries no one-line systemMessage", file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: one-line systemMessage present")

    # A quiet command must print nothing at all.
    rc, out, err = run_hook("cat text.txt", CWD)
    ran += 1
    if rc != 0 or out.strip():
        print(f"::error::quiet case must print nothing; rc={rc} stdout={out!r}", file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: quiet case prints nothing")

    # A non-Bash tool call must be ignored outright.
    rc, out, err = run_hook("cat binary.bin", CWD, tool_name="Read")
    ran += 1
    if rc != 0 or out.strip():
        print(f"::error::non-Bash tool call must be ignored; rc={rc} stdout={out!r}", file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: non-Bash tool call ignored")

    # Antigravity's adapter prints additionalContext and every collected
    # systemMessage separately, so carrying both would warn twice there.
    rc, out, err = run_hook("cat binary.bin", CWD, antigravity=True)
    ran += 1
    try:
        ag = json.loads(out) if rc == 0 else {}
    except json.JSONDecodeError:
        ag = {}
    ag_context = (ag.get("hookSpecificOutput") or {}).get("additionalContext")
    if not ag_context:
        print(f"::error::ANTIGRAVITY_AGENT output must carry additionalContext; rc={rc} stdout={out!r}",
              file=sys.stderr)
        failures += 1
    elif "systemMessage" in ag:
        print("::error::ANTIGRAVITY_AGENT output must not also carry systemMessage "
              "(the adapter prints both channels, so it would warn twice)", file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: under ANTIGRAVITY_AGENT, context only")

    # ai-config#3772: a truthy non-dict tool_input (found by this hook's own
    # third adversarial-review round) must not crash the hook.
    rc, out, err = run_raw_payload(
        {"tool_name": "Bash", "tool_input": "not-a-dict", "cwd": CWD})
    ran += 1
    if rc != 0:
        print(f"::error::a non-dict tool_input must not crash; rc={rc} stderr={err!r}",
              file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: a non-dict tool_input degrades silently, not a crash")

    return failures, ran


def unit_checks():
    """Direct checks of a few helpers whose behaviour is easy to get subtly
    wrong and hard to observe purely through `evaluate()` -- the device-path
    guard in particular, since `/dev/null` and `/proc/self/mem` are already
    non-files on a Windows test runner, which would make an `evaluate()`-only
    check pass for the wrong reason (non-existence rather than the device
    check).

    Returns `(failures, ran)`, same convention as `check_delivery` -- `ran`
    counts every `check(...)` call so `main()` can refuse a run whose count
    does not match `UNIT_CASES`.
    """
    failures = []
    ran = 0

    def check(label, got, want):
        nonlocal ran
        ran += 1
        ok = got == want
        print(f"{'OK  ' if ok else '::error::'} unit: {label} -> {got!r} (want {want!r})")
        if not ok:
            failures.append(label)

    check("device path /dev/null is never treated as binary",
          guard.is_binary_file("/dev/null"), False)
    check("device path /proc/self/mem is never treated as binary",
          guard.is_binary_file("/proc/self/mem"), False)
    check("_command_name strips a leading sudo",
          guard._command_name(["sudo", "cat", "x"]), ("cat", ["x"]))
    check("_command_name strips a leading VAR=value assignment",
          guard._command_name(["FOO=bar", "cat", "x"]), ("cat", ["x"]))
    check("has_bounded_read is head/tail-only",
          guard.has_bounded_read("cat", ["-c", "5"]), False)
    check("has_bounded_read: -n (a line count) does not exempt",
          guard.has_bounded_read("head", ["-n", "5", "f"]), False)
    check("has_bounded_read: -c with an attached value",
          guard.has_bounded_read("head", ["-c10", "f"]), True)
    check("has_bounded_read: --bytes= form",
          guard.has_bounded_read("tail", ["--bytes=10", "f"]), True)
    check("has_bounded_read stops at a literal --",
          guard.has_bounded_read("head", ["--", "-c"]), False)
    check("_posix_absolute treats a leading slash as absolute on any OS",
          guard._posix_absolute("/c/Users/x"), True)
    check("_posix_absolute treats a relative path as not absolute",
          guard._posix_absolute("relative/x"), False)
    check("_strip_redirections drops an operator and its target",
          guard._strip_redirections(["a.txt", ">", "out.bin"]), ["a.txt"])
    check("_strip_redirections drops a bare fd digit before the operator",
          guard._strip_redirections(["a.txt", "2", ">", "err.log"]), ["a.txt"])
    if os.name == "nt":
        check("_to_native translates an MSYS /c/... path on Windows",
              guard._to_native("/c/Users/x"), "C:/Users/x")
        check("_to_native translates a WSL /mnt/c/... path on Windows",
              guard._to_native("/mnt/c/Users/x"), "C:/Users/x")
        check("_to_native leaves a non-drive absolute path alone",
              guard._to_native("/dev/null"), "/dev/null")
    else:
        check("_to_native is a no-op off Windows",
              guard._to_native("/c/Users/x"), "/c/Users/x")

    return failures, ran


UNIT_CASES = 16 if os.name == "nt" else 14


# ---------------------------------------------------------------------------
# Mutation harness. Each entry reverts ONE clause in the subject's own
# source; `expect_flip` names the FIRES/QUIET case id(s) whose verdict must
# change. An empty `expect_flip` would be an admission that the mutated
# clause is untested, not a pass.
MUTATIONS = [
    ("M1-drop-nul-sniff",
     # Stop reading the file's content at all -- any regular, non-device
     # file is now "binary" regardless of what is in it. The Q1 text-file
     # case is the direct probe: it must start firing.
     ('        with open(path, "rb") as fh:\n'
      '            chunk = fh.read(SNIFF_BYTES)\n'
      '        return b"\\x00" in chunk',
      '        with open(path, "rb") as fh:\n'
      '            chunk = fh.read(SNIFF_BYTES)\n'
      '        return True'),
     {"Q1-cat-text-file", "Q13-head-n-on-a-text-file",
      "Q11-empty-file", "Q12-nul-past-sniff-window",
      # These three also read a real (now falsely "binary") text file --
      # Q17/Q18 read text.txt, Q19 reads text.txt too -- so the NUL-sniff
      # mutation flips them as a side effect, not because redirection
      # stripping is what is broken here.
      "Q17-redirect-target-not-read", "Q18-redirect-target-append-not-read",
      "Q19-stderr-redirect-fd-not-a-path",
      "Q21-noclobber-override-redirect-not-a-path"}),

    ("M2-drop-byte-limit-exemption",
     # `has_bounded_read` now always reports "not bounded", so a `-c`
     # byte-limited head/tail is treated exactly like an unbounded read.
     ('    if cmd_name not in ("head", "tail"):\n'
      '        return False\n'
      '    for a in _strip_redirections(args):',
      '    if cmd_name not in ("head", "tail"):\n'
      '        return False\n'
      '    return False\n'
      '    for a in _strip_redirections(args):'),
     {"Q3-head-c-space-form", "Q4-head-c-attached-form",
      "Q5-head-bytes-equals-form", "Q6-head-bytes-space-form",
      "Q7-tail-c-space-form"}),

    ("M3-drop-redirection-target-stripping",
     # `extract_paths` stops removing a redirection target, so the file a
     # command WRITES to is read back as if it were a candidate for reading.
     # The direct probe is Q17: `cat text.txt > redirect-target.bin` must
     # start firing on the (pre-existing, binary) redirection target.
     ('    for a in _strip_redirections(args):\n'
      '        if skip_next:',
      '    for a in args:\n'
      '        if skip_next:'),
     {"Q17-redirect-target-not-read", "Q18-redirect-target-append-not-read",
      "Q19-stderr-redirect-fd-not-a-path",
      "Q21-noclobber-override-redirect-not-a-path"}),

    ("M4-drop-noclobber-override-operator",
     # Remove `>|` from REDIR_OPS: the noclobber-override redirect is no
     # longer recognized, so its target is read back as a candidate path
     # again -- the second-review regression, direct-probed by Q21.
     ('"<&", "<<<", ">|"}', '"<&", "<<<"}'),
     {"Q21-noclobber-override-redirect-not-a-path"}),
]


def _verdict(mod, command):
    return mod.evaluate(command, CWD) is not None


def baseline_verdicts():
    return {cid: _verdict(guard, cmd) for cid, cmd in FIRES + QUIET}


def mutate():
    src = open(HOOK, encoding="utf-8").read()
    base = baseline_verdicts()
    failures = []
    for mid, (old, new), expect_flip in MUTATIONS:
        if old not in src:
            print(f"  FAIL {mid:32} anchor not found; mutation not applied", file=sys.stderr)
            failures.append(mid)
            continue
        fd, path = tempfile.mkstemp(suffix=f"-{mid}.py")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(src.replace(old, new, 1))
            mutant = _load(path, f"mutant_{mid.replace('-', '_')}")
            got = {cid: _verdict(mutant, cmd) for cid, cmd in FIRES + QUIET}
        except Exception as exc:
            print(f"  PASS {mid:32} mutant crashed to load/run ({exc!r:.60})")
            os.unlink(path)
            continue
        os.unlink(path)
        flipped = {cid for cid in base if got[cid] != base[cid]}
        ok = flipped >= expect_flip
        status = "PASS" if ok else "FAIL"
        print(f"  {status} {mid:32} expected_flip={sorted(expect_flip)} actual_flip={sorted(flipped)}")
        if not ok:
            failures.append(mid)
        else:
            named = ", ".join(sorted(expect_flip))
            print(f"       caught by: {named}")
    return failures


def main() -> int:
    failures = 0

    try:
        for cid, command in FIRES:
            if guard.evaluate(command, CWD) is None:
                print(f"::error::expected a warning: {cid}\n    {command}", file=sys.stderr)
                failures += 1
            else:
                print(f"OK   fires: {cid}")

        for cid, command in QUIET:
            result = guard.evaluate(command, CWD)
            if result is not None:
                print(f"::error::expected silence: {cid}\n    {command}\n{result}", file=sys.stderr)
                failures += 1
            else:
                print(f"OK   quiet: {cid}")

        unit_failures, unit_ran = unit_checks()
        failures += len(unit_failures)
        if unit_ran != UNIT_CASES:
            print(f"::error::unit_checks ran {unit_ran} case(s), but "
                  f"UNIT_CASES says {UNIT_CASES}; the total would "
                  "overstate what the suite exercised", file=sys.stderr)
            failures += 1

        delivery_failures, delivery_ran = check_delivery()
        failures += delivery_failures
        if delivery_ran != DELIVERY_CASES:
            print(f"::error::check_delivery ran {delivery_ran} case(s), but "
                  f"DELIVERY_CASES says {DELIVERY_CASES}; the total would "
                  "overstate what the suite exercised", file=sys.stderr)
            failures += 1

        print("\nMutation checks:")
        mutation_failures = mutate()
        failures += len(mutation_failures)
    finally:
        shutil.rmtree(CWD, ignore_errors=True)

    total = len(FIRES) + len(QUIET) + UNIT_CASES + DELIVERY_CASES + len(MUTATIONS)
    if failures:
        print(f"::error::{failures} of {total} check(s) failed", file=sys.stderr)
        return 1
    print(f"All {total} no-binary-file-read checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
