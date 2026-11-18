#!/usr/bin/env python3
"""Test the prose-relationship guard.

Run: python3 hooks/test-flag-prose-relationship-without-link.py hooks/flag-prose-relationship-without-link.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def human(text="go"):
    return {"type": "user", "message": {"content": [{"type": "text", "text": text}]}}


def human_str(text="go"):
    """A typed turn whose content is a bare string, as the harness often writes it."""
    return {"type": "user", "message": {"content": text}}


def reply(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def call(name, **inp):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]}}


def pr(body):
    return call("mcp__github__create_pull_request", title="t", body=body)


def iss(body):
    return call("mcp__github__issue_write", method="create", title="t", body=body)


def result():
    """A tool_result carrier record, as real transcripts interleave between tool calls."""
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "x", "content": "ok"}]}}


def sh(cmd):
    return call("Bash", command=cmd)


LINK = call("mcp__github__sub_issue_write", issue_number=1, sub_issue_id=2)
CASES = [
    ([human(), iss("Blocked by #12")], True, "prose blocked-by in an issue with no link blocks"),
    ([human(), pr("Blocked by #12")], False, "PR-to-PR blocked-by passes: GitHub cannot record it"),
    ([human(), pr("Stacked on #12")], False, "stacked on in a PR passes"),
    ([human(), pr("Depends on #12")], False, "depends on in a PR passes"),
    ([human(), sh("gh pr create --body 'Stacked on #12'")], False, "stacked on in gh pr create passes"),
    ([human(), iss("Stacked on #12")], True, "stacked on in an issue blocks"),
    ([human_str(), iss("Depends on #12"), human_str("next"), reply("Depends on #12 is how it reads")], False, "later turn with no body written passes (string-content human turn)"),
    ([human_str(), iss("Depends on #12"), human_str("next")], False, "string-content human turn ends the turn"),
    ([human(), reply("This is Blocked by #12 in prose")], False, "assistant reply text is not scanned (guards nothing new; also passes on the old hook)"),
    ([human(), sh("gh issue create --title t --body \"$(cat <<'EOF'\nBlocked by #3\nEOF\n)\"")], True, "heredoc issue body with a cue blocks"),
    ([human(), sh("gh pr create --title t --body \"$(cat <<'EOF'\nStacked on #3\nEOF\n)\"")], False, "heredoc PR body with a cue passes"),
    ([human(), sh("gh issue create --body \"$(cat <<'EOF'\ngh pr edit 4 --base main\nBlocked by #3\nEOF\n)\"")], True, "heredoc issue body with a gh pr edit line blocks"),
    ([human(), sh("bash -c \"gh issue create --body 'Blocked by #3'\"")], True, "bash -c wrapped gh issue create blocks"),
    ([human(), sh("bash -c \"gh pr create --body 'Stacked on #3'\"")], False, "bash -c wrapped gh pr create passes"),
    ([human(), sh("/usr/bin/gh issue create --body 'Blocked by #3'")], True, "path-qualified gh issue create blocks"),
    ([human(), sh("gh -R o/r issue create --body 'Blocked by #3'")], True, "gh global flag before the verb blocks"),
    ([human(), sh("gh -R o/r pr create --body 'Stacked on #3'")], False, "gh global flag before a PR verb passes"),
    ([human(), sh("GH_REPO=o/r gh issue create --body 'Blocked by #3'")], True, "env assignment prefix blocks"),
    ([human(), sh("env GH_REPO=o/r gh issue create --body 'Blocked by #3'")], True, "env wrapper blocks"),
    ([human(), sh("command gh issue create --body 'Blocked by #3'")], True, "command wrapper blocks"),
    ([human(), sh("for n in 1; do gh issue create --body 'Blocked by #3'; done")], True, "gh inside a for loop blocks"),
    ([human(), sh("gh issue create --body 'Step 1; gh pr create --fill. Blocked by #3'")], True, "issue body mentioning gh pr create after a semicolon blocks"),
    ([human(), sh("gh issue create --body \"gh pr edit 4 first. Blocked by #3\"")], True, "issue body starting with gh pr edit blocks"),
    ([human(), sh("gh issue create --body 'Run (gh pr edit 4) then. Blocked by #3'")], True, "issue body with a parenthesised gh pr edit blocks"),
    ([human(), sh("gh issue create --body '| step | gh pr create |\nBlocked by #3'")], True, "issue body with a table cell naming gh pr create blocks"),
    ([human(), sh("gh pr create --body 'Stacked on #3")], False, "unparseable gh pr create passes"),
    ([human(), sh("gh issue create --body 'Blocked by #3")], True, "unparseable gh issue create blocks"),
    ([human(), sh("echo 'gh issue create --body Blocked by #3'")], False, "echo text mentioning gh issue create passes"),
    ([human(), sh("echo gh issue create Blocked by #3")], False, "unquoted echo of gh issue create passes"),
    ([human(), sh("gh pr create --fill")], False, "gh pr create --fill passes"),
    ([human(), sh("gh issue view 3 --comments")], False, "gh issue view passes"),
    ([human(), sh("gh issue create --body 'Blocked by #3' && gh pr create --body 'x'")], True, "issue write chained with a PR write blocks"),
    ([human(), sh("gh issue create --body 'x' && gh pr create --body 'Stacked on #3'")], True, "known edge: a cue in a PR body chained with an issue write is flagged"),
    ([human(), iss("Blocked by #12"), result(), pr("Fixes the bug."), result()], True, "tool_result records between tool calls do not end the turn"),
    ([human(), iss("Blocked by #12"), result(), human_str("next"), result()], False, "tool_result records do not hide the turn boundary"),
    ([human(), call("mcp__github__issue_write", method="update", issue_number=7, body="Blocked by #12")], True, "issue_write update is treated as an issue body"),
    ([human(), call("mcp__github__issue_write", method="create", body="Part of Morrison-Lab/lds#5")], True, "cross-repo part of in an issue blocks"),
    ([human(), pr("Part of Morrison-Lab/lds#5")], False, "part of in a PR body passes"),
    ([human(), call("mcp__github__update_pull_request", body="Child of #5")], False, "child of in an updated PR body passes"),
    ([human(), sh("gh pr create --body 'Part of #5'")], False, "part of in gh pr create passes"),
    ([human(), sh("gh issue create --body 'Part of #5'")], True, "part of in gh issue create blocks"),
    ([human(), pr("Part of #5. Blocked by #6")], False, "PR body with part of and blocked by passes"),
    ([human(), sh("gh issue create --body 'Depends on #3'")], True, "gh issue create prose blocks"),
    ([human(), iss("Blocked by #12"), sh("gh issue edit 9 --add-blocked-by 12")], False, "later gh flag discharges"),
    ([human(), iss("Part of #5"), sh("gh api -X POST repos/o/r/issues/5/sub_issues -f sub_issue_id=7")], False, "later sub_issues call discharges"),
    ([human(), iss("Blocked by #12"), call("Bash", command="gh api repos/o/r/issues/9/dependencies/blocked_by -f issue_id=1")], False, "later REST dependency call discharges"),
    ([human(), iss("Blocked by #12"), LINK], False, "later sub_issue_write discharges"),
    ([human(), LINK, iss("Blocked by #12")], True, "link BEFORE the prose write does not discharge"),
    ([human(), call("mcp__github__issue_write", method="create", body="Part of #5", parent_issue_number=5)], False, "parent_issue_number in same call passes"),
    ([human(), pr("Closes #12")], False, "closing keyword is not a cue"),
    ([human(), pr("The rule: write `Blocked by #12` as a relationship.")], False, "quoted in a code span passes"),
    ([human(), pr("Fixes the bug.")], False, "no cue passes"),
    ([human(), pr("See #12 for background.")], False, "bare reference passes"),
    ([human(), iss("Blocked by #12"), human("next"), pr("Fixes the bug.")], False, "earlier turn is ignored"),
    ([human(), call("mcp__github__add_issue_comment", body="Blocked by #12")], False, "comment is not an issue/PR body"),
]


def run(events):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(e) for e in events))
        payload = {"transcript_path": path, "session_id": "s", "stop_hook_active": False}
        env = dict(os.environ, TMPDIR=d)
        out = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True, env=env)
        if not out.stdout.strip():
            return False
        verdict = json.loads(out.stdout)
        if verdict.get("decision") != "block":
            return False
        # The reason is the only part the agent reads, so assert what it says.
        reason = verdict.get("reason", "")
        assert "relationships field" in reason and "[!IMPORTANT]" in reason, verdict
        assert "needs #N merged first" in reason and "issue that PR closes" in reason, verdict
        return True


fail = 0
for events, expect, label in CASES:
    got = run(events)
    if got != expect:
        fail += 1
        print(f"FAIL {label}: expected block={expect}, got {got}")
print(f"{len(CASES) - fail}/{len(CASES)} passed")
sys.exit(1 if fail else 0)
