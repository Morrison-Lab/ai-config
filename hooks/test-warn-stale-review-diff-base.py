"""Test the warn-stale-review-diff-base hook.

Feeds the hook a PreToolUse payload per case. The hook reads no transcript --
it has no session-level discharge by design -- so a case is just a tool name,
a tool input, and a cwd.

A case is WARN when the hook emits a payload carrying BOTH an
`additionalContext` (the model's channel) and a `systemMessage` (the user's).
The assertion is on payload SHAPE rather than on `bool(stdout)`: a hook that
printed prose, that dropped one channel, or that emitted a block-shaped
`decision` would satisfy a truthiness check while being wrong in three
different directions.

Run:  python3 hooks/test-warn-stale-review-diff-base.py \
          hooks/warn-stale-review-diff-base.py
"""

import io
import json
import os
import shutil
import subprocess
import sys
import time
import tempfile

if len(sys.argv) < 2:
    sys.exit(f"Usage: python3 {sys.argv[0]} <path-to-hook>")
HOOK = sys.argv[1]

# The hook consults `git remote` to classify a slash-bearing base, so the cwd
# must be a real repository for those cases to exercise the real list.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(HOOK)))

if not os.path.isfile(HOOK):
    sys.exit(
        f"FATAL: hook not found at {HOOK} -- a missing file would otherwise "
        "read as 'silent' on every case and print a perfect pass"
    )


def run(command, tool_name="Bash", tool_input=None, timeout=None):
    """Run the hook on one payload; return WARN or silent.

    `timeout` exists so a case guarding against a RUNAWAY hook can fail
    promptly. Without it a regression does not fail the case at all --- it
    blocks until the hook finishes, surfacing as an unattributed CI hang
    rather than the named FAIL line the case is written to print.
    """
    if tool_input is None:
        tool_input = {"command": command}
    payload = {"tool_name": tool_name, "tool_input": tool_input,
               "cwd": REPO_ROOT}
    try:
        proc = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps(payload),
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT"

    if proc.returncode != 0:
        sys.exit(f"FATAL: hook exited {proc.returncode}\n{proc.stderr.strip()}")

    out = proc.stdout.strip()
    if not out:
        return "silent"

    try:
        parsed = json.loads(out)
    except ValueError:
        sys.exit(
            "FATAL: hook emitted non-JSON on stdout. A PreToolUse reminder "
            f"must emit a hookSpecificOutput payload.\n{out}"
        )
    if "decision" in parsed or "permissionDecision" in str(parsed):
        sys.exit(
            "FATAL: hook emitted a decision-shaped payload. This hook must "
            f"only ever add context, never block a tool call.\n{out}"
        )
    ctx = (parsed.get("hookSpecificOutput") or {}).get("additionalContext")
    if not isinstance(ctx, str) or not ctx.strip():
        sys.exit(
            "FATAL: hook emitted a payload with no additionalContext. Output "
            f"that is non-empty but unsurfaced is the failure mode.\n{out}"
        )
    if not isinstance(parsed.get("systemMessage"), str) or not parsed["systemMessage"].strip():
        sys.exit(
            "FATAL: hook emitted no systemMessage, so the reminder never "
            f"reaches the user who wrote the command.\n{out}"
        )
    if parsed["hookSpecificOutput"].get("hookEventName") != "PreToolUse":
        sys.exit(f"FATAL: wrong hookEventName in payload.\n{out}")
    return "WARN"


