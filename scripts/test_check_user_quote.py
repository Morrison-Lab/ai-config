#!/usr/bin/env python3
"""Tests for scripts/check-user-quote.py.

The tool's contract changed after ten revisions and eleven certification
fail-opens: it no longer decides who wrote a phrase. So these tests pin two
things instead of a classifier.

  COVERAGE  every record shape that can carry a user's prompt is read. An
            earlier revision read `message` alone and reported "Do not quote
            it" over sentences the transcript held as `queue-operation`.
  HONESTY   nothing in the output or the exit codes asserts authorship, a
            degraded read never reports as an absence, and the provenance
            printed beside a candidate is derived from the record.

Fixture shapes were taken from 27 real transcripts surveyed 2026-08-28. Per
`shared/workflow/fixtures-are-not-evidence.md` a fixture is evidence about the
code that reads it and nothing more -- which is part of why the tool no longer
draws conclusions from shapes it recognizes.
"""
import importlib.util
import json
import os
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
skipped = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def skip(name, why):
    """Reported and NOT counted, so a weakened run and a full one differ in the totals."""
    global skipped
    print(f"SKIP: {name} ({why})")
    skipped += 1


def user(text, human=False, **flags):
    record = {"message": {"role": "user", "content": text}, "userType": "external", **flags}
    if human:
        record["origin"] = {"kind": "human"}
    return record


def write(root, name, records):
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
    return path


