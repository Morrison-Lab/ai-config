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

    # SEVENTH-round adversarial-review finding: the identical incident
    # claim in ordinary PAST TENSE ("passed" rather than "pass") must
    # match too -- the two CLAIM_RE alternatives had drifted onto
    # different subject-noun/tense combinations, so "probe cases passed"
    # went unmatched while "probe cases pass" matched.
    ([edit(), PROBE, say("All 25 probe cases passed.")], True,
     "the identical incident claim in past tense ('passed') still warns"),
    ([edit(), say("The suite passed.")], True,
     "'the suite passed' (past tense) still warns"),
    ([edit(), say("The probe cases passed.")], True,
     "'probe cases passed' with no leading 'all' still warns (isolates the "
     "second CLAIM_RE alternative, whose subject-noun set once excluded "
     "cases/probes)"),

    # EIGHTH-round adversarial-review finding: the copula ("to be") plus
    # participle/adjective form -- "tests ARE passing", "the suite IS
    # green" -- is at least as ordinary a way to report results
    # conversationally as the bare forms above, and was unmatched.
    ([edit(), say("All 297 tests are passing.")], True,
     "'tests are passing' (copula + participle) warns"),
    ([edit(), say("The suite is green.")], True,
     "'the suite is green' (copula + adjective) warns"),
    ([edit(), say("The test suite is passing now.")], True,
     "'the test suite is passing now' warns"),
    ([edit(), say("The new error-handling branch is covered too.")], False,
     "an unrelated 'is' near 'error' does not spuriously warn"),

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

    # SECOND-round adversarial-review finding: a python-invocation STRING
    # quoted inside `echo` or a `#` comment is a MENTION, not a run, and
    # must not be recognized as one.
    ([edit(), bash('echo "run python3 hooks/test-foo.py before merging"'),
      say("All tests pass.")], True,
     "a python invocation quoted inside echo is a mention, not a run"),
    ([edit(), bash("# reminder: python3 hooks/test-foo.py hooks/foo.py"),
      say("All tests pass.")], True,
     "a python invocation named in a shell comment is a mention, not a run"),
    ([edit(), bash("cd hooks && python3 test-foo.py foo.py"),
      say("All tests pass.")], False,
     "a python invocation after && (a real command position) still counts"),

    # THIRD-round adversarial-review finding: the SAME mention-vs-run bug
    # existed for every OTHER keyword alternative too, since only the
    # python-file one was anchored in round two.
    ([edit(), bash('echo "remember to run pytest before merging"'),
      say("All tests pass.")], True,
     "'pytest' mentioned inside an unrelated echo is not a run"),
    ([edit(), bash('git commit -m "will run cargo test later"'),
      say("All tests pass.")], True,
     "'cargo test' mentioned inside a commit message is not a run"),
    ([edit(), bash('echo "npm test should be added to CI"'),
      say("All tests pass.")], True,
     "'npm test' mentioned inside an unrelated echo is not a run"),

    # THIRD-round finding: a small, explicit set of process wrappers must
    # still be recognized once every alternative is anchored to command
    # position, or the anchor itself becomes a regression.
    ([edit(), bash("timeout 60 pytest -q"), say("All tests pass.")], False,
     "'timeout N pytest' is still recognized as a real run"),
    ([edit(), bash("sudo npm test"), say("All tests pass.")], False,
     "'sudo npm test' is still recognized as a real run"),
    ([edit(), bash("env FOO=1 cargo test"), say("All tests pass.")], False,
     "'env VAR=val cargo test' is still recognized as a real run"),

    # THIRD-round finding: `test[-_]` must anchor the FILENAME, not match
    # as a substring anywhere inside an unrelated script name.
    ([edit(), bash("python3 scripts/latest_run.py"),
      say("All tests pass.")], True,
     "running an unrelated script named *latest_run.py* is not a suite run"),
    ([edit(), bash("python3 scripts/contest_data.py"),
      say("All tests pass.")], True,
     "running an unrelated script named *contest_data.py* is not a suite run"),
    ([edit(), bash("python3 scripts/attest_config.py"),
      say("All tests pass.")], True,
     "running an unrelated script named *attest_config.py* is not a suite run"),

    # THIRD-round finding: a heredoc BODY line is DATA, not a command, so a
    # documentation line mentioning a test invocation inside one must not
    # be read as a run. This is what motivated dropping the bare newline
    # from the command-position anchor.
    ([edit(), bash(
        "cat <<'EOF' > NOTES.md\n"
        "Remember to run\n"
        "python3 hooks/test-foo.py hooks/foo.py\n"
        "before merging.\n"
        "EOF"
     ), say("All tests pass.")], True,
     "a test invocation mentioned inside a heredoc BODY is not a run"),

    # FOURTH-round adversarial-review finding: _CMD_START's separator
    # characters are not quote-aware, so ORDINARY (non-adversarial) prose
    # containing one of them inside a quoted string was still misread as a
    # command boundary. `_strip_shell_literals` blanks quoted strings and
    # heredoc bodies before TEST_SUITE_RE ever sees the command.
    ([edit(), bash('echo "Build & pytest"'), say("All tests pass.")], True,
     "'&' inside a quoted echo string is not a command separator"),
    ([edit(), bash('git commit -m "docs: run lint; pytest; deploy steps"'),
      say("All tests pass.")], True,
     "';' inside a quoted commit message is not a command separator"),
    ([edit(), bash(
        "cat <<'EOF' > notes.txt\n"
        "Steps: build && pytest -q && deploy\n"
        "EOF"
     ), say("All tests pass.")], True,
     "'&&' inside a heredoc body is not a command separator"),

    # FOURTH-round finding: a bare keyword must not match an identically
    # named environment-variable assignment (`PYTEST=1 ./tool`), since
    # `\b` treats `=` as a word boundary.
    ([edit(), bash("PYTEST=1 ./mytool arg"), say("All tests pass.")], True,
     "PYTEST=1 as an env-var assignment is not a pytest run"),
    ([edit(), bash("RSPEC=1 ./deploy.sh"), say("All tests pass.")], True,
     "RSPEC=1 as an env-var assignment is not an rspec run"),

    # FIFTH-round adversarial-review finding: an ordinary PARTIAL script
    # or build target whose name merely STARTS with "test" (a lint-only,
    # watch-mode, or compile-only target) must not read as a full run --
    # bare `\b` is satisfied by a following `:` or `-`, both non-word
    # characters, so `npm run test:unit` matched exactly like `npm test`.
    ([edit(), bash("npm run test:unit"), say("All tests pass.")], True,
     "'npm run test:unit' (a partial script target) is not a full suite run"),
    ([edit(), bash("npm run test:watch"), say("All tests pass.")], True,
     "'npm run test:watch' (watch mode, not a completed run) is not a full run"),
    ([edit(), bash("mvn test-compile"), say("All tests pass.")], True,
     "'mvn test-compile' (a compile-only phase) is not a full test run"),
    ([edit(), bash("make test-unit"), say("All tests pass.")], True,
     "'make test-unit' (a named partial target) is not the full suite"),
    ([edit(), bash("yarn test:watch"), say("All tests pass.")], True,
     "'yarn test:watch' (watch mode) is not a completed full run"),
    ([edit(), bash("npm test"), say("All tests pass.")], False,
     "'npm test' (the bare, un-suffixed target) is still recognized as a real run"),
    ([edit(), bash("mvn test"), say("All tests pass.")], False,
     "'mvn test' (the bare, un-suffixed target) is still recognized as a real run"),

    # Adversarial-review finding: a disclosed partial result ("N passed, M
    # failed") must not read as a full passing claim.
    ([edit(), say("Ran the suite: 12 passed, 3 failed.")], False,
     "a disclosed partial result (passed AND failed nearby) does not warn"),
    ([edit(), say("2 of 297 tests failed; the rest passed.")], False,
     "an explicit failure count near a passing claim does not warn"),

    # SECOND-round adversarial-review finding: the fail-nearby check must
    # require an actual COUNT next to fail/error, not the bare word alone --
    # otherwise unrelated prose mentioning "error" wrongly suppresses a
    # genuine warning.
    ([edit(), say(
        "All tests pass. The new error-handling branch is covered too."
    )], True,
     "the bare word 'error' in unrelated prose does not suppress a genuine warning"),

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

    # SIXTH-round adversarial-review finding: `sed -i`/`perl -i` edit a
    # source file in place with no Edit tool call and no redirection for
    # BASH_WRITE_RE to see.
    ([bash("sed -i 's/foo/bar/' hooks/warn-stale-test-claim.py"),
      say("All tests pass.")], True,
     "a GNU 'sed -i' edit of a source file counts as a source edit"),
    ([bash("sed -i.bak 's/foo/bar/' hooks/warn-stale-test-claim.py"),
      say("All tests pass.")], True,
     "'sed -i.bak' (suffix attached to -i) still counts as a source edit"),
    ([bash("sed -i '' 's/foo/bar/' hooks/warn-stale-test-claim.py"),
      say("All tests pass.")], True,
     "BSD/macOS 'sed -i ''' (empty backup arg) still counts as a source edit"),
    ([bash("perl -pi -e 's/foo/bar/' hooks/warn-stale-test-claim.py"),
      say("All tests pass.")], True,
     "a bundled 'perl -pi' edit counts as a source edit"),
    ([bash("sed -i 's/foo/bar/' hooks/warn-stale-test-claim.py"),
      bash("pytest -q"), say("All tests pass.")], False,
     "a 'sed -i' edit followed by a real suite run does not warn"),
    ([bash("sed -n '1,5p' hooks/warn-stale-test-claim.py"),
      say("All tests pass.")], False,
     "'sed -n' (no -i, read-only) is not an edit"),
    ([bash("sed -i 's/x/y/' README.md"), say("All tests pass.")], False,
     "'sed -i' on a non-source file is not a stale-code edit"),
    ([bash("perl -Ilib -e 'print 1' hooks/warn-stale-test-claim.py"),
      say("All tests pass.")], False,
     "'perl -Ilib' (an unrelated include-path flag) is not an in-place edit"),

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

    # NINTH-round adversarial-review finding: a top-level JSON document
    # that is syntactically VALID but not an object (a bare list, string,
    # number, bool, or null) parses fine and then crashed the very next
    # line (`payload.get(...)`) with an uncaught AttributeError. Every one
    # of these must exit 0 with no traceback and no warning.
    for label, raw in [
        ("a bare JSON list", "[]"),
        ("a bare JSON string", '"hello"'),
        ("a bare JSON number", "42"),
        ("a bare JSON boolean", "true"),
        ("a bare JSON null", "null"),
        # TENTH-round adversarial-review finding: the dict guard above
        # only checks the top-level payload -- a dict/list/other
        # non-string VALUE at "transcript_path" is truthy, survives
        # `or ""`, and reached os.path.isfile() un-typechecked.
        ("a dict-valued transcript_path", '{"transcript_path": {"a": 1}}'),
        ("a list-valued transcript_path", '{"transcript_path": ["a", "b"]}'),
        ("a number-valued transcript_path", '{"transcript_path": 42}'),
        ("a bool-valued transcript_path", '{"transcript_path": true}'),
    ]:
        out = subprocess.run(
            [sys.executable, HOOK], input=raw,
            capture_output=True, text=True,
            env=dict(os.environ, TMPDIR=tempfile.mkdtemp()),
        )
        if out.returncode == 0 and "Traceback" not in out.stderr:
            print(f"PASS: {label} on stdin exits cleanly, no traceback")
            passes += 1
        else:
            print(f"FAIL: {label} on stdin crashed "
                  f"(rc={out.returncode}, stderr={out.stderr!r})")
            failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