WARN_CASES = [
    ("git diff main...refs/remotes/origin/feature",
     "a DIFFERENT branch behind the fully-qualified spelling still warns, so "
     "the `refs/remotes/` arm is pinned in both directions"),
    ("git diff main...origin/feature",
     "an ordinary review diff whose HEAD is remote-tracking: the head says "
     "NOTHING about the base's freshness, and exempting it would blind the "
     "hook to the measured incident's own shape one fetch removed"),
    ("git diff main...origin/pr-98",
     "the measured incident verbatim, had pr-98 been fetched as a "
     "remote-tracking ref instead of a local branch"),
    ("git diff -C main...HEAD",
     "`-C` is find-copies and never takes a SEPARATE argument in `git diff` "
     "or `git log`, so listing it in VALUE_OPTIONS ate the real range "
     "(`-L` and `-O` genuinely do take one, and stay)"),
    ("git diff refs/heads/v1.2.0...HEAD",
     "a `refs/heads/` prefix is proof of a local branch, so the tag test must "
     "not see the stripped stem -- `refs/heads/v1.2.0` is a BRANCH"),
    ("git diff main...pr-98",
     "the measured case: a bare local base in a three-dot review range"),
    ("git diff main..pr-98",
     "the two-dot form is exposed the same way"),
    ("git diff develop...HEAD",
     "a default branch named something other than main"),
    ("git log main...feature/x --oneline",
     "git log takes a range too"),
    ("git merge-base main pr-98 && git diff main...pr-98",
     "a merge-base call does not itself resolve the base from a remote"),
    ("git diff feature/foo...HEAD",
     "a slash does not make a ref remote-tracking -- local branches carry one"),
    ("git diff release/2.0...HEAD",
     "a release branch is local too"),
    ("git diff refs/heads/main...HEAD",
     "an explicit local ref is still a local branch"),
    ("git diff --stat main...pr-98",
     "an option between the subcommand and the range"),
    ("git diff 123-fix...HEAD",
     "an issue-numbered branch is not a tag -- the commonest branch prefix in "
     "this corpus, and a bare-integer tag exemption would swallow it"),
    ("git diff 2026-08-01...HEAD",
     "a date-shaped name is likelier a branch than a tag"),
    ("git diff v2-rewrite...HEAD",
     "`v` plus an integer plus a word is a feature branch, not a version"),
    ("git diff v1...HEAD",
     "a version with no dot is not unambiguously a tag"),
    ("echo hi && git diff main...pr-98",
     "a command after `&&` is at a command position"),
    ("for b in x; do git diff main...pr-98; done",
     "a loop body is a command position -- the review-dispatch shape"),
    ("sudo git diff main...pr-98",
     "a wrapper word does not hide the command"),
    ("git diff 3.11...HEAD",
     "a bare two-component dotted name is the maintenance-branch convention, "
     "not unambiguously a tag"),
    ("git diff 2.0...HEAD",
     "same"),
    ("printf 'a\nb\n' && git diff main...pr-98",
     "a newline in a quoted argument does not stop a later real command "
     "position from firing"),
    ("git fetch origin && git diff main...pr-98",
     "a fetch in the same command line does not discharge: the hook keys on "
     "the ref named, not on freshness it cannot measure"),
]