def run(root, phrase, *args):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), phrase, "--root", str(root), *args],
        capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def main() -> int:
    print("Testing check-user-quote.py...")

    # -- COVERAGE: all four record shapes -----------------------------------
    shapes = {
        "message/user": user("SENTINEL_MSG here", human=True),
        "queue-operation": {"type": "queue-operation", "operation": "enqueue",
                            "content": "SENTINEL_QUEUE here",
                            "sessionId": "s1"},
        "last-prompt": {"type": "last-prompt", "lastPrompt": "SENTINEL_LAST here",
                        "sessionId": "s1"},
        "attachment/queued_command": {"type": "attachment", "userType": "external",
                                      "attachment": {"type": "queued_command",
                                                     "prompt": "SENTINEL_ATTACH here"}},
    }
    for shape, record in shapes.items():
        found = [s for s, _ in cuq.texts(record)]
        check(f"{shape} is read", shape in found)
    # A prompt exists as queue-operation before it exists as message, so a
    # session ending in between leaves it only in the shape the old tool
    # skipped. This is the false-absence the rewrite exists to remove.
    with tempfile.TemporaryDirectory() as root:
        write(root, "a.jsonl", list(shapes.values()))
        for sentinel in ("SENTINEL_MSG", "SENTINEL_QUEUE", "SENTINEL_LAST", "SENTINEL_ATTACH"):
            code, _ = run(root, sentinel + " here")
            check(f"{sentinel} is found end to end", code == 0)

    check("an assistant message is read too, and labelled as such",
          ("message/assistant", "x") in list(cuq.texts(
              {"message": {"role": "assistant", "content": "x"}})))
    check("a record with no prose yields nothing",
          list(cuq.texts({"type": "attachment", "attachment": {"type": "hook_success"}})) == [])
    check("a non-str text block is skipped rather than crashing the scan",
          list(cuq.texts({"message": {"role": "user",
                                      "content": [{"type": "text", "text": {"n": 1}}]}})) == [])

    # -- HONESTY: provenance is derived, never asserted ---------------------
    facts = cuq.provenance(user("x", human=True, isSidechain=True))
    check("provenance reports the origin label", facts["origin.kind"] == "human")
    check("...and the flags that qualify it", "isSidechain" in facts["flags"])
    check("an absent origin is reported as absent, not guessed",
          cuq.provenance(user("x"))["origin.kind"] == "(absent)")
    for flag in cuq.PROVENANCE_FLAGS:
        check(f"{flag} is surfaced", flag in cuq.provenance(user("x", **{flag: True}))["flags"])

    # The eleven shapes that defeated the ten classifier revisions. Every one
    # is now REPORTED with its provenance rather than judged -- so the test is
    # that the record and its flags reach the reader, not that a verdict is
    # right.
    injections = {
        "appended reminder": "ok do it\n<system-reminder>A</system-reminder>",
        "mid-block": "before <system-reminder>A</system-reminder> after",
        "repeated opener": "<system-reminder>OUT <system-reminder>i</system-reminder> A</system-reminder>",
        "literal closing tag": "<system-reminder>about the </system-reminder> tag, A</system-reminder>",
        "truncated": "sure go ahead <system-reminder>A truncated",
        "teammate-message": "<teammate-message from='a2'>A</teammate-message>",
        "ide_selection": "fix this\n<ide_selection>A</ide_selection>",
        "entity-escaped": "ok\n&lt;system-reminder&gt;A&lt;/system-reminder&gt;",
        "namespaced": "<ns:system-reminder>A</ns:system-reminder>",
        "digit-led": "<2fa-reminder>A</2fa-reminder>",
        "dotted": "<system.reminder>A</system.reminder>",
    }
    with tempfile.TemporaryDirectory() as root:
        write(root, "a.jsonl", [user(text.replace("A", f"SENTINEL_{i}"), human=True)
                                for i, text in enumerate(injections.values())])
        for i, label in enumerate(injections):
            code, out = run(root, f"SENTINEL_{i}")
            check(f"{label}: the record is shown, not judged",
                  code == 0 and "does not decide who wrote anything" in out)

    check("the disclaimer is printed even when nothing is found",
          "does not decide who wrote anything" in run(
              tempfile.mkdtemp(), "nothing at all")[1])

    # -- collapse and ordering ----------------------------------------------
    raw = [
        {"file": "f", "shape": "last-prompt", "text": "same", "origin.kind": "(absent)",
         "flags": "(none)", "userType": "x", "session": "s"},
        {"file": "f", "shape": "last-prompt", "text": "same", "origin.kind": "(absent)",
         "flags": "(none)", "userType": "x", "session": "s"},
        {"file": "f", "shape": "message/user", "text": "same", "origin.kind": "human",
         "flags": "(none)", "userType": "x", "session": "s"},
    ]
    collapsed = cuq.collapse(raw)
    check("identical texts in one shape collapse to a single entry", len(collapsed) == 2)
    check("...carrying how many records held them",
          any(c["copies"] == 2 for c in collapsed))
    check("a human-labelled user message sorts first, so evidence leads",
          collapsed[0]["shape"] == "message/user")
    check("an assistant message sorts after a user one",
          cuq._rank({"shape": "message/assistant", "origin.kind": "(absent)"})
          > cuq._rank({"shape": "message/user", "origin.kind": "(absent)"}))

    # -- HONESTY: a degraded read is never an absence -----------------------
    with tempfile.TemporaryDirectory() as root:
        path = Path(root) / "torn.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(user("a good turn", human=True)) + "\n")
            handle.write('{"message": {"role": "user", "cont')
        code, out = run(root, "a phrase genuinely absent")
        check("an unparseable line makes the run degraded, not absent", code == 2)
        check("...and says the space could not be read", "could not be read" in out)

    with tempfile.TemporaryDirectory() as root:
        write(root, "ok.jsonl", [user("a real turn", human=True)])
        (Path(root) / "gone.jsonl").symlink_to(Path(root) / "nothing-here")
        code, out = run(root, "a phrase genuinely absent")
        check("an unreadable file makes the run degraded, not absent", code == 2)
        check("...and names it", "UNREADABLE" in out)

    if os.geteuid() != 0:
        with tempfile.TemporaryDirectory() as root:
            write(root, "top.jsonl", [user("a real turn", human=True)])
            hidden = Path(root) / "hidden"
            write(root, "hidden/x.jsonl", [user("SENTINEL_INSIDE", human=True)])
            hidden.chmod(0o000)
            try:
                check("an unreadable DIRECTORY is not swallowed", run(root, "SENTINEL_INSIDE")[0] == 2)
            finally:
                hidden.chmod(0o755)
    else:
        skip("unreadable directory", "running as root; permission bits do not apply")

    code = subprocess.run([sys.executable, str(SCRIPT), "x", "--root", "/nonexistent-xyz"],
                          capture_output=True, text=True).returncode
    check("a --root that is not a directory is a usage error, not an absence", code == 2)

    empty = subprocess.run([sys.executable, str(SCRIPT), "  **  "],
                           capture_output=True, text=True)
    check("an empty phrase is a usage error, not an absence",
          empty.returncode == 2 and "empty after normalization" in empty.stderr)

    env = dict(os.environ, CLAUDE_CONFIG_DIR="~nosuchuser12345/x")
    env.pop("HOME", None)
    result = subprocess.run([sys.executable, str(SCRIPT), "hi"],
                            capture_output=True, text=True, env=env)
    check("a crash resolving the root exits 2, not 1", result.returncode == 2)

    with tempfile.TemporaryDirectory() as root:
        write(root, "a.jsonl", [user("a real turn", human=True)])
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys, importlib.util as i;"
             "s=i.spec_from_file_location('m',%r);m=i.module_from_spec(s);s.loader.exec_module(m);"
             "m.texts=lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom'));"
             "sys.exit(m.main(['q','--root',%r]))" % (str(SCRIPT), root)],
            capture_output=True, text=True)
        check("an unexpected exception exits 2", result.returncode == 2)
        check("...and names what failed", "failed before it could answer" in result.stderr)

    # Found the record, then died printing it, and exited 1 -- "no record".
    with tempfile.TemporaryDirectory() as root:
        # The glyph is BUILT, not typed: `shared/coding/ascii-punctuation-in-source.md`
        # forbids a literal em-dash in a tracked source file, string literals
        # included, and CI's non-ASCII gate does not scan .py -- so nothing here
        # would have caught it.
        write(root, "a.jsonl", [user(f"merge it {chr(0x2014)} now", human=True)])
        env = dict(os.environ, LC_ALL="C", LANG="C", PYTHONUTF8="0")
        env.pop("PYTHONIOENCODING", None)
        result = subprocess.run([sys.executable, str(SCRIPT), "merge it", "--root", root],
                                capture_output=True, text=True, env=env)
        check("an unencodable character still reports the record", result.returncode == 0)

    # -- JSON carries the same counts on every branch ------------------------
    with tempfile.TemporaryDirectory() as root:
        write(root, "a.jsonl", [user("a real turn", human=True)])
        payload = json.loads(run(root, "a real turn", "--json")[1])
        check("--json reports the search space and the candidates",
              payload["status"] == "found" and payload["files"] == 1
              and payload["texts_examined"] >= 1 and len(payload["candidates"]) == 1)
        payload = json.loads(run(root, "nothing here", "--json")[1])
        check("--json on the absent branch keeps the same keys",
              payload["status"] == "absent" and "texts_examined" in payload)

    with tempfile.TemporaryDirectory() as home:
        env = dict(os.environ, HOME=home, CLAUDE_CONFIG_DIR=str(Path(home) / "nothing"))
        result = subprocess.run([sys.executable, str(SCRIPT), "x", "--json"],
                                capture_output=True, text=True, env=env)
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
        check("--json on the missing-root branch exits 2 with the full schema on stdout",
              result.returncode == 2 and payload.get("status") == "degraded"
              and "files" in payload and "reason" in payload)

    # -- nested transcripts and norm ----------------------------------------
    with tempfile.TemporaryDirectory() as root:
        write(root, "proj/session/subagents/agent-1.jsonl", [user("SENTINEL_NESTED")])
        code, out = run(root, "SENTINEL_NESTED")
        check("nested subagent transcripts are reached", code == 0 and "agent-1.jsonl" in out)

    check("norm collapses whitespace and inline markup", cuq.norm("A  `b`  **c**") == "a b c")
    check("norm is not degenerate", cuq.norm("hello") == "hello")

    print(f"\n{passes} passed, {failures} failed, {skipped} skipped")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
