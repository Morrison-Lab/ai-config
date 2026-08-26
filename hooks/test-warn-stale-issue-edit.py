"""Tests for warn-stale-issue-edit.py.

Four acceptance cases from ai-config#2282, plus the near-misses a warn-only
guard has to let through:

  - open: VIEW_ISSUE + FETCH after the request, result OPEN -> silent
  - closed/superseded: latest view result is CLOSED -> warn
  - stale-check: both checks exist, but only BEFORE the request -> warn
  - non-issue task: no forge issue in user prose -> silent

Command-position / heredoc / mapping-name cases pin that a GitHub MCP
VIEW_ISSUE spelling discharges and that prose quoting `gh issue view` does
not. Payload-shape checks satisfy `scripts/check-hook-output-shape.py`.

Run: python3 hooks/test-warn-stale-issue-edit.py hooks/warn-stale-issue-edit.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

if len(sys.argv) < 2:
    sys.exit(f"Usage: python3 {sys.argv[0]} <path-to-hook>")
HOOK = os.path.abspath(sys.argv[1])

import importlib.util

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


def user(text):
    return {"type": "user", "message": {"content": [{"type": "text", "text": text}]}}


def tool(name, inp, tool_id=None):
    block = {"type": "tool_use", "name": name, "input": inp}
    if tool_id:
        block["id"] = tool_id
    return {"type": "assistant", "message": {"content": [block]}}


def result(text, tool_use_id=None):
    block = {"type": "tool_result", "content": text}
    if tool_use_id:
        block["tool_use_id"] = tool_use_id
    return {"type": "user", "message": {"content": [block]}}


def write_transcript(entries):
    fh = tempfile.NamedTemporaryFile(
        "w", suffix=".jsonl", delete=False, encoding="utf-8",
    )
    for entry in entries:
        fh.write(json.dumps(entry) + "\n")
    fh.close()
    return fh.name


def run_hook(transcript_path, tool_name="Write", extra_input=None):
    inp = {"file_path": "hooks/example.py", "content": "x"}
    if extra_input:
        inp.update(extra_input)
    payload = json.dumps({
        "tool_name": tool_name,
        "tool_input": inp,
        "transcript_path": transcript_path,
        "hook_event_name": "PreToolUse",
    })
    proc = subprocess.run(
        [sys.executable, HOOK],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        return {"_exit": proc.returncode, "_stderr": proc.stderr}
    if not proc.stdout.strip():
        return {}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"_raw": proc.stdout}


def warned(payload):
    if not payload:
        return False
    extra = (payload.get("hookSpecificOutput") or {}).get("additionalContext")
    return bool(payload.get("systemMessage") or extra)


def kind_of(payload):
    msg = payload.get("systemMessage") or ""
    extra = (payload.get("hookSpecificOutput") or {}).get("additionalContext") or ""
    blob = msg + "\n" + extra
    if "CLOSED" in blob:
        return "closed"
    if "predate" in blob or "stale (predates" in blob:
        return "stale"
    if warned(payload):
        return "missing"
    return "silent"


ISSUE_URL = (
    "Implement https://github.com/Morrison-Lab/ai-config/issues/2282 "
    "on Morrison-Lab/ai-config."
)
NAMING = user(ISSUE_URL)
VIEW = tool("Bash", {"command": "gh issue view 2282 --json state,title,body"}, "v1")
VIEW_OPEN = result('{"state":"OPEN","title":"Guard"}', "v1")
VIEW_CLOSED = result('{"state":"CLOSED","title":"already done"}', "v1")
FETCH = tool("Bash", {"command": "git fetch origin main"}, "f1")


# ---------------------------------------------------------------------------
# find_issue_ref
# ---------------------------------------------------------------------------

check(
    "GitHub issue URL",
    subject.find_issue_ref(ISSUE_URL)["number"],
    "2282",
)
check(
    "GitHub URL owner/repo",
    (subject.find_issue_ref(ISSUE_URL)["owner"],
     subject.find_issue_ref(ISSUE_URL)["repo"]),
    ("Morrison-Lab", "ai-config"),
)
check(
    "GitLab issue URL",
    subject.find_issue_ref(
        "Please implement https://gitlab.com/acme/proj/-/issues/44"
    )["number"],
    "44",
)
check(
    "owner/repo#N shorthand",
    subject.find_issue_ref("Look at ucdavis/rampp#140 before coding")["number"],
    "140",
)
check(
    "implement #N",
    subject.find_issue_ref("implement #99 on this repo")["number"],
    "99",
)
check(
    "implement 2-factor is not an issue",
    subject.find_issue_ref("implement 2-factor auth on the login page"),
    None,
)
check(
    "implementing a dated sentence is not an issue",
    subject.find_issue_ref("implementing 2026-08-26 the remaining slice"),
    None,
)
check(
    "fixes 3 bugs is not an issue",
    subject.find_issue_ref("this PR fixes 3 bugs in the parser"),
    None,
)
check(
    "issue 2282 without hash still counts",
    subject.find_issue_ref("please grab issue 2282")["number"],
    "2282",
)
check(
    "pull URL is not an issue",
    subject.find_issue_ref(
        "Review https://github.com/Morrison-Lab/ai-config/pull/2317"
    ),
    None,
)
check(
    "URL wins over later shorthand recurrences",
    subject.find_issue_ref(
        ISSUE_URL + " Recurred as ucdavis/bcs#266 and ucdavis/rampp#140."
    )["number"],
    "2282",
)
check("plain status prose", subject.find_issue_ref("fix the README typo"), None)

stems = subject.load_mapping_stems()
check(
    "VIEW_ISSUE mapping yields an MCP stem",
    bool(stems["view_mcp"]) and stems["view_mcp"].startswith("mcp__"),
    True,
)
check(
    "VIEW_ISSUE mapping yields a CLI stem containing 'issue view'",
    "issue view" in stems["view_cli"],
    True,
)
check(
    "FETCH mapping yields a git fetch stem",
    stems["fetch_cli"].startswith("git fetch"),
    True,
)


# ---------------------------------------------------------------------------
# command-position / heredoc
# ---------------------------------------------------------------------------

issue = {"number": "2282", "owner": "Morrison-Lab", "repo": "ai-config"}
check(
    "gh issue view at command position",
    subject.command_views_issue("gh issue view 2282", issue, stems["view_cli"]),
    True,
)
check(
    "glab issue view at command position",
    subject.command_views_issue("glab issue view 2282", issue, stems["view_cli"]),
    True,
)
check(
    "wrong issue number does not view",
    subject.command_views_issue("gh issue view 99", issue, stems["view_cli"]),
    False,
)
check(
    "prose mentioning gh issue view does not view",
    subject.command_views_issue(
        "echo 'run gh issue view 2282 first'", issue, stems["view_cli"],
    ),
    False,
)
check(
    "heredoc body quoting gh issue view does not view",
    subject.command_views_issue(
        "cat <<'EOF' > /tmp/x.md\ngh issue view 2282\nEOF",
        issue,
        stems["view_cli"],
    ),
    False,
)
check(
    "git fetch at command position",
    subject.command_fetches_remote("git fetch origin main", stems["fetch_cli"]),
    True,
)
check(
    "git ls-remote at command position",
    subject.command_fetches_remote(
        "git ls-remote --heads origin main", stems["fetch_cli"],
    ),
    True,
)
check(
    "echo git fetch does not fetch",
    subject.command_fetches_remote("echo git fetch origin", stems["fetch_cli"]),
    False,
)
check(
    "MCP issue_read with issue_number views",
    subject.mcp_views_issue(
        stems["view_mcp"],
        {"issue_number": 2282, "method": "get"},
        issue,
        stems["view_mcp"],
    ),
    True,
)
check(
    "MCP issue_read of a different number does not view",
    subject.mcp_views_issue(
        stems["view_mcp"],
        {"issue_number": 99, "method": "get"},
        issue,
        stems["view_mcp"],
    ),
    False,
)
check(
    "unrelated MCP tool does not view",
    subject.mcp_views_issue(
        "mcp__github__get_me",
        {"issue_number": 2282},
        issue,
        stems["view_mcp"],
    ),
    False,
)


# ---------------------------------------------------------------------------
# End-to-end: the four acceptance cases
# ---------------------------------------------------------------------------

non_issue = write_transcript([user("Fix the typo in README.md")])
out = run_hook(non_issue)
check("non-issue task is silent", warned(out), False)
check("non-issue emits no permissionDecision", "permissionDecision" in out, False)

missing = write_transcript([NAMING])
out = run_hook(missing)
check("issue-driven edit with no checks warns", warned(out), True)
check("missing-check kind", kind_of(out), "missing")
check(
    "missing-check systemMessage is a non-empty string",
    isinstance(out.get("systemMessage"), str) and bool(out.get("systemMessage")),
    True,
)
check(
    "missing-check additionalContext is present",
    bool((out.get("hookSpecificOutput") or {}).get("additionalContext")),
    True,
)
check("missing-check never denies", "permissionDecision" in out, False)

open_ok = write_transcript([NAMING, VIEW, VIEW_OPEN, FETCH])
out = run_hook(open_ok)
check("open issue with fresh view+fetch is silent", warned(out), False)

closed = write_transcript([NAMING, VIEW, VIEW_CLOSED, FETCH])
out = run_hook(closed)
check("closed issue warns", warned(out), True)
check("closed-check kind", kind_of(out), "closed")
check(
    "closed additionalContext names CLOSED",
    "CLOSED" in ((out.get("hookSpecificOutput") or {}).get("additionalContext") or ""),
    True,
)

stale = write_transcript([VIEW, VIEW_OPEN, FETCH, NAMING])
out = run_hook(stale)
check("checks before the request warn as stale", warned(out), True)
check("stale-check kind", kind_of(out), "stale")
check(
    "stale systemMessage mentions predate",
    "predate" in (out.get("systemMessage") or ""),
    True,
)

two_factor = write_transcript([
    user("Please implement 2-factor auth on the login form."),
])
out = run_hook(two_factor)
check("implement 2-factor does not arm the write guard", warned(out), False)

closed_then_open = write_transcript([
    NAMING,
    VIEW,
    VIEW_CLOSED,
    tool("Bash", {"command": "gh issue view 2282 --json state"}, "v2"),
    result('{"state":"OPEN"}', "v2"),
    FETCH,
])
out = run_hook(closed_then_open)
check("latest view OPEN after an earlier CLOSED is silent", warned(out), False)

jq_closed = write_transcript([
    NAMING,
    tool("Bash", {"command": "gh issue view 2282 --jq .state"}, "jq1"),
    result("CLOSED\n", "jq1"),
    FETCH,
])
out = run_hook(jq_closed)
check("bare jq CLOSED counts as closed", kind_of(out), "closed")

quoted_in_body = write_transcript([
    NAMING,
    tool("Bash", {"command": "gh issue view 2282"}, "b1"),
    result(
        "title:\tGuard\nstate:\tOPEN\n--\n"
        "The matcher must not treat a body that quotes "
        '{"state": "closed"} as the issue state.\n',
        "b1",
    ),
    FETCH,
])
out = run_hook(quoted_in_body)
check("OPEN header with closed JSON in the body is silent", warned(out), False)

followup_shorthand = write_transcript([
    NAMING,
    VIEW,
    VIEW_OPEN,
    FETCH,
    user("look at ucdavis/rampp#140 for the incident"),
])
out = run_hook(followup_shorthand)
check(
    "incidental owner/repo#N follow-up does not retarget",
    warned(out),
    False,
)


# ---------------------------------------------------------------------------
# Mapping MCP spelling, GitLab, ls-remote; unrelated tools stay silent
# ---------------------------------------------------------------------------

mcp_view = tool(stems["view_mcp"], {"issue_number": 2282, "method": "get"}, "m1")
mcp_open = result('{"state": "OPEN"}', "m1")
mapped = write_transcript([NAMING, mcp_view, mcp_open, FETCH])
out = run_hook(mapped)
check(
    "VIEW_ISSUE MCP stem from tool-mappings.yml discharges the view half",
    warned(out),
    False,
)

glab = write_transcript([
    user("Implement https://gitlab.com/acme/proj/-/issues/44"),
    tool("Bash", {"command": "glab issue view 44"}, "g1"),
    result("State: open", "g1"),
    tool("Bash", {"command": "git ls-remote --heads origin main"}, "l1"),
])
out = run_hook(glab)
check("glab view + git ls-remote is silent", warned(out), False)

wrong_n = write_transcript([
    NAMING,
    tool("Bash", {"command": "gh issue view 99 --json state"}, "w1"),
    result('{"state":"OPEN"}', "w1"),
    FETCH,
])
out = run_hook(wrong_n)
check("view of a different issue number still warns", warned(out), True)

heredoc_tx = write_transcript([
    NAMING,
    tool("Bash", {
        "command": "cat <<'EOF' > notes.md\ngh issue view 2282\ngit fetch origin\nEOF",
    }),
])
out = run_hook(heredoc_tx)
check("heredoc quoting the checks does not discharge", warned(out), True)

out = run_hook(missing, tool_name="Bash")
check("Bash (not a write) stays silent even with an issue", warned(out), False)

out = run_hook(missing, tool_name="Edit")
check("Edit is a write tool and warns", warned(out), True)

out = run_hook(missing, tool_name="NotebookEdit")
check("NotebookEdit is a write tool and warns", warned(out), True)

out = run_hook(open_ok, tool_name="StrReplace")
check("Cursor StrReplace on a fresh-checked issue is silent", warned(out), False)

# Fail open on a missing transcript rather than warning with no evidence.
out = run_hook("/no/such/transcript.jsonl")
check("missing transcript fails open (silent)", warned(out), False)

# Mutation-style: a warn payload must not look like a Stop-hook reason-only
# emit, which the harness discards.
missing_payload = run_hook(write_transcript([NAMING]))
check(
    "warn payload has no reason-without-decision",
    "reason" in missing_payload and "decision" not in missing_payload,
    False,
)


if failures:
    sys.exit(f"{failures} failure(s)")
print("All tests passed.")