SILENT_CASES = [
    ("git rev-list --count main..refs/remotes/origin/main",
     "the fully-qualified remote-tracking spelling of the freshness idiom: "
     "pins the `refs/remotes/` arm of `remote_tracking_branch`, which the "
     "base-side case cannot reach"),
    ("git rev-list --count refs/heads/main..origin/main",
     "and the fully-qualified LOCAL spelling: the comparison must normalize "
     "the base, or it warns on the very idiom it exempts"),
    ("git rev-list --count main~2..origin/main",
     "a revision suffix on the base is still that branch"),
    ("git diff main...origin/main",
     "same branch on both sides is a staleness measurement, not a review "
     "scope -- the ONLY shape the head exemption may cover"),
    ("git rev-list --count main..origin/main",
     "`<local>..<remote>` measures the local ref's staleness -- the idiom "
     "`post-merge` prescribes -- so the local ref is the measurement SUBJECT, "
     "not a review scope"),
    ("git log --oneline main..origin/main",
     "the same freshness idiom in its `log` spelling"),
    ("git diff $BASE...HEAD",
     "a shell expansion is not a ref: `$` sits outside the ref class, so the "
     "match sees a base named `BASE`, and warning here would fire on the "
     "NOTE's OWN recommended remediation"),
    ("git diff origin/main...HEAD",
     "a remote-tracking base is the correct form"),
    ("git diff refs/remotes/origin/main...HEAD",
     "an explicit remote-tracking ref"),
    ("git diff HEAD~1..HEAD",
     "a symbolic base cannot go stale"),
    ("git diff 6345e92...pr-98",
     "a raw SHA names one commit, not a moving branch"),
    ("git diff v1.2.0...v1.3.0",
     "version tags are immutable"),
    ("git diff 1.2.0...HEAD",
     "three components are unambiguous without a `v` prefix"),
    ("git diff v1.2...HEAD",
     "two components are, with one"),
    ("git diff --cached",
     "no range at all"),
    ("git diff DESCRIPTION",
     "a pathspec is not a range"),
    ("git rebase main",
     "rebase is not a range-reading subcommand"),
    ("echo 'git diff origin/<default-branch>...HEAD'",
     "a documentation placeholder must not match"),
    ("cat <<'EOF' > f.md\ngit diff main...pr-98\nEOF",
     "a heredoc body is file content, not a command"),
    ("git commit -m \"stop using git diff main...HEAD as the base\"",
     "a quoted mention is text the command carries, not a ref it reads"),
    ("grep -rn 'git diff main...pr-98' shared/",
     "grepping for the anti-pattern must not trip the hook that documents it"),
    ("gh pr comment 98 --body \"I ran git diff main...pr-98\"",
     "a PR comment body is quoted text"),
    ("gh pr comment 98 --body \"the base was local (git diff main...pr-98) so "
     "the scope grew\"",
     "a parenthesis inside quoted prose must not re-arm the anchor -- this is "
     "the comment a session writes when reporting this very rule"),
    ("git commit -m \"fix scope (git diff main...HEAD was wrong)\"",
     "same, in a commit message"),
    ("gh pr comment 98 --body \"fetch first, then git diff main...pr-98\"",
     "`then` in ordinary English must not re-arm the anchor"),
    ("gh issue comment 1 --body \"for each PR, do git diff main...HEAD\"",
     "nor `do`"),
    ("gh pr comment 98 --body \"run `git diff main...pr-98` to reproduce\"",
     "nor a backtick code span, which is how this corpus writes a command "
     "inside a comment body"),
    ("git commit -m 'see `git diff main...HEAD` for scope'",
     "same, in a commit message"),
    ('gh pr comment 98 --body "the scope was wrong.\n'
     'git diff main...pr-98 produced 53 files.\nfixed now"',
     "a newline INSIDE a quoted body is not a command position, even though a "
     "newline between commands is"),
    ('git commit -m "line one\ngit diff main...HEAD is wrong"',
     "same, in a multi-line commit message"),
    ("git log --grep main...HEAD",
     "a space-separated option value is not a range"),
    ("git diff v1.2.0-rc1...HEAD",
     "a recognized pre-release suffix is still a tag"),
    ("git diff origin/main...HEAD -- a.b..c.d",
     "a pathspec after `--` is not a range, and the base here is already right"),
    ("git log --grep=main...HEAD",
     "an option value is not a range"),
    ("git diff -...HEAD",
     "an option-shaped token is skipped before any ref classification"),
    ("git diff ~...HEAD",
     "a base with no alphanumeric reaches `is_local_branch_base` (it does not "
     "start with `-`) and names no ref: the guard `normalize_base` does NOT "
     "subsume, since `~` survives dot-stripping"),
]

