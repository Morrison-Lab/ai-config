"""Test the remind-mergeability-on-status Stop hook (ai-config#4380).

Case one is the reported incident shape: a stacked MR reported as "open,
pipeline green" with no mergeability field ever read.

The negatives decide whether the guard survives. A reply that DID read
mergeability, a reply with no status language, a reply quoting the trigger in
backticks or a fence, and a status reply that precedes the latest user prompt
must all stay silent.

Run: python3 hooks/test-remind-mergeability-on-status.py hooks/remind-mergeability-on-status.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]
SHAPE_ERRORS = []


def user(text):
    return {"type": "user", "message": {"content": text}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


def tool(command):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "t1", "input": {"command": command}}]}}


def tool_result():
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}}


STATUS = ("MR !125 (https://gitlab.example.com/g/p/-/merge_requests/125) "
          "is open and the pipeline is green.")

CASES = [
    ([user("status?"), say(STATUS)], True,
     "status reply, no mergeability query -> fires"),
    ([user("status?"), tool("glab mr view 125 --output json | jq .state"),
      tool_result(), say(STATUS)], False,
     "glab mr view query -> silent"),
    ([user("status?"), tool("glab api projects/1/merge_requests/125 | jq .has_conflicts"),
      tool_result(), say(STATUS)], False,
     "has_conflicts query -> silent"),
    ([user("status?"), tool("gh pr view 9 --json mergeable,mergeStateStatus"),
      tool_result(), say("PR #9 checks are passing.")], False,
     "gh mergeable query -> silent"),
    ([user("status?"), tool("gh api repos/o/r/pulls/9 --jq .mergeable_state"),
      tool_result(), say("PR #9 CI is green.")], False,
     "mergeable_state query -> silent"),
    ([user("status?"), tool("glab api x | jq .detailed_merge_status"),
      tool_result(), say(STATUS)], False,
     "detailed_merge_status query -> silent"),
    ([user("status?"), say("Renamed the helper and pushed the commit.")], False,
     "no PR reference and no status language -> silent"),
    ([user("status?"), say("See #123 for the design discussion.")], False,
     "PR-like reference without status wording -> silent"),
    ([user("status?"), say("CI is green on the local branch.")], False,
     "status wording without a PR/MR reference -> silent"),
    ([user("status?"), say("The rule fires on `MR !125 pipeline is green`.")], False,
     "backticked quote of the trigger -> silent"),
    ([user("status?"), say("Example:\n```\nPR #9 checks are passing\n```\nDone.")], False,
     "fenced quote of the trigger -> silent"),
    ([user("status?"), say("> PR #9 checks are passing\nI disagree.")], False,
     "blockquoted trigger -> silent"),
    ([user("first"), tool("gh pr view 9 --json mergeable"), tool_result(),
      say("ok"), user("again?"), say("PR #9 checks are passing.")], True,
     "query predates the latest user prompt -> fires"),
    ([user("status?"), say("PR #9 checks are passing."),
      tool("gh pr view 9 --json mergeable"), tool_result(), say("Done.")], False,
     "final message has no status language -> silent"),
    ([user("status?"), say("https://github.com/o/r/pull/9 pipeline passing")], True,
     "github pull URL with pipeline wording -> fires"),
]

def run(events):
    td = tempfile.mkdtemp()
    try:
        path = os.path.join(td, "transcript.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for e in events:
                fh.write(json.dumps(e) + "\n")
        env = dict(os.environ, TMPDIR=td, TEMP=td, TMP=td)
        out = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True, env=env,
        ).stdout.strip()
        if not out:
            return False
        payload = json.loads(out)
        # A Stop hook's output is surfaced only via systemMessage (or a block
        # decision); anything else reaches nobody.
        if not payload.get("systemMessage"):
            SHAPE_ERRORS.append(sorted(payload))
        if payload.get("decision") == "block":
            SHAPE_ERRORS.append(["must-not-block"])
        return True
    finally:
        shutil.rmtree(td, ignore_errors=True)


def main():
    failures = 0
    for events, want, label in CASES:
        got = run(events)
        ok = got == want
        failures += 0 if ok else 1
        print(f"{'ok  ' if ok else 'FAIL'}  {'fires' if want else 'silent'}: {label}")
    # Fires at most once per distinct message.
    td = tempfile.mkdtemp()
    try:
        path = os.path.join(td, "t.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for e in [user("s"), say(STATUS)]:
                fh.write(json.dumps(e) + "\n")
        env = dict(os.environ, TMPDIR=td, TEMP=td, TMP=td)
        outs = [subprocess.run([sys.executable, HOOK],
                               input=json.dumps({"transcript_path": path}),
                               capture_output=True, text=True, env=env).stdout.strip()
                for _ in range(2)]
        ok = bool(outs[0]) and not outs[1]
        failures += 0 if ok else 1
        print(f"{'ok  ' if ok else 'FAIL'}  once-per-message sentinel")
    finally:
        shutil.rmtree(td, ignore_errors=True)
    # Fail-open on garbage input.
    bad = subprocess.run([sys.executable, HOOK], input="not json",
                         capture_output=True, text=True)
    ok = bad.returncode == 0 and not bad.stdout.strip()
    failures += 0 if ok else 1
    print(f"{'ok  ' if ok else 'FAIL'}  fails open on bad stdin")
    if SHAPE_ERRORS:
        failures += 1
        print(f"FAIL  payload shape: {SHAPE_ERRORS}")
    total = len(CASES) + 2
    print(f"\n{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
