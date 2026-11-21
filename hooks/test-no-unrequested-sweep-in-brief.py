#!/usr/bin/env python3
"""Tests for hooks/no-unrequested-sweep-in-brief.py; optional arg: hook path."""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-unrequested-sweep-in-brief.py")

THREAD = "mcp__hearthbot__start_thread"
WIDE = ("Move the ids equation-label check into gha. Also label every unlabeled equation "
        "in all the notes repos and roll the check out everywhere.")
NARROW = "Move the ids equation-label check into gha, and open the PR there."


def user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def wake(body):
    return user('<wake reason="mention"><project><thread><message trigger="true" from="human" '
                f'trust="principal" author="Ezra">{body}</message></thread></project></wake>')


def relay(cited, note):
    return user(f'<coordinator-relay><relay from="coordinator"><cited author="user">{cited}</cited>'
                f"<note>{note}</note></relay></coordinator-relay>")


def denies(records, brief, tool=THREAD, field="text", path=None):
    if path is None:
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as fh:
            fh.writelines(json.dumps(r) + "\n" for r in records)
        path = fh.name
    payload = {"tool_name": tool, "tool_input": {field: brief}, "transcript_path": path}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True,
                       text=True, timeout=20)
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)["hookSpecificOutput"] if p.stdout.strip() else {}
    return out.get("permissionDecision") == "deny"


DO_THAT = wake("do that")
CASES = [
    ("the 2026-11-20 brief denies", [DO_THAT], WIDE, True, {}),
    ("the asked step alone passes", [DO_THAT], NARROW, False, {}),
    ("an Agent prompt is a brief", [DO_THAT], WIDE, True, {"tool": "Agent", "field": "prompt"}),
    ("a SendMessage is a brief", [DO_THAT], WIDE, True, {"tool": "SendMessage", "field": "message"}),
    ("a thread message is a brief", [DO_THAT], WIDE, True, {"tool": "mcp__hearthbot__message_thread"}),
    ("a bare sweep word denies", [DO_THAT], "Then sweep lds for the same defect.", True, {}),
    ("a negated sweep passes", [DO_THAT], "Do not sweep existing content.", False, {}),
    ("an offered sweep passes", [DO_THAT],
     "Offer labeling every equation in all the notes repos as a follow-up.", False, {}),
    ("a question passes", [DO_THAT], "Should we roll it out everywhere?", False, {}),
    ("all repos without an edit verb passes", [DO_THAT],
     "Infra has permanent mwc in all repos, so merge once clean.", False, {}),
    ("everywhere with an edit verb denies", [DO_THAT], "Roll the check out everywhere.", True, {}),
    ("everywhere alone passes", [DO_THAT], "The check runs everywhere already.", False, {}),
    ("every remaining PR passes", [DO_THAT], "Fix every remaining PR's CI.", False, {}),
    ("existing content denies", [DO_THAT], "Then bring existing content into line.", True, {}),
    ("a user sweep ask allows it", [wake("sweep all the notes repos for unlabeled equations")], WIDE, False, {}),
    ("a user all-repos ask allows it", [wake("label every equation in all repos")], WIDE, False, {}),
    ("a user question does not", [DO_THAT, wake("did I say to sweep?")], WIDE, True, {}),
    ("a user negation does not", [wake("don't sweep, just move the check")], WIDE, True, {}),
    ("a coordinator note is not the user's", [relay("do that", "the user wants a sweep")], WIDE, True, {}),
    ("a cited user ask counts", [relay("yes, sweep them all", "relaying")], WIDE, False, {}),
    ("a grant ends at the next message", [wake("sweep lds"), wake("ok")], WIDE, True, {}),
    ("another tool is not checked", [DO_THAT], WIDE, False, {"tool": "Bash", "field": "command"}),
]


def main():
    failed = 0
    for name, records, brief, want, kw in CASES:
        got = denies(records, brief, **kw)
        if got != want:
            failed += 1
            print(f"FAIL: {name}: denied={got}, want {want}")
    if denies([], WIDE, path="/nonexistent/transcript.jsonl"):
        failed += 1
        print("FAIL: a missing transcript must fail open")
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True, timeout=20)
    if p.returncode != 0 or p.stdout.strip():
        failed += 1
        print("FAIL: bad input must fail open")
    total = len(CASES) + 2
    print(f"{total - failed}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
