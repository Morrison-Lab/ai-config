"""Test the no-unreviewed-pr guard.

The guard's value is concentrated in the negative cases: a draft PR
legitimately defers review, and a session that already requested a reviewer
must not be nagged. A guard that fires on correct behaviour gets disabled,
and then the case it exists for goes unprotected too.

Run: python3 hooks/test-no-unreviewed-pr.py hooks/no-unreviewed-pr.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def bash(cmd):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": cmd}}]}}


def tool(name, **inp):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": inp}]}}


def result(body):
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "content": body}]}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


OK = result("{\"requested_reviewers\":[{\"login\":\"Copilot\"}]}")
FAILED = result("{\"status\":422,\"message\":\"Review cannot be requested\"}")

CREATE = bash("gh pr create --base main --title x --body y  # pulls/1038")
CREATE_DRAFT = bash("gh pr create --draft --base main --title x")
READY = bash("gh pr ready 1038")
UNDO = bash("gh pr ready 1038 --undo")
REQUEST = bash("gh api repos/o/r/pulls/1038/requested_reviewers -X POST "
               "-f 'reviewers[]=copilot-pull-request-reviewer[bot]'")
CREATE_WITH_REVIEWER = bash("gh pr create --base main --title x --reviewer "
                            "copilot-pull-request-reviewer  # pulls/1038")
# A file whose CONTENT mentions the CLI strings. Matching a non-shell tool's
# serialized input is the heredoc false positive README.md:265-271 warns
# about, and these very hook files contain both strings in their prose.
WRITE_DOC = tool("create", path="hooks/no-unreviewed-pr.py",
                 file_text="matches gh pr create and requested_reviewers")

CASES = [
    ([CREATE, say("Opened #1038. Review owed.")], True,
     "gh pr create with no reviewer request blocks"),
    ([tool("create_pull_request", title="x", body="y"), say("Opened.")], True,
     "the harness create tool with no request blocks"),
    ([READY, say("Marked it ready.")], True,
     "gh pr ready with no request blocks"),

    ([CREATE, REQUEST, OK, say("Opened and requested.")], False,
     "a SUCCESSFUL request discharges it"),
    ([CREATE, CREATE_WITH_REVIEWER, OK, say("Opened with a reviewer.")], False,
     "gh pr create --reviewer discharges it"),

    # A 422 still produces a tool_use, so trusting the attempt alone would let
    # the session stop with no reviewer attached.
    ([CREATE, REQUEST, FAILED, say("Requested.")], True,
     "a FAILED (422) request does not discharge it"),

    ([CREATE_DRAFT, say("Opened as a draft.")], False,
     "a draft PR does not block"),
    ([tool("create_pull_request", title="x", draft=True), say("Draft.")], False,
     "the harness draft flag does not block"),
    ([CREATE_DRAFT, READY, say("Ready now.")], True,
     "readying a draft later re-arms the guard"),
    # `gh pr ready --undo` converts BACK to draft. Without the negative
    # lookahead it matches RX_OPEN and behaves in exactly the wrong direction.
    ([CREATE, UNDO, say("Held as a draft.")], False,
     "gh pr ready --undo is a draft action, not an open one"),
    # --undo also matches RX_OPEN's own `gh pr ready` alternative, so this
    # only passes because RX_DRAFT is checked FIRST (if/elif). A version
    # that checked RX_OPEN first, or as an independent `if`, would open the
    # PR here instead of holding it -- covered by re-deriving the case
    # directly against the hook rather than trusting the label above.
    ([CREATE, UNDO], "ordering", "RX_DRAFT must be checked before RX_OPEN"),
    ([tool("create_pull_request", title="x", body="y  pulls/1038"),
      tool("update_pull_request", pull_number=1038, draft=True),
      say("Converted back to draft.")], False,
     "update_pull_request draft:true defers review again"),

    # Scalar timestamps lose obligations across PRs: opening A then B and
    # requesting only B silently forgot A. That IS the two-PR failure this
    # hook exists to catch, so it must be tracked per PR.
    ([bash("gh pr create --title a  # pulls/1038"),
      bash("gh pr create --title b  # pulls/1040"),
      bash("gh api repos/o/r/pulls/1040/requested_reviewers -X POST"), OK,
      say("Opened both, requested one.")], True,
     "requesting for one PR does not clear another's obligation"),
    ([bash("gh pr create --title a  # pulls/1038"),
      bash("gh api repos/o/r/pulls/1038/requested_reviewers -X POST"), OK,
      bash("gh pr create --draft --title b  # pulls/1040"),
      say("One reviewed, one draft.")], False,
     "a later draft does not silence an already-satisfied PR"),

    # Non-shell tools must never be text-matched.
    ([WRITE_DOC, say("Wrote the hook file.")], False,
     "writing a file mentioning the CLI strings creates no obligation"),
    ([CREATE, tool("create", path="doc.md",
                   file_text="see requested_reviewers"), say("Documented.")],
     True, "a file mentioning requested_reviewers does not discharge"),

    ([bash("git status --short"), say("All clean.")], False,
     "a session that opened no PR does not block"),
    ([REQUEST, OK, say("Re-requested on #1029.")], False,
     "a bare re-request with no open does not block"),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
        out = subprocess.run(
            [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True, env=env,
        ).stdout
        return '"decision": "block"' in out or '"decision":"block"' in out
    finally:
        os.unlink(path)


def main():
    passes = failures = 0
    for events, expected, label in CASES:
        if expected == "ordering":
            # Re-derive PR state directly: after --undo, the PR must be
            # ABSENT from open_prs (drafted), not merely "not blocking" --
            # a coincidentally-passing block check would not catch a wrong
            # check order the way inspecting the actual state does.
            import importlib.util
            spec = importlib.util.spec_from_file_location("_h", HOOK)
            hookmod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(hookmod)
            fd, path = tempfile.mkstemp(suffix=".jsonl")
            with os.fdopen(fd, "w") as fh:
                for e in events:
                    fh.write(json.dumps(e) + "\n")
            open_prs, _ = hookmod.scan(path)
            os.unlink(path)
            got_ordering = "1038" not in open_prs
            if got_ordering:
                print(f"PASS: {label}")
                passes += 1
            else:
                print(f"FAIL: {label} (PR #1038 still marked open after --undo)")
                failures += 1
            continue
        got = run(events)
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected block={expected}, got {got})")
            failures += 1

    # The recovery commands must be copy-pasteable: an unquoted `<` is a shell
    # redirect, so a placeholder-bearing argument has to be quoted.
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in [CREATE, say("Opened it.")]:
            fh.write(json.dumps(e) + "\n")
    out = subprocess.run(
        [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
        capture_output=True, text=True,
        env=dict(os.environ, TMPDIR=tempfile.mkdtemp()),
    ).stdout
    os.unlink(path)
    reason = json.loads(out).get("reason", "") if out.strip() else ""
    bare = [ln for ln in reason.splitlines()
            if "<" in ln and "gh " in ln and '"<' not in ln and "'<" not in ln
            and "/<" not in ln.split("#")[0].replace('"', "")]
    if not [ln for ln in reason.splitlines()
            if ln.strip().startswith("gh ") and "<" in ln
            and '"' not in ln and "'" not in ln]:
        print("PASS: recovery commands quote their placeholders")
        passes += 1
    else:
        print(f"FAIL: unquoted placeholder in recovery command: {bare[:1]}")
        failures += 1

    out = subprocess.run(
        [sys.executable, HOOK], input='{"transcript_path": "/nonexistent"}',
        capture_output=True, text=True,
    )
    if out.returncode == 0 and "block" not in out.stdout:
        print("PASS: fails open on an unreadable transcript")
        passes += 1
    else:
        print("FAIL: should fail open on an unreadable transcript")
        failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
