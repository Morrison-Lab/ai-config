#!/usr/bin/env python3
"""Tests for flag-chained-push.py.

Mirrors `test-flag-cd-into-main-checkout.py`'s shape: a lexical FIRES/QUIET
split for `evaluate()`, then an end-to-end delivery check that runs the hook
as a subprocess and reads the payload it actually prints -- `evaluate()`
returning the right text proves nothing about whether the warning reaches the
session (ai-config#3068 recorded exactly that gap for a sibling hook).

Run: python3 hooks/test-flag-chained-push.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
HOOK = HERE / "flag-chained-push.py"
spec = importlib.util.spec_from_file_location("guard", HOOK)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

FIRES = [
    ("chained after a commit with &&",
     'git add -A && git commit -m "x" && git push'),
    ("chained after a plain command with ;",
     "git status; git push"),
    ("chained after a command with ||",
     "git status || git push"),
    ("piped onward",
     "git push origin HEAD | tee push.log"),
    ("fd-duplication redirect (the digit-as-token shape)",
     "git push origin HEAD 2>&1"),
    ("fd-duplication redirect piped onward",
     "git push origin HEAD 2>&1 | tee push.log"),
    ("plain output redirect",
     "git push origin HEAD > push.log"),
    ("append redirect",
     "git push origin HEAD >> push.log"),
    ("bash &> shorthand",
     "git push origin HEAD &> push.log"),
    ("chained before, with -C",
     "cd /repo && git -C /repo push origin HEAD"),
    ("chained before, across a newline",
     "git fetch origin\ngit push"),
    ("chained after, with a preceding pipeline unrelated to the push",
     "echo hi | cat; git push"),
    # `\` + newline is a line CONTINUATION, not a separator -- built with
    # chr(92)/chr(10) rather than a literal escape, since this exact source
    # text passing through a shell heredoc once already collapsed the
    # intended backslash-newline into something else (see CLAUDE.md's
    # "Tool transport collapses doubled backslashes"). A prior version of
    # this hook read the continuation as a hard `;` split and matched
    # `GIT_PUSH_RE` against neither half -- silent on the exact incident
    # shape in the hook's own docstring (measured 2026-09-05 review).
    ("git push split across a continued line",
     'git add -A && git commit -m "x" && git ' + chr(92) + chr(10)
     + "  push origin HEAD"),
    # A heredoc's BODY is masked, but same-line text after the `<<TAG`
    # introducer is real command text, not body -- `&& git push` here chains
    # a genuine push on the very line that opens the heredoc. An earlier
    # version's single tag-to-terminator regex swallowed this same-line text
    # along with the real body (measured 2026-09-05 review).
    ("chained push on the same line as a heredoc introducer",
     "cat <<'EOF' && git push\nbody line\nEOF"),
    ("chained push on the same line as an indented (<<-) heredoc introducer",
     "cat <<-'EOF' && git push\n  body line\n  EOF"),
    # A QUOTED heredoc tag ('EOF') does not strip a trailing backslash inside
    # its own body -- that suppression only applies to command/parameter
    # EXPANSION, not to literal content. Joining continuations before
    # masking heredocs erased the newline right before this body's own
    # trailing backslash, so the terminator's `^EOF$` no longer matched at
    # any line start, the heredoc read as unterminated, and masking ran to
    # the end of the string -- swallowing the real `&& git push` after it
    # (measured 2026-09-05 review, second pass).
    ("chained push after a heredoc whose body ends in a real backslash",
     "cat <<'EOF'\nsome body line" + chr(92) + chr(10)
     + "EOF\n&& git push"),
    # A literal `<<` inside an ORDINARY quoted string (a commit message
    # quoting a retry count, a shift-left operator, a diff marker) is not a
    # heredoc. Detecting heredocs before applying any quote awareness read
    # it as a genuine, unterminated tag and masked everything after it to
    # the end of the string -- silently swallowing the real chained `git
    # push` that follows, on exactly the commit-then-push shape this hook
    # exists to catch (measured 2026-09-05 review, third pass).
    ("chained push after a commit message containing a literal << (double-quoted)",
     'git commit -m "see << 3 retries" -q\ngit push'),
    ("chained push after a commit message containing a literal << (single-quoted)",
     "echo 'retry << 3 times'\ngit push"),
    # A real heredoc following ordinary quoted text that itself contains
    # `<<` -- the fake match inside the quote must be skipped so the REAL
    # heredoc's body still gets masked, and the genuine push chained after
    # it (via the newline following the terminator) still fires.
    ("chained push after a real heredoc, with a quoted << earlier on the line",
     'echo "a << b" && cat <<EOF\nbody\nEOF\ngit push'),
    # A backslash-escaped quote OUTSIDE any real quoting is a literal
    # character, not an opener -- real shell syntax escapes the very next
    # character that way. Treating it as an opener read the rest of the
    # command as one giant unterminated quoted span and masked all of it
    # away, silently swallowing the real chained `git push` after it
    # (measured 2026-09-05 review, fourth pass).
    ("chained push after an escaped double-quote outside any real quoting",
     "echo " + chr(92) + '" && git push'),
    ("chained push after an escaped single-quote outside any real quoting",
     "echo " + chr(92) + "' && git push"),
]

QUIET = [
    ("bare git push", "git push origin HEAD"),
    ("bare git push with the safe force form, alone",
     "git push --force-with-lease --force-if-includes"),
    ("bare git -C push, alone", "git -C /repo push origin HEAD"),
    ("push mentioned inside a double-quoted string",
     'git commit -m "push it live"'),
    ("push mentioned inside a single-quoted string",
     "git commit -m 'remember to push later'"),
    ("git push inside a heredoc body",
     "cat <<'EOF'\ngit push origin main\nEOF"),
    ("no push at all", "git status --short && git log -1"),
    ("push followed by && but nothing before or after IT specifically",
     "git push && echo done"),
    ("git push inside a heredoc body, with unrelated text after the tag",
     "cat <<'EOF' && echo unrelated\ngit push origin main\nEOF"),
    ("git push inside an indented (<<-) heredoc body",
     "cat <<-'EOF'\n  git push origin main\n  EOF"),
    # Two heredocs introduced on ONE line deliver their bodies in order,
    # immediately after that line. Advancing past only the FIRST tag's
    # terminator before resuming the outer search left the second tag's
    # `<<TAG` token -- which sits BEFORE the resumed position, on the shared
    # intro line -- unfound, so its body was never masked and a `git push`
    # inside it matched (measured 2026-09-05 review, second pass).
    ("git push inside the SECOND of two heredocs sharing one intro line",
     "cat <<'A' <<'B'\nbodyA\nA\ngit push origin main\nB"),
    ("a literal << inside a quoted string, with no real heredoc or push",
     'git commit -m "see << 3 retries" -q'),
]


DELIVERY_CASES = 7


def run_hook(command: str, antigravity: bool = False):
    """Run the hook as the harness does and return (rc, stdout, stderr)."""
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    env = {k: v for k, v in os.environ.items() if k != "ANTIGRAVITY_AGENT"}
    if antigravity:
        env["ANTIGRAVITY_AGENT"] = "1"
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def check_delivery():
    """The warning must reach the session, not just exist in `evaluate()`.

    Returns `(failures, ran)`, with `ran` incremented BEFORE each check so
    the count is meaningful on both the passing and failing path -- `main`
    refuses a run whose count differs from `DELIVERY_CASES`, so a deleted
    check cannot silently shrink what the suite claims to cover.
    """
    failures = 0
    ran = 0

    rc, out, err = run_hook("git status && git push")
    ran += 1
    if rc != 0:
        print(f"::error::hook must never block; exited {rc}\n{err}", file=sys.stderr)
        return failures + 1, ran

    ran += 1
    try:
        payload = json.loads(out)
    except json.JSONDecodeError as exc:
        print(f"::error::hook emitted non-JSON on stdout ({exc}): {out!r}",
              file=sys.stderr)
        return failures + 1, ran

    hso = payload.get("hookSpecificOutput") or {}
    context = hso.get("additionalContext")
    ran += 1
    if not context:
        print("::error::warning carries no hookSpecificOutput.additionalContext",
              file=sys.stderr)
        failures += 1
    elif "git push" not in context:
        print(f"::error::additionalContext is not the warning text: {context!r}",
              file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: warning rides on additionalContext")

    ran += 1
    if hso.get("hookEventName") != "PreToolUse":
        print(f"::error::hookEventName must be PreToolUse, got "
              f"{hso.get('hookEventName')!r}", file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: hookEventName names PreToolUse")

    # This guard must never make the harness more permissive than it was
    # without it.
    ran += 1
    if "permissionDecision" in hso:
        print(f"::error::guard emitted permissionDecision="
              f"{hso['permissionDecision']!r}; it must only ever add context",
              file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: no permissionDecision")

    # A quiet command must print nothing at all.
    rc, out, err = run_hook("git push origin HEAD")
    ran += 1
    if rc != 0 or out.strip():
        print(f"::error::quiet case must print nothing; rc={rc} stdout={out!r}",
              file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: quiet case prints nothing")

    # Antigravity's adapter prints `additionalContext` and every collected
    # `systemMessage` separately, so a payload carrying both would warn
    # twice there.
    rc, out, err = run_hook("git status && git push", antigravity=True)
    ran += 1
    try:
        ag = json.loads(out) if rc == 0 else {}
    except json.JSONDecodeError:
        ag = {}
    ag_context = (ag.get("hookSpecificOutput") or {}).get("additionalContext")
    if not ag_context:
        print(f"::error::ANTIGRAVITY_AGENT output must carry additionalContext; "
              f"rc={rc} stdout={out!r}", file=sys.stderr)
        failures += 1
    elif "systemMessage" in ag:
        print("::error::ANTIGRAVITY_AGENT output must not carry systemMessage",
              file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: under ANTIGRAVITY_AGENT, context only")

    return failures, ran


def main() -> int:
    failures = 0

    for label, command in FIRES:
        if guard.evaluate(command) is None:
            print(f"::error::expected a warning: {label}\n    {command!r}",
                  file=sys.stderr)
            failures += 1
        else:
            print(f"OK   fires: {label}")

    for label, command in QUIET:
        result = guard.evaluate(command)
        if result is not None:
            print(f"::error::expected silence: {label}\n    {command!r}\n{result}",
                  file=sys.stderr)
            failures += 1
        else:
            print(f"OK   quiet: {label}")

    # The message must name the alternative, or it teaches nothing.
    message = guard.evaluate("git status && git push")
    for needed in ("no-clobbering-push.py", "own Bash call",
                   "check-before-pushing.md"):
        if needed not in message:
            print(f"::error::warning text omits {needed!r}", file=sys.stderr)
            failures += 1

    delivery_failures, delivery_ran = check_delivery()
    failures += delivery_failures
    if delivery_ran != DELIVERY_CASES:
        print(f"::error::check_delivery ran {delivery_ran} case(s), but "
              f"DELIVERY_CASES says {DELIVERY_CASES}", file=sys.stderr)
        failures += 1

    total = len(FIRES) + len(QUIET) + DELIVERY_CASES
    if failures:
        print(f"::error::{failures} of {total} case(s) failed", file=sys.stderr)
        return 1
    print(f"All {total} flag-chained-push cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
