#!/usr/bin/env python3
"""Tests for hooks/warn-partial-validation-before-push.py.

Every case drives the hook the way the harness does -- a JSON payload on
stdin, a real transcript file on disk -- rather than calling `scan` directly,
so the payload shape is part of what is pinned. `memories/claude-code-hooks.md`
records a probe that read only stdout and so could not tell an allow from a
crash; the runner here reads the EXIT STATUS first and fails loudly on a
non-zero one before interpreting anything.

The `cwd` handed to the hook is this repository, because the hook is scoped to
a checkout that actually has `scripts/run-local-validation.py`. One case
deliberately points it elsewhere to pin that gate.
"""
import json
import os
import subprocess
import sys
import tempfile

HOOKS_DIR = os.path.dirname(os.path.realpath(__file__))
HOOK = os.path.join(HOOKS_DIR, "warn-partial-validation-before-push.py")
REPO = os.path.dirname(HOOKS_DIR)

PASSED = []
FAILED = []


def transcript(commands, sidechain=False, antigravity=False):
    """Write a transcript whose records carry `commands`."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for cmd in commands:
            if antigravity:
                rec = {
                    "type": "GENERIC",
                    "source": "MODEL",
                    "tool_calls": [
                        {"name": "run_command",
                         "function": {"arguments": json.dumps({"command": cmd})}},
                    ],
                }
            else:
                rec = {
                    "type": "assistant",
                    "isSidechain": sidechain,
                    "message": {"content": [
                        {"type": "tool_use", "name": "Bash",
                         "input": {"command": cmd}},
                    ]},
                }
            fh.write(json.dumps(rec) + "\n")
    return path


def run(command, commands, sidechain=False, antigravity=False,
        transcript_path=None, cwd=REPO, env=None, tool_name="Bash"):
    """Return (fired, payload_or_none). Raises on a crashed hook."""
    path = transcript_path
    made = None
    if path is None:
        made = path = transcript(commands, sidechain=sidechain,
                                 antigravity=antigravity)
    try:
        payload = {
            "tool_name": tool_name,
            "tool_input": {"command": command},
            "transcript_path": path,
            "cwd": cwd,
        }
        child_env = dict(os.environ)
        child_env.pop("ANTIGRAVITY_AGENT", None)
        child_env.update(env or {})
        proc = subprocess.run(
            [sys.executable, HOOK], input=json.dumps(payload),
            capture_output=True, text=True, env=child_env,
        )
        if proc.returncode != 0:
            raise AssertionError(
                "FATAL: hook exited %s on %r\nstderr: %s"
                % (proc.returncode, command, proc.stderr))
        out = proc.stdout.strip()
        if not out:
            return False, None
        return True, json.loads(out)
    finally:
        if made:
            os.unlink(made)


def check(label, cond):
    (PASSED if cond else FAILED).append(label)
    print(("PASS: " if cond else "FAIL: ") + label)


CHECKER = "python3 scripts/check-ascii-punctuation.py"
CHECKER2 = "python3 scripts/check-links.py"
DERIVED = "python3 scripts/run-local-validation.py --base origin/main"
PUSH = "git push origin my-branch"


def main():
    # --- the case the hook exists for ------------------------------------
    fired, out = run(PUSH, [CHECKER, CHECKER2])
    check("warns on a push after hand-run checkers only", fired)
    ctx = ((out or {}).get("hookSpecificOutput") or {}).get("additionalContext", "")
    check("...and the warning is surfaced as additionalContext",
          isinstance(ctx, str) and bool(ctx.strip()))
    check("...and as a systemMessage the operator sees",
          bool(((out or {}).get("systemMessage") or "").strip()))
    check("...and names run-local-validation.py in the context",
          "run-local-validation.py" in ctx)
    check("...and names a checker it actually saw",
          "check-ascii-punctuation.py" in ctx)
    check("...and declares the right event",
          ((out or {}).get("hookSpecificOutput") or {}).get("hookEventName")
          == "PreToolUse")

    # --- COMMAND POSITION, not substring ---------------------------------
    # Both directions were wrong in the first cut: a command that merely NAMED
    # the derivation silenced the guard, and one that merely named a checker
    # counted as having run it.
    check("a grep NAMING the derivation does not count as having run it",
          run(PUSH, [CHECKER, 'grep -r "run-local-validation.py" memories/'])[0])
    # `cat hooks/warn-partial-validation-before-push.py` was the first spelling
    # here and was VACUOUS: that command's text never contains the derivation's
    # own name, so it passed with the substring bug present. Paging the
    # derivation's source does contain it, and fails under that mutation.
    check("...nor does paging the derivation's own source",
          run(PUSH, [CHECKER,
                     "sed -n '1,50p' scripts/run-local-validation.py"])[0])
    check("a grep NAMING a checker does not count as having run it",
          not run(PUSH,
                  ['grep -rn "scripts/check-ascii-punctuation.py" README.md'])[0])
    check("a direct (non-interpreter) checker invocation still counts",
          run(PUSH, ["./scripts/check-links.py"])[0])
    check("an interpreter flag before the script does not hide it",
          run(PUSH, ["python3 -u scripts/check-links.py"])[0])

    # --- the ways it must stay silent ------------------------------------
    check("silent once the derived sweep has run",
          not run(PUSH, [CHECKER, DERIVED])[0])
    check("silent when the sweep ran BEFORE the checkers, not only after",
          not run(PUSH, [DERIVED, CHECKER])[0])
    check("silent when no checker ran at all (a different failure)",
          not run(PUSH, ["git status", "ls"])[0])
    check("silent on a command that is not a push",
          not run("git status", [CHECKER])[0])
    check("silent on a commit, which is not a push",
          not run("git commit -m x", [CHECKER])[0])
    check("silent on a word merely containing push",
          not run("git log --grep=push", [CHECKER])[0])
    check("silent on prose about pushing inside a commit message",
          not run('git commit -m "please push later"', [CHECKER])[0])
    check("silent in a repo with no run-local-validation.py to point at",
          not run(PUSH, [CHECKER], cwd=tempfile.gettempdir())[0])

    # --- wrappers hiding the real program --------------------------------
    # Each of these is a GENUINE run of a checker. Missing one makes the hook
    # nag a session that did the work, which erodes trust faster than a miss.
    for spelling, label in (
        ("uv run scripts/check-links.py", "uv run"),
        ("poetry run scripts/check-links.py", "poetry run"),
        ('bash -c "python3 scripts/check-links.py"', "bash -c"),
        ("env python3 scripts/check-links.py", "env"),
        ("python3 -u scripts/check-links.py", "an interpreter flag"),
        ("./scripts/check-links.py", "a direct exec"),
        ("make check && python3 scripts/check-links.py", "a chained command"),
    ):
        check("a checker run via " + label + " counts as run",
              run(PUSH, [spelling])[0] is True)

    # The ACCEPTED cost of requiring the runner in command position. Each of
    # these genuinely runs the sweep and is not credited, so the hook warns
    # when it need not have. Pinned rather than left implicit: the alternative
    # -- accepting a runner anywhere earlier in the argv -- let
    # `grep python3 scripts/run-local-validation.py` silence the guard.
    for spelling, label in (
        ("timeout 60 python3 scripts/run-local-validation.py", "timeout"),
        ("sudo -u me python3 scripts/run-local-validation.py", "sudo -u"),
        ("xargs python3 scripts/run-local-validation.py", "xargs"),
        ("make validate", "make"),
        ("$PY scripts/run-local-validation.py", "a runner in a variable"),
    ):
        check("the sweep behind " + label + " is NOT credited (accepted cost)",
              run(PUSH, [CHECKER, spelling])[0] is True)
    # Inside `-c`, a RUN and a READ can sit in one token. Without expansion
    # the whole string is opaque and its basename is whatever came last, so
    # the `cat` below was counted as a run of check-y.
    fired, out = run(PUSH, [
        'bash -c "python3 scripts/check-x.py && cat scripts/check-y.py"'])
    ctx = ((out or {}).get("hookSpecificOutput") or {}).get("additionalContext", "")
    check("inside -c, the run counts", fired and "check-x.py" in ctx)
    check("...and the read beside it does not", fired and "check-y.py" not in ctx)

    check("the sweep run via bash -c silences the hook",
          not run(PUSH, [CHECKER,
                         'bash -c "python3 scripts/run-local-validation.py"'])[0])
    check("...and via uv run",
          not run(PUSH, [CHECKER, "uv run scripts/run-local-validation.py"])[0])
    check("...and by absolute path",
          not run(PUSH, [CHECKER,
                         "python3 /repo/scripts/run-local-validation.py"])[0])
    check("a push wrapped in bash -c is still seen as a push",
          run('bash -c "git push origin main"', [CHECKER])[0])

    # --- readers do not count, whatever they are reading -----------------
    for reader, label in (
        ('grep -rn "scripts/check-links.py" README.md', "grep"),
        ("cat scripts/check-links.py", "cat"),
        ("sed -n '1,50p' scripts/check-links.py", "sed"),
        ("git log --oneline scripts/check-links.py", "git log"),
        # A blacklist of readers never listed these, so each SILENCED the
        # guard. A whitelist of runners rejects them without knowing them.
        ("flake8 scripts/check-links.py", "an unlisted linter"),
        ("pylint --rcfile=x.cfg scripts/check-links.py", "pylint"),
        ("some-linter --file=scripts/check-links.py", "a --file= argument"),
    ):
        check("a checker merely READ by " + label + " does not count",
              not run(PUSH, [reader])[0])

    # THE severe case: a runner NAMED as an argument to a reader. A Python
    # file's own text contains "python3" constantly, so this is ordinary.
    check("grep python3 <derivation> does not silence the hook",
          run(PUSH, [CHECKER,
                     "grep python3 scripts/run-local-validation.py"])[0])
    check("...and does not credit a checker either",
          not run(PUSH, ["grep python3 scripts/check-links.py"])[0])

    # An interpreter running CODE or a MODULE is not running this file.
    for spelling, label in (
        ("python3 -c scripts/run-local-validation.py", "-c with a bare path"),
        ('python3 -c "print(1)" scripts/run-local-validation.py', "-c passthrough"),
        ("python3 -m pytest scripts/run-local-validation.py", "-m"),
        # CPython accepts the flag ATTACHED to its argument (`python3 -mpip`),
        # and exact-token matching missed that spelling entirely.
        ("python3 -munittest scripts/run-local-validation.py", "an attached -m"),
        ("python3 -cpass scripts/run-local-validation.py", "an attached -c"),
        # The interpreter prints and exits; the file argument is never reached.
        ("python3 --version scripts/run-local-validation.py", "--version"),
        ("python3 -V scripts/run-local-validation.py", "-V"),
        ("python3 --help scripts/run-local-validation.py", "--help"),
        ("python3 --python=scripts/run-local-validation.py other.py",
         "a --flag= value"),
    ):
        check("the sweep named via " + label + " does not silence the hook",
              run(PUSH, [CHECKER, spelling])[0])

    # The severe direction: a redirect that OVERWRITES the derivation must
    # never read as having run it.
    check("a redirect onto the derivation does not silence the hook",
          run(PUSH, [CHECKER, "echo oops > scripts/run-local-validation.py"])[0])
    check("...nor does a linter pointed at it",
          run(PUSH, [CHECKER, "flake8 scripts/run-local-validation.py"])[0])

    # --- the cwd gate walks up to the repo root ---------------------------
    check("fires from a SUBDIRECTORY of the protected repo",
          run(PUSH, [CHECKER], cwd=os.path.join(REPO, "hooks"))[0])
    check("...and from a deeper one",
          run(PUSH, [CHECKER], cwd=os.path.join(REPO, "skills", "ums"))[0])

    # A nested clone must not inherit its parent's answer.
    nest = tempfile.mkdtemp()
    os.makedirs(os.path.join(nest, "scripts"))
    open(os.path.join(nest, "scripts", "run-local-validation.py"), "w").close()
    inner = os.path.join(nest, "vendor", "other")
    os.makedirs(inner)
    open(os.path.join(inner, ".git"), "w").close()
    check("fires in the outer repo that has the script",
          run(PUSH, [CHECKER], cwd=nest)[0])
    check("...and NOT in a nested repo that does not",
          not run(PUSH, [CHECKER], cwd=inner)[0])

    # A BARE repo has no `.git` entry at all, so the boundary test has to
    # recognize its layout directly.
    bare = os.path.join(nest, "mirror.git")
    os.makedirs(os.path.join(bare, "objects"))
    os.makedirs(os.path.join(bare, "refs"))
    open(os.path.join(bare, "HEAD"), "w").close()
    check("...nor in a nested BARE repo",
          not run(PUSH, [CHECKER], cwd=os.path.join(bare, "refs"))[0])

    # --- the tool_name gate ------------------------------------------------
    for name in ("Bash", "bash", "run_command", "execute_command", "terminal",
                 "shell", "PowerShell", ""):
        check("accepts tool_name " + (name or "(empty)"),
              run(PUSH, [CHECKER], tool_name=name)[0])
    check("ignores a tool that carries no shell command",
          not run(PUSH, [CHECKER], tool_name="Read")[0])

    # --- push spellings that must still fire -----------------------------
    for spelling in (
        "git push",
        "git push -u origin feature",
        "git push --force-with-lease --force-if-includes origin f",
        "git -C /some/worktree push origin main",
        "git --git-dir /repo/dotgit push origin main",
        "git -c user.name=x push",
        "git --no-pager push",
        "cd /tmp && git push origin main",
        "GIT_DIR=/x git push origin main",
    ):
        fired, _ = run(spelling, [CHECKER])
        check("fires on: " + spelling, fired)

    # --- scope ------------------------------------------------------------
    check("a subagent's checkers do not count as this session's habit",
          not run(PUSH, [CHECKER], sidechain=True)[0])
    check("an Antigravity-shaped transcript is read, not silently skipped",
          run(PUSH, [CHECKER], antigravity=True)[0])
    check("...and its derived sweep silences the hook the same way",
          not run(PUSH, [CHECKER, DERIVED], antigravity=True)[0])

    fired, out = run(PUSH, [CHECKER], env={"ANTIGRAVITY_AGENT": "1"})
    check("under ANTIGRAVITY_AGENT the context is still emitted",
          fired and bool(((out or {}).get("hookSpecificOutput") or {})
                         .get("additionalContext", "").strip()))
    check("...and systemMessage is omitted, which that harness requires",
          fired and "systemMessage" not in (out or {}))

    # --- the documented limit, pinned rather than discovered --------------
    # The FIRST version of this pin re-ran the same call as "silent once the
    # derived sweep has run" with the same cwd, so it could not fail
    # differently and pinned nothing. The gap is about the push happening in a
    # DIFFERENT repository from the sweep, so the test has to supply one.
    other = tempfile.mkdtemp()
    os.makedirs(os.path.join(other, "scripts"))
    open(os.path.join(other, "scripts", "run-local-validation.py"), "w").close()
    open(os.path.join(other, ".git"), "w").close()
    check("a sweep recorded anywhere silences a push from ANOTHER repo (#3698)",
          not run(PUSH, [CHECKER, DERIVED], cwd=other)[0])
    check("...and that repo would otherwise be warned",
          run(PUSH, [CHECKER], cwd=other)[0])

    # --- degraded inputs fail open and silent -----------------------------
    check("silent when the transcript path does not exist",
          not run(PUSH, [], transcript_path="/nonexistent/path.jsonl")[0])

    proc = subprocess.run([sys.executable, HOOK], input="not json",
                          capture_output=True, text=True)
    check("malformed stdin exits 0 with no output",
          proc.returncode == 0 and not proc.stdout.strip())

    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write("{not json\n")
        fh.write(json.dumps({
            "type": "assistant",
            "message": {"content": [
                {"type": "tool_use", "name": "Bash",
                 "input": {"command": CHECKER}}]},
        }) + "\n")
    try:
        fired, _ = run(PUSH, [], transcript_path=path)
        check("an unparseable transcript line is skipped, not fatal", fired)
    finally:
        os.unlink(path)

    # --- negative control -------------------------------------------------
    # A suite that only ever saw one answer would agree with a hook that
    # always fired, or never did.
    check("negative control: both outcomes were exercised",
          any(lbl.startswith(("warns on", "fires on")) for lbl in PASSED)
          and any(lbl.startswith("silent") for lbl in PASSED))

    print("\n%d passed, %d failed" % (len(PASSED), len(FAILED)))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