BRIEF_WARN = (
    "Review the diff: git diff main...pr-98, applying the repo standards.",
    "an Agent brief carrying the same bare local base",
)
BRIEF_SILENT = (
    "Review the diff: git diff origin/main...pr-98.",
    "an Agent brief with a remote-tracking base",
)
# `github` is NOT a remote of this checkout, so this case is silent only
# because a brief unions FALLBACK_REMOTES in. Deleting that union leaves
# `origin/main` above silent either way, which is why that case cannot pin it.
BRIEF_SILENT_FALLBACK = (
    "Review the diff: git diff github/main...pr-98.",
    "a brief naming a remote this checkout lacks is still exempt, via the "
    "FALLBACK_REMOTES union (deleting the union must fail HERE)",
)

total = wrong = 0
print("--- expected WARN")
for cmd, desc in WARN_CASES:
    verdict = run(cmd)
    total += 1
    wrong += verdict != "WARN"
    print(f"{verdict:<7} {desc}")

print("\n--- expected silent")
for cmd, desc in SILENT_CASES:
    verdict = run(cmd)
    total += 1
    wrong += verdict != "silent"
    print(f"{verdict:<7} {desc}")

print("\n--- Agent briefs")
for prompt, desc, want in ((BRIEF_WARN[0], BRIEF_WARN[1], "WARN"),
                           (BRIEF_SILENT[0], BRIEF_SILENT[1], "silent"),
                           (BRIEF_SILENT_FALLBACK[0],
                            BRIEF_SILENT_FALLBACK[1], "silent")):
    verdict = run(None, tool_name="Agent",
                  tool_input={"prompt": prompt, "description": "review"})
    total += 1
    wrong += verdict != want
    print(f"{verdict:<7} {desc}")

# The command-position pattern once admitted 2^N parses over N option tokens
# when the overall match failed: n=34 took 8.4s against a 10s timeout.
#
# Time the PATTERN, in this process, rather than a hook subprocess. The
# Run the probe in a SUBPROCESS under a timeout. Timing it in-process cannot
# work: under the regression the search itself blocks for minutes, so the guard
# would hang rather than fail -- which is the very defect it exists to catch,
# merely relocated. A timeout converts the hang into a prompt, attributable
# failure. Timing the pattern alone (not the hook) keeps an unrelated stall in
# `git remote`, itself under a 5s timeout, from being misread as backtracking.
_PROBE = (
    "import re, sys, time\n"
    "ns = {}\n"
    "exec(compile(open(sys.argv[1], encoding='utf-8').read(), sys.argv[1],"
    " 'exec'), {'__name__': '_probe'}, ns)\n"
    "probe = 'git ' + '-a ' * 40 + 'nope main...HEAD'\n"
    "t = time.time()\n"
    "ns['RX_GIT_RANGE_CMD_SHELL'].search(probe)\n"
    "print(time.time() - t)\n"
)
try:
    _proc = subprocess.run([sys.executable, "-c", _PROBE, HOOK],
                           capture_output=True, text=True, timeout=15)
    _elapsed = float(_proc.stdout.strip())
    _ok = _elapsed < 1.0
    _detail = f"{_elapsed * 1000:.1f}ms"
except subprocess.TimeoutExpired:
    _ok = False
    _detail = "TIMED OUT -- catastrophic backtracking is back"
except (ValueError, KeyError) as _exc:
    _ok = False
    _detail = f"probe failed: {_exc}"
total += 1
wrong += not _ok
print(f"{'ok' if _ok else 'FAIL':<7} many option tokens before an unlisted "
      f"subcommand stay fast ({_detail})")

# And the end-to-end path must not hang: a runaway hook fails HERE, promptly.
_verdict = run("git " + "-a " * 40 + "nope main...HEAD", timeout=20)
total += 1
_ok = _verdict != "TIMEOUT"
wrong += not _ok
print(f"{'ok' if _ok else 'FAIL':<7} the same command completes end to end "
      "within 20s")

