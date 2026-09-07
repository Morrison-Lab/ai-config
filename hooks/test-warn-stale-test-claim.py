"""Test the warn-stale-test-claim guard.

The reported incident (ai-config, session 2026-09-06/07): a source file was
edited, an ad-hoc inline probe was run and passed, and the reply reported
"All 25 probe cases pass" while the project's own test suite had not been
run since the edit. Running it afterward found 2 of 297 failures.

The value here is concentrated in the ORDERING cases -- edit-then-claim
without an intervening real suite run warns; suite-after-edit-then-claim does
not -- and in the self-reference case, since this docstring and the hook's
own docstring both quote the exact phrases the matcher looks for.

Run: python3 hooks/test-warn-stale-test-claim.py hooks/warn-stale-test-claim.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def edit(path="hooks/no-push-without-self-review.py"):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Edit", "input": {
            "file_path": path, "old_string": "a", "new_string": "b"}}]}}


def bash(command):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": command}}]}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


PROBE = bash(
    "python3 - <<'PY'\n"
    "from hook import predicate\n"
    "print(predicate('x'))\n"
    "PY"
)

# (events, should_warn, label)
CASES = [
    # The reported incident, verbatim in shape: edit, ad-hoc probe (not a
    # recognized suite), claim of passing.
    ([edit(), PROBE, say(
        "All 25 probe cases pass, including every one of the five forgeries."
    )], True, "edit + ad-hoc probe + passing claim warns (the reported case)"),

    # Edit, no test run at all, claim of passing -- "never run" branch.
    ([edit(), say("Tests pass.")], True,
     "edit with no suite invocation anywhere, then a passing claim, warns"),

    # Edit, then the REAL suite runs, then the claim -- must not warn.
    ([edit(), bash("pytest hooks/test-warn-stale-test-claim.py"),
      say("All 25 test cases pass.")], False,
     "edit followed by an actual pytest run before the claim does not warn"),

    # The real suite ran BEFORE the edit -- stale, must warn.
    ([bash("pytest -q"), edit(), say("25 passed.")], True,
     "a suite run before the edit (not after) still warns"),

    # No edit at all -- nothing is stale regardless of the claim.
    ([bash("pytest -q"), say("All tests pass.")], False,
     "a passing claim with no source edit in the transcript does not warn"),

    # An edit to a non-source file (docs) should not count as a stale-code
    # edit.
    ([edit(path="README.md"), say("All tests pass.")], False,
     "editing a non-source file does not count as a stale code edit"),

    # THE self-reference case: a reply discussing or quoting this very rule,
    # with the example phrase in backticks, must not warn even though an
    # edit happened with no suite run.
    ([edit(), say(
        "I added `warn-stale-test-claim.py`, which fires when a reply "
        "says something like `\"all N cases pass\"` right after an edit "
        "with no real suite run in between."
    )], False,
     "quoting the rule's own example phrase in backticks does not warn"),

    # An ordinary reply with neither claim nor edit.
    ([bash("git status --short"), say("Nothing to report.")], False,
     "an ordinary reply with no claim does not warn"),
    ([], False, "an empty transcript does not warn"),

    # devtools::test() and other suite spellings are recognized.
    ([edit(path="R/foo.R"), bash("devtools::test()"),
      say("All tests pass.")], False,
     "devtools::test() after the edit is recognized as a real suite run"),
    ([edit(path="R/foo.R"), say("devtools::test() says all tests pass.")],
     True, "a claim naming devtools::test() in prose (not run) still warns"),

    # Adversarial-review finding: MENTIONING a test file must not read as
    # RUNNING it. `cat`, `git diff`, and an editor opening the file all name
    # it without executing it.
    ([edit(), bash("cat hooks/test-warn-stale-test-claim.py"),
      say("All tests pass.")], True,
     "merely CATTING the test file does not count as running the suite"),
    ([edit(), bash("git diff hooks/test-warn-stale-test-claim.py"),
      say("All tests pass.")], True,
     "diffing the test file does not count as running the suite"),
    ([edit(), bash("python3 hooks/test-warn-stale-test-claim.py "
                   "hooks/warn-stale-test-claim.py"),
      say("All 12 tests pass.")], False,
     "actually invoking `python3 hooks/test-*.py ...` is recognized as a run"),

    # Adversarial-review finding: a disclosed partial result ("N passed, M
    # failed") must not read as a full passing claim.
    ([edit(), say("Ran the suite: 12 passed, 3 failed.")], False,
     "a disclosed partial result (passed AND failed nearby) does not warn"),
    ([edit(), say("2 of 297 tests failed; the rest passed.")], False,
     "an explicit failure count near a passing claim does not warn"),

    # Adversarial-review finding: intra-turn ordering. A single reply that
    # edits AND runs the real suite in the same turn, in that order, must
    # not warn even though both tool calls share one JSONL record.
    ([{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Edit", "input": {
            "file_path": "hooks/warn-stale-test-claim.py",
            "old_string": "a", "new_string": "b"}},
        {"type": "tool_use", "name": "Bash", "input": {
            "command": "pytest -q"}},
    ]}}, say("All tests pass.")], False,
     "edit then real suite run WITHIN THE SAME turn/record does not warn"),
    ([{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {
            "command": "pytest -q"}},
        {"type": "tool_use", "name": "Edit", "input": {
            "file_path": "hooks/warn-stale-test-claim.py",
            "old_string": "a", "new_string": "b"}},
    ]}}, say("All tests pass.")], True,
     "real suite run then edit WITHIN THE SAME turn/record still warns"),

    # A Bash command that WRITES a source file via redirection/heredoc, not
    # through the Edit tool -- the secondary BASH_WRITE_RE path.
    ([bash("cat <<'EOF' > hooks/scratch.py\nprint(1)\nEOF"),
      say("All tests pass.")], True,
     "a heredoc write to a .py file via Bash counts as a source edit"),
    ([bash("cat <<'EOF' > hooks/scratch.py\nprint(1)\nEOF"),
      bash("pytest -q"), say("All tests pass.")], False,
     "a heredoc write followed by a real suite run does not warn"),

]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
        r = subprocess.run(
            [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True, env=env,
        )
        assert '"decision": "block"' not in r.stdout, "guard must never block"
        if not r.stdout.strip():
            return False
        payload = json.loads(r.stdout)
        assert "systemMessage" in payload, "warn-only Stop hook must emit systemMessage"
        return "tests pass" in payload["systemMessage"].lower() or "claims tests pass" in payload["systemMessage"].lower()
    finally:
        os.unlink(path)


def main():
    passes = failures = 0
    for events, expected, label in CASES:
        got = run(events)
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected warn={expected}, got {got})")
            failures += 1

    # Once-per-message sentinel: a second run over the same message is silent.
    events = [edit(), say("All 25 probe cases pass.")]
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
    payload = json.dumps({"transcript_path": path})
    first = subprocess.run([sys.executable, HOOK], input=payload,
                           capture_output=True, text=True, env=env).stdout
    second = subprocess.run([sys.executable, HOOK], input=payload,
                            capture_output=True, text=True, env=env).stdout
    os.unlink(path)
    if "systemMessage" in first and "systemMessage" not in second:
        print("PASS: warns once per distinct message")
        passes += 1
    else:
        print("FAIL: sentinel did not suppress the repeat")
        failures += 1

    # Adversarial-review finding: the sentinel must be keyed on transcript
    # path too, so two DIFFERENT sessions producing the identical short
    # final reply do not share one /tmp sentinel and swallow the second
    # session's genuine warning.
    events_a = [edit(), say("All 25 probe cases pass.")]
    fd_a, path_a = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd_a, "w") as fh:
        for e in events_a:
            fh.write(json.dumps(e) + "\n")
    fd_b, path_b = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd_b, "w") as fh:
        for e in events_a:  # identical content, different transcript file
            fh.write(json.dumps(e) + "\n")
    shared_env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
    out_a = subprocess.run(
        [sys.executable, HOOK], input=json.dumps({"transcript_path": path_a}),
        capture_output=True, text=True, env=shared_env,
    ).stdout
    out_b = subprocess.run(
        [sys.executable, HOOK], input=json.dumps({"transcript_path": path_b}),
        capture_output=True, text=True, env=shared_env,
    ).stdout
    os.unlink(path_a)
    os.unlink(path_b)
    if "systemMessage" in out_a and "systemMessage" in out_b:
        print("PASS: two sessions with an identical reply both warn "
              "(sentinel is keyed on transcript path)")
        passes += 1
    else:
        print("FAIL: a second session's identical-text warning was "
              "swallowed by the first session's sentinel")
        failures += 1

    # A missing transcript_path must not crash.
    out = subprocess.run(
        [sys.executable, HOOK], input=json.dumps({}),
        capture_output=True, text=True, env=dict(os.environ, TMPDIR=tempfile.mkdtemp()),
    )
    if out.returncode == 0 and "systemMessage" not in out.stdout:
        print("PASS: a missing transcript_path exits cleanly with no warning")
        passes += 1
    else:
        print(f"FAIL: missing transcript_path misbehaved (rc={out.returncode}, "
              f"stdout={out.stdout!r})")
        failures += 1

    # A malformed (non-JSON) transcript line must not crash the scan; the
    # well-formed lines around it should still be read.
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(edit()) + "\n")
        fh.write("{not valid json\n")
        fh.write(json.dumps(say("All tests pass.")) + "\n")
    out = subprocess.run(
        [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
        capture_output=True, text=True, env=dict(os.environ, TMPDIR=tempfile.mkdtemp()),
    )
    os.unlink(path)
    if out.returncode == 0 and "systemMessage" in out.stdout:
        print("PASS: a malformed transcript line is skipped, not fatal")
        passes += 1
    else:
        print(f"FAIL: a malformed transcript line broke the scan "
              f"(rc={out.returncode}, stdout={out.stdout!r})")
        failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
