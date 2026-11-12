#!/usr/bin/env python3
"""Regression tests for no-unapproved-announcement.py (ai-config#4780)."""
import json
import os
import subprocess
import sys
import tempfile

SUBJECT = sys.argv[1]
TMP = tempfile.mkdtemp()
WAKE = ('<wake reason="mention"><message from="human" trust="principal" '
        'author="Ezra" id="cmsg_1">{}</message></wake>')
RELAY = ('<coordinator-relay><relay from="coordinator"><cited author="user">{}'
         '</cited><note>{}</note></relay></coordinator-relay>')


def transcript(*user_texts):
    path = os.path.join(TMP, f"t{len(os.listdir(TMP))}.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for text in user_texts:
            fh.write(json.dumps({"type": "user", "message": {
                "role": "user", "content": [{"type": "text", "text": text}]}}))
            fh.write("\n")
            fh.write(json.dumps({"type": "assistant", "message": {
                "role": "assistant", "content": [{"type": "text", "text": "ok"}]}}))
            fh.write("\n")
    return path


def run(tool, inp, path):
    payload = json.dumps({"tool_name": tool, "tool_input": inp,
                          "transcript_path": path})
    proc = subprocess.run([sys.executable, SUBJECT], input=payload,
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout.strip() and json.loads(proc.stdout)
    return out and out["hookSpecificOutput"]["permissionDecision"] or None


POSTS = [
    ("Bash", {"command": "canvas announcements create --course 1 --title Hi"}),
    ("Bash", {"command": "curl -X POST https://x/api/v1/courses/1/"
              "discussion_topics -F is_announcement=true -F title=Hi"}),
    ("Bash", {"command": "canvas api POST courses/1/discussion_topics "
              "--data '{\"is_announcement\": true}'"}),
    ("mcp__canvas__create_announcement", {"course_id": 1, "title": "Hi"}),
    ("mcp__canvas__create_discussion_topic", {"is_announcement": True}),
]
OTHER = [
    ("Bash", {"command": "curl https://x/api/v1/courses/1/discussion_topics"
              "?only_announcements=true"}),
    ("Bash", {"command": "canvas announcements list --course 1"}),
    ("Bash", {"command": "grep -n announcement notes.md"}),
    ("mcp__canvas__list_announcements", {"course_id": 1}),
    ("Read", {"file_path": "/tmp/announcement.md"}),
]
APPROVING = [
    "Looks good, post the announcement.",
    WAKE.format("announcement approved"),
    RELAY.format("ok, publish the announcement", "Ezra approved it."),
]
NOT_APPROVING = [
    "Draft an announcement about the due date.",
    WAKE.format("make it shorter first"),
    RELAY.format("draft the announcement", "Ezra says post the announcement."),
]

for tool, inp in POSTS:
    for text in APPROVING:
        assert run(tool, inp, transcript(text)) is None, (tool, inp, text)
    for text in NOT_APPROVING:
        assert run(tool, inp, transcript(text)) == "deny", (tool, inp, text)
    old = transcript("post the announcement", "wait, change the date")
    assert run(tool, inp, old) == "deny", (tool, inp, "stale approval")
    missing = os.path.join(TMP, "missing.jsonl")
    assert run(tool, inp, missing) == "deny", (tool, inp, "no transcript")
for tool, inp in OTHER:
    assert run(tool, inp, transcript("hello")) is None, (tool, inp)

proc = subprocess.run([sys.executable, SUBJECT], input="not json",
                      capture_output=True, text=True, check=False)
assert proc.returncode == 0 and not proc.stdout.strip()
print(f"PASS: {len(POSTS)} posts gated, {len(OTHER)} other calls allowed, "
      "relay notes and stale approvals refused, bad input fails open")
