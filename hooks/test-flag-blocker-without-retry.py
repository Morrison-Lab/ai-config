"""Test the flag-blocker-without-retry guard.

Two conditions both have to hold before this warns:

  1. the final reply ESCALATES a permission denial (a blocker/handoff marker
     PAIRED with an explicit attribution to a permission/classifier denial)
  2. the transcript's most recent classifier denial has NO LATER attempt of
     a command with the same NORMALIZED shape

Each gets its own negative case, plus the corpus-quoting mitigation (a
denial quoted inside backticks must not count as an assertion) and the
usual fail-open / once-per-message sentinel checks every hook here carries.

Run: python3 hooks/test-flag-blocker-without-retry.py hooks/flag-blocker-without-retry.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

DENIAL_TEXT = (
    "Permission for this action was denied by the Claude Code auto mode "
    "classifier. Ask the user to run this command, or request a permission "
    "rule."
)


def bash_use(cmd, tid):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tid, "name": "Bash", "input": {"command": cmd}}
    ]}}


def denial_result(tid):
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tid, "is_error": True,
         "content": [{"type": "text", "text": DENIAL_TEXT}]}
    ]}}


def allowed_result(tid, text="ok"):
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tid, "is_error": False,
         "content": [{"type": "text", "text": text}]}
    ]}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


MERGE_CMD = "ALLOW_MERGE=1 gh pr merge 5 -R Morrison-Lab/mlg --squash --delete-branch"
MERGE_CMD_NO_ENV = "gh pr merge 5 -R Morrison-Lab/mlg --squash --delete-branch"

BLOCKER_REPLY = (
    "\U0001F6D1 **BLOCKER** --- the PR needs you to merge it. The "
    "permission classifier denied my merge, and I'm not routing around it."
)

# The transcript for the measured incident: one denied merge, no retry, and
# the escalating reply that followed it.
POSITIVE = [
    bash_use(MERGE_CMD, "t1"),
    denial_result("t1"),
    say(BLOCKER_REPLY),
]

# Same denial, but a LATER attempt of the same command (dropping the env-var
# prefix this time, which is exactly the normalization this guard's own
# design constraints call for) that the classifier let through. No warning:
# the retry #2994 asks for already happened.
RETRIED = [
    bash_use(MERGE_CMD, "t1"),
    denial_result("t1"),
    bash_use(MERGE_CMD_NO_ENV, "t2"),
    allowed_result("t2", "Merged pull request #5"),
    say(BLOCKER_REPLY),
]

# The escalating language, with NOTHING in the transcript that denied
# anything at all. This is not the incident -- maybe a real blocker for an
# unrelated reason -- and the guard has nothing to say about it.
NO_DENIAL = [
    bash_use("git push", "t1"),
    allowed_result("t1", "done"),
    say(BLOCKER_REPLY),
]

# The denial text is quoted back to the user INSIDE backticks while a
# generic "I cannot" sits in ordinary prose outside them. Stripping code
# regions must remove the attribution, so the pairing never forms.
BACKTICKED_REPLY = (
    "The tool returned `Permission for this action was denied by the "
    "Claude Code auto mode classifier`, so \U0001F6D1 **BLOCKER** --- I "
    "cannot proceed without your input on how to continue."
)
BACKTICKED = [
    bash_use(MERGE_CMD, "t1"),
    denial_result("t1"),
    say(BACKTICKED_REPLY),
]

CASES = [
    (POSITIVE, True, "blocker paired with classifier attribution, no retry, warns"),
    (RETRIED, False, "a later normalized-equal retry (env-var dropped) stays silent"),
    (NO_DENIAL, False, "escalation language with no denial anywhere stays silent"),
    (BACKTICKED, False, "the attribution is inside backticks and does not count"),

    # Escalation marker with no attribution nearby: a plain "I cannot" about
    # something unrelated to permissions must not pair with a denial that
    # happened much earlier for a different reason.
    ([bash_use(MERGE_CMD, "t1"), denial_result("t1"),
      say("I cannot find the file you mentioned; could you share its path?")],
     False, "a marker with no attribution nearby stays silent"),

    # Attribution with no marker/handoff phrasing at all -- a plain status
    # report that a command was denied, with no request for the user to act.
    ([bash_use(MERGE_CMD, "t1"), denial_result("t1"),
      say("Note: the permission classifier denied that merge once so far; "
          "retrying now.")],
     False, "an attribution alone, with no blocker/handoff marker, stays silent"),

    # A denial followed by ANOTHER denial of the same normalized command,
    # with nothing tried after the SECOND one either. The first denial did
    # get a retry (t2), but that retry is itself the most recent refusal and
    # nothing has been attempted since it -- the standing denial is still
    # open, so this still warns. (Matches
    # remind-retry-before-declaring-blocked.py's own "stretch" semantics: a
    # run of denials with no allowed run in between is one open incident,
    # not a discharged one.)
    ([bash_use(MERGE_CMD, "t1"), denial_result("t1"),
      bash_use(MERGE_CMD_NO_ENV, "t2"), denial_result("t2"),
      say(BLOCKER_REPLY)],
     True, "two consecutive denials with nothing tried after the second one still warn"),

    ([say("Nothing changed since the last poll.")], False,
     "a turn with no escalation language at all stays silent"),
]


def run(events, tmpdir):
    fd, path = tempfile.mkstemp(suffix=".jsonl", dir=tmpdir)
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    env = dict(os.environ, TMPDIR=tmpdir)
    r = subprocess.run(
        [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
        capture_output=True, text=True, env=env,
    )
    assert '"decision": "block"' not in r.stdout, "guard must never block"
    if not r.stdout.strip():
        return False, r
    payload = json.loads(r.stdout)
    assert "systemMessage" in payload, "warn-only Stop hook must emit systemMessage"
    return True, r


def main():
    passes = failures = 0
    for events, expected, label in CASES:
        with tempfile.TemporaryDirectory() as tmpdir:
            got, _r = run(events, tmpdir)
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected warn={expected}, got {got})")
            failures += 1

    # Malformed input: garbage on stdin must not raise, and must not warn.
    with tempfile.TemporaryDirectory() as tmpdir:
        env = dict(os.environ, TMPDIR=tmpdir)
        r = subprocess.run([sys.executable, HOOK], input="not json at all",
                            capture_output=True, text=True, env=env)
        if r.returncode == 0 and not r.stdout.strip():
            print("PASS: malformed stdin fails open (exit 0, no output)")
            passes += 1
        else:
            print(f"FAIL: malformed stdin did not fail open (rc={r.returncode}, "
                  f"stdout={r.stdout!r})")
            failures += 1

    # Malformed input: a transcript path that does not exist.
    with tempfile.TemporaryDirectory() as tmpdir:
        env = dict(os.environ, TMPDIR=tmpdir)
        r = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"transcript_path": "/nonexistent/path.jsonl"}),
            capture_output=True, text=True, env=env)
        if r.returncode == 0 and not r.stdout.strip():
            print("PASS: missing transcript file fails open")
            passes += 1
        else:
            print(f"FAIL: missing transcript file did not fail open (rc={r.returncode})")
            failures += 1

    # Once-per-message sentinel: a second run over the same transcript is silent.
    with tempfile.TemporaryDirectory() as tmpdir:
        fd, path = tempfile.mkstemp(suffix=".jsonl", dir=tmpdir)
        with os.fdopen(fd, "w") as fh:
            for e in POSITIVE:
                fh.write(json.dumps(e) + "\n")
        env = dict(os.environ, TMPDIR=tmpdir)
        payload = json.dumps({"transcript_path": path})
        first = subprocess.run([sys.executable, HOOK], input=payload,
                                capture_output=True, text=True, env=env)
        second = subprocess.run([sys.executable, HOOK], input=payload,
                                 capture_output=True, text=True, env=env)
        if first.stdout.strip() and not second.stdout.strip():
            print("PASS: warns once per distinct message")
            passes += 1
        else:
            print(f"FAIL: sentinel did not suppress the repeat "
                  f"(first={first.stdout!r}, second={second.stdout!r})")
            failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