print("\n--- fail-open and environment")
# A type-confused `cwd` reaches `os.path.join` inside `main()` and is the
# cheapest way to force the broad handler the docstring advertises. Without it
# the "fails open everywhere" guarantee is unpinned by any test.
_proc = subprocess.run(
    [sys.executable, HOOK],
    input=json.dumps({"tool_name": "Bash",
                      "tool_input": {"command": "git diff main...HEAD"},
                      "cwd": 5}),
    capture_output=True, text=True,
)
total += 1
_ok = _proc.returncode == 0
wrong += not _ok
print(f"{'silent' if _ok else 'WARN':<7} a non-string cwd cannot break the tool "
      "(exit 0 from the broad handler)")

_proc = subprocess.run([sys.executable, HOOK, "--dry-run",
                        "git diff main...HEAD"], capture_output=True, text=True)
total += 1
_ok = _proc.returncode == 0 and "main" in _proc.stdout
wrong += not _ok
print(f"{'ok' if _ok else 'FAIL':<7} `--dry-run` names the base on stdout")
_proc = subprocess.run([sys.executable, HOOK], input="not json",
                       capture_output=True, text=True)
total += 1
_ok = _proc.returncode == 0 and not _proc.stdout.strip()
wrong += not _ok
print(f"{'silent' if _ok else 'WARN':<7} unparseable stdin fails open")

# A cwd that is not a directory falls back to FALLBACK_REMOTES, by way of the
# `FileNotFoundError` that `subprocess.run` raises for it. `origin` is in the
# fallback set, so it is exempt; `hc2-gitlab` is not, so it warns. Asserting
# both directions is what distinguishes a real fallback from an ambient read of
# whatever repository the hook process sits in -- a base of `main` would warn
# under any remote set and pin nothing.
for _base, _want in (("origin/main", "silent"), ("hc2-gitlab/main", "WARN")):
    _proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": f"git diff {_base}...HEAD"},
                          "cwd": "/nonexistent-path-for-this-test"}),
        capture_output=True, text=True,
    )
    total += 1
    _got = "WARN" if (_proc.returncode == 0 and _proc.stdout.strip()) else "silent"
    wrong += _got != _want
    print(f"{_got:<7} a nonexistent cwd falls back to the default remote names "
          f"({_base} -> {_want})")

# A fallback name must NOT be exempt in a repository whose real remote list
# omits it. Pinned against a scratch repo rather than this checkout, since a
# contributor who has run `git remote add fork ...` -- the convention the
# fallback set exists for -- would otherwise see a spurious local failure.
_forkless = tempfile.mkdtemp()
try:
    subprocess.run(["git", "init", "-q", _forkless], check=True,
                   capture_output=True)
    subprocess.run(["git", "-C", _forkless, "remote", "add", "origin",
                    "https://example.invalid/r.git"], check=True,
                   capture_output=True)
    _proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": "git diff fork/x...HEAD"},
                          "cwd": _forkless}),
        capture_output=True, text=True,
    )
    total += 1
    _ok = _proc.returncode == 0 and _proc.stdout.strip()
    wrong += not _ok
    print(f"{'WARN' if _ok else 'silent':<7} a fallback name is NOT exempt in "
          "a repo whose real remote list omits it")
finally:
    shutil.rmtree(_forkless, ignore_errors=True)

