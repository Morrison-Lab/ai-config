"""Test the flag-book-unavailable-without-library-search guard.

The warning needs all of: a reply that says a book is unreachable, and a
transcript missing a search of the project library OR of the mlr repo. Each
gets its own negative case, plus the corpus-quoting mitigation (a claim inside
backticks is not an assertion) and the fail-open / once-per-message checks.

Run: python3 hooks/test-flag-book-unavailable-without-library-search.py hooks/flag-book-unavailable-without-library-search.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def say(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def reply(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "mcp__hearthbot__post_message", "input": {"text": text}}]}}


def bash(cmd):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": cmd}}]}}


def mlr_listing():
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "mcp__github__get_file_contents",
         "input": {"owner": "Morrison-Lab", "repo": "mlr", "path": "books"}}]}}


LIB = bash("pdftotext /mnt/project-files/books/ISLP-2023.pdf - | grep -i 'feature matrix'")
WEB = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "WebSearch", "input": {"query": "feature matrix design matrix"}}]}}

CLAIM = "I could not reach ESL, Murphy, Bishop or the patsy docs, so those are unchecked."

CASES = [
    ([WEB, say(CLAIM)], True, "web search only, book unreachable: warns (the reported case)"),
    ([WEB, reply(CLAIM)], True, "same claim through the thread reply tool warns"),
    ([LIB, say(CLAIM)], True, "library searched but mlr not: warns"),
    ([mlr_listing(), say(CLAIM)], True, "mlr searched but library not: warns"),
    ([LIB, mlr_listing(), say(CLAIM)], False, "both searched: silent"),
    ([WEB, say("ESL says the input matrix X has p + 1 columns.")], False,
     "a reply about a book with no unavailability claim is silent"),
    ([WEB, say("The patsy docs are not available offline.")], False,
     "an unavailable non-book is silent"),
    ([WEB, say("The rule says `could not reach the book` is never acceptable.")], False,
     "a claim quoted in backticks is not an assertion"),
    ([WEB], False, "no reply text: silent"),
]


def run(transcript, payload_extra=None):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for m in transcript:
                fh.write(json.dumps(m) + "\n")
        env = dict(os.environ, TMPDIR=d)
        payload = {"transcript_path": path}
        payload.update(payload_extra or {})
        first = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                               capture_output=True, text=True, env=env)
        second = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                                capture_output=True, text=True, env=env)
        return first, second


def fired(proc):
    return "flag-book-unavailable-without-library-search" in (proc.stdout + proc.stderr)


passed = failed = 0
for transcript, expect, name in CASES:
    first, second = run(transcript)
    ok = fired(first) == expect and first.returncode == 0
    if expect:
        ok = ok and not fired(second)  # once per distinct message
        try:
            out = json.loads(first.stdout)
            # the reason is the only part the agent reads (ai-config#4796)
            ok = ok and out.get("decision") == "block" and bool(out.get("reason"))
        except Exception:
            ok = False
    print(("PASS" if ok else "FAIL"), "-", name)
    passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)

bad = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
ok = bad.returncode == 0 and not bad.stdout
print(("PASS" if ok else "FAIL"), "- malformed stdin fails open")
passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)

missing = subprocess.run([sys.executable, HOOK], input=json.dumps({"transcript_path": "/nonexistent"}),
                         capture_output=True, text=True)
ok = missing.returncode == 0 and not missing.stdout
print(("PASS" if ok else "FAIL"), "- missing transcript fails open")
passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)

print(f"{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
