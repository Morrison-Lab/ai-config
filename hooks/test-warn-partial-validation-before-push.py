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
        transcript_path=None, cwd=REPO, env=None, tool_name="Bash",
        agent_id=None):
    """Return (partial_note_fired, payload_or_none); the no-run note does
    not set the flag (use nudged()). Raises on a crashed hook."""
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
        if agent_id:
            payload["agent_id"] = agent_id
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
        parsed = json.loads(out)
        return _context(parsed).startswith(PARTIAL_LEAD), parsed
    finally:
        if made:
            os.unlink(made)


# `run()[0]` is True only for the partial note, so a positive case proves a
# checker was COUNTED; "not counted" is `nudged()` (#3533), "nothing" `silent()`.
PARTIAL_LEAD = "This session ran "
NO_RUN_LEAD = "This session has not run "


def _context(out):
    return ((out or {}).get("hookSpecificOutput") or {}).get(
        "additionalContext", "")


def nudged(*args, **kwargs):
    """True when the hook's context is the no-run note."""
    _, out = run(*args, **kwargs)
    return _context(out).startswith(NO_RUN_LEAD)


def silent(*args, **kwargs):
    """True when the hook printed nothing at all."""
    _, out = run(*args, **kwargs)
    return out is None


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
          nudged(PUSH,
                  ['grep -rn "scripts/check-ascii-punctuation.py" README.md']))
    check("a direct (non-interpreter) checker invocation still counts",
          run(PUSH, ["./scripts/check-links.py"])[0])
    check("an interpreter flag before the script does not hide it",
          run(PUSH, ["python3 -u scripts/check-links.py"])[0])

    # --- the ways it must stay silent ------------------------------------
    check("silent once the derived sweep has run",
          silent(PUSH, [CHECKER, DERIVED]))
    check("silent when the sweep ran BEFORE the checkers, not only after",
          silent(PUSH, [DERIVED, CHECKER]))
    check("warns with the no-run note when nothing ran at all (#3533)",
          nudged(PUSH, ["git status", "ls"]))
    _, out = run(PUSH, [])
    check("...and it names the --changed run as the command to use",
          "run-local-validation.py --changed" in _context(out))
    check("...and tells the operator too",
          "--changed" in ((out or {}).get("systemMessage") or ""))
    check("the partial note names the --changed run as well",
          "run-local-validation.py --changed"
          in _context(run(PUSH, [CHECKER])[1]))
    check("silent with no checker once the sweep has run",
          silent(PUSH, ["git status", DERIVED]))
    check("silent after the recommended --changed spelling",
          silent(PUSH, ["python3 scripts/run-local-validation.py --changed"]))
    for args in ("--changed 2>&1 | tail -40", "--base origin/main --changed",
                 "--only x", "--list"):
        check("a run with " + args + " counts as the sweep (#5428)",
              silent(PUSH, ["python3 scripts/run-local-validation.py " + args]))
    sweep = "python3 scripts/run-local-validation.py --changed"
    # The live transcript already holds the push's own command at PreToolUse.
    check("a sweep in the push's own command is credited",
          silent(sweep + " && " + PUSH, [sweep + " && " + PUSH]))
    check("...in either order, a documented limit",
          silent(PUSH + " && " + sweep, [PUSH + " && " + sweep]))
    check("...where a push before the sweep is still a push",
          nudged(PUSH + " && " + sweep, ["git status"]))
    heredoc = "git commit -F - <<'EOF'\n    " + sweep + "\nEOF\n" + PUSH
    check("...but not one quoted in a heredoc body", nudged(heredoc, [heredoc]))
    check("silent on a command that is not a push",
          silent("git status", [CHECKER]))
    check("silent on a commit, which is not a push",
          silent("git commit -m x", [CHECKER]))
    check("silent on a word merely containing push",
          silent("git log --grep=push", [CHECKER]))
    check("silent on prose about pushing inside a commit message",
          silent('git commit -m "please push later"', [CHECKER]))
    check("silent in a repo with no run-local-validation.py to point at",
          silent(PUSH, [CHECKER], cwd=tempfile.gettempdir()))
    check("...and the no-run note stays silent there too",
          silent(PUSH, [], cwd=tempfile.gettempdir()))

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
          silent(PUSH, [CHECKER,
                         'bash -c "python3 scripts/run-local-validation.py"']))
    check("...and via uv run",
          silent(PUSH, [CHECKER, "uv run scripts/run-local-validation.py"]))
    check("...and by absolute path",
          silent(PUSH, [CHECKER,
                         "python3 /repo/scripts/run-local-validation.py"]))
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
              nudged(PUSH, [reader]))

    # THE severe case: a runner NAMED as an argument to a reader. A Python
    # file's own text contains "python3" constantly, so this is ordinary.
    check("grep python3 <derivation> does not silence the hook",
          run(PUSH, [CHECKER,
                     "grep python3 scripts/run-local-validation.py"])[0])
    check("...and does not credit a checker either",
          nudged(PUSH, ["grep python3 scripts/check-links.py"]))

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
    open(os.path.join(nest, "scripts", "run-local-validation.py"), "w", encoding="utf-8").close()
    inner = os.path.join(nest, "vendor", "other")
    os.makedirs(inner)
    open(os.path.join(inner, ".git"), "w", encoding="utf-8").close()
    check("fires in the outer repo that has the script",
          run(PUSH, [CHECKER], cwd=nest)[0])
    check("...and NOT in a nested repo that does not",
          silent(PUSH, [CHECKER], cwd=inner))

    # A BARE repo has no `.git` entry at all, so the boundary test has to
    # recognize its layout directly.
    bare = os.path.join(nest, "mirror.git")
    os.makedirs(os.path.join(bare, "objects"))
    os.makedirs(os.path.join(bare, "refs"))
    open(os.path.join(bare, "HEAD"), "w", encoding="utf-8").close()
    check("...nor in a nested BARE repo",
          silent(PUSH, [CHECKER], cwd=os.path.join(bare, "refs")))

    # --- the tool_name gate ------------------------------------------------
    for name in ("Bash", "bash", "run_command", "execute_command", "terminal",
                 "shell", "PowerShell", ""):
        check("accepts tool_name " + (name or "(empty)"),
              run(PUSH, [CHECKER], tool_name=name)[0])
    check("ignores a tool that carries no shell command",
          silent(PUSH, [CHECKER], tool_name="Read"))

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
          nudged(PUSH, [CHECKER], sidechain=True))
    check("silent on a push inside a subagent when nothing ran",
          silent(PUSH, ["ls"], agent_id="abc123"))
    check("...nor the partial note, built from the parent's checkers",
          silent(PUSH, [CHECKER], agent_id="abc123"))
    check("an Antigravity-shaped transcript is read, not silently skipped",
          run(PUSH, [CHECKER], antigravity=True)[0])
    check("...and its derived sweep silences the hook the same way",
          silent(PUSH, [CHECKER, DERIVED], antigravity=True))

    fired, out = run(PUSH, [CHECKER], env={"ANTIGRAVITY_AGENT": "1"})
    check("under ANTIGRAVITY_AGENT the context is still emitted",
          fired and bool(((out or {}).get("hookSpecificOutput") or {})
                         .get("additionalContext", "").strip()))
    check("...and systemMessage is omitted, which that harness requires",
          fired and "systemMessage" not in (out or {}))
    _, out = run(PUSH, ["ls"], env={"ANTIGRAVITY_AGENT": "1"})
    check("...and the no-run note keeps its context and drops systemMessage",
          _context(out).startswith(NO_RUN_LEAD)
          and "systemMessage" not in (out or {}))

    # --- the documented limit, pinned rather than discovered --------------
    # The FIRST version of this pin re-ran the same call as "silent once the
    # derived sweep has run" with the same cwd, so it could not fail
    # differently and pinned nothing. The gap is about the push happening in a
    # DIFFERENT repository from the sweep, so the test has to supply one.
    other = tempfile.mkdtemp()
    os.makedirs(os.path.join(other, "scripts"))
    open(os.path.join(other, "scripts", "run-local-validation.py"), "w", encoding="utf-8").close()
    open(os.path.join(other, ".git"), "w", encoding="utf-8").close()
    check("a sweep recorded anywhere silences a push from ANOTHER repo (#3698)",
          silent(PUSH, [CHECKER, DERIVED], cwd=other))
    check("...and that repo would otherwise be warned",
          run(PUSH, [CHECKER], cwd=other)[0])

    # --- degraded inputs fail open and silent -----------------------------
    check("silent when the transcript path does not exist",
          silent(PUSH, [], transcript_path="/nonexistent/path.jsonl"))

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
