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

import json
import os
import shutil
import subprocess
import sys
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


def run(command, _unused=None, tool_name="Bash", tool_input=None):
    """Run the hook on one payload; return WARN or silent."""
    if tool_input is None:
        tool_input = {"command": command}
    payload = {"tool_name": tool_name, "tool_input": tool_input,
               "cwd": REPO_ROOT}
    proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True, text=True,
    )

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
    ("git fetch origin && git diff main...pr-98",
     "a fetch in the same command line does not discharge: the hook keys on "
     "the ref named, not on freshness it cannot measure"),
]

SILENT_CASES = [
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
    ("git diff origin/main...HEAD -- a.b..c.d",
     "a pathspec after `--` is not a range, and the base here is already right"),
    ("git log --grep=main...HEAD",
     "an option value is not a range"),
    ("git diff -...HEAD",
     "a base with no alphanumeric names no ref -- `-` is in the ref class and "
     "survives dot-stripping, so this is the guard `normalize_base` does NOT "
     "subsume"),
]

BRIEF_WARN = (
    "Review the diff: git diff main...pr-98, applying the repo standards.",
    "an Agent brief carrying the same bare local base",
)
BRIEF_SILENT = (
    "Review the diff: git diff origin/main...pr-98.",
    "an Agent brief with a remote-tracking base",
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
                           (BRIEF_SILENT[0], BRIEF_SILENT[1], "silent")):
    verdict = run(None, tool_name="Agent",
                  tool_input={"prompt": prompt, "description": "review"})
    total += 1
    wrong += verdict != want
    print(f"{verdict:<7} {desc}")

print("\n--- fail-open and environment")
_proc = subprocess.run([sys.executable, HOOK], input="not json",
                       capture_output=True, text=True)
total += 1
_ok = _proc.returncode == 0 and not _proc.stdout.strip()
wrong += not _ok
print(f"{'silent' if _ok else 'WARN':<7} unparseable stdin fails open")

# `git remote` is consulted only to classify a slash-bearing base. A cwd that
# is not a git repository must fall back rather than raise, and must still
# reach a verdict -- a silent failure here would read as a pass on every case.
_proc = subprocess.run(
    [sys.executable, HOOK],
    input=json.dumps({"tool_name": "Bash",
                      "tool_input": {"command": "git diff main...pr-98"},
                      "cwd": "/nonexistent-path-for-this-test"}),
    capture_output=True, text=True,
)
total += 1
_ok = _proc.returncode == 0 and "additionalContext" in _proc.stdout
wrong += not _ok
print(f"{'WARN' if _ok else 'silent':<7} a nonexistent cwd falls back to the "
      "default remote names and still warns")

# `origin` is a real remote of this repository, so the real list exempts it.
# `fork` is not, and the fallback set contains it -- so if the fallback were
# unioned in on the success path (rather than used only on failure), a LOCAL
# branch named `fork/x` would be exempt in every repository.
_proc = subprocess.run(
    [sys.executable, HOOK],
    input=json.dumps({"tool_name": "Bash",
                      "tool_input": {"command": "git diff fork/x...HEAD"},
                      "cwd": REPO_ROOT}),
    capture_output=True, text=True,
)
total += 1
_ok = _proc.returncode == 0 and "additionalContext" in _proc.stdout
wrong += not _ok
print(f"{'WARN' if _ok else 'silent':<7} a fallback name is NOT exempt in a "
      "repo whose real remote list omits it")

# A repository whose remote is named something other than `origin`. This pins
# that the real `git remote` output is consulted rather than a guessed set:
# `hc2-gitlab` is in no fallback list, so only a live read can exempt it.
_scratch = tempfile.mkdtemp()
try:
    subprocess.run(["git", "init", "-q", _scratch], check=True,
                   capture_output=True)
    subprocess.run(["git", "-C", _scratch, "remote", "add", "hc2-gitlab",
                    "https://example.invalid/r.git"], check=True,
                   capture_output=True)
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
finally:
    shutil.rmtree(_scratch, ignore_errors=True)

print(f"\n{total - wrong}/{total} correct")
sys.exit(1 if wrong else 0)
