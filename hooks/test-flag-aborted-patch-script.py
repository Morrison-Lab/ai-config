"""Test the flag-aborted-patch-script guard.

Three design choices carry the value, and each has its own negative case.

WINDOW-BOUNDED: the traceback only matters between commits. A traceback
before an earlier commit was already the previous commit's problem, so it
must not warn on the next one.

WRITE-GATED: a traceback from a script that changed nothing is not a partial
patch. Warning on every traceback would train the reader to ignore this,
which per README costs more than the missing hook.

RESOLVED-BY-A-CLEAN-WRITE: a later writing command that ran clean is taken
as the re-application. Deliberately weak (it does not check WHICH files),
because the transcript does not record which edits were intended.

Run: python3 hooks/test-flag-aborted-patch-script.py \
         hooks/flag-aborted-patch-script.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

PATCH_CMD = (
    "python3 - <<'PY'\n"
    "def patch(p, old, new):\n"
    "    s = open(p).read()\n"
    "    assert old in s\n"
    "    open(p, 'w').write(s.replace(old, new))\n"
    "patch('a.md', 'x', 'y')\n"
    "PY"
)
TB = ("Traceback (most recent call last):\n"
      '  File "<stdin>", line 7, in <module>\n'
      "AssertionError")


def use(cmd, tid, key="command"):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tid, "input": {key: cmd}}]}}


def result(text, tid, is_error=False):
    block = {"type": "tool_result", "tool_use_id": tid, "content": text}
    if is_error:
        block["is_error"] = True
    return {"type": "user", "message": {"content": [block]}}


COMMIT = "git commit -F /tmp/msg.txt"

# The incident's own shape: one script, three target files, raising on the
# first. Its text names all three, which is what makes partial repair
# detectable at all.
THREE_FILE_PATCH = (
    "python3 - <<'PY'\n"
    "patch('memories/gh-cli.md', a, b)\n"
    "patch('CLAUDE.md', c, d)\n"
    "patch('skills/use-math-macros/SKILL.md', e, f)\n"
    "open('memories/gh-cli.md', 'w').write(s)\n"
    "PY"
)

CASES = [
    # The reported incident, in shape.
    ([use(PATCH_CMD, "t1"), result(TB, "t1")], True,
     "a writing script that raised, then a commit, warns (the reported case)"),

    # WRITE-GATED negatives.
    ([use("python3 -c 'raise SystemExit(1)'", "t1"), result(TB, "t1")], False,
     "a traceback from a command that writes nothing does not warn"),
    ([use("python3 -c \"print(open('a.md').read())\"", "t1"),
      result(TB, "t1")], False,
     "a traceback from a read-only script does not warn"),

    # RESOLVED negative.
    ([use(PATCH_CMD, "t1"), result(TB, "t1"),
      use(PATCH_CMD, "t2"), result("patched\n", "t2")], False,
     "a later writing command that ran clean clears the pending traceback"),

    # WINDOW negative.
    ([use(PATCH_CMD, "t1"), result(TB, "t1"),
      use(COMMIT, "t2"), result("[main abc] msg\n", "t2")], False,
     "a traceback already carried past an earlier commit does not re-warn"),

    # Ordinary clean sessions.
    ([use(PATCH_CMD, "t1"), result("ok\n", "t1")], False,
     "a writing script that ran clean does not warn"),
    ([], False, "an empty transcript does not warn"),
    ([use("git status --short", "t1"), result(" M a.md\n", "t1")], False,
     "no traceback anywhere does not warn"),

    # sed -i is a patch too.
    ([use("sed -i 's/x/y/' a.md", "t1"), result(TB, "t1")], True,
     "an in-place sed that raised warns"),

    # F2: WRITES is matched against the command's TEXT, so a read-only
    # command whose SUBJECT contains those patterns must not count as a
    # write. Auditing hook sources for exactly these strings is routine in
    # this repo, and the grep's own output contains a literal traceback.
    ([use("grep -n 'sed -i\\|.write(\\|Traceback' hooks/x.py", "t1"),
      result("12: Traceback (most recent call last):\n", "t1")], False,
     "a read-only grep whose output quotes a traceback does not warn"),
    ([use("cat notes.md", "t1"), result(TB, "t1")], False,
     "a cat whose output contains a traceback does not warn"),

    # R2-F1: a wrapper must not defeat the read-only exclusion. `env`,
    # `sudo` and `timeout` are ordinary in this repo's hooks and CI, and
    # without wrapper-stripping each turns a plain grep into a "writer" on
    # the strength of the text it was grepping FOR.
    ([use('env grep -n ".write(" hooks/x.py', "t1"), result(TB, "t1")], False,
     "an env-wrapped read-only grep does not warn"),
    ([use('timeout 5 grep -n "sed -i" hooks/x.py', "t1"), result(TB, "t1")],
     False, "a timeout-wrapped read-only grep does not warn"),
    # ... and a wrapper OPTION taking a separate value must not be read as
    # the program. Skipping only dash-led and numeric tokens stopped at
    # `me`, which is in no read-only set, so `sudo -u me grep` read as a
    # writer -- the one wrapper shape every sibling guard here already
    # covers by name, and the exact false positive R2-F1 exists to prevent.
    ([use('sudo -u me grep -n ".write(" hooks/x.py', "t1"), result(TB, "t1")],
     False, "a sudo -u wrapped read-only grep does not warn"),

    # The counterweight, and the asymmetry the lookahead relies on: it may
    # only ever find a READ-ONLY program, so a wrapper grammar it cannot
    # parse still reads as a writer rather than being silently cleared.
    # Without this, narrowing `_program` until everything looked read-only
    # would pass the case above.
    ([use("sudo -u me sed -i s/a/b/ hooks/x.py", "t1"), result(TB, "t1"),
      use("git commit -m x", "t2")], True,
     "a sudo -u wrapped in-place edit still warns"),

    # R3: a leading `VAR=value` assignment is not the program. Without the
    # skip, `_program` returns "CI=1", which is not in READ_ONLY, so an
    # env-prefixed audit grep reads as a writer.
    ([use('CI=1 grep -n ".write(" hooks/x.py', "t1"), result(TB, "t1")],
     False, "a leading env assignment does not hide the read-only program"),

    # R3: a shell keyword can be argv[0] of a segment -- the splitter breaks
    # on `;`, so a loop body arrives as `do grep ...`. Without the
    # SHELL_KEYWORDS half, "do" is returned as the program.
    ([use('for f in *.py; do grep -l ".write(" "$f"; done', "t1"),
      result(TB, "t1")], False,
     "a shell-keyword-led loop body does not hide the read-only program"),

    # R4: the header exclusion must remove the HEADER only. A loop whose
    # BODY genuinely writes is still a write -- without this, broadening the
    # header tuple (say, to include "do") silently stops detecting every
    # in-place edit performed inside a loop.
    ([use('for f in *.py; do sed -i s/a/b/ "$f"; done', "t1"),
      result(TB, "t1")], True,
     "a for-loop whose body writes still warns"),

    # R5-D1: the motivating incident's own shape. A 3-file patch script
    # raises on file 1; the session repairs ONLY file 1 with a narrow
    # `sed -i`. Files 2 and 3 are still unedited, so the warning must
    # survive that partial fix -- clearing on any later write is what let
    # the incident through.
    ([use(THREE_FILE_PATCH, "t1"), result(TB, "t1"),
      use("sed -i 's/old/new/' memories/gh-cli.md", "t2"),
      result("", "t2")], True,
     "a narrow single-file fix does NOT clear a multi-file aborted patch"),
    ([use(THREE_FILE_PATCH, "t1"), result(TB, "t1"),
      use(THREE_FILE_PATCH, "t2"), result("ok\n", "t2")], False,
     "re-running the same multi-file script DOES clear it"),

    # R6-D1: a status line naming the files it believes were fixed must not
    # discharge the warning. This hook's own text asks the reader to produce
    # exactly such a summary, so counting its mentions as coverage would let
    # the summary clear the warning it was written in response to.
    ([use(THREE_FILE_PATCH, "t1"), result(TB, "t1"),
      use('echo "fixed memories/gh-cli.md CLAUDE.md '
          'skills/use-math-macros/SKILL.md" | tee /tmp/status.log', "t2"),
      result("", "t2")], True,
     "an echoed summary naming the files does NOT clear the warning"),

    # The pair the README makes a claim about, and the one the suite could
    # not see. An announcer does two separate things: it contributes no
    # path of its own, AND it disables the whole-command fallback that
    # recovers a heredoc's targets. Only the first is obvious, so a later
    # command that genuinely re-runs the failed heredoc and then announces
    # reads as a real fix and still clears nothing. Not the incident's own
    # shape -- that was the narrow single-file repair R5-D1 pins -- but a
    # heredoc is the shape the incident's FAILED command had, so it is the
    # re-run a session would most plausibly reach for. Pinned so the
    # README's wording stays answerable to the code.
    ([use(THREE_FILE_PATCH, "t1"), result(TB, "t1"),
      use(THREE_FILE_PATCH + '\necho "fixed all three"', "t2"),
      result("", "t2")], True,
     "a heredoc re-run WITH an announcer does not clear"),

    # Its counterweight: writer segments that name the paths themselves are
    # unaffected by the announcer, because they never needed the fallback.
    # Without this case, narrowing the announcer rule until nothing ever
    # cleared would pass every other case in the suite.
    ([use(THREE_FILE_PATCH, "t1"), result(TB, "t1"),
      use("sed -i s/a/b/ memories/gh-cli.md; sed -i s/c/d/ CLAUDE.md; "
          "sed -i s/e/f/ skills/use-math-macros/SKILL.md; "
          'echo "fixed all three"', "t2"),
      result("", "t2")], False,
     "named writer segments clear even alongside an announcer"),

    # R7: the writer's OWN target is often extensionless (`tee log`,
    # `/dev/null`, a bare build-log). An earlier gate keyed on "no writing
    # segment named a path", which such a target satisfies -- so the
    # heredoc fallback fired and recovered the echoed filenames after all,
    # reopening the hole the previous round claimed to close.
    ([use(THREE_FILE_PATCH, "t1"), result(TB, "t1"),
      use('echo "fixed memories/gh-cli.md CLAUDE.md '
          'skills/use-math-macros/SKILL.md" | tee log', "t2"),
      result("", "t2")], True,
     "an echoed summary piped to an EXTENSIONLESS target still warns"),
    ([use(THREE_FILE_PATCH, "t1"), result(TB, "t1"),
      use('echo "all fixed" | tee /dev/null', "t2"), result("", "t2")], True,
     "an echoed summary piped to /dev/null still warns"),

    # R6-D2: `sed -i 's/a/b/'` must not read as a path. Requiring a file
    # extension keeps the substitution expression out of the target set, so
    # a correct re-application with DIFFERENT replacement text still counts.
    ([use("sed -i 's/a/b/' file1.md; sed -i 's/c/d/' file2.md", "t1"),
      result(TB, "t1"),
      use("sed -i 's/x/y/' file1.md; sed -i 's/p/q/' file2.md", "t2"),
      result("", "t2")], False,
     "a sed pair re-applied with new replacement text clears it"),

    # R2-F2: `git` is in READ_ONLY, and nothing exercised that membership.
    ([use('git log --grep=".write(" --oneline', "t1"), result(TB, "t1")],
     False, "a git command matching a write pattern does not warn"),

    # R2-F3: `tee` is a WRITES member with no case behind it.
    ([use("cmd | tee out.txt", "t1"), result(TB, "t1")], True,
     "a tee that raised warns"),

    # F3: the window closes on a commit that LANDED, not on the attempt. A
    # rejected commit leaves the partial patch exactly as unresolved.
    ([use(PATCH_CMD, "t1"), result(TB, "t1"),
      use(COMMIT, "t2"),
      result("pre-commit hook refused: lint failed\n", "t2", is_error=True)],
     True, "a REJECTED commit does not close the window"),
]


def run(events, commit_cmd=COMMIT, env=None, path=None, tool="Bash",
        payload_key="command"):
    keep = path is not None
    if not keep:
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
    with open(path, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        env = env or dict(os.environ, TMPDIR=tempfile.mkdtemp())
        ti = {payload_key: COMMIT if commit_cmd is None else commit_cmd}
        payload = json.dumps({
            "transcript_path": path,
            "tool_name": tool,
            "tool_input": ti,
        })
        r = subprocess.run([sys.executable, HOOK], input=payload,
                           capture_output=True, text=True, env=env)
        # Must never block: a partial patch is not decidable, only suggestive.
        assert '"permissionDecision"' not in r.stdout, "guard must never block"
        assert '"decision": "block"' not in r.stdout, "guard must never block"
        if not r.stdout.strip():
            return False
        out = json.loads(r.stdout)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        return "flag-aborted-patch-script" in ctx
    finally:
        if not keep:
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

    # F1: argv-based commit detection. `\b` sits between `commit` and `-`,
    # so a regex scan matches `git commit-tree`; and a quoted mention in an
    # echo is not a commit at all. Both must be silent.
    ev = [use(PATCH_CMD, "t1"), result(TB, "t1")]
    for cc, label in [
        ("git commit-tree $(git write-tree) -p HEAD -m m",
         "git commit-tree is not git commit"),
        ('echo "never run git commit without tests"',
         "an echo mentioning git commit is not a commit"),
        ("git commit-graph write", "git commit-graph write is not a commit"),
    ]:
        if not run(ev, commit_cmd=cc):
            print(f"PASS: {label}"); passes += 1
        else:
            print(f"FAIL: {label}"); failures += 1

    # R2-F4: the commit's OWN result text is not re-examined as a write.
    # Without the `continue` after the commit-result branch, a rejected
    # commit whose message quotes a write pattern falls through and is
    # re-registered as a pending traceback against its own command.
    # The commit command must itself match WRITES for the fallthrough to be
    # reachable at all -- a bare `git commit` does not, since `git` is in
    # READ_ONLY. Piping it through `tee` (a real habit when capturing commit
    # output) is the shape that exposes it.
    ev_ct = [use(COMMIT + " | tee /tmp/commit.log", "t1"),
             result("error: hook refused; the file calls .write( directly\n"
                    + TB, "t1", is_error=True)]
    if not run(ev_ct):
        print("PASS: a commit's own result text is not read as a write")
        passes += 1
    else:
        print("FAIL: commit result fell through into the write check")
        failures += 1

    # R4: main() has its OWN command-extraction fallback for the incoming
    # commit's tool_input, separate from _command()'s for the historical
    # scan. The `script`-key case below exercises only the latter, so this
    # covers the former -- removing either clause must fail something.
    for key in ("CommandLine", "cmd", "script"):
        if run([use(PATCH_CMD, "t1"), result(TB, "t1")],
               commit_cmd=None, payload_key=key):
            print(f"PASS: main() reads the commit command under `{key}`")
            passes += 1
        else:
            print(f"FAIL: main() missed the commit command under `{key}`")
            failures += 1

    # F4: some harness shapes carry the command under `script` rather than
    # `command`. Every sibling hook reads that fallback; without a case for
    # it, dropping it here is an undetectable mutation.
    if run([use(PATCH_CMD, "t1", key="script"), result(TB, "t1")]):
        print("PASS: reads a command carried under `script`"); passes += 1
    else:
        print("FAIL: missed a command carried under `script`"); failures += 1

    # F5: two DISTINCT tracebacks in one transcript need distinct sentinels.
    # Without tb_at in the key, the first suppresses the warning for the
    # second -- silently, and undetectably by any other case here.
    env2 = dict(os.environ, TMPDIR=tempfile.mkdtemp())
    fd, shared2 = tempfile.mkstemp(suffix=".jsonl"); os.close(fd)
    first_tb = [use(PATCH_CMD, "t1"), result(TB, "t1")]
    # Same transcript, grown: the earlier traceback is resolved by a clean
    # write and a landed commit, then a SECOND, different traceback occurs.
    second_tb = first_tb + [
        use(PATCH_CMD, "t2"), result("ok\n", "t2"),
        use(COMMIT, "t3"), result("[main abc] msg\n", "t3"),
        use("sed -i 's/a/b/' other.md", "t4"), result(TB, "t4"),
    ]
    a = run(first_tb, env=env2, path=shared2)
    b = run(second_tb, env=env2, path=shared2)
    os.unlink(shared2)
    if a and b:
        print("PASS: a second distinct traceback warns again"); passes += 1
    else:
        print(f"FAIL: second traceback suppressed (first={a}, second={b})")
        failures += 1

    # Only fires on the Bash tool. Without this case, deleting the
    # tool_name gate is an undetectable mutation: every other case passes
    # tool_name="Bash", so nothing exercises the non-Bash branch.
    if not run([use(PATCH_CMD, "t1"), result(TB, "t1")], tool="Edit"):
        print("PASS: does not fire on a non-Bash tool"); passes += 1
    else:
        print("FAIL: fired on a non-Bash tool"); failures += 1

    # Only fires on a commit: the same transcript with a non-commit command
    # is silent, which is what keeps it out of the way of ordinary work.
    if not run([use(PATCH_CMD, "t1"), result(TB, "t1")],
               commit_cmd="git status --short"):
        print("PASS: does not fire on a non-commit command"); passes += 1
    else:
        print("FAIL: fired on a non-commit command"); failures += 1

    # Once-per-traceback sentinel: a second commit attempt is silent.
    env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
    ev = [use(PATCH_CMD, "t1"), result(TB, "t1")]
    # Same transcript PATH both times: the sentinel is keyed on it, so a
    # fresh temp file per call would test nothing.
    fd, shared = tempfile.mkstemp(suffix=".jsonl"); os.close(fd)
    first = run(ev, env=env, path=shared)
    second = run(ev, env=env, path=shared)
    os.unlink(shared)
    if first and not second:
        print("PASS: warns once per traceback"); passes += 1
    else:
        print(f"FAIL: sentinel (first={first}, second={second})"); failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
