#!/usr/bin/env python3
"""Test the no-ready-before-preview guard.

Verifies that a reply calling a named PR ready for review or merge is refused
(PreToolUse) or blocked (Stop) unless a tool result since the last user turn,
and after the last push, shows that PR's deployed preview, and that negated,
preview-conditional, no-preview, quoted and non-PR text passes.

Run: python3 hooks/test-no-ready-before-preview.py hooks/no-ready-before-preview.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-ready-before-preview.py")

USER = {"type": "user", "message": {"content": [{"type": "text", "text": "status?"}]}}
SYSTEM = {"type": "user", "message": {"content": [
    {"type": "text", "text": "<system-reminder>wake</system-reminder>"}]}}


def call(tool_id, name="Bash", **inp):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tool_id, "name": name, "input": inp}]}}


def result(tool_id, text="{}", is_error=False):
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tool_id, "content": text,
         "is_error": is_error}]}}


def say(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def posted(text):
    return call("p0", name="mcp__hearthbot__post_message", text=text)


URL = "Preview: https://morrison-lab.github.io/lds/pr-preview/pr-3130/"
COMMENTS = [call("g1", name="mcp__github__pull_request_read", method="get_comments",
                 owner="Morrison-Lab", repo="lds", pullNumber=3130),
            result("g1", URL)]
COMMENTS_LIST = [call("g1", name="mcp__github__pull_request_read", method="get_comments",
                      owner="Morrison-Lab", repo="lds", pullNumber=3130),
                 {"type": "user", "message": {"content": [
                     {"type": "tool_result", "tool_use_id": "g1",
                      "content": [{"type": "text", "text": URL}]}]}}]
OTHER_PREVIEW = [call("g1", name="mcp__github__pull_request_read", method="get_comments",
                      owner="Morrison-Lab", repo="lds", pullNumber=3131),
                 result("g1", "https://morrison-lab.github.io/lds/pr-preview/pr-3131/")]
NO_COMMENT = [call("g1", name="mcp__github__pull_request_read", method="get_comments",
                   owner="Morrison-Lab", repo="lds", pullNumber=3130), result("g1", "[]")]
ERRORED = [call("g1", name="mcp__github__pull_request_read", method="get_comments",
                owner="Morrison-Lab", repo="lds", pullNumber=3130),
           result("g1", URL, is_error=True)]
PUSH = [call("b2", command="git push -u origin claude/x"), result("b2", "ok")]
MCP_PUSH = [call("b3", name="mcp__github__push_files", owner="o", repo="r"), result("b3")]

CLAIM = "lds#3130 is ready for your review."

# (pre-events, text, expected_block, label). Each runs in both modes.
CASES = [
    # The incident and its shapes
    ([USER], CLAIM, True, "the lds#3130 incident blocks with no preview read"),
    ([USER], "PR #3130 is ready for review.", True, "ready for review blocks"),
    ([USER], "#3130 is ready to merge.", True, "ready to merge blocks"),
    ([USER], "The PR is ready for you to review.", True, "unnumbered PR claim blocks"),
    ([USER], "lds#3130 is ready for your merge word.", True, "merge word blocks"),
    ([USER] + NO_COMMENT, CLAIM, True, "a comment read with no preview link blocks"),
    ([USER] + ERRORED, CLAIM, True, "an errored read does not count"),
    ([USER] + OTHER_PREVIEW, CLAIM, True, "another PR's preview does not cover #3130"),
    (COMMENTS + [USER], CLAIM, True, "a preview read before the last user turn does not count"),
    ([USER] + COMMENTS + PUSH, CLAIM, True, "a push after the preview read voids it"),
    ([USER] + COMMENTS + MCP_PUSH, CLAIM, True, "an MCP push after the preview read voids it"),

    # Evidence of a deployed preview passes
    ([USER] + COMMENTS, CLAIM, False, "the preview comment for #3130 passes"),
    ([USER] + COMMENTS_LIST, CLAIM, False, "a list-shaped tool result passes"),
    ([USER] + PUSH + COMMENTS, CLAIM, False, "a preview read after the push passes"),
    ([USER] + COMMENTS, "The PR is ready for your review.", False,
     "an unnumbered claim passes after any preview read"),
    (COMMENTS + [SYSTEM], CLAIM, False, "a system-reminder is not a user turn"),

    # Honest statements pass
    ([USER], "lds#3130 is not ready for review yet: the preview is still deploying.", False,
     "negated claim passes"),
    ([USER], "lds#3130 will be ready for your review once the preview deploys.", False,
     "readiness conditional on the preview passes"),
    ([USER], "ai-config#6088 is ready for review; this repo has no preview.", False,
     "a stated no-preview repo passes"),
    ([USER], "ai-config#6088 is ready for review. The repo doesn't publish a preview.", False,
     "no-preview stated in another sentence passes"),
    ([USER], 'You said "#3130 is ready for review" earlier.', False, "quoted words pass"),
    ([USER], "The draft is ready for review.", False, "no PR in the sentence passes"),
    ([USER], "The hook catches `#3130 is ready for review`.", False, "code span passes"),
    ([USER], "lds#3130 merged at 15:40 PST.", False, "unrelated PR text passes"),
]


def write(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    return path


def run(payload, tmpdir=None):
    env = dict(os.environ, TMPDIR=tmpdir or tempfile.mkdtemp())
    return subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                          capture_output=True, text=True, env=env)


def pretool(events, text, tmpdir=None):
    path = write(events)
    try:
        out = run({"transcript_path": path, "tool_name": "mcp__hearthbot__post_message",
                   "tool_input": {"text": text}}, tmpdir).stdout
    finally:
        os.unlink(path)
    if not out.strip():
        return False
    spec = json.loads(out)["hookSpecificOutput"]
    assert spec["hookEventName"] == "PreToolUse"
    assert "no-ready-before-preview" in spec["permissionDecisionReason"]
    return spec["permissionDecision"] == "deny"


def stop(events, text, tmpdir=None):
    path = write(events + [say(text)])
    try:
        out = run({"transcript_path": path}, tmpdir).stdout
    finally:
        os.unlink(path)
    if not out.strip():
        return False
    data = json.loads(out)
    assert "no-ready-before-preview" in data["reason"]
    return data["decision"] == "block"


def main():
    passes = failures = 0

    def check(ok, label):
        nonlocal passes, failures
        print(("PASS: " if ok else "FAIL: ") + label)
        if ok:
            passes += 1
        else:
            failures += 1

    for events, text, expected, label in CASES:
        check(pretool(events, text) == expected, f"[PreToolUse] {label}")
        check(stop(events, text) == expected, f"[Stop] {label}")

    path = write([USER] + OTHER_PREVIEW)
    out = run({"transcript_path": path, "tool_name": "mcp__hearthbot__post_message",
               "tool_input": {"text": CLAIM}}).stdout
    os.unlink(path)
    check("deployed preview of #3130" in out, "the reason names the PR without a preview")

    path = write([USER])
    out = run({"transcript_path": path, "tool_name": "Bash",
               "tool_input": {"command": "echo " + CLAIM}}).stdout
    os.unlink(path)
    check(not out.strip(), "a non-reply tool call is ignored")

    check(not stop([USER, posted(CLAIM), result("p0")], CLAIM),
          "Stop yields when a reply tool ran this turn")
    check(stop([USER, posted(CLAIM), result("p0", "denied", is_error=True)], CLAIM),
          "Stop still judges the text when the reply tool call was denied")

    d = tempfile.mkdtemp()
    path = write([USER])
    try:
        def deny(text):
            out = run({"transcript_path": path, "tool_name": "mcp__hearthbot__post_message",
                       "tool_input": {"text": text}}, d).stdout
            return '"deny"' in out
        first, second = deny(CLAIM), deny(CLAIM)
        check(first and not second, "sentinel refuses the same text only once")
        third = deny("PR #3130 is ready for review.")
        fourth = deny("PR #3130 is ready to merge.")
        check(third and not fourth, "a reworded claim is refused at most twice per turn")
    finally:
        os.unlink(path)

    bad = subprocess.run([sys.executable, HOOK], input="not json",
                         capture_output=True, text=True)
    check(bad.returncode == 0 and not bad.stdout.strip(), "unreadable payload fails open")

    with tempfile.TemporaryDirectory() as tmp:
        lone = os.path.join(tmp, "no-ready-before-preview.py")
        with open(HOOK, encoding="utf-8") as src, open(lone, "w", encoding="utf-8") as dst:
            dst.write(src.read())
        orphan = subprocess.run([sys.executable, lone], input="{}",
                                capture_output=True, text=True)
    check(orphan.returncode == 0 and not orphan.stdout.strip(),
          "missing sibling module fails open")

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
