"""Test the no-undefined-claim-without-def-search guard (ai-config#4949).

Case one is the reported incident (Morrison-Lab/dds#36, 2026-11-04). Each
negative isolates one narrowing: the search must name a `def-` anchor, be a
search call, and not be the comment's own prose.

Run: python3 hooks/test-no-undefined-claim-without-def-search.py \
         hooks/no-undefined-claim-without-def-search.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
SUBJECT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    HERE, "no-undefined-claim-without-def-search.py")

CLAIM = "No lds, mds, pds or sds page defines them, so I left them unlinked."
USER = {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "link the terms"}]}}


def call(name, **inp):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": name, "input": inp}]}}


def result():
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "content": "ok"}]}}


GREP = call("Bash", command="grep -rn '{#def-rank' /home/user/mds/chapters")
GREP_NO_ANCHOR = call("Bash", command="grep -rn rank /home/user/mds/chapters")
READ_ONLY = call("Read", file_path="/home/user/mds/def-rank.qmd")
SEARCH_API = call("Bash", command="gh api -X GET search/code -f q='def-rank repo:Morrison-Lab/mds'")
OWN_PROSE = call("mcp__github__add_issue_comment", body="I will grep for def-rank later")

# (transcript entries, tool_name, tool_input, expect deny, label)
CASES = [
    ([USER], "mcp__github__add_issue_comment", {"body": CLAIM}, True,
     "the reported incident: claim with no search"),
    ([USER], "mcp__github__add_reply_to_pull_request_comment", {"body": CLAIM}, True,
     "the same claim in a review reply"),
    ([USER], "Bash", {"command": "gh pr comment 36 --body 'No lds, mds, pds or sds page defines them.'"}, True,
     "the same claim through gh pr comment"),
    ([USER], "mcp__github__add_issue_comment",
     {"body": "This term is not defined in mds, so I kept it plain."}, True,
     "not defined in <site>"),
    ([USER], "mcp__github__add_issue_comment",
     {"body": "No page on win defines this term, so I kept it plain."}, True,
     "no page on <non-core site> defines it"),
    ([USER], "mcp__github__add_issue_comment",
     {"body": "This term isn't defined anywhere in rme, so I kept it plain."}, True,
     "isn't defined anywhere in <site>"),
    ([USER, GREP, result()], "mcp__github__add_issue_comment", {"body": CLAIM}, False,
     "a grep of a def- anchor this turn: allowed"),
    ([USER, SEARCH_API, result()], "mcp__github__add_issue_comment", {"body": CLAIM}, False,
     "a search/code query naming def-: allowed"),
    ([USER, GREP_NO_ANCHOR, result()], "mcp__github__add_issue_comment", {"body": CLAIM}, True,
     "a grep that names no def- anchor is not evidence"),
    ([USER, READ_ONLY, result()], "mcp__github__add_issue_comment", {"body": CLAIM}, True,
     "a file read is not a search"),
    ([USER, OWN_PROSE, result()], "mcp__github__add_issue_comment", {"body": CLAIM}, True,
     "the comment's own prose naming def-rank is not evidence"),
    ([GREP, result(), USER], "mcp__github__add_issue_comment", {"body": CLAIM}, True,
     "a search before the last user message does not count"),
    ([USER], "mcp__github__add_issue_comment",
     {"body": "The rule says `no mds page defines it` needs a search first."}, False,
     "a claim quoted in backticks is a citation, not a claim"),
    ([USER], "mcp__github__add_issue_comment",
     {"body": "mds defines rank in def-rank, so I linked it."}, False,
     "a comment that links a definition makes no undefined claim"),
    ([USER], "mcp__github__add_issue_comment",
     {"body": "No page in this PR defines a rank function."}, False,
     "no prereq site is named: silent"),
    ([USER], "Bash", {"command": "gh pr view 36"}, False, "an unrelated Bash call"),
]


def run(entries, tool, tool_input, transcript_ok=True):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "t.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for e in entries:
                fh.write(json.dumps(e) + "\n")
        payload = {"tool_name": tool, "tool_input": tool_input,
                   "transcript_path": path if transcript_ok else os.path.join(tmp, "missing.jsonl")}
        proc = subprocess.run([sys.executable, SUBJECT], input=json.dumps(payload),
                              capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return "permissionDecision" in proc.stdout and '"deny"' in proc.stdout


def main() -> int:
    failures = 0
    for entries, tool, tool_input, expect, label in CASES:
        got = run(entries, tool, tool_input)
        ok = got == expect
        failures += not ok
        print(("PASS" if ok else "FAIL"), label)
    ok = not run([USER], "mcp__github__add_issue_comment", {"body": CLAIM}, transcript_ok=False)
    failures += not ok
    print(("PASS" if ok else "FAIL"), "an unreadable transcript fails open")
    proc = subprocess.run([sys.executable, SUBJECT], input="not json", capture_output=True,
                          text=True, timeout=30)
    ok = proc.returncode == 0 and not proc.stdout.strip()
    failures += not ok
    print(("PASS" if ok else "FAIL"), "unparseable input fails open")
    total = len(CASES) + 2
    print(f"{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
