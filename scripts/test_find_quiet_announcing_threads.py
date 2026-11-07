#!/usr/bin/env python3
"""Tests for scripts/find-quiet-announcing-threads.py (ai-config#5054).

Run: python3 scripts/test_find_quiet_announcing_threads.py
"""
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("fqat", HERE / "find-quiet-announcing-threads.py")
fqat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fqat)

FAILS = []
NOW = datetime(2026, 11, 7, 11, 0, tzinfo=timezone.utc)


def check(name, got, want):
    ok = got == want
    print(("  ok      " if ok else "  FAIL    ") + name)
    if not ok:
        print(f"          got {got!r}, want {want!r}")
        FAILS.append(name)


def thread(reply, last="2026-11-07T10:30:00Z", state="working"):
    return {"id": "cmsg_1", "title": "t", "last_reply": reply,
            "last_activity": last, "state": state}


def ids(threads, **kw):
    return [f["id"] for f in fqat.quiet_announcers(threads, NOW, **kw)]


check("announcement then 30 quiet minutes is flagged",
      ids([thread("The fix is pushed. I'm starting the next layer now.")]), ["cmsg_1"])
check("recent activity is not flagged",
      ids([thread("I'm starting the next layer now.", last="2026-11-07T10:55:00Z")]), [])
check("conditional sequencing is not flagged",
      ids([thread("I'll push once the review lands.")]), [])
check("a reply with no announcement is not flagged",
      ids([thread("The PR is merged.")]), [])
check("a blocked thread is not flagged",
      ids([thread("I'm starting the next layer now.", state="blocked")]), [])
check("the quiet threshold is configurable",
      ids([thread("I'm starting the next layer now.", last="2026-11-07T10:55:00Z")],
          quiet_minutes=3), ["cmsg_1"])
check("the nudge quotes the announcement",
      [f["announcement"] for f in fqat.quiet_announcers(
          [thread("Done. I'm starting the next layer now.")], NOW)],
      ["I'm starting the next layer now."])

# Command line: exit codes, including the empty search space.
script = str(HERE / "find-quiet-announcing-threads.py")
run = lambda data, *a: subprocess.run(
    [sys.executable, script, "--now", "2026-11-07T11:00:00Z", *a],
    input=json.dumps(data), capture_output=True, text=True)
check("exit 1 when a thread is flagged",
      run([thread("I'm starting the next layer now.")]).returncode, 1)
check("exit 0 when nothing is flagged", run([thread("Merged.")]).returncode, 0)
check("exit 2 on an empty snapshot list", run([]).returncode, 2)

bad = thread("I'm starting the next layer now.")
del bad["last_activity"]
r = run([thread("I'm starting the next layer now."), bad])
check("exit 2 when a record lacks a required key", r.returncode, 2)
check("nothing printed for an untrustworthy list", r.stdout, "")
check("exit 2 when a record is not an object", run(["text"]).returncode, 2)
check("exit 2 on an unparseable last_activity",
      run([thread("Merged.", last="yesterday")]).returncode, 2)

check("exit 2 on a last_activity with no UTC offset",
      run([thread("I'm starting the next layer now.", last="2026-11-07T10:00:00")]).returncode, 2)
check("exit 2 on a --now with no UTC offset",
      subprocess.run([sys.executable, script, "--now", "2026-11-07T11:00:00"],
                     input=json.dumps([thread("Merged.")]), capture_output=True, text=True).returncode, 2)
check("an offset other than Z is accepted",
      run([thread("Merged.", last="2026-11-07T02:30:00-08:00")]).returncode, 0)

for field, value in (("last_reply", 12345), ("last_reply", ["a"]), ("last_reply", True),
                     ("id", 7), ("title", 3), ("state", None)):
    bad = thread("I'm starting the next layer now.")
    bad[field] = value
    check(f"exit 2 when {field} is {value!r}", run([bad]).returncode, 2)
check("exit 2 when the snapshots are a number", run(5).returncode, 2)
check("exit 2 when the snapshots are an object", run({"id": "x"}).returncode, 2)

print(f"\n{len(FAILS)} failure(s)")
sys.exit(1 if FAILS else 0)
