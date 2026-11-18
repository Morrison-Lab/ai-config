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
    ([human(), sh("gh issue create --body 'Blocked by #3' && gh pr create --body 'x'")], True, "issue write chained with a PR write still blocks"),
    ([human(), sh("gh issue create --body 'Blocked by #3. Next: gh pr edit 4'")], True, "issue body containing the text gh pr edit still blocks"),
    ([human(), sh("gh pr create --body 'Stacked on #3' && gh issue create --body 'Blocked by #4'")], True, "PR write chained with an issue write blocks on the issue"),
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
