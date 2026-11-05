#!/usr/bin/env python3
"""Tests for hooks/no-answer-from-recall.py (ai-config#4957).

Run: python3 hooks/test-no-answer-from-recall.py [hooks/no-answer-from-recall.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "no-answer-from-recall.py")
POST = "mcp__hearthbot__post_message"

# (name, tool, text, should_deny)
CASES = [
    ("the triggering slip", POST, "ISL uses Auto and Boston, from my memory of the book, not checked against the text. Where does the book live?", True),
    ("from memory", POST, "The Smarket data has 1250 rows, from memory.", True),
    ("from recall", POST, "That is from recall, so treat it with care.", True),
    ("as I recall", POST, "As I recall, chapter 4 covers LDA.", True),
    ("if I remember correctly", POST, "If I remember correctly the exercise is 4.7.", True),
    ("off the top of my head", POST, "Off the top of my head, it is Table 3.4.", True),
    ("relay to the coordinator", "mcp__hearthbot__message_coordinator", "From my memory the rule lives in psw.", True),
    ("where-asks are left to a follow-up issue", POST, "Where does the book live so I can check it?", False),
    ("where asked after searching", POST, "I searched /mnt/project-files and mlr and found no copy. Where does the book live?", False),
    ("checked against the text", POST, "I checked the datasets against ISL section 3.6 in /mnt/project-files/books/isl.pdf.", False),
    ("not from memory", POST, "These numbers are read from the PDF, not from memory.", False),
    ("rather than from recall", POST, "I quoted the page rather than from recall.", False),
    ("memory as a noun in code", POST, "The job uses 4 GB of memory and finished.", False),
    ("project memory file", POST, "I saved the rule to project memory.", False),
    ("where should the file go", POST, "Where should the new file go?", False),
    ("review: where can I find the API docs", POST, "Where can I find the API docs for this?", False),
    ("review: where is the migration file", POST, "Tell me where the migration file is so I can edit it.", False),
    ("review: where to save the output file", POST, "Where do you want the output file saved?", False),
    ("review: memory bank subsystem", POST, "From the memory bank subsystem, the value was loaded correctly.", False),
    ("review2: software library", POST, "Where is the shared library for this package?", False),
    ("review2: PDF icon", POST, "Point me to the PDF icon in the toolbar.", False),
    ("review2: paper citation format", POST, "Tell me where the research paper citation format is documented.", False),
    ("review3: memory of growing up", POST, "From the memory of growing up here, this town has changed a lot.", False),
    ("review3: recollection of survivors", POST, "The museum exhibit tells the story from the recollection of survivors.", False),
    ("review3: book club", POST, "Where is the book club meeting this week?", False),
    ("review4: test suite", POST, "I haven't checked against the test suite yet, but the build passes.", False),
    ("review4: linter rules", POST, "This hasn't been checked against the linter rules.", False),
    ("review4: migration", POST, "The schema was not checked against the latest migration.", False),
    ("review4: memory card", POST, "I retrieved the photos from my memory card.", False),
    ("review4: recall buffer", POST, "From my memory buffer, the files restored fine.", False),
    ("review4: as I recall you", POST, "Let's meet tomorrow, as I recall you mentioned 3pm works.", False),
    ("review6: memory bank as personal recall", POST, "From my memory bank of childhood experiences, I'd say it was 1995.", True),
    ("unrelated tool", "Bash", "From my memory this works.", False),
    ("no text", POST, None, False),
]


def run(tool, text):
    payload = {"tool_name": tool, "tool_input": {"text": text} if text is not None else {}}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True)
    return p.returncode, p.stdout


def main():
    fails = 0
    for name, tool, text, deny in CASES:
        rc, out = run(tool, text)
        denied = '"permissionDecision": "deny"' in out
        ok = rc == 0 and denied == deny
        print(("  ok      " if ok else "  FAIL    ") + name)
        fails += 0 if ok else 1
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
    ok = p.returncode == 0 and not p.stdout
    print(("  ok      " if ok else "  FAIL    ") + "fails open on garbage stdin")
    fails += 0 if ok else 1
    total = len(CASES) + 1
    print(f"\n{total - fails}/{total} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
