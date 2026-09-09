"""Tests for warn-title-only-issue-edit.py.

The reported incident (Morrison-Lab/gha#839, 2026-09-07) is case 1, verbatim
in shape: `gh issue edit 839 -R owner/repo --title "..."` with no body flag,
and no body edit anywhere afterward.

The negative controls are the ones that decide whether this guard survives:

  - a single command passing BOTH `--title` and `--body` must stay silent
  - a body-only edit must stay silent
  - `gh issue create --title` (a new issue, not an edit) must stay silent
  - a title-only edit for N followed by a LATER body edit for the SAME N
    must stay silent -- this is the case that rules out `PreToolUse`; see
    the module docstring
  - a title-only edit for N followed by a body edit for a DIFFERENT M must
    still warn
  - prose merely quoting `gh issue edit --title` (no tool call) must stay
    silent -- this corpus quotes that string constantly, including in this
    hook's own docstring and in this very file

Run: python3 hooks/test-warn-title-only-issue-edit.py hooks/warn-title-only-issue-edit.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile

if len(sys.argv) < 2:
    sys.exit(f"Usage: python3 {sys.argv[0]} <path-to-hook>")
HOOK = os.path.abspath(sys.argv[1])

spec = importlib.util.spec_from_file_location("subject", HOOK)
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)

failures = 0


def check(label, got, want):
    global failures
    if got != want:
        print(f"FAIL: {label}: got {got!r}, want {want!r}")
        failures += 1
    else:
        print(f"PASS: {label}")


def assistant_bash(command, tool_id=None):
    block = {"type": "tool_use", "name": "Bash", "input": {"command": command}}
    if tool_id:
        block["id"] = tool_id
    return {"type": "assistant", "message": {"content": [block]}}


def assistant_mcp(tool_input, tool_id=None):
    block = {"type": "tool_use", "name": "mcp__github__issue_write", "input": tool_input}
    if tool_id:
        block["id"] = tool_id
    return {"type": "assistant", "message": {"content": [block]}}


def assistant_text(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def write_transcript(entries):
    fh = tempfile.NamedTemporaryFile(
        "w", suffix=".jsonl", delete=False, encoding="utf-8",
    )
    for entry in entries:
        fh.write(json.dumps(entry) + "\n")
    fh.close()
    return fh.name


def run_hook(entries):
    path = write_transcript(entries)
    try:
        payload = json.dumps({"transcript_path": path, "hook_event_name": "Stop"})
        env = {k: v for k, v in os.environ.items() if k != "ANTIGRAVITY_AGENT"}
        proc = subprocess.run(
            [sys.executable, HOOK],
            input=payload,
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
    finally:
        os.remove(path)
    if proc.returncode != 0:
        return {"_exit": proc.returncode, "_stderr": proc.stderr}
    if not proc.stdout.strip():
        return {}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"_raw": proc.stdout}


def warned(payload):
    """Payload-shape check per scripts/check-hook-output-shape.py: a
    warn-only Stop hook must surface through `systemMessage`, not merely
    print something."""
    return bool(payload.get("systemMessage"))


def clear_sentinels():
    for f in os.listdir(tempfile.gettempdir()):
        if f.startswith(".claude-title-only-issue-"):
            try:
                os.remove(os.path.join(tempfile.gettempdir(), f))
            except OSError:
                pass


# ---------------------------------------------------------------------------
# End-to-end acceptance cases
# ---------------------------------------------------------------------------

CASES = [
    (
        "gha#839 shape: title-only edit, nothing after",
        [assistant_bash('gh issue edit 839 -R Morrison-Lab/gha --title "five stubs"')],
        True,
    ),
    (
        "title + body in one command: silent",
        [assistant_bash('gh issue edit 839 -R Morrison-Lab/gha --title "t" --body "b"')],
        False,
    ),
    (
        "body-only edit: silent",
        [assistant_bash('gh issue edit 839 --body "corrected body"')],
        False,
    ),
    (
        "gh issue create --title is not an edit: silent",
        [assistant_bash('gh issue create --title "t" --body "b"')],
        False,
    ),
    (
        "title-only edit then a LATER body edit, same issue: silent",
        [
            assistant_bash('gh issue edit 839 --title "t"'),
            assistant_bash('gh issue edit 839 --body "b, finally"'),
        ],
        False,
    ),
    (
        "title-only edit for N, body edit for a DIFFERENT issue M: still warns",
        [
            assistant_bash('gh issue edit 839 --title "t"'),
            assistant_bash('gh issue edit 840 --body "unrelated"'),
        ],
        True,
    ),
    (
        "prose quoting the command, no tool call: silent",
        [assistant_text('I ran `gh issue edit 839 --title "x"` a moment ago.')],
        False,
    ),
    (
        "this file's own docstring text, no tool call: silent",
        [assistant_text(__doc__ or "")],
        False,
    ),
    (
        "glab issue update --title with no description: warns",
        [assistant_bash('glab issue update 12 --title "renamed"')],
        True,
    ),
    (
        "glab issue update --title --description together: silent",
        [assistant_bash('glab issue update 12 --title "t" --description "d"')],
        False,
    ),
    (
        "-t/-b short flags together: silent",
        [assistant_bash('gh issue edit 5 -t "short title" -b "short body"')],
        False,
    ),
    (
        "-t short flag alone: warns",
        [assistant_bash('gh issue edit 5 -t "short title only"')],
        True,
    ),
    (
        "--body-file counts as a body edit: silent",
        [assistant_bash('gh issue edit 5 --title "t" --body-file notes.md')],
        False,
    ),
    (
        "mcp issue_write update with title, no body key: warns",
        [assistant_mcp({"method": "update", "issue_number": 7,
                         "owner": "acme", "repo": "widgets", "title": "new"})],
        True,
    ),
    (
        "mcp issue_write update with title AND body: silent",
        [assistant_mcp({"method": "update", "issue_number": 7,
                         "owner": "acme", "repo": "widgets",
                         "title": "new", "body": "new body too"})],
        False,
    ),
    (
        "mcp issue_write create (new issue): silent",
        [assistant_mcp({"method": "create", "owner": "acme",
                         "repo": "widgets", "title": "brand new"})],
        False,
    ),
    (
        "later mcp body-only update resolves an earlier CLI title-only edit",
        [
            assistant_bash('gh issue edit 839 -R acme/widgets --title "t"'),
            assistant_mcp({"method": "update", "issue_number": 839,
                            "owner": "acme", "repo": "widgets",
                            "body": "the real correction"}),
        ],
        False,
    ),
    (
        "env-prefixed invocation still detected",
        [assistant_bash('GH_TOKEN=x gh issue edit 839 --title "t"')],
        True,
    ),
    (
        "chained command: title-only edit after an unrelated command",
        [assistant_bash('echo hi && gh issue edit 839 --title "t"')],
        True,
    ),
    (
        "heredoc BODY documenting the command is not an invocation: silent",
        [assistant_bash(
            'cat > notes.md <<\'EOF\'\n'
            'gh issue edit 839 --title "renamed"\n'
            'EOF\n'
        )],
        False,
    ),
]

for label, entries, expect_warn in CASES:
    clear_sentinels()
    payload = run_hook(entries)
    got = warned(payload)
    check(label, got, expect_warn)
    if got:
        check(f"{label}: shape uses systemMessage", "systemMessage" in payload, True)


# ---------------------------------------------------------------------------
# Sentinel: fires once per (transcript, issue), not once per Stop call
# ---------------------------------------------------------------------------

def test_sentinel_dedupes():
    clear_sentinels()
    entries = [assistant_bash('gh issue edit 839 --title "t"')]
    path = write_transcript(entries)
    try:
        payload_cmd = json.dumps({"transcript_path": path, "hook_event_name": "Stop"})
        env = {k: v for k, v in os.environ.items() if k != "ANTIGRAVITY_AGENT"}
        first = subprocess.run([sys.executable, HOOK], input=payload_cmd,
                                capture_output=True, text=True, env=env)
        second = subprocess.run([sys.executable, HOOK], input=payload_cmd,
                                 capture_output=True, text=True, env=env)
    finally:
        os.remove(path)
    check("first Stop call on unresolved edit warns",
          bool(json.loads(first.stdout).get("systemMessage")) if first.stdout.strip() else False,
          True)
    check("second Stop call on the SAME transcript stays silent",
          second.stdout.strip(), "")


test_sentinel_dedupes()


def test_sentinel_keyed_per_issue():
    """A sentinel for issue A must not suppress a later warning about a
    DIFFERENT unresolved issue B in the same transcript. The sentinel key
    must include the issue number (and repo), not just the transcript path.
    """
    clear_sentinels()
    env = {k: v for k, v in os.environ.items() if k != "ANTIGRAVITY_AGENT"}
    fh = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    fh.write(json.dumps(assistant_bash('gh issue edit 111 --title "t"')) + "\n")
    fh.close()
    path = fh.name
    try:
        payload_cmd = json.dumps({"transcript_path": path, "hook_event_name": "Stop"})
        first = subprocess.run([sys.executable, HOOK], input=payload_cmd,
                                capture_output=True, text=True, env=env)
        with open(path, "a", encoding="utf-8") as fh2:
            fh2.write(json.dumps(assistant_bash('gh issue edit 222 --title "t2"')) + "\n")
        second = subprocess.run([sys.executable, HOOK], input=payload_cmd,
                                 capture_output=True, text=True, env=env)
    finally:
        os.remove(path)
    check("issue A warns on first Stop",
          bool(json.loads(first.stdout).get("systemMessage")) if first.stdout.strip() else False,
          True)
    second_payload = json.loads(second.stdout) if second.stdout.strip() else {}
    check("a later, different unresolved issue B still warns",
          bool(second_payload.get("systemMessage")), True)


test_sentinel_keyed_per_issue()


def test_two_simultaneously_unresolved_issues_both_reported():
    """Adversarial-review finding: an earlier version tracked only the
    single most-recently-touched offender, so a SECOND, different issue
    left stale in the same transcript at the same time was silently
    dropped for as long as the first stayed the most recent one.
    """
    clear_sentinels()
    entries = [
        assistant_bash('gh issue edit 100 --title "t100"'),
        assistant_bash('gh issue edit 200 --title "t200"'),
    ]
    payload = run_hook(entries)
    msg = payload.get("systemMessage") or ""
    check("both issues named when both are simultaneously unresolved",
          ("100" in msg, "200" in msg), (True, True))


test_two_simultaneously_unresolved_issues_both_reported()


def test_reoffense_after_resolution_warns_again():
    """Adversarial-review finding: a sentinel keyed only on (transcript,
    issue) permanently silences a genuinely NEW title-only offense on the
    same issue later in the same session, even after the first offense
    was resolved by a body edit in between.
    """
    clear_sentinels()
    env = {k: v for k, v in os.environ.items() if k != "ANTIGRAVITY_AGENT"}
    fh = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    fh.write(json.dumps(assistant_bash('gh issue edit 5 --title "first title"')) + "\n")
    fh.close()
    path = fh.name
    try:
        payload_cmd = json.dumps({"transcript_path": path, "hook_event_name": "Stop"})
        first = subprocess.run([sys.executable, HOOK], input=payload_cmd,
                                capture_output=True, text=True, env=env)
        with open(path, "a", encoding="utf-8") as fh2:
            fh2.write(json.dumps(assistant_bash('gh issue edit 5 --body "resolved it"')) + "\n")
            fh2.write(json.dumps(assistant_bash('gh issue edit 5 --title "second title, reoffense"')) + "\n")
        second = subprocess.run([sys.executable, HOOK], input=payload_cmd,
                                 capture_output=True, text=True, env=env)
    finally:
        os.remove(path)
    check("first offense on #5 warns",
          bool(json.loads(first.stdout).get("systemMessage")) if first.stdout.strip() else False,
          True)
    second_payload = json.loads(second.stdout) if second.stdout.strip() else {}
    check("a later reoffense on the SAME issue, after resolution, warns again",
          bool(second_payload.get("systemMessage")), True)


test_reoffense_after_resolution_warns_again()


# ---------------------------------------------------------------------------
# Unit-level checks on the parser
# ---------------------------------------------------------------------------

call = subject.parse_edit_segment('gh issue edit 839 -R Morrison-Lab/gha --title "five stubs"')
check("parse_edit_segment: number", call.number, "839")
check("parse_edit_segment: repo", call.repo, "Morrison-Lab/gha")
check("parse_edit_segment: has_title", call.has_title, True)
check("parse_edit_segment: has_body", call.has_body, False)

check(
    "parse_edit_segment: issue URL as positional",
    subject.parse_edit_segment(
        'gh issue edit https://github.com/o/r/issues/42 --title "t"'
    ).number,
    "42",
)

check(
    "parse_edit_segment: non-edit command returns None",
    subject.parse_edit_segment('gh issue view 839'),
    None,
)

check(
    "same_issue: same number, no repo info on either side",
    subject.same_issue(
        subject.EditCall("gh", "5", None, True, False),
        subject.EditCall("gh", "5", None, False, True),
    ),
    True,
)
check(
    "same_issue: same number, different repos",
    subject.same_issue(
        subject.EditCall("gh", "5", "a/b", True, False),
        subject.EditCall("gh", "5", "c/d", False, True),
    ),
    False,
)

# A real `create` payload never carries `issue_number` (the issue does not
# exist yet), so the end-to-end "create is silent" case above is silent for
# TWO independent reasons and cannot alone pin the `method` guard. Call the
# parser directly with a crafted `method: create` input that DOES carry a
# number, isolating the guard this test exists to pin.
check(
    "_mcp_edit_call: method=create is excluded even with a number present",
    subject.parse_edit_segment is not None and subject._mcp_edit_call(
        {"method": "create", "issue_number": 7, "owner": "acme",
         "repo": "widgets", "title": "brand new"}
    ),
    None,
)


# ---------------------------------------------------------------------------
# Payload-shape assertion (scripts/check-hook-output-shape.py's own bar):
# a warn must surface through `systemMessage`, never `reason` alone.
# ---------------------------------------------------------------------------

clear_sentinels()
shape_payload = run_hook([assistant_bash('gh issue edit 839 --title "t"')])
check("shape: systemMessage present on a fire", bool(shape_payload.get("systemMessage")), True)
check("shape: no bare 'reason'-only payload", "reason" in shape_payload, False)


# ---------------------------------------------------------------------------
# Adversarial-review finding: an MCP-sourced offense must not be described
# with a `gh` command that does not exist ("gh issue update" is not a real
# `gh` subcommand -- "gh issue edit" is).
# ---------------------------------------------------------------------------

clear_sentinels()
mcp_payload = run_hook([assistant_mcp({
    "method": "update", "issue_number": 42, "owner": "acme",
    "repo": "widgets", "title": "renamed",
})])
mcp_msg = mcp_payload.get("systemMessage") or ""
check("MCP-sourced warning does not quote the nonexistent 'gh issue update'",
      "gh issue update" in mcp_msg, False)
check("MCP-sourced warning names the real tool instead",
      "mcp__github__issue_write" in mcp_msg, True)


# ---------------------------------------------------------------------------
# --dry-run / --simulate argv path (house convention: several sibling hook
# test files exercise this; an earlier version of this suite did not).
# ---------------------------------------------------------------------------

def test_dry_run_path():
    clear_sentinels()
    path = write_transcript([assistant_bash('gh issue edit 9 --title "t"')])
    try:
        env = {k: v for k, v in os.environ.items() if k != "ANTIGRAVITY_AGENT"}
        # Bare-path positional form.
        out1 = subprocess.run(
            [sys.executable, HOOK, "--dry-run", path],
            capture_output=True, text=True, env=env,
        )
        # Inline-JSON positional form.
        out2 = subprocess.run(
            [sys.executable, HOOK, "--dry-run",
             json.dumps({"transcript_path": path})],
            capture_output=True, text=True, env=env,
        )
        # Dry-run must not gate on (or write) the sentinel, so a THIRD
        # dry-run call against the SAME unresolved edit warns again rather
        # than going quiet the way a real Stop call's second invocation
        # would. Run it before the file is removed below.
        out3 = subprocess.run(
            [sys.executable, HOOK, "--dry-run", path],
            capture_output=True, text=True, env=env,
        )
    finally:
        os.remove(path)
    p1 = json.loads(out1.stdout) if out1.stdout.strip() else {}
    p2 = json.loads(out2.stdout) if out2.stdout.strip() else {}
    check("dry-run with a bare path positional warns", bool(p1.get("systemMessage")), True)
    check("dry-run with an inline-JSON positional warns", bool(p2.get("systemMessage")), True)
    p3 = json.loads(out3.stdout) if out3.stdout.strip() else {}
    check("a repeated dry-run call is not sentinel-suppressed",
          bool(p3.get("systemMessage")), True)


test_dry_run_path()


if failures:
    print(f"\n{failures} failure(s)")
    sys.exit(1)
print("\nAll tests passed.")