# A repository whose remote is named something other than `origin`. This pins
# that the real `git remote` output is consulted rather than a guessed set:
# `hc2-gitlab` is in no fallback list, so only a live read can exempt it.
# Both temp roots are created BEFORE the try, so the finally block cannot
# raise NameError over a `git init` failure and hide the real cause.
_scratch = tempfile.mkdtemp()
_home = tempfile.mkdtemp()
try:
    subprocess.run(["git", "init", "-q", _scratch], check=True,
                   capture_output=True)
    subprocess.run(["git", "-C", _scratch, "remote", "add", "hc2-gitlab",
                    "https://example.invalid/r.git"], check=True,
                   capture_output=True)

    # The same repository reachable as `~/repo`, for the expanduser case.
    # A platform without symlink privilege skips that one case loudly rather
    # than failing the suite.
    try:
        os.symlink(_scratch, os.path.join(_home, "repo"))
        _can_symlink = True
    except (OSError, NotImplementedError) as _exc:
        _can_symlink = False
        print(f"SKIP    expanduser case: cannot create a symlink ({_exc})")
    _proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"tool_name": "Bash",
                          "tool_input": {"command":
                                         "git diff hc2-gitlab/main...HEAD"},
                          "cwd": _scratch}),
        capture_output=True, text=True,
    )
    total += 1
    _ok = _proc.returncode == 0 and not _proc.stdout.strip()
    wrong += not _ok
    print(f"{'silent' if _ok else 'WARN':<7} a remote named neither `origin` "
          "nor anything in the fallback set is exempt, read from git itself")

    # The same repository reached through `git -C`, from a DIFFERENT cwd. The
    # classification must follow the repository the command targets.
    _proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"tool_name": "Bash",
                          "tool_input": {"command":
                                         f"git -C {_scratch} diff "
                                         "hc2-gitlab/main...HEAD"},
                          "cwd": REPO_ROOT}),
        capture_output=True, text=True,
    )
    total += 1
    _ok = _proc.returncode == 0 and not _proc.stdout.strip()
    wrong += not _ok
    print(f"{'silent' if _ok else 'WARN':<7} `git -C <path>` classifies against "
          "that repository's remotes, not the session's")
    # A quoted `-C` path containing spaces must still match, and must still
    # resolve. Both the option-scanning pattern and the `-C` capture used to
    # stop at the first space, and both degraded silently.
    _spaced = os.path.join(_scratch, "a dir with spaces")
    subprocess.run(["git", "init", "-q", _spaced], check=True,
                   capture_output=True)
    _proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"tool_name": "Bash",
                          "tool_input": {"command":
                                         f'git -C "{_spaced}" diff '
                                         "main...pr-98"},
                          "cwd": REPO_ROOT}),
        capture_output=True, text=True,
    )
    total += 1
    _ok = _proc.returncode == 0 and _proc.stdout.strip()
    wrong += not _ok
    print(f"{'WARN' if _ok else 'silent':<7} a quoted `-C` path containing "
          "spaces still matches")

    # `~` must be expanded before the path is tested, or the command is
    # classified against the session repository instead.
    if _can_symlink:
        _proc = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"tool_name": "Bash",
                              "tool_input": {"command":
                                             "git -C ~/repo diff "
                                             "hc2-gitlab/main...HEAD"},
                              "cwd": REPO_ROOT}),
            capture_output=True, text=True,
            env=dict(os.environ, HOME=_home),
        )
        total += 1
        _ok = _proc.returncode == 0 and not _proc.stdout.strip()
        wrong += not _ok
        print(f"{'silent' if _ok else 'WARN':<7} a `~` in a `-C` path is "
              "expanded")

    # A relative `-C` path resolves against the SESSION cwd, not the hook
    # process's. `hc2-gitlab` is exempt only if the right repo was read.
    _proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"tool_name": "Bash",
                          "tool_input": {"command":
                                         f"git -C {os.path.basename(_scratch)} "
                                         "diff hc2-gitlab/main...HEAD"},
                          "cwd": os.path.dirname(_scratch)}),
        capture_output=True, text=True,
    )
    total += 1
    _ok = _proc.returncode == 0 and not _proc.stdout.strip()
    wrong += not _ok
    print(f"{'silent' if _ok else 'WARN':<7} a relative `-C` path resolves "
          "against the session cwd")
finally:
    shutil.rmtree(_scratch, ignore_errors=True)
    shutil.rmtree(_home, ignore_errors=True)

print(f"\n{total - wrong}/{total} correct")
sys.exit(1 if wrong else 0)
