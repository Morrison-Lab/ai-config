#!/usr/bin/env python3
"""Tests for scripts/check-user-quote.py.

The classifier is the whole check: `message.role == "user"` is a transport
role, so every harness-injected record is a candidate false positive, and a
false positive here CERTIFIES a fabricated attribution rather than merely
missing one.  Each exclusion therefore gets its own case.

These fixtures exercise the classifier, not the transcript format itself --
per `shared/workflow/fixtures-are-not-evidence.md` a fixture is evidence about
the code that reads it and nothing more.  The field names and shapes were
derived by surveying 21 real transcripts on 2026-08-28 (6,660 records, 1,977
user-role); a harness change to those shapes is a thing these tests cannot see.
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check-user-quote.py"
spec = importlib.util.spec_from_file_location("cuq", SCRIPT)
cuq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cuq)

passes = 0
failures = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def user(text, **flags):
    return {"message": {"role": "user", "content": text}, "userType": "external", **flags}


def write(root, name, records, extra_lines=()):
    path = Path(root) / name
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
        for line in extra_lines:
            handle.write(line + "\n")
    return path


def run(root, phrase, *args):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), phrase, "--root", str(root), *args],
        capture_output=True, text=True,
    )
    return result.returncode, result.stdout + result.stderr


def main() -> int:
    print("Testing check-user-quote.py...")

    # -- classify(): one case per exclusion, plus the positive ------------
    check("a plain typed turn classifies as typed",
          cuq.classify(user("merge it")) == ("typed", ""))
    check("isMeta is excluded (stop-hook output, harness continuations)",
          cuq.classify(user("Stop hook feedback", isMeta=True))[0] == "excluded")
    check("isCompactSummary is excluded",
          cuq.classify(user("summary", isCompactSummary=True))[0] == "excluded")
    check("isSidechain is excluded (a subagent brief is assistant prose)",
          cuq.classify(user("You are an adversarial reviewer", isSidechain=True))[0] == "excluded")
    check("an assistant-role record is excluded",
          cuq.classify({"message": {"role": "assistant", "content": "x"}})[0] == "excluded")
    check("a tool_result carrier is excluded",
          cuq.classify({"message": {"role": "user",
                                    "content": [{"type": "tool_result", "content": "out"}]},
                        "userType": "external"})[0] == "excluded")
    check("a task-notification envelope is excluded",
          cuq.classify(user("<task-notification>\n<task-id>x</task-id>"))[0] == "excluded")
    check("a system-reminder envelope is excluded",
          cuq.classify(user("<system-reminder>do the thing</system-reminder>"))[0] == "excluded")
    check("an empty body is excluded",
          cuq.classify(user("   "))[0] == "excluded")
    check("a non-external userType is excluded",
          cuq.classify({"message": {"role": "user", "content": "x"}, "userType": "internal"})[0]
          == "excluded")

    # The prefixes are ANCHORED, so a turn that merely quotes an envelope tag
    # stays a typed turn. Reporting a misquote must not itself be excluded --
    # the same reason hooks/no-misattributed-quote.py carries an absence marker.
    check("a turn quoting an envelope tag mid-sentence stays typed",
          cuq.classify(user('why did a <task-notification> arrive here?')) == ("typed", ""))

    # -- end to end -------------------------------------------------------
    with tempfile.TemporaryDirectory() as root:
        write(root, "a.jsonl", [
            user("please merge it"),
            user("Stop hook feedback: there are unpushed commits", isMeta=True),
            user("This session is being continued from a previous conversation"),
            {"message": {"role": "assistant", "content": "I said something quotable"}},
        ])
        code, out = run(root, "merge it")
        check("a real typed turn is found and exits 0", code == 0 and "TYPED TURN" in out)

        code, out = run(root, "unpushed commits")
        check("a phrase only in an isMeta record is NOT found", code == 1)
        check("...and exits 1, distinct from unsearchable", code == 1)

        code, out = run(root, "unpushed commits", "--show-excluded")
        check("--show-excluded names why the near miss was excluded",
              "harness injection" in out and "EXCLUDED" in out)

        code, out = run(root, "I said something quotable")
        check("an assistant record is never a hit", code == 1)

        # The negative control. A run reporting zero over a space with no typed
        # turns has not searched anything, and must not read as an absence.
        code, out = run(root, "merge it", "--root", str(Path(root) / "nope"))
        check("a missing root is unsearchable (exit 2), not absent", code == 2)

    with tempfile.TemporaryDirectory() as root:
        write(root, "only-noise.jsonl", [user("injected", isMeta=True)])
        code, out = run(root, "anything")
        check("zero typed turns anywhere is unsearchable (exit 2)", code == 2)
        check("...and says so rather than reporting an absence",
              "unsearched space" in out)

    # A live session appends while this reads, so a torn line is expected. It
    # must be counted and stepped over: aborting the scan would end it early
    # and print a zero, which reads exactly like a genuine absence.
    with tempfile.TemporaryDirectory() as root:
        write(root, "torn.jsonl", [user("first turn")],
              extra_lines=["{not json", "", '{"message": {"role": "user", "content": "merge it"}, "userType": "external"}'])
        code, out = run(root, "merge it")
        check("a torn line does not end the scan", code == 0)
        check("unparseable lines are counted and reported", "1 unparseable line" in out)

    # Nested transcripts: subagent files live a directory deeper, and a glob of
    # */*.jsonl misses them. They are excluded by isSidechain, not by being
    # unreachable -- so the scan must still reach and count them.
    with tempfile.TemporaryDirectory() as root:
        nested = Path(root) / "proj" / "session" / "subagents"
        nested.mkdir(parents=True)
        write(root, "proj/session/subagents/agent-1.jsonl",
              [user("brief text here", isSidechain=True)])
        write(root, "proj/top.jsonl", [user("a typed turn")])
        code, out = run(root, "brief text here", "--show-excluded")
        check("nested subagent transcripts are reached", "subagent transcript" in out)
        check("...and do not count as a hit", code == 1)

    # -- norm(): the substring test this corpus already uses ---------------
    check("norm collapses whitespace and inline markup",
          cuq.norm("a  `b`  **c**") == cuq.norm("a b c"))

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
