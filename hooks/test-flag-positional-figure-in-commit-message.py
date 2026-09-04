#!/usr/bin/env python3
"""Test the flag-positional-figure-in-commit-message guard.

The positive cases are this repository's own history, verbatim in shape:
`4e1dea144`'s "13 lines above", `593d25ccf`'s "39 lines below",
`fcb4ee10d`'s "77 lines earlier", `f2f706fa1`'s "~130 lines later", plus the
properties the corpus forces -- `38a0738cc`'s newline between the number and
the unit, `6f5b9dde3`'s newline between the unit and the positional word, and
`1385f7b48`'s "140 lines LATER". Measured 2026-09-03 on `origin/main`: 14
occurrences across 13 of roughly 2400 commit messages.

The negative cases decide whether the guard survives. A diffstat ("3 files
changed"), a bare dimensional count ("143 characters" -- 53 commits in this
history, overwhelmingly legitimate measured facts), a version number, an
issue reference, a SHA, a date and a time are all things a commit message is
supposed to say. So is `0709c1a28`'s "The 60-to-80 range is human guidance",
which an earlier `\\d+-to-\\d+ range` arm fired on -- its only match in the
whole history, and a misfire; the arm is gone and two cases here pin that.
So are `git commit-tree` and `git commit-graph write`, which write no
message at all.

Run: python3 hooks/test-flag-positional-figure-in-commit-message.py \\
         hooks/flag-positional-figure-in-commit-message.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

# Payloads a fire produced that the harness would discard; see fired().
SHAPE_ERRORS = []

PROMPT = {"type": "user", "message": {"content": "commit the fix"}}


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def commit(message, quote='"'):
    """A `git commit -m` call carrying `message`."""
    return bash(f"git commit -m {quote}{message}{quote}")


# --- the measured shapes, from this repo's own history ----------------------
CASES = [
    # (payload, should_fire, label)
    (commit("fix(prose): the bullet restated an instruction 13 lines above"),
     True, "4e1dea144's shape: 'N lines above' warns"),
    (commit("docs: drop the pointer to its own sibling 39 lines below"),
     True, "593d25ccf's shape: 'N lines below' warns"),
    (commit("docs: the section says, 77 lines earlier, that the operand is bound"),
     True, "fcb4ee10d's shape: 'N lines earlier' warns"),
    (commit("docs: depends on a section defined ~130 lines later"),
     True, "f2f706fa1's shape: '~N lines later' warns"),
    (commit("docs: an entry on the same tool already sat ~2000 lines below"),
     True, "60edf4c1e's shape: a tilde-prefixed thousands figure warns"),
    (commit("docs: the quoted span runs 143 characters below the anchor"),
     True, "a dimensional unit WITH a positional word warns"),
    (commit("docs: the paragraph repeats a claim made 40 words earlier"),
     True, "'N words earlier' warns"),
    (commit("docs: the fingerprint sits 12 chars above the delimiter"),
     True, "'N chars above' warns"),

    # --- the two properties the corpus forces -------------------------------
    (commit("fix(prose): restated an identical instruction 30\n  lines above"),
     True, "38a0738cc: a newline between the number and the unit still warns"),
    (commit("docs: an exception to this file's own remedy 25 lines\n   above"),
     True, "6f5b9dde3: a newline between the unit and the positional word warns"),
    (commit("docs: the heuristic pointed at content ~140 lines LATER"),
     True, "1385f7b48: the figure is the target shape whatever its case"),

    # --- SCOPE DISCIPLINE: things a commit message is supposed to say -------
    # `0709c1a28`'s "The 60-to-80 range is human guidance" was the ONLY match
    # a `\\d+-to-\\d+ range` arm had in the whole history, and it is a misfire:
    # the sentence states what a style guide asks for, locates no passage,
    # decays on no insertion, and deleting its numbers would destroy it. The
    # arm is gone; this pins that it stays gone.
    (commit("docs: state what the CI check enforces; the 60-to-80 range is "
            "human guidance"),
     False, "0709c1a28: a style-guide range locates no passage and must not fire"),
    (commit("style: rewrap the paragraph into the 60-to-80 range"),
     False, "no 'N-to-N range' arm exists: zero true positives, one false one"),
    (commit("chore: regenerate fixtures -- 3 files changed, 2 insertions"),
     False, "a diffstat is derived by git itself, not asserted"),
    (commit("chore: trim skill descriptions to 9000 characters"),
     False, "a bare dimensional count is a measured fact (53 commits carry one)"),
    (commit("fix: truncate the tail at 300 chars before rendering"),
     False, "a bare 'N chars' with no positional word stays silent"),
    (commit("chore(deps): bump actions/checkout from 4.1.2 to 4.2.0"),
     False, "a version number is not a positional figure"),
    (commit("fix(hooks): register the guard (closes #2947, refs #2900)"),
     False, "issue and PR numbers stay silent"),
    (commit("revert: back out 4e1dea144cafe0011 from main"),
     False, "a SHA stays silent"),
    (commit("docs: record the 2026-09-01 measurement, taken at 12:47 PT"),
     False, "a date and a clock time stay silent"),
    (commit("perf: cut the scan from 7200 ms to 40 ms"),
     False, "a timing measurement stays silent"),

    # --- the command word, per no-unshipped-commit.py's `(?![\\w-])` --------
    (bash('git commit-tree $t -m "restates the note 13 lines above"'),
     False, "git commit-tree writes no message and must not match"),
    (bash('git commit-graph write --reachable  # 13 lines above'),
     False, "git commit-graph write must not match"),
    (bash('git log --oneline -m "13 lines above"'),
     False, "a non-commit git subcommand stays silent"),
    (bash('echo "restated an instruction 13 lines above"'),
     False, "a non-git Bash command stays silent"),
    (bash('git commit --amend --no-edit'),
     False, "a commit with no message flag has nothing to read"),

    # --- invocation shapes --------------------------------------------------
    (bash('FOO=1 GIT_AUTHOR_NAME=x git commit -m "the note 13 lines above"'),
     True, "leading env assignments before git do not hide the commit"),
    (bash('git -C /tmp/wt commit -m "the note 13 lines above"'),
     True, "a global -C flag before the subcommand does not hide it"),
    (bash('git -c user.name=x commit -m "the note 13 lines above"'),
     True, "a global -c k=v flag before the subcommand does not hide it"),
    (bash("git commit -m 'the note 13 lines above'"),
     True, "a single-quoted message is read"),
    (bash('git commit -m "fix: tidy" -m "detail: the note 13 lines above"'),
     True, "a repeated -m is concatenated, as git does"),
    (bash('git commit -m"the note 13 lines above"'),
     True, "the attached -m\"...\" form is read"),

    # --- CLUSTERED short flags ----------------------------------------------
    # `-am` is among the commonest commit invocations there is, and a
    # token-equality test against `-m` sees none of it -- a large silent
    # blind spot rather than an edge case.
    (bash('git commit -am "the note 13 lines above"'),
     True, "-am: a clustered short flag with m LAST takes the next token"),
    (bash('git commit -sm "the note 13 lines above"'),
     True, "-sm: the same, with a different leading flag"),
    (bash('git commit -asm "the note 13 lines above"'),
     True, "-asm: a three-letter cluster with m last"),
    (bash('git commit -am "chore: routine tidy of the fixtures"'),
     False, "-am with a clean message stays silent"),
    (bash('git commit -ma "the note 13 lines above"'),
     False, "-ma is `-m a`, so the message is 'a' and the quoted text is a pathspec"),
    (bash('git commit -ams "the note 13 lines above"'),
     False, "-ams is `-a -m s`: m is not last, so the next token is not the message"),
    (bash('git commit -av'),
     False, "a cluster with no value-taking letter stays silent"),
    (bash('git commit -am'),
     False, "a dangling cluster with no value fails silent"),
    (bash('git commit --message="the note 13 lines above"'),
     True, "--message=... is read"),
    (bash('git status && git commit -m "the note 13 lines above"'),
     True, "a chained command does not hide the commit"),
    (bash('git commit -m "fix: unrelated; see below | pipe"'),
     False, "separators inside the quoted message do not split it"),
    (bash('git commit -m "fix: unrelated" && echo "13 lines above"'),
     False, "a figure in a CHAINED non-commit segment does not fire"),
    (bash('git commit -m "the note 13 lines above'),
     False, "an unbalanced quote fails silent rather than loud"),
]


def write_transcript(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    return path


def run(payload, extra_args=(), cwd=None):
    """Run the hook end-to-end; return the parsed stdout payload, or {}.

    A FRESH `TMPDIR` per call: the fire-once sentinel lives in
    `tempfile.gettempdir()`, and several cases below commit the same message,
    so a sentinel written by one would silently suppress a later one.
    """
    tpath = write_transcript([PROMPT])
    tmpdir = tempfile.mkdtemp()
    try:
        full = dict(payload, transcript_path=tpath, cwd=cwd or os.getcwd())
        env = dict(os.environ, TMPDIR=tmpdir)
        env.pop("ANTIGRAVITY_AGENT", None)
        r = subprocess.run(
            [sys.executable, HOOK, *extra_args], input=json.dumps(full),
            capture_output=True, text=True, env=env)
        assert r.returncode == 0, f"hook exited {r.returncode}: {r.stderr}"
        assert "permissionDecision" not in r.stdout, "guard must never block"
        if not r.stdout.strip():
            return {}
        return json.loads(r.stdout)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        os.unlink(tpath)


def fired(out):
    """True when the payload carries a warning the harness would surface.

    `bool(out)` alone would score any output as a fire. A warn-only
    PreToolUse hook surfaces through `hookSpecificOutput.additionalContext`
    (to the model) and `systemMessage` (to the user); a payload with neither
    is recorded as a shape error rather than counted as a fire.
    """
    if not out:
        return False
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext")
    if not ctx or not isinstance(out.get("systemMessage"), str):
        SHAPE_ERRORS.append(sorted(out))
        return False
    return True


def check_output_shape():
    """The warning names the figure and says to delete rather than recount."""
    out = run(commit("docs: the section 13 lines above says otherwise"))
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""
    msg = out.get("systemMessage") or ""
    ok = ("13 lines above" in ctx and "13 lines above" in msg
          and "delete the number" in ctx.lower()
          and "not to correct it" in ctx.lower()
          and "name the target" in ctx.lower()
          and "\n" not in msg
          and (out.get("hookSpecificOutput") or {}).get("hookEventName") == "PreToolUse")
    print(f"{'ok  ' if ok else 'FAIL'}  the warning names the figure and says "
          f"to delete rather than recount, in both surfaces")
    return 0 if ok else 1


def check_newline_figure_is_normalized():
    """A wrapped figure is reported on one line, so systemMessage stays single-line."""
    out = run(commit("fix: restated an instruction 30\n  lines above"))
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""
    msg = out.get("systemMessage") or ""
    ok = "30 lines above" in ctx and "30 lines above" in msg and "\n" not in msg
    print(f"{'ok  ' if ok else 'FAIL'}  a wrapped figure is normalized to one line")
    return 0 if ok else 1


def check_body_file():
    """`-F <file>` and `--file=<file>` bodies are read off disk."""
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w") as fh:
        fh.write("docs: rewrite\n\nThe note sits 77 lines earlier in the file.\n")
    try:
        short = fired(run(bash(f"git commit -F {path}")))
        long = fired(run(bash(f"git commit --file={path}")))
    finally:
        os.unlink(path)
    ok = short and long
    print(f"{'ok  ' if ok else 'FAIL'}  a -F / --file= message is read off disk")
    return 0 if ok else 1


def check_cluster_body_file():
    """A clustered `-aF <file>` reads the file, like a bare -F."""
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w") as fh:
        fh.write("docs: rewrite\n\nThe note sits 77 lines earlier in the file.\n")
    try:
        ok = fired(run(bash(f"git commit -aF {path}")))
    finally:
        os.unlink(path)
    print(f"{'ok  ' if ok else 'FAIL'}  a clustered -aF reads the file too")
    return 0 if ok else 1


def check_deleted_cwd():
    """A deleted working directory must not produce a traceback or exit 1.

    `os.getcwd()` raises FileNotFoundError there, so the fallback for a
    payload with no `cwd` has to sit inside the guarded block -- otherwise
    the "fails silent, always" contract is broken by the one condition the
    hook cannot see coming.
    """
    tpath = write_transcript([PROMPT])
    gone = tempfile.mkdtemp()
    tmpdir = tempfile.mkdtemp()
    try:
        payload = commit("docs: the section 13 lines above says otherwise")
        # No `cwd` key at all, so the hook must fall back to os.getcwd().
        env = dict(os.environ, TMPDIR=tmpdir)
        env.pop("ANTIGRAVITY_AGENT", None)
        proc = subprocess.Popen(
            [sys.executable, os.path.abspath(HOOK)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, env=env, cwd=gone,
            preexec_fn=(lambda: os.rmdir(gone)) if hasattr(os, "fork") else None)
        out, err = proc.communicate(json.dumps(dict(payload, transcript_path=tpath)))
        ok = proc.returncode == 0 and "Traceback" not in err
    except OSError:
        # Some platforms refuse to spawn into a directory at all; the
        # condition this pins cannot arise there.
        ok = True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        shutil.rmtree(gone, ignore_errors=True)
        os.unlink(tpath)
    print(f"{'ok  ' if ok else 'FAIL'}  a deleted working directory exits 0 "
          f"with no traceback")
    return 0 if ok else 1


def check_body_file_clean():
    """A `-F` file with no positional figure stays silent."""
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w") as fh:
        fh.write("docs: rewrite\n\n3 files changed, 2 insertions.\n")
    try:
        out = run(bash(f"git commit -F {path}"))
    finally:
        os.unlink(path)
    ok = not fired(out)
    print(f"{'ok  ' if ok else 'FAIL'}  a clean -F message stays silent")
    return 0 if ok else 1


def check_missing_body_file():
    """A missing or stdin `-F` target fails silent, never loud."""
    missing = run(bash("git commit -F /nonexistent/path/to/msg-13-lines-above.txt"))
    stdin = run(bash("git commit -F -"))
    # An unreadable -F abandons the whole segment rather than judging the
    # fraction of the message it CAN see: the figure may well live in the
    # part that stayed invisible, so a verdict drawn from the rest would be
    # asserting more than was observed. Pins the branch -- treating the
    # unreadable file as empty text would let the -m half fire here.
    partial = run(bash('git commit -F /nonexistent/msg.txt '
                       '-m "the note 13 lines above"'))
    ok = not fired(missing) and not fired(stdin) and not fired(partial)
    print(f"{'ok  ' if ok else 'FAIL'}  an unreadable or stdin -F target is "
          f"silent, and abandons the segment rather than judging part of it")
    return 0 if ok else 1


def check_dry_run():
    """--dry-run reports the verdict offline and never writes a sentinel."""
    payload = commit("docs: the section 13 lines above says otherwise")
    out = run(payload, ("--dry-run",))
    again = run(payload, ("--dry-run",))
    ok = fired(out) and fired(again)
    quiet = run(bash("git status"), ("--dry-run",))
    ok = ok and quiet == {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
    print(f"{'ok  ' if ok else 'FAIL'}  --dry-run warns without a sentinel, and "
          f"reports an empty PreToolUse payload when silent")
    return 0 if ok else 1


def check_sentinel():
    """Once per distinct message: the second identical commit is silent."""
    tpath = write_transcript([PROMPT])
    tmpdir = tempfile.mkdtemp()
    try:
        full = dict(commit("docs: the section 13 lines above says otherwise"),
                    transcript_path=tpath, cwd=os.getcwd())
        env = dict(os.environ, TMPDIR=tmpdir)
        env.pop("ANTIGRAVITY_AGENT", None)
        first = subprocess.run([sys.executable, HOOK], input=json.dumps(full),
                               capture_output=True, text=True, env=env).stdout
        second = subprocess.run([sys.executable, HOOK], input=json.dumps(full),
                                capture_output=True, text=True, env=env).stdout
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        os.unlink(tpath)
    ok = "systemMessage" in first and not second.strip()
    print(f"{'ok  ' if ok else 'FAIL'}  warns once per distinct message")
    return 0 if ok else 1


def check_malformed_input():
    """Malformed stdin, and payload shapes this does not recognise, fail open."""
    r = subprocess.run([sys.executable, HOOK], input="not json",
                       capture_output=True, text=True)
    ok = r.returncode == 0 and not r.stdout.strip()
    for payload in (
        {"tool_name": "Bash", "tool_input": "not a dict"},
        {"tool_name": "Bash", "tool_input": {}},
        {"tool_name": "Write", "tool_input": {
            "file_path": "/tmp/x.md",
            "content": "git commit -m 'the note 13 lines above'"}},
        {},
    ):
        r2 = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                            capture_output=True, text=True)
        ok = ok and r2.returncode == 0 and not r2.stdout.strip()
    print(f"{'ok  ' if ok else 'FAIL'}  malformed and unrecognised payloads "
          f"fail open and silent")
    return 0 if ok else 1


def main():
    failures = 0
    failures += check_output_shape()
    failures += check_newline_figure_is_normalized()
    failures += check_body_file()
    failures += check_cluster_body_file()
    failures += check_deleted_cwd()
    failures += check_body_file_clean()
    failures += check_missing_body_file()
    failures += check_dry_run()
    failures += check_sentinel()
    failures += check_malformed_input()
    case_failures = 0
    for payload, want, label in CASES:
        got = fired(run(payload))
        ok = got == want
        if not ok:
            case_failures += 1
        print(f"{'ok  ' if ok else 'FAIL'}  fire={got!s:5} want={want!s:5}  {label}")
    failures += case_failures
    print(f"\n{len(CASES) - case_failures}/{len(CASES)} cases passed")
    if SHAPE_ERRORS:
        print(f"FAIL  {len(SHAPE_ERRORS)} fire(s) emitted a payload the harness "
              f"would discard: {SHAPE_ERRORS[0]}")
        failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
